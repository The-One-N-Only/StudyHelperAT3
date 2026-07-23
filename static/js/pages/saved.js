"use strict";

import { showToast } from '../toast.js';
import { createCard } from '../card.js';

let pageRoot = null;

export function initSaved(root) {
    pageRoot = root;
    root.innerHTML = `
        <div class="container-fluid py-4 archive-page archive-page-saved">
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
                <div class="d-flex flex-column flex-md-row align-items-start align-items-md-center justify-content-between gap-3 mb-4">
                    <div>
                        <h1 class="archive-page-title mb-1">Saved Sources</h1>
                        <p class="text-muted mb-0">View all the sources you have saved across your searches, grouped by search query.</p>
                    </div>
                </div>
                <div id="savedGroupsContainer"></div>
            </div>
        </div>
    `;

    window.onItemUnsaved = () => {
        loadSavedItems();
    };

    loadSavedItems();
}

async function loadSavedItems() {
    const container = pageRoot.querySelector('#savedGroupsContainer');
    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border" role="status" aria-hidden="true"></div>
            <p class="text-muted mt-2">Loading saved sources...</p>
        </div>
    `;

    try {
        const response = await fetch('/api/saved');
        const data = await response.json();
        if (!data.status) {
            throw new Error(data.error || 'Unable to load saved sources');
        }
        renderSavedGroups(data.groups);
    } catch (error) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-exclamation-triangle display-4" aria-hidden="true"></i>
                <h5>Unable to load saved sources</h5>
                <p>${escapeHtml(error.message || 'Please try again later.')}</p>
            </div>
        `;
    }
}

function renderSavedGroups(groups) {
    const container = pageRoot.querySelector('#savedGroupsContainer');
    container.innerHTML = '';

    if (!groups || groups.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5">
                <span class="browse-empty-engraving" aria-hidden="true"></span>
                <h5>No saved sources yet</h5>
                <p class="text-muted">Save sources from your Browse searches and they will appear here, grouped by your search query.</p>
            </div>
        `;
        return;
    }

    groups.forEach((group) => {
        const groupSection = document.createElement('div');
        groupSection.className = 'saved-group mb-4';

        const sectionHeader = document.createElement('div');
        sectionHeader.className = 'd-flex align-items-center justify-content-between mb-3';
        sectionHeader.innerHTML = `
            <div>
                <h4 class="saved-group-header mb-1">
                    <i class="bi bi-search me-2" aria-hidden="true"></i>${escapeHtml(group.query)}
                </h4>
                <span class="badge bg-primary bg-opacity-10 text-primary archive-count-badge">${group.items.length} source${group.items.length !== 1 ? 's' : ''}</span>
            </div>
        `;
        groupSection.appendChild(sectionHeader);

        const row = document.createElement('div');
        row.className = 'row row-cols-1 row-cols-sm-2 row-cols-md-4 row-cols-lg-4 g-2';

        group.items.forEach((item) => {
            const col = document.createElement('div');
            col.className = 'col';
            col.appendChild(createCard(item));
            row.appendChild(col);
        });

        groupSection.appendChild(row);
        container.appendChild(groupSection);
    });
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value;
    return div.innerHTML;
}
