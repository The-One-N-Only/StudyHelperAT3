"use strict";

import { showToast } from '../toast.js';
import { createCard } from '../card.js';

const DEFAULT_SOURCES = ['wikipedia', 'gbooks', 'pubmed', 'scholar', 'whitelist'];
const BROWSE_STORAGE_KEY = 'studyhelper_browse_state';
let pageRoot = null;
let currentSearchResults = [];
let currentSourceCounts = {};
let whitelistDomains = [];
let lastSearchQuery = null;
let lastSearchSources = null;
let lastSearchFilters = null;
let isLoadingMore = false;
let resultWindow = 10;
let searchExhausted = false;
let searchGeneration = 0;

function normalizeIdentityText(value) {
    if (value === null || value === undefined) return '';
    if (!['string', 'number', 'boolean'].includes(typeof value)) return '';
    const collapsed = String(value).trim().replace(/\s+/gu, ' ');
    return collapsed
        .toLowerCase()
        .replace(/\u00df/gu, 'ss')
        .replace(/\u03c2/gu, '\u03c3');
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

function resultIdentity(item) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return null;

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

function deduplicateResults(results) {
    if (!Array.isArray(results)) return [];

    const uniqueResults = [];
    const seenIdentities = new Set();
    const seenUrls = new Set();
    results.forEach((item) => {
        const identity = resultIdentity(item);
        const identityKey = identity ? JSON.stringify(identity) : '';
        const sourceUrl = item && typeof item === 'object' && !Array.isArray(item)
            ? canonicalSourceUrl(item.source_url)
            : '';

        if (identityKey && seenIdentities.has(identityKey)) return;
        if (sourceUrl && seenUrls.has(sourceUrl)) return;

        uniqueResults.push(item);
        if (identityKey) seenIdentities.add(identityKey);
        if (sourceUrl) seenUrls.add(sourceUrl);
    });
    return uniqueResults;
}

function structuralFallbackKey(value, ancestors = new Set()) {
    if (value === null) return 'null';
    if (typeof value === 'string') return `string:${JSON.stringify(value)}`;
    if (typeof value === 'boolean') return `boolean:${value}`;
    if (typeof value === 'number' && Number.isFinite(value)) return `number:${value}`;
    if (!value || typeof value !== 'object' || ancestors.has(value)) return '';

    ancestors.add(value);
    let key = '';
    if (Array.isArray(value)) {
        const entries = value.map((entry) => structuralFallbackKey(entry, ancestors));
        if (entries.every(Boolean)) key = `array:[${entries.join(',')}]`;
    } else {
        const entries = Object.keys(value).sort().map((name) => {
            const entryKey = structuralFallbackKey(value[name], ancestors);
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
    return {
        results: mergedResults,
        addedCount: mergedResults.length - existingResults.length
    };
}

// Load whitelisted domains
async function loadWhitelistDomains() {
    try {
        const response = await fetch('/static/whitelist.json');
        if (response.ok) {
            const whitelist = await response.json();
            whitelistDomains = whitelist.domains || [];
        }
    } catch (err) {
        console.warn('Unable to load whitelist domains', err);
    }
}

export function initBrowse(root) {
    pageRoot = root;
    pageRoot.innerHTML = `
        <div class="archive-page archive-page-browse">
            <span class="archive-illustration illustration-books" aria-hidden="true"></span>
            <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
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
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="filterWikipedia" value="wikipedia" checked>
                                        <label class="form-check-label" for="filterWikipedia">Wikipedia</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="filterGBooks" value="gbooks" checked>
                                        <label class="form-check-label" for="filterGBooks">Google Books</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="filterPubMed" value="pubmed" checked>
                                        <label class="form-check-label" for="filterPubMed">PubMed</label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="filterScholar" value="scholar">
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
            <div class="border-end p-3 flex-shrink-0 browse-sidebar" style="width: 320px; min-width: 320px; overflow-y: auto;" id="sidebarContainer"></div>
            <div class="flex-grow-1 p-3 overflow-y-auto browse-results-pane">
                <div id="resultsContainer">
                    <div class="text-center py-5">
                        <i class="bi bi-mortarboard display-4 text-muted" aria-hidden="true"></i>
                        <h5>Search verified academic sources</h5>
                        <p class="text-muted">Use the search bar above to find academic resources from trusted sources</p>
                    </div>
                </div>
                <div id="googleCseContainer" class="mt-4"></div>
            </div>
        </div>
            </div>
        </div>
    `;

    loadWhitelistDomains().then(() => {
        renderWhitelistCheckboxes();
    });

    registerEvents();
    renderSidebar();
    ensureGoogleCustomSearch();
    restoreBrowseState();
}

function ensureGoogleCustomSearch() {
    const existingScript = document.getElementById('google-cse-script');
    if (existingScript) {
        if (window.google?.search?.cse?.element) {
            window.google.search.cse.element.render({
                div: 'googleCseContainer',
                tag: 'search'
            });
        }
        return;
    }

    window.__gcse = {
        callback: function() {
            if (window.google?.search?.cse?.element) {
                window.google.search.cse.element.render({
                    div: 'googleCseContainer',
                    tag: 'search'
                });
            }
        }
    };

    const script = document.createElement('script');
    script.id = 'google-cse-script';
    script.async = true;
    script.src = 'https://cse.google.com/cse.js?cx=7675fc4c77c124dee';
    document.body.appendChild(script);
}

function registerEvents() {
    const searchInput = pageRoot.querySelector('#searchInput');
    const goBtn = pageRoot.querySelector('#goBtn');
    const filtersDropdown = pageRoot.querySelector('#filtersDropdown');
    const dropdownMenu = pageRoot.querySelector('.browse-dropdown-menu');
    const sortingSelect = pageRoot.querySelector('#filterSorting');

    goBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
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

    document.addEventListener('click', () => {
        if (!dropdownMenu) return;
        dropdownMenu.classList.remove('show');
        filtersDropdown?.setAttribute('aria-expanded', 'false');
    });

    sortingSelect?.addEventListener('change', () => {
        if (currentSearchResults.length > 0) {
            const sortedResults = sortResults(currentSearchResults, sortingSelect.value);
            renderResults(sortedResults);
        }
    });
}

function getDisplayNameForSource(source) {
    if (source === 'wikipedia') return 'Wikipedia';
    if (source === 'gbooks') return 'Google Books';
    if (source === 'pubmed') return 'PubMed';
    if (source === 'scholar') return 'Google Scholar';
    if (source === 'whitelist') return 'Whitelisted Sources';
    if (source.startsWith('whitelist_')) {
        const domain = source.split('_', 2)[1];
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
        const domain = source.split('_', 2)[1];
        return item.source_url && item.source_url.includes(domain);
    }
    return sourceName.includes(source.toLowerCase());
}

function renderSidebar(sourceCounts = {}, results = []) {
    const sidebar = pageRoot.querySelector('#sidebarContainer');
    const selectedSources = lastSearchSources || [];
    if (!selectedSources.length) {
        sidebar.innerHTML = `
            <div class="card surface-leather ai-overview-panel mb-3">
                <div class="card-header">
                    <h5 class="card-title mb-0">AI Overview</h5>
                </div>
                <div class="card-body">
                    <p class="text-muted small mb-0">AI search insights will appear here after you run a search. For now, results are gathered from trusted academic sources across the full whitelist.</p>
                </div>
            </div>
        `;
        return;
    }

    let html = '<div class="card surface-leather source-summary-panel mb-3">';
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
            html += `<div class="small text-muted">No results yet for this source.</div>`;
        }
        html += '</div>';
    });

    html += '</div></div>';
    sidebar.innerHTML = html;
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
    
    return domain.replace('www.', '').replace('.com', '').replace('.org', '').replace('.net', '').replace('.edu', '');
}

function renderWhitelistCheckboxes() {
    const container = pageRoot.querySelector('#whitelistCheckboxes');
    if (!container || !whitelistDomains || whitelistDomains.length === 0) return;
    
    let html = '<label class="form-label mb-2 small">Whitelisted Sites</label>';
    
    whitelistDomains.forEach((domain, idx) => {
        const displayName = getDisplayNameForDomain(domain);
        const checkId = `filterWhitelist_${idx}`;
        html += `
            <div class="form-check">
                <input class="form-check-input whitelist-domain-checkbox" type="checkbox" id="${checkId}" value="whitelist_${domain}" checked>
                <label class="form-check-label" for="${checkId}">${displayName}</label>
            </div>
        `;
    });
    
    container.innerHTML = html;
    if (lastSearchSources !== null) {
        applySelectedSources(lastSearchSources);
    }
}

function appendQueryTerm(term) {
    const searchInput = pageRoot.querySelector('#searchInput');
    const current = searchInput.value.trim();
    searchInput.value = current ? `${current} ${term}` : term;
    searchInput.focus();
}

function getSelectedSources() {
    const browseDropdownMenu = pageRoot.querySelector('.browse-dropdown-menu');
    const checkedInputs = browseDropdownMenu
        ? browseDropdownMenu.querySelectorAll('input[type="checkbox"]:checked')
        : pageRoot.querySelectorAll('input[type="checkbox"]:checked');
    
    const sources = new Set();
    Array.from(checkedInputs).forEach((checkbox) => {
        const value = checkbox.value;
        if (value.startsWith('whitelist_')) {
            sources.add(value);
        } else {
            sources.add(value);
        }
    });
    
    return Array.from(sources);
}

function applySelectedSources(sources) {
    if (!Array.isArray(sources)) return;
    const selectedSources = new Set(sources);
    pageRoot.querySelectorAll('input[type="checkbox"][value]').forEach((checkbox) => {
        checkbox.checked = selectedSources.has(checkbox.value);
    });
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
        query: searchInput?.value.trim() || '',
        sources: getSelectedSources(),
        filters: {
            min_date: pageRoot.querySelector('#filterYearFrom').value.trim(),
            max_date: pageRoot.querySelector('#filterYearTo').value.trim(),
            content_type: pageRoot.querySelector('#filterContentType').value,
            sorting: pageRoot.querySelector('#filterSorting').value
        },
        results: currentSearchResults,
        resultWindow,
        searchExhausted
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

        const searchInput = pageRoot.querySelector('#searchInput');
        const yearFromEl = pageRoot.querySelector('#filterYearFrom');
        const yearToEl = pageRoot.querySelector('#filterYearTo');
        const contentTypeEl = pageRoot.querySelector('#filterContentType');
        const sortingEl = pageRoot.querySelector('#filterSorting');

        const restoredQuery = typeof state.query === 'string' ? state.query.trim() : '';
        const restoredSources = Array.isArray(state.sources)
            ? state.sources.filter((source) => typeof source === 'string')
            : [];
        const restoredFilters = state.filters
            && typeof state.filters === 'object'
            && !Array.isArray(state.filters)
            ? { ...state.filters }
            : {};

        if (searchInput) searchInput.value = restoredQuery;
        if (yearFromEl) yearFromEl.value = restoredFilters.min_date || '';
        if (yearToEl) yearToEl.value = restoredFilters.max_date || '';
        if (contentTypeEl) contentTypeEl.value = restoredFilters.content_type || '';
        if (sortingEl) sortingEl.value = restoredFilters.sorting || '';

        lastSearchQuery = restoredQuery || null;
        lastSearchSources = restoredSources;
        lastSearchFilters = restoredFilters;
        resultWindow = Number.isInteger(state.resultWindow)
            && state.resultWindow >= 10
            && state.resultWindow % 10 === 0
            ? state.resultWindow
            : 10;
        searchExhausted = state.searchExhausted === true;
        applySelectedSources(restoredSources);

        currentSearchResults = deduplicateResults(state.results);
        if (currentSearchResults.length > 0) {
            renderResults(sortResults(currentSearchResults, state.filters?.sorting || ''));
            renderSidebar(currentSourceCounts, currentSearchResults);
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

function performSearch() {
    const query = pageRoot.querySelector('#searchInput').value.trim();
    if (!query) return;

    const sources = getSelectedSources();
    if (sources.length === 0) {
        showToast('Please select at least one source', 'warning');
        return;
    }

    const generation = ++searchGeneration;
    const filters = buildFilters();
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Searching...</p></div>';

    // Save search parameters for "load more" functionality
    lastSearchQuery = query;
    lastSearchSources = sources;
    lastSearchFilters = filters;
    isLoadingMore = false;
    resultWindow = 10;
    searchExhausted = false;

    fetch('/api/browse/search-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sources, num_results: 10, filters })
    })
        .then((r) => r.json())
        .then((result) => {
            if (generation !== searchGeneration) return;
            if (result.status) {
                currentSearchResults = deduplicateResults(result.results);
                currentSourceCounts = result.source_counts || {};
                saveBrowseState();
                renderResults(currentSearchResults);
                renderSidebar(currentSourceCounts, currentSearchResults);
            } else {
                showNoResults();
            }
        })
        .catch(() => {
            if (generation !== searchGeneration) return;
            showToast('Search failed', 'danger');
            showNoResults();
        });
}

function renderResults(results) {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '';

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
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'text-center mt-4 mb-3';
        buttonContainer.innerHTML = `
            <button class="btn btn-outline-primary btn-secondary-wood" id="loadMoreBtn" type="button"${searchExhausted ? ' disabled' : ''}>
                <span id="loadMoreText">${searchExhausted ? 'No more results.' : 'Load More Results'}</span>
                <span id="loadMoreSpinner" class="spinner-border spinner-border-sm ms-2" role="status" aria-hidden="true" style="display: none;"></span>
            </button>
        `;
        resultsContainer.appendChild(buttonContainer);

        const loadMoreBtn = pageRoot.querySelector('#loadMoreBtn');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', loadMoreResults);
        }
    }
}

