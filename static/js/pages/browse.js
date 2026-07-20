"use strict";

import { showToast } from '../toast.js';
import { createCard } from '../card.js';
import { fetchBrowseSummary } from '../browse-summary.js';

const DEFAULT_SOURCES = ['wikipedia', 'gbooks', 'scholar'];
const BROWSE_STORAGE_KEY = 'studyhelper_browse_state';
const BROWSE_STATE_VERSION = 2;
const BROWSE_REQUEST_TIMEOUT_MS = 30000;
const BROWSE_WHITELIST_TIMEOUT_MS = 5000;
const BROWSE_SUMMARY_TIMEOUT_MS = 15000;
const RESULTS_PER_SOURCE_PER_RANK = 1;
const MAX_VISIBLE_SOURCE_RANK = 10;
const SUMMARY_RESULT_LIMIT = 10;
const SUMMARY_TEXT_LIMIT = 6000;
const SUMMARY_FIELD_LIMITS = Object.freeze({
    title: 500,
    description: 2000,
    source_name: 200,
});
const DEDUPE_IDENTITY_PROPERTY = '_dedupe_identity';
const CANONICAL_SOURCE_URL_PROPERTY = '_canonical_source_url';
const RESPONSE_METADATA_PROPERTIES = new Set([
    DEDUPE_IDENTITY_PROPERTY,
    CANONICAL_SOURCE_URL_PROPERTY
]);
let pageRoot = null;
let currentSearchResults = [];
let currentGroupedResults = {};
let currentGroupPage = 1;
let currentSourceCounts = {};
let whitelistDomains = [];
let lastSearchQuery = null;
let lastSearchSources = null;
let whitelistSourcesRendered = false;
let pendingMasterSourceSelection = null;
let pendingSourceSelectionOverrides = new Map();
let isLoadingMore = false;
let searchGeneration = 0;
let searchIntentGeneration = 0;
let browseInitGeneration = 0;
let browseSourceReadiness = Promise.resolve();
let isInitialSearchPending = false;
const searchLoaders = new Map();
let currentOverview = overviewState();
let overviewRequestGeneration = 0;
let activeOverviewController = null;

function overviewState(status = 'idle', query = '', text = '', error = '') {
    return { status, query, text, error };
}

function normalizedSummaryField(value, limit) {
    return typeof value === 'string' ? value.trim().slice(0, limit) : '';
}

function safeSummarySourceUrl(value) {
    if (typeof value !== 'string') return '';
    try {
        const parsed = new URL(value.trim());
        if (!['http:', 'https:'].includes(parsed.protocol)) return '';
        if (parsed.username || parsed.password) return '';
        parsed.hash = '';
        return parsed.href.slice(0, 2048);
    } catch (_err) {
        return '';
    }
}

function normalizeIdentityText(value) {
    if (value === null || value === undefined) return '';
    if (!['string', 'number', 'boolean'].includes(typeof value)) return '';
    return String(value).trim().replace(/\s+/gu, ' ').toLowerCase();
}

function normalizeSourceId(value) {
    if (typeof value === 'string') return value.trim();
    if (typeof value === 'boolean') return String(value);
    if (typeof value === 'number' && Number.isFinite(value)) return String(value);
    return '';
}

function canonicalSourceUrl(value) {
    if (typeof value !== 'string') return '';

    const rawValue = value.trim();
    if (!rawValue || /\s/u.test(rawValue) || rawValue.includes('\\')) return '';

    const match = rawValue.match(
        /^([A-Za-z][A-Za-z0-9+.-]*):\/\/([^/?#]+)([^?#]*)(\?[^#]*)?(?:#.*)?$/u
    );
    if (!match) return '';

    const scheme = match[1].toLowerCase();
    if (scheme !== 'http' && scheme !== 'https') return '';

    try {
        const parsed = new URL(rawValue);
        if (!parsed.hostname || parsed.protocol !== `${scheme}:`) return '';
    } catch (_err) {
        return '';
    }

    const authority = match[2];
    const userinfoEnd = authority.lastIndexOf('@');
    const userinfo = userinfoEnd >= 0 ? authority.slice(0, userinfoEnd + 1) : '';
    const hostAndPort = authority.slice(userinfoEnd + 1);
    let normalizedHostAndPort = '';

    if (hostAndPort.startsWith('[')) {
        const closingBracket = hostAndPort.indexOf(']');
        if (closingBracket < 2) return '';
        const hostname = hostAndPort.slice(1, closingBracket).toLowerCase();
        const port = hostAndPort.slice(closingBracket + 1);
        normalizedHostAndPort = `[${hostname}]${port}`;
    } else {
        const portStart = hostAndPort.lastIndexOf(':');
        const hasPort = portStart >= 0;
        const hostname = (hasPort ? hostAndPort.slice(0, portStart) : hostAndPort).toLowerCase();
        const port = hasPort ? hostAndPort.slice(portStart) : '';
        if (!hostname || hostname.includes(':')) return '';
        normalizedHostAndPort = `${hostname}${port}`;
    }

    return `${scheme}://${userinfo}${normalizedHostAndPort}${match[3]}${match[4] || ''}`;
}

function hasResponseDedupeMetadata(item) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false;
    return Object.prototype.hasOwnProperty.call(item, DEDUPE_IDENTITY_PROPERTY)
        || Object.prototype.hasOwnProperty.call(item, CANONICAL_SOURCE_URL_PROPERTY);
}

function resultIdentity(item) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return null;
    if (hasResponseDedupeMetadata(item)) {
        const identity = item[DEDUPE_IDENTITY_PROPERTY];
        return typeof identity === 'string' && identity ? identity : null;
    }

    const sourceName = normalizeIdentityText(item.source_name);
    const sourceId = normalizeSourceId(item.source_id);
    if (sourceName && sourceId) {
        return ['source_id', sourceName, sourceId];
    }

    const sourceUrl = canonicalSourceUrl(item.source_url);
    if (sourceUrl) {
        return ['url', sourceUrl];
    }

    const title = normalizeIdentityText(item.title);
    if (sourceName && title) {
        return ['display', sourceName, title];
    }

    return null;
}

function resultIdentityKey(item) {
    const identity = resultIdentity(item);
    if (typeof identity === 'string') return identity;
    return identity ? JSON.stringify(identity) : '';
}

function resultCanonicalSourceUrl(item) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return '';
    if (hasResponseDedupeMetadata(item)) {
        const sourceUrl = item[CANONICAL_SOURCE_URL_PROPERTY];
        return typeof sourceUrl === 'string' ? sourceUrl : '';
    }
    return canonicalSourceUrl(item.source_url);
}

