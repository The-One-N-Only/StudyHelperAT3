"use strict";

import { showToast } from '../main.js';
import { createCard } from '../card.js';

let currentFilters = [];
let pageRoot = null;

export function initBrowse(root) {
    pageRoot = root;
    pageRoot.innerHTML = `
        <div class="bg-body-tertiary border-bottom p-3 mb-3">
            <div class="container-fluid">
                <div class="row g-3 align-items-end">
                    <div class="col">
                        <div class="input-group input-group-lg">
                            <span class="input-group-text"><i class="bi bi-search"></i></span>
                            <input type="text" class="form-control" id="searchInput" placeholder="Search verified academic sources...">
                            <button class="btn btn-primary" id="goBtn">Go</button>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <label for="atnInput" class="form-label">Assessment Task (optional)</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="atnInput" placeholder="Enter your assessment task...">
                            <button class="btn btn-outline-secondary" id="clearAtnBtn" type="button">×</button>
                        </div>
                        <div class="mt-1">
                            <span class="badge bg-secondary" id="modeBadge">Search Mode</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex" style="height: calc(100vh - 200px);">
            <div class="border-end p-3" style="width: 250px; overflow-y: auto;" id="filterContainer"></div>
            <div class="flex-grow-1 p-3 overflow-y-auto">
                <div id=\"aiSummaryBox\" class=\"card mb-4 d-none\" style=\"max-width: 600px;\">
                    <div class=\"card-header p-2\" style=\"cursor: pointer;\" data-bs-toggle=\"collapse\" data-bs-target=\"#aiSummaryContent\">
                        <h6 class=\"mb-0\">
                            <i class=\"bi bi-chevron-down me-2\" id=\"summaryChevron\"></i>
                            <strong>AI Overview</strong>
                        </h6>
                    </div>
                    <div class=\"collapse show\" id=\"aiSummaryContent\">
                        <div class=\"card-body p-3\">
                            <p class=\"card-text text-muted ai-summary-text small mb-0\">Generating summary...</p>
                        </div>
                    </div>
                </div>
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
    loadFilters();
}

function registerEvents() {
    const searchInput = pageRoot.querySelector('#searchInput');
    const goBtn = pageRoot.querySelector('#goBtn');
    const atnInput = pageRoot.querySelector('#atnInput');
    const clearAtnBtn = pageRoot.querySelector('#clearAtnBtn');

    goBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    atnInput.addEventListener('input', updateModeBadge);
    clearAtnBtn.addEventListener('click', () => {
        atnInput.value = '';
        updateModeBadge();
    });

    pageRoot.addEventListener('change', (event) => {
        if (event.target && event.target.name === 'sources') {
            renderFilters();
        }
    });
}

function loadFilters() {
    fetch('/api/filters')
        .then((r) => r.json())
        .then((data) => {
            currentFilters = data.filters || [];
            renderFilters();
            updateModeBadge();
        })
        .catch(() => {
            showToast('Unable to load search filters', 'danger');
        });
}

function renderFilters() {
    const filterContainer = pageRoot.querySelector('#filterContainer');
    filterContainer.innerHTML = '';

    const selectedSources = getSelectedSources();

    currentFilters.forEach((filter) => {
        if (filter.shown_source && !selectedSources.includes(filter.shown_source)) return;

        const card = document.createElement('div');
        card.className = 'card mb-3';
        card.innerHTML = `
            <div class="card-header">${filter.title}</div>
            <div class="card-body">
                ${renderFilterControl(filter)}
            </div>
        `;
        filterContainer.appendChild(card);
    });

    pageRoot.querySelectorAll('input[type="range"]').forEach((range) => {
        const valueLabel = pageRoot.querySelector(`#${range.id}Value`);
        if (valueLabel) {
            valueLabel.textContent = range.value;
            range.addEventListener('input', () => {
                valueLabel.textContent = range.value;
            });
        }
    });
}

