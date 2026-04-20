"use strict";

import { showToast } from './main.js';
import { createCard } from './card.js';

let currentFilters = {};

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    const goBtn = document.getElementById('goBtn');
    const resultsContainer = document.getElementById('resultsContainer');
    const atnInput = document.getElementById('atnInput');
    const clearAtnBtn = document.getElementById('clearAtnBtn');
    
    // Load filters from JSON
    fetch('/static/src/filters.json').then(r => r.json()).then(data => {
        currentFilters = data.filters;
        renderFilters();
        updateModeBadge();
    });
    
    goBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    atnInput.addEventListener('input', updateModeBadge);
    clearAtnBtn.addEventListener('click', () => {
        atnInput.value = '';
        updateModeBadge();
    });
});

function renderFilters() {
    const filterContainer = document.getElementById('filterContainer');
    filterContainer.innerHTML = '';
    
    currentFilters.forEach(filter => {
        if (filter.shown_source && filter.shown_source !== getSelectedSource()) return;
        
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
}

function renderFilterControl(filter) {
    if (filter.type === 'radio') {
        return filter.options.map(opt => `
            <div class="form-check">
                <input class="form-check-input" type="radio" name="${filter.name}" id="${opt.id}" value="${opt.id}" ${filter.default === opt.id ? 'checked' : ''}>
                <label class="form-check-label" for="${opt.id}">${opt.name}</label>
            </div>
        `).join('');
    } else if (filter.type === 'range') {
        return `
            <label for="${filter.id}" class="form-label">${filter.name}: <span id="${filter.id}Value">${filter.default}</span></label>
            <input type="range" class="form-range" id="${filter.id}" min="${filter.min}" max="${filter.max}" step="${filter.step}" value="${filter.default}">
        `;
    }
    return '';
}

function getSelectedSource() {
    return document.querySelector('input[name="source"]:checked')?.value || 'wikipedia';
}

function updateModeBadge() {
    const badge = document.getElementById('modeBadge');
    const atn = document.getElementById('atnInput').value.trim();
    if (atn) {
        badge.className = 'badge bg-primary';
        badge.textContent = 'ATN Mode';
    } else {
        badge.className = 'badge bg-secondary';
        badge.textContent = 'Search Mode';
    }
}

function performSearch() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) return;
    
    const source = getSelectedSource();
    const numResults = parseInt(document.getElementById('resultsSlider').value);
    const filters = {};
    if (source === 'gbooks') {
        filters.download = document.querySelector('input[name="download"]:checked')?.value;
        filters.available = document.querySelector('input[name="available"]:checked')?.value;
        filters.print = document.querySelector('input[name="print"]:checked')?.value;
    }
    
    const resultsContainer = document.getElementById('resultsContainer');
    resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Searching...</p></div>';
    
    fetch('/api/browse/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query, source, num_results: numResults, filters})
    }).then(r => r.json()).then(result => {
        if (result.status) {
            renderResults(result.results);
        } else {
            resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted"></i><h5>No results found</h5></div>';
        }
    }).catch(() => {
        showToast('Search failed', 'danger');
    });
}

function renderResults(results) {
    const resultsContainer = document.getElementById('resultsContainer');
    resultsContainer.innerHTML = '';
    
    if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="text-center"><i class="bi bi-search display-4 text-muted"></i><h5>No results found</h5></div>';
        return;
    }
    
    const row = document.createElement('div');
    row.className = 'row row-cols-2 row-cols-md-3 row-cols-xl-4 g-3';
    results.forEach(item => {
        const col = document.createElement('div');
        col.className = 'col';
        col.appendChild(createCard(item));
        row.appendChild(col);
    });
    resultsContainer.appendChild(row);
}