function normalizedBrowseThumbnail(value) {
    if (typeof value !== 'string' || !value || value.length > 255) return '';
    if (value !== value.trim() || /\s/u.test(value) || value.includes('\\')) return '';

    try {
        const parsed = new URL(value);
        if (
            parsed.protocol !== 'https:'
            || parsed.username
            || parsed.password
            || (parsed.port && parsed.port !== '443')
            || parsed.hash
        ) {
            return '';
        }
        const normalized = parsed.href;
        return normalized.length <= 255 ? normalized : '';
    } catch (_err) {
        return '';
    }
}

function normalizedGoogleBooksVolumeId(value) {
    return typeof value === 'string' && /^[A-Za-z0-9_-]{1,220}$/u.test(value)
        ? value
        : '';
}

function sanitizeBrowseResult(item) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return item;
    const sanitized = {
        ...item,
        thumb_url: normalizedBrowseThumbnail(item.thumb_url),
    };
    if (Object.prototype.hasOwnProperty.call(item, 'google_books_volume_id')) {
        sanitized.google_books_volume_id = normalizedGoogleBooksVolumeId(
            item.google_books_volume_id
        );
    }
    return sanitized;
}

function deduplicateResults(results) {
    if (!Array.isArray(results)) return [];

    const parents = Array.from({ length: results.length }, (_, index) => index);
    const ranks = Array(results.length).fill(0);
    const find = (startIndex) => {
        let index = startIndex;
        while (parents[index] !== index) {
            parents[index] = parents[parents[index]];
            index = parents[index];
        }
        return index;
    };
    const union = (left, right) => {
        let leftRoot = find(left);
        let rightRoot = find(right);
        if (leftRoot === rightRoot) return;
        if (ranks[leftRoot] < ranks[rightRoot]) {
            [leftRoot, rightRoot] = [rightRoot, leftRoot];
        }
        parents[rightRoot] = leftRoot;
        if (ranks[leftRoot] === ranks[rightRoot]) ranks[leftRoot] += 1;
    };

    const firstIndexByKey = new Map();
    results.forEach((item, index) => {
        const identityKey = resultIdentityKey(item);
        const sourceUrl = resultCanonicalSourceUrl(item);
        const keys = [];
        if (identityKey) keys.push(`identity:${identityKey}`);
        if (sourceUrl) keys.push(`url:${sourceUrl}`);
        keys.forEach((key) => {
            if (firstIndexByKey.has(key)) {
                union(index, firstIndexByKey.get(key));
            } else {
                firstIndexByKey.set(key, index);
            }
        });
    });

    const firstIndexByComponent = new Map();
    results.forEach((_item, index) => {
        const root = find(index);
        if (!firstIndexByComponent.has(root)) firstIndexByComponent.set(root, index);
    });
    return results.filter(
        (_item, index) => firstIndexByComponent.get(find(index)) === index
    );
}

function structuralFallbackKey(value, ancestors = new Set(), isRoot = true) {
    if (value === null) return 'null';
    if (typeof value === 'string') return `string:${JSON.stringify(value)}`;
    if (typeof value === 'boolean') return `boolean:${value}`;
    if (typeof value === 'number' && Number.isFinite(value)) return `number:${value}`;
    if (!value || typeof value !== 'object' || ancestors.has(value)) return '';

    ancestors.add(value);
    let key = '';
    if (Array.isArray(value)) {
        const entries = value.map((entry) => structuralFallbackKey(entry, ancestors, false));
        if (entries.every(Boolean)) key = `array:[${entries.join(',')}]`;
    } else {
        const entries = Object.keys(value)
            .filter((name) => !isRoot || !RESPONSE_METADATA_PROPERTIES.has(name))
            .sort()
            .map((name) => {
                const entryKey = structuralFallbackKey(value[name], ancestors, false);
                return entryKey ? `${JSON.stringify(name)}:${entryKey}` : '';
            });
        if (entries.every(Boolean)) key = `object:{${entries.join(',')}}`;
    }
    ancestors.delete(value);
    return key;
}

function mergeUniqueResults(existing, incoming) {
    const existingResults = deduplicateResults(existing);
    const existingFallbackCounts = new Map();
    existingResults.forEach((item) => {
        if (resultIdentity(item) !== null) return;
        const key = structuralFallbackKey(item);
        if (!key) return;
        existingFallbackCounts.set(key, (existingFallbackCounts.get(key) || 0) + 1);
    });

    const incomingFallbackCounts = new Map();
    const unseenIncoming = (Array.isArray(incoming) ? incoming : []).filter((item) => {
        if (resultIdentity(item) !== null) return true;
        const key = structuralFallbackKey(item);
        if (!key) return true;
        const occurrence = (incomingFallbackCounts.get(key) || 0) + 1;
        incomingFallbackCounts.set(key, occurrence);
        return occurrence > (existingFallbackCounts.get(key) || 0);
    });
    const mergedResults = deduplicateResults([
        ...existingResults,
        ...unseenIncoming
    ]);
    const existingReferences = new Set(existingResults);
    return {
        results: mergedResults,
        addedCount: mergedResults.filter((item) => !existingReferences.has(item)).length
    };
}

// Load whitelisted domains
async function loadWhitelistDomains() {
    const controller = new AbortController();
    let timeoutId = null;

    try {
        const timeout = new Promise((resolve) => {
            timeoutId = setTimeout(() => {
                controller.abort();
                resolve(null);
            }, BROWSE_WHITELIST_TIMEOUT_MS);
        });
        const response = await Promise.race([
            fetch('/static/whitelist.json', { signal: controller.signal }),
            timeout,
        ]);
        if (!response || !response.ok) return [];
        const whitelist = await response.json();
        return [
            ...(whitelist.domains || []),
            ...(whitelist.domain_patterns || []),
        ];
    } catch (err) {
        if (err?.name !== 'AbortError') {
            console.warn('Unable to load whitelist domains', err);
        }
        return [];
    } finally {
        if (timeoutId !== null) clearTimeout(timeoutId);
    }
}

function getInitialBrowseQuery() {
    try {
        const params = new URLSearchParams(window.location?.search || '');
        return (params.get('q') || params.get('query') || '').trim();
    } catch (_err) {
        return '';
    }
}

function updateBrowseUrl(query) {
    if (!window.history?.replaceState) return;

    const pathname = window.location?.pathname || '/browse';
    const params = new URLSearchParams(window.location?.search || '');
    params.set('q', query);
    const queryString = params.toString();
    window.history.replaceState({}, '', `${pathname}${queryString ? `?${queryString}` : ''}`);
}

function browseRequestError(result, fallbackMessage) {
    const serverMessage = result
        && typeof result === 'object'
        && !Array.isArray(result)
        && typeof result.error === 'string'
        ? result.error.trim()
        : '';
    const error = new Error(serverMessage || fallbackMessage);
    error.isSafeBrowseError = true;
    return error;
}