function renderFilterControl(filter) {
    if (filter.type === 'radio') {
        return filter.options
            .map(
                (opt) => `
            <div class="form-check">
                <input class="form-check-input" type="radio" name="${filter.name}" id="${opt.id}" value="${opt.id}" ${filter.default === opt.id ? 'checked' : ''}>
                <label class="form-check-label" for="${opt.id}">${opt.name}</label>
            </div>`
            )
            .join('');
    }
    if (filter.type === 'checkbox') {
        return filter.options
            .map(
                (opt) => `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" name="${filter.name}" id="${opt.id}" value="${opt.id}" ${opt.checked ? 'checked' : ''}>
                <label class="form-check-label" for="${opt.id}">${opt.name}</label>
            </div>`
            )
            .join('');
    }
    if (filter.type === 'range') {
        return `
            <label for="${filter.id}" class="form-label">${filter.name}: <span id="${filter.id}Value">${filter.default}</span></label>
            <input type="range" class="form-range" id="${filter.id}" min="${filter.min}" max="${filter.max}" step="${filter.step}" value="${filter.default}">`;
    }
    return '';
}

function getSelectedSources() {
    return Array.from(pageRoot.querySelectorAll('input[name="sources"]:checked')).map(cb => cb.value);
}

function updateModeBadge() {
    const badge = pageRoot.querySelector('#modeBadge');
    const atn = pageRoot.querySelector('#atnInput').value.trim();
    if (atn) {
        badge.className = 'badge bg-primary';
        badge.textContent = 'ATN Mode';
    } else {
        badge.className = 'badge bg-secondary';
        badge.textContent = 'Search Mode';
    }
}

function performSearch() {
    const query = pageRoot.querySelector('#searchInput').value.trim();
    if (!query) return;

    const sources = getSelectedSources();
    if (sources.length === 0) {
        showToast('Please select at least one source', 'warning');
        return;
    }

    const numResults = parseInt(pageRoot.querySelector('#resultsSlider').value, 10);
    const filters = {};
    if (sources.includes('gbooks')) {
        filters.download = pageRoot.querySelector('input[name="download"]:checked')?.value;
        filters.available = pageRoot.querySelector('input[name="available"]:checked')?.value;
        filters.print = pageRoot.querySelector('input[name="print"]:checked')?.value;
    }

    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Searching...</p></div>';

    fetch('/api/browse/search-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, sources, num_results: numResults, filters })
    })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                renderResults(result.results, query);
            } else {
                showNoResults();
            }
        })
        .catch(() => {
            showToast('Search failed', 'danger');
            showNoResults();
        });
}

function renderResults(results, query) {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '';

    const summaryBox = pageRoot.querySelector('#aiSummaryBox');
    summaryBox.classList.remove('d-none');
    summaryBox.querySelector('.ai-summary-text').innerHTML = `Generating summary for <strong>${escapeHtml(query)}</strong>...`;

    if (results.length === 0) {
        showNoResults();
        return;
    }

    const row = document.createElement('div');
    row.className = 'row row-cols-2 row-cols-md-3 row-cols-xl-4 g-3';
    results.forEach((item) => {
        const col = document.createElement('div');
        col.className = 'col';
        col.appendChild(createCard(item));
        row.appendChild(col);
    });
    resultsContainer.appendChild(row);

    const atn = pageRoot.querySelector('#atnInput').value.trim();
    summarizeSearchResults(query, results, atn);
}

function summarizeSearchResults(query, results, atn) {
    const summaryBox = pageRoot.querySelector('#aiSummaryBox');
    const trimmedResults = results.slice(0, 8).map((item) => ({
        title: item.title || '',
        description: item.description || '',
        source_name: item.source_name || '',
        source_url: item.source_url || ''
    }));

    fetch('/api/browse/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, results: trimmedResults, atn })
    })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                const text = result.summary.replace(/^\*\*|\*\*$/g, '').trim();
                summaryBox.querySelector('.ai-summary-text').textContent = text;
            } else {
                summaryBox.querySelector('.ai-summary-text').textContent = 'AI summarisation is currently unavailable.';
            }
        })
        .catch(() => {
            summaryBox.querySelector('.ai-summary-text').textContent = 'AI summarisation failed. Please try again later.';
        });
}

function showNoResults() {
    const resultsContainer = pageRoot.querySelector('#resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted"></i><h5>No results found</h5></div>';
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value;
    return div.innerHTML;
}
