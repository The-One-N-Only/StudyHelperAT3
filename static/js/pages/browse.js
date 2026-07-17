"use strict";

import { showToast } from '../toast.js';
import { createCard } from '../card.js';

const DEFAULT_SOURCES = ['wikipedia', 'gbooks', 'pubmed', 'scholar', 'whitelist'];
const BROWSE_STORAGE_KEY = 'studyhelper_browse_state';
let pageRoot = null;
let currentSearchResults = [];
let currentGroupedResults = {};
let currentSourceCounts = {};
let currentPageIndex = 1;
let whitelistDomains = [];
let lastSearchQuery = null;
let lastSearchSources = null;
let lastSearchFilters = null;
let currentSummary = null;
let isLoadingMore = false;

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
        <div class="bg-body-tertiary border-bottom p-3 mb-3">
            <div class="container-fluid">
                <div class="row g-3 align-items-center">
                    <div class="col-12">
                        <div class="dropdown d-inline-block w-100 position-relative">
                            <div class="input-group input-group-lg browse-search-group w-100">
                                <span class="input-group-text"><i class="bi bi-search"></i></span>
                                <input type="text" class="form-control browse-search-input" id="searchInput" placeholder="Search verified academic sources...">
                                <button class="btn btn-primary" id="goBtn">Go</button>
                                <button class="btn btn-outline-secondary dropdown-toggle" type="button" id="filtersDropdown">Filters</button>
                            </div>
                            <div class="browse-dropdown-menu p-3" aria-labelledby="filtersDropdown" style="min-width: 320px;">
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
        <div class="d-flex" style="height: calc(100vh - 200px);">
            <div class="border-end p-3 flex-shrink-0" style="width: 320px; min-width: 320px; overflow-y: auto;" id="sidebarContainer"></div>
            <div class="flex-grow-1 p-3 overflow-y-auto">
                <div id="resultsContainer">
                    <div class="text-center py-5">
                        <i class="bi bi-mortarboard display-4 text-muted"></i>
                        <h5>Search verified academic sources</h5>
                        <p class="text-muted">Use the search bar above to find academic resources from trusted sources</p>
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
    restoreBrowseState();
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
            <div class="card mb-3">
                <div class="card-header">
                    <h5 class="card-title mb-0">Alexander says:</h5>
                </div>
                <div class="card-body">
                    <p class="text-muted small mb-0">AI search insights will appear here after you run a search. For now, results are gathered from trusted academic sources across the full whitelist.</p>
                </div>
            </div>
        `;
        return;
    }

    let html = '<div class="card mb-3">';
    html += '<div class="card-header"><h5 class="card-title mb-0">Alexander says:</h5></div>';
    html += '<div class="card-body">';
    if (currentSummary) {
        html += `<p class="small text-muted mb-0">${escapeHtml(currentSummary)}</p>`;
    } else {
        html += '<p class="small text-muted mb-0">Summarising search results...</p>';
    }
    html += '</div></div>';

    html += '<div class="card mb-3">';
    html += '<div class="card-header"><h5 class="card-title mb-0">Search sources</h5></div>';
    html += '<div class="list-group list-group-flush">';

    selectedSources.forEach((source) => {
        const displayName = getDisplayNameForSource(source);
        let count = 0;
        if (sourceCounts[source] != null) {
            count = sourceCounts[source];
        } else if (source === 'whitelist') {
            count = Object.keys(currentSourceCounts)
                .filter((key) => key.startsWith('whitelist_'))
                .reduce((sum, key) => sum + (currentSourceCounts[key] || 0), 0);
        } else {
            count = results.filter((item) => itemMatchesSource(item, source)).length;
        }

        const topItem = results.find((item) => itemMatchesSource(item, source));

        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <strong>${escapeHtml(displayName)}</strong>
                    <span class="badge bg-primary rounded-pill">${count}</span>
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

function getSourcesToDisplay() {
    if (!lastSearchSources || lastSearchSources.length === 0) return [];

    const sources = [];
    lastSearchSources.forEach((source) => {
        if (source === 'whitelist') {
            Object.keys(currentGroupedResults).forEach((key) => {
                if (key.startsWith('whitelist_') && !sources.includes(key)) {
                    sources.push(key);
                }
            });
        } else if (!sources.includes(source)) {
            sources.push(source);
        }
    });

    return sources;
}

function getVisibleResults() {
    const sources = getSourcesToDisplay();
    const visible = [];

    sources.forEach((source) => {
        const items = currentGroupedResults[source] || [];
        visible.push(...items.slice(0, currentPageIndex));
    });

    return visible;
}

function hasMoreResults() {
    return Object.values(currentGroupedResults).some((items) => items.length > currentPageIndex);
}

function getAllResults() {
    return Object.values(currentGroupedResults).flat();
}

function groupResultsBySource(results) {
    const grouped = {};
    results.forEach((item) => {
        const sourceName = (item.source_name || '').toLowerCase();
        let sourceKey = 'unknown';

        if (sourceName === 'wikipedia') {
            sourceKey = 'wikipedia';
        } else if (sourceName === 'gbooks' || sourceName === 'google books') {
            sourceKey = 'gbooks';
        } else if (sourceName === 'pubmed') {
            sourceKey = 'pubmed';
        } else if (sourceName === 'scholar' || sourceName === 'google scholar') {
            sourceKey = 'scholar';
        } else if (item.source_url) {
            const match = item.source_url.match(/^https?:\/\/([^\/]+)\/?.*$/);
            if (match) {
                sourceKey = `whitelist_${match[1]}`;
            }
        } else {
            sourceKey = sourceName || 'unknown';
        }

        if (!grouped[sourceKey]) {
            grouped[sourceKey] = [];
        }
        grouped[sourceKey].push(item);
    });
    return grouped;
}

function computeSourceCounts(groupedResults) {
    const counts = {};
    Object.keys(groupedResults).forEach((source) => {
        counts[source] = groupedResults[source].length;
    });
    return counts;
}

function loadSearchSummary(query) {
    const sidebar = pageRoot.querySelector('#sidebarContainer');
    if (!sidebar) return;
    currentSummary = null;
    renderSidebar(currentSourceCounts, getVisibleResults());

    const summaryResults = getAllResults();
    fetch('/api/browse/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, results: summaryResults })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.status && data.summary) {
                currentSummary = data.summary;
            } else {
                currentSummary = 'Unable to generate summary.';
            }
            renderSidebar(currentSourceCounts, getVisibleResults());
        })
        .catch(() => {
            currentSummary = 'Unable to generate summary.';
            renderSidebar(currentSourceCounts, getVisibleResults());
        });
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
        grouped_results: currentGroupedResults,
        page_index: currentPageIndex,
        summary: currentSummary
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
        const sourceCheckboxes = pageRoot.querySelectorAll('input[type="checkbox"][value]');

        if (searchInput && state.query) searchInput.value = state.query;
        if (yearFromEl && state.filters?.min_date) yearFromEl.value = state.filters.min_date;
        if (yearToEl && state.filters?.max_date) yearToEl.value = state.filters.max_date;
        if (contentTypeEl && state.filters?.content_type) contentTypeEl.value = state.filters.content_type;
        if (sortingEl && state.filters?.sorting) sortingEl.value = state.filters.sorting;

        if (sourceCheckboxes.length && Array.isArray(state.sources)) {
            sourceCheckboxes.forEach((checkbox) => {
                if (checkbox.value.startsWith('whitelist_')) {
                    checkbox.checked = state.sources.includes(checkbox.value) || state.sources.includes('whitelist');
                } else {
                    checkbox.checked = state.sources.includes(checkbox.value);
                }
            });
        }

        if (state.grouped_results && typeof state.grouped_results === 'object') {
            currentGroupedResults = state.grouped_results;
            currentPageIndex = state.page_index || 1;
            lastSearchSources = Array.isArray(state.sources) ? state.sources : [];
            currentSummary = state.summary || null;
            currentSearchResults = getVisibleResults();
            renderResults(sortResults(currentSearchResults, state.filters?.sorting || ''));
            currentSourceCounts = computeSourceCounts(currentGroupedResults);
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

function escapeHtml(text) {
    if (text == null) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function performSearch() {
    const query = pageRoot.querySelector('#searchInput').value.trim();
    if (!query) return;

    const sources = getSelectedSources();
    if (sources.length === 0) {
        showToast('Please select at least one source', 'warning');
        return;
    }

    const filters = buildFilters();
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Searching...</p></div>';

    lastSearchQuery = query;
    lastSearchSources = sources;
    lastSearchFilters = filters;
    currentPageIndex = 1;
    currentSummary = null;
    isLoadingMore = false;

    fetch('/api/browse/search-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sources, num_results: 10, filters })
    })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                currentGroupedResults = result.grouped_results || groupResultsBySource(result.results || []);
                currentSearchResults = getVisibleResults();
                currentSourceCounts = result.source_counts || computeSourceCounts(currentGroupedResults);
                saveBrowseState();
                renderResults(currentSearchResults);
                renderSidebar(currentSourceCounts, currentSearchResults);
                loadSearchSummary(query);
            } else {
                showNoResults();
            }
        })
        .catch(() => {
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

    if (results.length > 0) {
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'text-center mt-4 mb-3';
        buttonContainer.innerHTML = `
            <button class="btn btn-outline-primary" id="loadMoreBtn" ${hasMoreResults() ? '' : 'disabled'}>
                <span id="loadMoreText">Load More Results</span>
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
    if (isLoadingMore || !lastSearchQuery || !lastSearchSources) {
        return;
    }

    if (!hasMoreResults()) {
        showToast('No more results available', 'info');
        return;
    }

    isLoadingMore = true;
    currentPageIndex += 1;
    currentSearchResults = getVisibleResults();
    renderResults(currentSearchResults);
    renderSidebar(currentSourceCounts, currentSearchResults);
    saveBrowseState();
    isLoadingMore = false;
}

function showNoResults() {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted"></i><h5>No results found</h5></div>';
}