async function fetchBrowseResults(payload) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), BROWSE_REQUEST_TIMEOUT_MS);

    try {
        const response = await fetch('/api/browse/search-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal
        });
        let result = null;
        try {
            result = await response.json();
        } catch (_err) {
            throw browseRequestError(null, 'Browse search returned an invalid response.');
        }
        if (!response.ok || !result || result.status !== true) {
            throw browseRequestError(result, 'Browse search failed. Try again shortly.');
        }
        return result;
    } catch (error) {
        if (error?.name === 'AbortError') {
            throw browseRequestError(null, 'Browse search timed out. Try again.');
        }
        if (error?.isSafeBrowseError) throw error;
        throw browseRequestError(
            null,
            'Browse search could not reach SerpAPI. Try again shortly.',
        );
    } finally {
        clearTimeout(timeoutId);
    }
}

function sourceErrorCount(result) {
    const sourceErrors = result?.source_errors;
    if (!sourceErrors || typeof sourceErrors !== 'object' || Array.isArray(sourceErrors)) {
        return 0;
    }
    return Object.keys(sourceErrors).length;
}

function escapeHtml(value) {
    const entities = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    };
    return String(value ?? '').replace(/[&<>"']/g, (character) => entities[character]);
}

function showPartialSourceWarning(result) {
    const failedCount = sourceErrorCount(result);
    if (failedCount > 0) {
        showToast(
            `${failedCount} selected source${failedCount === 1 ? '' : 's'} could not be searched. Showing available results.`,
            'warning',
        );
    }
}

function syncBrowseLoadingState(resultsContainer) {
    if (!resultsContainer) return;
    // Loader membership is intent-owned, so it is also the source of truth for
    // blocking restored paging throughout readiness and request work.
    isInitialSearchPending = searchLoaders.size > 0;
    const containerLoaders = Array.from(searchLoaders.values()).filter(
        (loader) => loader.container === resultsContainer
    );
    const activeLoader = containerLoaders.at(-1);
    containerLoaders.forEach((loader) => {
        const isActive = loader === activeLoader;
        loader.element.hidden = !isActive;
        loader.element.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    });
    const isBusy = Boolean(activeLoader);
    if (isBusy) {
        resultsContainer.classList.add('browse-results-loading');
    } else {
        resultsContainer.classList.remove('browse-results-loading');
    }
    resultsContainer.setAttribute('aria-busy', isBusy ? 'true' : 'false');

    if (resultsContainer === pageRoot?.querySelector('#resultsContainer')) {
        const sortingSelect = pageRoot.querySelector('#filterSorting');
        if (sortingSelect) sortingSelect.disabled = isBusy || isInitialSearchPending;
    }
}

function clearSearchLoader(intentGeneration) {
    const loader = searchLoaders.get(intentGeneration);
    if (!loader) return;
    searchLoaders.delete(intentGeneration);
    loader.element.remove();
    syncBrowseLoadingState(loader.container);
}

function clearSupersededSearchLoaders(intentGeneration) {
    Array.from(searchLoaders.keys()).forEach((generation) => {
        if (generation !== intentGeneration) clearSearchLoader(generation);
    });
}

function clearResultsBehindSearchLoader(intentGeneration) {
    const loader = searchLoaders.get(intentGeneration);
    if (!loader) return;
    loader.element.remove();
    loader.container.innerHTML = '';
    loader.container.appendChild(loader.element);
    syncBrowseLoadingState(loader.container);
}

function clearAllSearchLoaders() {
    Array.from(searchLoaders.keys()).forEach(clearSearchLoader);
}

function renderBrowseEmptyState() {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    if (!resultsContainer) return;
    resultsContainer.innerHTML = `
        <div class="browse-empty-state text-center py-5">
            <span class="browse-empty-engraving" aria-hidden="true"></span>
            <h5>Search verified academic sources</h5>
            <p class="text-muted">Use the search bar above to find academic resources from trusted sources</p>
        </div>
    `;
    syncBrowseLoadingState(resultsContainer);
}

function renderSearchLoader(intentGeneration) {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    if (!resultsContainer) return;

    const loader = document.createElement('div');
    loader.className = 'loader-container';
    loader.dataset.browseLoaderGeneration = String(intentGeneration);
    loader.setAttribute('data-browse-loader-generation', String(intentGeneration));
    loader.innerHTML = `
        <picture class="browse-loader-picture">
            <source media="(prefers-reduced-motion: reduce)" srcset="/static/img/loaders/bible-page-turn-still.png">
            <img class="browse-loader-art" src="/static/img/loaders/bible-page-turn.gif" alt="" aria-hidden="true">
        </picture>
        <p class="browse-loader-status mb-0" role="status" aria-live="polite">Researching...</p>
    `;
    resultsContainer.appendChild(loader);
    searchLoaders.set(intentGeneration, {
        container: resultsContainer,
        element: loader,
    });
    syncBrowseLoadingState(resultsContainer);
}

export function initBrowse(root) {
    const initGeneration = ++browseInitGeneration;
    searchIntentGeneration += 1;
    searchGeneration += 1;
    isInitialSearchPending = false;
    isLoadingMore = false;
    clearAllSearchLoaders();
    cancelOverviewRequest();
    currentOverview = overviewState();
    pageRoot = root;
    if (sessionStorage.getItem('browse_from_sidebar') === 'true') {
        localStorage.removeItem(BROWSE_STORAGE_KEY);
        sessionStorage.removeItem('browse_from_sidebar');
    }
    whitelistDomains = [];
    whitelistSourcesRendered = false;
    pendingMasterSourceSelection = null;
    pendingSourceSelectionOverrides = new Map();
    pageRoot.innerHTML = `
        <div class="archive-page archive-page-browse">
            <span class="archive-illustration illustration-books" aria-hidden="true"></span>
            <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
            <span class="archive-illustration illustration-oil-lamp" aria-hidden="true"></span>
            <span class="archive-illustration illustration-armillary-sphere" aria-hidden="true"></span>
            <span class="archive-illustration illustration-hourglass" aria-hidden="true"></span>
            <span class="archive-illustration illustration-telescope" aria-hidden="true"></span>
            <span class="archive-illustration illustration-candlestick" aria-hidden="true"></span>
            <span class="archive-illustration illustration-victorian-man" aria-hidden="true"></span>
            <span class="archive-illustration illustration-scholar" aria-hidden="true"></span>
            <div class="archive-content">
        <div class="bg-body-tertiary border-bottom browse-search-shell p-3 mb-3">
            <div class="container-fluid">
                <div class="row g-3 align-items-center">
                    <div class="col-12">
                        <div class="dropdown d-inline-block w-100 position-relative">
                            <div class="input-group input-group-lg browse-search-group w-100">
                                <span class="input-group-text"><i class="bi bi-search" aria-hidden="true"></i></span>
                                <input type="text" class="form-control browse-search-input" id="searchInput" placeholder="Search verified academic sources...">
                                <button class="btn btn-primary btn-brass" id="goBtn" type="button">Go</button>
                                <button class="btn btn-outline-secondary archive-dropdown dropdown-toggle" type="button" id="filtersDropdown" aria-expanded="false" aria-controls="browseFiltersMenu">Filters</button>
                            </div>
                            <div class="browse-dropdown-menu archive-dropdown-menu p-3" id="browseFiltersMenu" aria-labelledby="filtersDropdown" style="min-width: 320px;">
                                <div class="mb-3">
                                    <label class="form-label mb-2">Sources</label>
                                    <div class="form-check mb-2 pb-2 border-bottom">
                                        <input class="form-check-input" type="checkbox" id="filterAllSources">
                                        <label class="form-check-label" for="filterAllSources">All sources</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input browse-source-checkbox" type="checkbox" id="filterWikipedia" value="wikipedia" checked>
                                        <label class="form-check-label" for="filterWikipedia">Wikipedia</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input browse-source-checkbox" type="checkbox" id="filterGBooks" value="gbooks" checked>
                                        <label class="form-check-label" for="filterGBooks">Google Books</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input browse-source-checkbox" type="checkbox" id="filterPubMed" value="pubmed">
                                        <label class="form-check-label" for="filterPubMed">PubMed</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input browse-source-checkbox" type="checkbox" id="filterScholar" value="scholar" checked>
                                        <label class="form-check-label" for="filterScholar">Google Scholar</label>
                                    </div>
                                    <div id="whitelistCheckboxes" class="ps-2 border-start mt-2"></div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label mb-2">Year range</label>
                                    <div class="input-group">
                                        <input type="number" class="form-control" id="filterYearFrom" placeholder="From" min="1900" max="2030">
                                        <input type="number" class="form-control" id="filterYearTo" placeholder="To" min="1900" max="2030">
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label mb-2">Content type</label>
                                    <select class="form-select" id="filterContentType">
                                        <option value="">Any</option>
                                        <option value="review">Review article</option>
                                        <option value="survey">Survey</option>
                                        <option value="case study">Case study</option>
                                        <option value="full text">Full text</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label mb-2">Sorting</label>
                                    <select class="form-select" id="filterSorting">
                                        <option value="">Default</option>
                                        <option value="recent">Most recent</option>
                                        <option value="highly_cited">Highly cited</option>
                                        <option value="open_access">Open access</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex browse-results-layout" style="height: calc(100vh - 200px);">
            <div class="border-end p-3 flex-shrink-0 browse-sidebar surface-wood" style="width: 320px; min-width: 320px; overflow-y: auto;" id="sidebarContainer"></div>
            <div class="flex-grow-1 p-3 overflow-y-auto browse-results-pane">
                <div id="resultsContainer" aria-busy="false"></div>
            </div>
        </div>
            </div>
        </div>
    `;

    const sortingSelect = pageRoot.querySelector('#filterSorting');
    if (sortingSelect) sortingSelect.disabled = false;
    renderBrowseEmptyState();

    const initialQuery = getInitialBrowseQuery();

    registerEvents(initGeneration);
    renderSidebar();
    restoreBrowseState();

    browseSourceReadiness = loadWhitelistDomains().then((domains) => {
        if (initGeneration !== browseInitGeneration) return false;
        whitelistDomains = domains;
        try {
            renderWhitelistCheckboxes();
        } catch (err) {
            console.warn('Unable to render whitelist domains', err);
            settleWhitelistSourcesWithoutDynamic();
        }
        return true;
    });

    if (initialQuery) {
        const searchInput = pageRoot.querySelector('#searchInput');
        if (searchInput) searchInput.value = initialQuery;
        performSearch({ updateUrl: false, initGeneration });
    }
}

function registerEvents(initGeneration) {
    const searchInput = pageRoot.querySelector('#searchInput');
    const goBtn = pageRoot.querySelector('#goBtn');
    const filtersDropdown = pageRoot.querySelector('#filtersDropdown');
    const dropdownMenu = pageRoot.querySelector('.browse-dropdown-menu');
    const sortingSelect = pageRoot.querySelector('#filterSorting');
    const sourceMasterCheckbox = pageRoot.querySelector('#filterAllSources');

    goBtn.addEventListener('click', () => {
        performSearch({ initGeneration });
    });
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch({ initGeneration });
        }
    });

    filtersDropdown?.addEventListener('click', (event) => {
        event.stopPropagation();
        if (!dropdownMenu) return;
        const open = dropdownMenu.classList.toggle('show');
        filtersDropdown.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    dropdownMenu?.addEventListener('click', (event) => {
        event.stopPropagation();
    });

    sourceMasterCheckbox?.addEventListener('change', () => {
        setAllSourcesSelected(sourceMasterCheckbox.checked);
        if (!whitelistSourcesRendered) {
            pendingMasterSourceSelection = sourceMasterCheckbox.checked;
            pendingSourceSelectionOverrides.clear();
        }
    });

    dropdownMenu?.addEventListener('change', (event) => {
        if (event.target?.classList?.contains('browse-source-checkbox')) {
            syncMasterSourceCheckbox();
            if (!whitelistSourcesRendered) {
                pendingSourceSelectionOverrides.set(
                    event.target.value,
                    event.target.checked,
                );
            }
        }
    });

    document.addEventListener('click', () => {
        if (!dropdownMenu) return;
        dropdownMenu.classList.remove('show');
        filtersDropdown?.setAttribute('aria-expanded', 'false');
    });

    sortingSelect?.addEventListener('change', () => {
        if (!isInitialSearchPending && currentSearchResults.length > 0) {
            const sortedResults = sortResults(getVisibleResults(), sortingSelect.value);
            renderResults(sortedResults);
        }
    });

    syncMasterSourceCheckbox();
}

function getDisplayNameForSource(source) {
    if (source === 'wikipedia') return 'Wikipedia';
    if (source === 'gbooks') return 'Google Books';
    if (source === 'pubmed') return 'PubMed';
    if (source === 'scholar') return 'Google Scholar';
    if (source === 'whitelist') return 'Whitelisted Sources';
    if (source.startsWith('whitelist_')) {
        const domain = source.slice('whitelist_'.length);
        return getDisplayNameForDomain(domain) || domain;
    }
    return source.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());
}