function loadMoreResults() {
    if (isLoadingMore || searchExhausted || !lastSearchQuery || !lastSearchSources) {
        return;
    }

    const generation = searchGeneration;
    isLoadingMore = true;
    const nextWindow = resultWindow + 10;
    const loadMoreBtn = pageRoot.querySelector('#loadMoreBtn');
    const loadMoreText = pageRoot.querySelector('#loadMoreText');
    const loadMoreSpinner = pageRoot.querySelector('#loadMoreSpinner');

    if (loadMoreBtn) {
        loadMoreBtn.disabled = true;
    }
    if (loadMoreText) {
        loadMoreText.textContent = 'Loading...';
    }
    if (loadMoreSpinner) {
        loadMoreSpinner.style.display = 'inline-block';
    }

    fetch('/api/browse/search-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: lastSearchQuery,
            sources: lastSearchSources,
            num_results: nextWindow,
            filters: lastSearchFilters || {}
        })
    })
        .then((r) => {
            if (generation !== searchGeneration) return null;
            if (!r.ok) throw new Error('Load more request failed');
            return r.json();
        })
        .then((result) => {
            if (generation !== searchGeneration || !result) return;
            if (result.status) {
                const merged = mergeUniqueResults(currentSearchResults, result.results);
                currentSearchResults = merged.results;
                resultWindow = nextWindow;
                searchExhausted = merged.addedCount === 0;
                if (result.source_counts) {
                    currentSourceCounts = result.source_counts;
                }
                saveBrowseState();
                renderResults(currentSearchResults);
                renderSidebar(currentSourceCounts, currentSearchResults);
            } else {
                showToast('Failed to load more results', 'danger');
            }
        })
        .catch(() => {
            if (generation !== searchGeneration) return;
            showToast('Failed to load more results', 'danger');
        })
        .finally(() => {
            if (generation !== searchGeneration) return;
            isLoadingMore = false;
            const currentLoadMoreBtn = pageRoot.querySelector('#loadMoreBtn');
            const currentLoadMoreText = pageRoot.querySelector('#loadMoreText');
            const currentLoadMoreSpinner = pageRoot.querySelector('#loadMoreSpinner');
            if (currentLoadMoreBtn) {
                currentLoadMoreBtn.disabled = searchExhausted;
            }
            if (currentLoadMoreText) {
                currentLoadMoreText.textContent = searchExhausted
                    ? 'No more results.'
                    : 'Load More Results';
            }
            if (currentLoadMoreSpinner) {
                currentLoadMoreSpinner.style.display = 'none';
            }
        });
}

function showNoResults() {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted" aria-hidden="true"></i><h5>No results found</h5></div>';
}
