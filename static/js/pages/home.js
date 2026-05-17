"use strict";

import { createCard } from '../card.js';

export function initHome(root, data = {}) {
    const saved = data.saved || [];
    const recentlyViewed = data.recently_viewed || [];
    const recentlySearched = data.recently_searched || [];

    root.innerHTML = `
        <div class="row g-4">
            <div class="col-12 text-center">
                <h1 class="mb-3">Welcome to StudyLib</h1>
                <p class="text-muted">Your verified academic study resource aggregator.</p>
            </div>

            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-bookmark-fill me-2"></i>
                        <h5 class="mb-0">Saved Items</h5>
                        <a href="/saved" class="ms-auto btn btn-link btn-sm">View all →</a>
                    </div>
                    <div class="card-body">
                        <div class="d-flex gap-3 overflow-x-auto pb-2 scroll-row" id="savedContainer"></div>
                    </div>
                </div>
            </div>

            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-eye me-2"></i>
                        <h5 class="mb-0">Recently Viewed</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-flex gap-3 overflow-x-auto pb-2 scroll-row" id="viewedContainer"></div>
                    </div>
                </div>
            </div>

            <div class="col-12">
                <div class="card">
                    <div class="card-header d-flex align-items-center">
                        <i class="bi bi-search me-2"></i>
                        <h5 class="mb-0">Recently Searched</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-flex gap-3 overflow-x-auto pb-2 scroll-row" id="searchedContainer"></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    renderSection('savedContainer', saved, 'No saved items yet.');
    renderSection('viewedContainer', recentlyViewed, 'No recently viewed items yet.');
    renderSection('searchedContainer', recentlySearched, 'No recent searches yet.');
}

function renderSection(containerId, items, emptyMessage) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    if (!items.length) {
        container.innerHTML = `<div class="text-muted">${emptyMessage}</div>`;
        return;
    }
    items.forEach(item => {
        const wrapper = document.createElement('div');
        wrapper.className = 'flex-shrink-0';
        wrapper.style.minWidth = '220px';
        wrapper.appendChild(createCard(item));
        container.appendChild(wrapper);
    });
}