function itemMatchesSource(item, source) {
    if (!item || !item.source_name) return false;
    const sourceName = item.source_name.toLowerCase();
    if (source === 'wikipedia') {
        return sourceName === 'wikipedia';
    }
    if (source === 'gbooks') {
        return sourceName === 'gbooks' || sourceName === 'google books';
    }
    if (source === 'pubmed') {
        return sourceName === 'pubmed';
    }
    if (source === 'scholar') {
        return sourceName === 'scholar' || sourceName === 'google scholar';
    }
    if (source === 'whitelist') {
        return !['wikipedia', 'pubmed', 'gbooks', 'scholar'].includes(sourceName);
    }
    if (source.startsWith('whitelist_')) {
        const domain = source.slice('whitelist_'.length);
        try {
            const hostname = new URL(item.source_url).hostname;
            if (domain.startsWith('*.')) {
                return hostname.endsWith(domain.slice(1));
            }
            return hostname === domain || hostname.endsWith(`.${domain}`);
        } catch (_err) {
            return false;
        }
    }
    return sourceName.includes(source.toLowerCase());
}

function renderOverviewCard() {
    const hasResults = currentSearchResults.length > 0;
    let body = '';
    if (currentOverview.status === 'loading') {
        body = `
            <div class="d-flex align-items-center gap-2">
                <span class="spinner-border spinner-border-sm ai-overview-spinner" aria-hidden="true"></span>
                <span>Creating overview…</span>
            </div>`;
    } else if (currentOverview.status === 'success') {
        body = `<p class="small mb-0">${escapeHtml(currentOverview.text)}</p>`;
    } else if (currentOverview.status === 'error') {
        body = `
            <p class="small mb-2">${escapeHtml(currentOverview.error)}</p>
            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" type="button" data-overview-action="retry">Retry</button>`;
    } else if (currentOverview.status === 'empty') {
        body = '<p class="small mb-0">No overview is available because this search returned no results.</p>';
    } else if (hasResults && lastSearchQuery) {
        body = `
            <p class="small mb-2">Generate an overview of these search results.</p>
            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" type="button" data-overview-action="generate">Generate overview</button>`;
    } else {
        body = '<p class="small mb-0">AI search insights will appear here after you run a search.</p>';
    }

    return `
        <section class="card surface-leather ai-overview-panel mb-3" aria-labelledby="browseOverviewTitle">
            <div class="card-header">
                <h2 class="card-title h5 mb-0" id="browseOverviewTitle">Alexander says...</h2>
            </div>
            <div class="card-body" data-overview-status="${currentOverview.status}" aria-live="polite" aria-busy="${currentOverview.status === 'loading' ? 'true' : 'false'}">
                ${body}
            </div>
        </section>`;
}

