"use strict";

import { showToast } from '../toast.js';
import { createCard } from '../card.js';

const DEFAULT_SOURCES = ['wikipedia', 'gbooks', 'pubmed', 'scholar'];
let pageRoot = null;
let currentSearchResults = [];

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

    registerEvents();
    renderSidebar();
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

function renderSidebar() {
    const sidebar = pageRoot.querySelector('#sidebarContainer');
    sidebar.innerHTML = `
        <div class="card mb-3">
            <div class="card-header">
                <h5 class="card-title mb-0">AI Overview</h5>
            </div>
            <div class="card-body">
                <p class="text-muted small mb-0">AI search insights will appear here after you run a search. For now, results are gathered from trusted academic sources across the full whitelist.</p>
            </div>
        </div>
    `;
}

function appendQueryTerm(term) {
    const searchInput = pageRoot.querySelector('#searchInput');
    const current = searchInput.value.trim();
    searchInput.value = current ? `${current} ${term}` : term;
    searchInput.focus();
}

function getSelectedSources() {
    const dropdownToggle = pageRoot.querySelector('#filtersDropdown');
    const dropdownMenu = dropdownToggle?.closest('.dropdown')?.querySelector('.dropdown-menu');
    const checkedInputs = dropdownMenu
        ? dropdownMenu.querySelectorAll('input[type="checkbox"]:checked')
        : pageRoot.querySelectorAll('input[type="checkbox"]:checked');
    return Array.from(checkedInputs).map((checkbox) => checkbox.value);
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

    const filters = buildFilters();
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Searching...</p></div>';

    fetch('/api/browse/search-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sources, num_results: 10, filters })
    })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                currentSearchResults = result.results || [];
                renderResults(currentSearchResults);
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
}

function showNoResults() {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted"></i><h5>No results found</h5></div>';
}