function bindOverviewAction(sidebar) {
    const action = sidebar.querySelector('[data-overview-action]');
    action?.addEventListener('click', () => {
        if (!lastSearchQuery || currentSearchResults.length === 0) return;
        void loadSearchSummary(lastSearchQuery, searchGeneration);
    });
}

function renderSidebar(sourceCounts = {}, results = []) {
    const sidebar = pageRoot.querySelector('#sidebarContainer');
    const selectedSources = lastSearchSources || [];
    let html = renderOverviewCard();

    if (selectedSources.length) {
        html += '<div class="card surface-leather source-summary-panel mb-3">';
        html += '<div class="card-header"><h5 class="card-title mb-0">Search sources</h5></div>';
        html += '<div class="list-group list-group-flush">';

        selectedSources.forEach((source) => {
            const displayName = getDisplayNameForSource(source);
            const count = sourceCounts[source] != null ? sourceCounts[source] : results.filter((item) => itemMatchesSource(item, source)).length;
            const topItem = results.find((item) => itemMatchesSource(item, source));

            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <strong>${escapeHtml(displayName)}</strong>
                        <span class="badge bg-primary rounded-pill archive-count-badge">${count}</span>
                    </div>
            `;
            if (topItem) {
                html += `<div class="small text-truncate"><strong>${escapeHtml(topItem.title)}</strong></div>`;
                html += `<div class="small text-muted text-truncate">${escapeHtml(topItem.description || topItem.source_url || '')}</div>`;
            } else {
                html += '<div class="small text-muted">No results yet for this source.</div>';
            }
            html += '</div>';
        });

        html += '</div></div>';
    }
    sidebar.innerHTML = html;
    bindOverviewAction(sidebar);
}

function cancelOverviewRequest() {
    overviewRequestGeneration += 1;
    activeOverviewController?.abort();
    activeOverviewController = null;
}

async function loadSearchSummary(query, ownerSearchGeneration) {
    const results = buildSummaryResults();
    if (!results.length) {
        currentOverview = overviewState('empty', query);
        renderSidebar(currentSourceCounts, currentSearchResults);
        return;
    }

    cancelOverviewRequest();
    const requestGeneration = overviewRequestGeneration;
    const controller = new AbortController();
    activeOverviewController = controller;
    let timedOut = false;
    const timeoutId = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, BROWSE_SUMMARY_TIMEOUT_MS);
    currentOverview = overviewState('loading', query);
    renderSidebar(currentSourceCounts, currentSearchResults);

    try {
        const summary = await fetchBrowseSummary({ query, results }, controller.signal);
        if (
            ownerSearchGeneration !== searchGeneration
            || requestGeneration !== overviewRequestGeneration
        ) return;
        currentOverview = overviewState(
            'success',
            query,
            summary.slice(0, SUMMARY_TEXT_LIMIT),
        );
        saveBrowseState();
        renderSidebar(currentSourceCounts, currentSearchResults);
    } catch (error) {
        if (
            ownerSearchGeneration !== searchGeneration
            || requestGeneration !== overviewRequestGeneration
        ) return;
        if (error?.name === 'AbortError' && !timedOut) return;
        const message = timedOut
            ? 'Overview took too long. Try again.'
            : (error?.message || 'Unable to create overview. Try again.');
        currentOverview = overviewState('error', query, '', message);
        renderSidebar(currentSourceCounts, currentSearchResults);
    } finally {
        clearTimeout(timeoutId);
        if (requestGeneration === overviewRequestGeneration) {
            activeOverviewController = null;
        }
    }
}

function groupResultsBySource(results) {
    const grouped = {};
    const selectedSources = lastSearchSources || [];
    deduplicateResults(results).forEach((item) => {
        let source = selectedSources.find((candidate) => itemMatchesSource(item, candidate));
        if (!source && selectedSources.length > 0) {
            source = selectedSources[0];
        }
        if (!source) {
            const sourceName = normalizeIdentityText(item?.source_name);
            if (sourceName === 'wikipedia') source = 'wikipedia';
            else if (sourceName === 'gbooks' || sourceName === 'google books') source = 'gbooks';
            else if (sourceName === 'pubmed') source = 'pubmed';
            else if (sourceName === 'scholar' || sourceName === 'google scholar') source = 'scholar';
            else {
                try {
                    source = `whitelist_${new URL(item.source_url).hostname}`;
                } catch (_err) {
                    source = sourceName || 'unknown';
                }
            }
        }
        grouped[source] ||= [];
        grouped[source].push(item);
    });
    return grouped;
}

function deduplicateGroupedResults(groupedResults) {
    const safeGroups = groupedResults && typeof groupedResults === 'object'
        && !Array.isArray(groupedResults)
        ? groupedResults
        : {};
    const entries = Object.entries(safeGroups).flatMap(([source, items]) => (
        Array.isArray(items)
            ? items.map((item) => ({ source, item: sanitizeBrowseResult(item) }))
            : []
    ));
    const uniqueItems = deduplicateResults(entries.map(({ item }) => item));
    const deduplicated = Object.fromEntries(
        Object.keys(safeGroups).map((source) => [source, []]),
    );
    let uniqueIndex = 0;
    entries.forEach(({ source, item }) => {
        if (item !== uniqueItems[uniqueIndex]) return;
        deduplicated[source].push(item);
        uniqueIndex += 1;
    });
    return deduplicated;
}

function normalizedGroupedResults(groupedResults, fallbackResults) {
    const hasGroups = groupedResults && typeof groupedResults === 'object'
        && !Array.isArray(groupedResults)
        && Object.keys(groupedResults).length > 0;
    return deduplicateGroupedResults(
        hasGroups ? groupedResults : groupResultsBySource(fallbackResults),
    );
}

function sourcesToDisplay() {
    const sources = [];
    (lastSearchSources || []).forEach((source) => {
        if (source === 'whitelist') {
            Object.keys(currentGroupedResults).forEach((group) => {
                if (group.startsWith('whitelist_') && !sources.includes(group)) {
                    sources.push(group);
                }
            });
        } else if (!sources.includes(source)) {
            sources.push(source);
        }
    });
    return sources;
}

function summarySourceIdentity(item, source, sourceUrl) {
    if (sourceUrl) {
        try {
            const hostname = new URL(sourceUrl).hostname.toLowerCase();
            if (hostname) return `domain:${hostname.replace(/^www\./u, '')}`;
        } catch (_err) {
            // safeSummarySourceUrl already validates URLs; retain a defensive fallback.
        }
    }
    const sourceName = normalizeIdentityText(item?.source_name);
    return sourceName ? `name:${sourceName}` : `group:${source}`;
}

function buildSummaryResults(
    groupedResults = currentGroupedResults,
    sources = sourcesToDisplay(),
) {
    const summaryResults = [];
    const seen = new Set();
    for (const source of sources) {
        const item = (groupedResults[source] || [])[0];
        if (!item) continue;
        const sourceUrl = safeSummarySourceUrl(item.source_url);
        const identity = summarySourceIdentity(item, source, sourceUrl);
        if (seen.has(identity)) continue;
        seen.add(identity);
        summaryResults.push({
            title: normalizedSummaryField(
                item.title,
                SUMMARY_FIELD_LIMITS.title,
            ) || 'Untitled',
            description: normalizedSummaryField(
                item.description,
                SUMMARY_FIELD_LIMITS.description,
            ),
            source_name: normalizedSummaryField(
                item.source_name,
                SUMMARY_FIELD_LIMITS.source_name,
            ),
            source_url: sourceUrl,
            whitelist_rank: 1,
        });
        if (summaryResults.length === SUMMARY_RESULT_LIMIT) break;
    }
    return summaryResults;
}

function getVisibleResults() {
    const visible = [];
    const visibleRank = Math.min(currentGroupPage, MAX_VISIBLE_SOURCE_RANK);
    const visibleCount = RESULTS_PER_SOURCE_PER_RANK * visibleRank;
    sourcesToDisplay().forEach((source) => {
        visible.push(...(currentGroupedResults[source] || []).slice(0, visibleCount));
    });
    return deduplicateResults(visible);
}

function hasBufferedGroupedResults() {
    if (currentGroupPage >= MAX_VISIBLE_SOURCE_RANK) return false;
    const visibleCount = RESULTS_PER_SOURCE_PER_RANK * currentGroupPage;
    return sourcesToDisplay().some((source) => (
        (currentGroupedResults[source] || []).length > visibleCount
    ));
}

function renderCurrentResults() {
    const sorting = pageRoot.querySelector('#filterSorting')?.value || '';
    renderResults(sortResults(getVisibleResults(), sorting));
    renderSidebar(currentSourceCounts, currentSearchResults);
}

function getDisplayNameForDomain(domain) {
    const domainNames = {
        'en.wikipedia.org': 'Wikipedia',
        'web.md': 'WebMD',
        'scholar.google.com': 'Google Scholar',
        'pubmed.ncbi.nlm.nih.gov': 'PubMed',
        'www.jstor.org': 'JSTOR',
        'eric.ed.gov': 'ERIC',
        'www.sciencedirect.com': 'ScienceDirect',
        'link.springer.com': 'Springer',
        'www.researchgate.net': 'ResearchGate',
        'www.academia.edu': 'Academia',
        'books.google.com': 'Google Books',
        'www.britannica.com': 'Britannica',
        'www.bbc.co.uk': 'BBC',
        'www.nationalgeographic.com': 'National Geographic',
    };
    
    if (domainNames[domain]) {
        return domainNames[domain];
    }
    if (domain.startsWith('*.')) {
        return `All ${domain.slice(2)} sites`;
    }
    
    return domain.replace('www.', '').replace('.com', '').replace('.org', '').replace('.net', '').replace('.edu', '');
}

function getSourceCheckboxes() {
    const filtersMenu = pageRoot?.querySelector('.browse-dropdown-menu');
    return filtersMenu
        ? Array.from(filtersMenu.querySelectorAll('.browse-source-checkbox'))
        : [];
}

function syncMasterSourceCheckbox() {
    const masterCheckbox = pageRoot?.querySelector('#filterAllSources');
    if (!masterCheckbox) return;

    const sourceCheckboxes = getSourceCheckboxes();
    const checkedCount = sourceCheckboxes.filter((checkbox) => checkbox.checked).length;
    masterCheckbox.checked = sourceCheckboxes.length > 0
        && checkedCount === sourceCheckboxes.length;
    masterCheckbox.indeterminate = checkedCount > 0
        && checkedCount < sourceCheckboxes.length;
}

function setAllSourcesSelected(selected) {
    getSourceCheckboxes().forEach((checkbox) => {
        checkbox.checked = selected;
    });
    syncMasterSourceCheckbox();
}

function settleWhitelistSourcesWithoutDynamic() {
    whitelistDomains = [];
    whitelistSourcesRendered = true;
    pendingMasterSourceSelection = null;
    pendingSourceSelectionOverrides.clear();
    syncMasterSourceCheckbox();
}

function renderWhitelistCheckboxes() {
    const container = pageRoot.querySelector('#whitelistCheckboxes');
    if (!container) return;
    if (!whitelistDomains || whitelistDomains.length === 0) {
        settleWhitelistSourcesWithoutDynamic();
        return;
    }
    
    let html = '<label class="form-label mb-2 small">Whitelisted Sites</label>';

    // Broad domain fan-out stays opt-in; restored user choices are reapplied below.
    whitelistDomains.forEach((domain, idx) => {
        const displayName = getDisplayNameForDomain(domain);
        const checkId = `filterWhitelist_${idx}`;
        html += `
            <div class="form-check">
                <input class="form-check-input browse-source-checkbox whitelist-domain-checkbox" type="checkbox" id="${checkId}" value="whitelist_${domain}">
                <label class="form-check-label" for="${checkId}">${displayName}</label>
            </div>
        `;
    });
    
    container.innerHTML = html;
    if (pendingMasterSourceSelection !== null) {
        setAllSourcesSelected(pendingMasterSourceSelection);
    } else if (lastSearchSources !== null) {
        applySelectedSources(lastSearchSources);
    } else {
        syncMasterSourceCheckbox();
    }

    if (pendingSourceSelectionOverrides.size > 0) {
        const sourceCheckboxes = new Map(
            getSourceCheckboxes().map((checkbox) => [checkbox.value, checkbox])
        );
        pendingSourceSelectionOverrides.forEach((checked, source) => {
            const checkbox = sourceCheckboxes.get(source);
            if (checkbox) checkbox.checked = checked;
        });
        syncMasterSourceCheckbox();
    }

    whitelistSourcesRendered = true;
    pendingMasterSourceSelection = null;
    pendingSourceSelectionOverrides.clear();
}

function appendQueryTerm(term) {
    const searchInput = pageRoot.querySelector('#searchInput');
    const current = searchInput.value.trim();
    searchInput.value = current ? `${current} ${term}` : term;
    searchInput.focus();
}

function getSelectedSources() {
    return Array.from(new Set(
        getSourceCheckboxes()
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) => checkbox.value)
    ));
}

function applySelectedSources(sources) {
    if (!Array.isArray(sources)) return;
    const selectedSources = new Set(sources);
    getSourceCheckboxes().forEach((checkbox) => {
        checkbox.checked = selectedSources.has(checkbox.value);
    });
    syncMasterSourceCheckbox();
}

function buildFilters() {
    const filters = {};
    const yearFrom = pageRoot.querySelector('#filterYearFrom').value.trim();
    const yearTo = pageRoot.querySelector('#filterYearTo').value.trim();
    const contentType = pageRoot.querySelector('#filterContentType').value;

    if (yearFrom) filters.min_date = yearFrom;
    if (yearTo) filters.max_date = yearTo;
    if (contentType) filters.content_type = contentType;

    return filters;
}

function getBrowseState() {
    const searchInput = pageRoot.querySelector('#searchInput');
    return {
        version: BROWSE_STATE_VERSION,
        query: searchInput?.value.trim() || '',
        sources: getSelectedSources(),
        filters: {
            min_date: pageRoot.querySelector('#filterYearFrom').value.trim(),
            max_date: pageRoot.querySelector('#filterYearTo').value.trim(),
            content_type: pageRoot.querySelector('#filterContentType').value,
            sorting: pageRoot.querySelector('#filterSorting').value
        },
        results: currentSearchResults,
        groupedResults: currentGroupedResults,
        sourceCounts: currentSourceCounts,
        groupPage: currentGroupPage,
        resultWindow: 10,
        searchExhausted: false,
        overview: (
            currentOverview.status === 'success'
            && currentOverview.query === lastSearchQuery
            && currentOverview.text
        )
            ? { query: currentOverview.query, text: currentOverview.text }
            : null,
    };
}

function saveBrowseState() {
    const state = getBrowseState();
    try {
        localStorage.setItem(BROWSE_STORAGE_KEY, JSON.stringify(state));
    } catch (err) {
        console.warn('Unable to save browse state', err);
    }
}

function restoreBrowseState() {
    try {
        const stateString = localStorage.getItem(BROWSE_STORAGE_KEY);
        if (!stateString) return;
        const state = JSON.parse(stateString);
        if (!state || typeof state !== 'object') return;
        const isCurrentState = state.version === BROWSE_STATE_VERSION;
        const preservesExplicitSources = isCurrentState || state.version === 1;

        const searchInput = pageRoot.querySelector('#searchInput');
        const yearFromEl = pageRoot.querySelector('#filterYearFrom');
        const yearToEl = pageRoot.querySelector('#filterYearTo');
        const contentTypeEl = pageRoot.querySelector('#filterContentType');
        const sortingEl = pageRoot.querySelector('#filterSorting');

        const restoredQuery = typeof state.query === 'string' ? state.query.trim() : '';
        const storedSources = Array.isArray(state.sources)
            ? state.sources
                .filter((source) => typeof source === 'string')
                .map((source) => source.trim())
                .filter(Boolean)
            : [];
        const restoredSources = Array.from(new Set(
            preservesExplicitSources
                ? storedSources
                : storedSources.filter(
                    (source) => !source.toLowerCase().startsWith('whitelist_')
                )
        ));
        const storedFilters = state.filters
            && typeof state.filters === 'object'
            && !Array.isArray(state.filters)
            ? state.filters
            : {};
        const restoredFilters = {
            min_date: typeof storedFilters.min_date === 'string' ? storedFilters.min_date : '',
            max_date: typeof storedFilters.max_date === 'string' ? storedFilters.max_date : '',
            content_type: typeof storedFilters.content_type === 'string'
                ? storedFilters.content_type
                : '',
            sorting: typeof storedFilters.sorting === 'string' ? storedFilters.sorting : ''
        };

        if (searchInput) searchInput.value = restoredQuery;
        if (yearFromEl) yearFromEl.value = restoredFilters.min_date || '';
        if (yearToEl) yearToEl.value = restoredFilters.max_date || '';
        if (contentTypeEl) contentTypeEl.value = restoredFilters.content_type || '';
        if (sortingEl) sortingEl.value = restoredFilters.sorting || '';

        lastSearchQuery = restoredQuery || null;
        lastSearchSources = restoredSources;
        const restoredGroupPage = Number.isInteger(state.groupPage) && state.groupPage >= 1
            ? state.groupPage
            : 1;
        currentGroupPage = Math.min(restoredGroupPage, MAX_VISIBLE_SOURCE_RANK);
        applySelectedSources(restoredSources);

        currentGroupedResults = normalizedGroupedResults(
            state.groupedResults,
            state.results,
        );
        currentSearchResults = deduplicateResults(
            Object.values(currentGroupedResults).flat(),
        );
        currentSourceCounts = state.sourceCounts
            && typeof state.sourceCounts === 'object'
            && !Array.isArray(state.sourceCounts)
            ? state.sourceCounts
            : {};
        const storedOverview = state.overview;
        const restoredOverviewQuery = typeof storedOverview?.query === 'string'
            ? storedOverview.query.trim()
            : '';
        const restoredOverviewText = typeof storedOverview?.text === 'string'
            ? storedOverview.text.trim()
            : '';
        const hasMatchingOverview = (
            isCurrentState
            && restoredOverviewQuery === restoredQuery
            && restoredOverviewText.length > 0
            && restoredOverviewText.length <= SUMMARY_TEXT_LIMIT
        );
        currentOverview = hasMatchingOverview
            ? overviewState('success', restoredQuery, restoredOverviewText)
            : overviewState('idle', restoredQuery);
        if (currentSearchResults.length > 0) {
            renderCurrentResults();
        }
        if (!isCurrentState) {
            saveBrowseState();
        }
    } catch (err) {
        console.warn('Unable to restore browse state', err);
    }
}

function sortResults(results, sortingCriteria) {
    if (!sortingCriteria) return results;

    const sorted = [...results];
    switch (sortingCriteria) {
        case 'recent':
            sorted.sort((a, b) => {
                const dateA = new Date(a.date || a.publication_date || 0);
                const dateB = new Date(b.date || b.publication_date || 0);
                return dateB - dateA;
            });
            break;
        case 'highly_cited':
            sorted.sort((a, b) => {
                const citesA = a.citations || a.citation_count || 0;
                const citesB = b.citations || b.citation_count || 0;
                return citesB - citesA;
            });
            break;
        case 'open_access':
            sorted.sort((a, b) => {
                const accessA = a.is_open_access || a.open_access ? 1 : 0;
                const accessB = b.is_open_access || b.open_access ? 1 : 0;
                return accessB - accessA;
            });
            break;
        default:
            break;
    }
    return sorted;
}

async function performSearch(options = {}) {
    const initGeneration = options.initGeneration ?? browseInitGeneration;
    if (initGeneration !== browseInitGeneration) return;

    const query = pageRoot.querySelector('#searchInput').value.trim();
    if (!query) return;

    const intentGeneration = ++searchIntentGeneration;
    renderSearchLoader(intentGeneration);
    const filters = buildFilters();
    const sourceReadiness = browseSourceReadiness;
    await sourceReadiness;
    if (
        initGeneration !== browseInitGeneration
        || intentGeneration !== searchIntentGeneration
    ) {
        clearSearchLoader(intentGeneration);
        return;
    }

    const sources = getSelectedSources();
    if (sources.length === 0) {
        showToast('Please select at least one source', 'warning');
        clearSearchLoader(intentGeneration);
        return;
    }

    clearSupersededSearchLoaders(intentGeneration);
    clearResultsBehindSearchLoader(intentGeneration);
    cancelOverviewRequest();
    const generation = ++searchGeneration;
    currentOverview = overviewState('idle', query);
    if (options.updateUrl !== false) updateBrowseUrl(query);

    const resultsContainer = pageRoot.querySelector('#resultsContainer');

    // Keep query/source ownership stable while cached ranks are revealed.
    lastSearchQuery = query;
    lastSearchSources = sources;
    isLoadingMore = false;
    isInitialSearchPending = true;
    currentSearchResults = [];
    currentGroupedResults = {};
    currentGroupPage = 1;
    currentSourceCounts = {};

    syncBrowseLoadingState(resultsContainer);
    renderSidebar(currentSourceCounts, currentSearchResults);

    try {
        const result = await fetchBrowseResults({
            query,
            sources,
            num_results: 10,
            filters,
        });
        if (generation !== searchGeneration) return;

        currentGroupedResults = normalizedGroupedResults(
            result.grouped_results,
            result.results,
        );
        currentSearchResults = deduplicateResults(
            Object.values(currentGroupedResults).flat(),
        );
        currentSourceCounts = result.source_counts || {};
        currentOverview = currentSearchResults.length
            ? overviewState('idle', query)
            : overviewState('empty', query);
        saveBrowseState();
        clearSearchLoader(intentGeneration);
        renderCurrentResults();
        showPartialSourceWarning(result);
        if (currentSearchResults.length) {
            void loadSearchSummary(query, generation);
        }
    } catch (error) {
        if (generation !== searchGeneration) return;
        clearSearchLoader(intentGeneration);
        showToast(error.message, 'danger');
        showNoResults();
    } finally {
        if (generation !== searchGeneration) return;
        isInitialSearchPending = false;
        syncBrowseLoadingState(pageRoot.querySelector('#resultsContainer'));
    }
}

function renderResults(results) {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '';
    syncBrowseLoadingState(resultsContainer);

    if (!results || results.length === 0) {
        showNoResults();
        return;
    }

    const row = document.createElement('div');
    row.className = 'row row-cols-1 row-cols-sm-2 row-cols-md-4 row-cols-lg-4 g-2 browse-results-row';
    results.forEach((item) => {
        const col = document.createElement('div');
        col.className = 'col';
        col.appendChild(createCard(item));
        row.appendChild(col);
    });
    resultsContainer.appendChild(row);

    // Add "Load More" button if there are results
    if (results.length > 0) {
        const loadMoreUnavailable = !hasBufferedGroupedResults();
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'text-center mt-4 mb-3';
        buttonContainer.innerHTML = `
            <button class="btn btn-outline-primary btn-secondary-wood" id="loadMoreBtn" type="button"${loadMoreUnavailable ? ' disabled' : ''}>
                <span id="loadMoreText">${loadMoreUnavailable ? 'No more results.' : 'Load More Results'}</span>
                <span id="loadMoreSpinner" class="spinner-border spinner-border-sm ms-2" role="status" aria-hidden="true" style="display: none;"></span>
            </button>
        `;
        resultsContainer.appendChild(buttonContainer);

        const loadMoreBtn = pageRoot.querySelector('#loadMoreBtn');
        if (loadMoreBtn) {
            if (loadMoreUnavailable) loadMoreBtn.disabled = true;
            loadMoreBtn.addEventListener('click', () => {
                loadMoreResults();
            });
        }
    }
}

async function loadMoreResults() {
    if (
        isInitialSearchPending
        || isLoadingMore
        || !lastSearchQuery
        || !lastSearchSources
        || currentGroupPage >= MAX_VISIBLE_SOURCE_RANK
        || !hasBufferedGroupedResults()
    ) {
        return;
    }

    currentGroupPage += 1;
    saveBrowseState();
    renderCurrentResults();
}

function showNoResults() {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted" aria-hidden="true"></i><h5>No results found</h5></div>';
    syncBrowseLoadingState(resultsContainer);
}
