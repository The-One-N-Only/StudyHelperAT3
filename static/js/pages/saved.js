"use strict";

import { showToast } from '../main.js';

let pageRoot = null;
let savedItems = [];

export function initSaved(root, data = {}) {
    pageRoot = root;
    savedItems = data.saved_items || [];

    pageRoot.innerHTML = `
        <div class="container py-4" style="max-width: 900px;">
            <div class="row">
                <div class="col-12">
                    <h4 class="mb-4">
                        <i class="bi bi-bookmark-fill me-2"></i>
                        Saved Items
                        <span class="badge bg-primary ms-2" id="countBadge">${savedItems.length}</span>
                    </h4>
                    <div class="row row-cols-2 row-cols-md-3 row-cols-lg-4 g-3" id="savedContainer"></div>
                </div>
            </div>
        </div>
    `;

    renderSavedItems(savedItems);
}

function renderSavedItems(items) {
    const container = pageRoot.querySelector('#savedContainer');
    container.innerHTML = '';

    if (!items.length) {
        container.innerHTML = '<div class="text-center text-muted">No saved items yet.</div>';
        return;
    }

    items.forEach((item) => {
        const card = createSavedCard(item);
        const col = document.createElement('div');
        col.className = 'col';
        col.appendChild(card);
        container.appendChild(col);
    });
}

function createSavedCard(item) {
    const card = document.createElement('div');
    card.className = 'card card-fixed shadow-sm rounded-3 h-100';
    card.innerHTML = `
        <img src="${item.thumb_url || '/static/img/placeholder.png'}" class="card-img-top" style="height: 130px; object-fit: contain; background-color: var(--bs-body-secondary);" alt="">
        <div class="card-body">
            <h6 class="card-title text-truncate mb-1">${item.title}</h6>
            <p class="card-text small text-muted card-description mb-2">${item.description}</p>
            <div class="d-flex align-items-center justify-content-between">
                <small class="text-muted"><i class="bi bi-globe2"></i> ${item.source_name}</small>
                <button class="btn btn-link btn-sm p-0 unsave-btn" data-item-id="${item.id}">
                    <i class="bi bi-bookmark-x-fill text-danger"></i>
                </button>
            </div>
        </div>
        <div class="card-footer bg-transparent border-top p-2">
            <button class="btn btn-outline-secondary btn-sm w-50 view-btn" data-item-id="${item.id}">View</button>
            <button class="btn btn-primary btn-sm w-50 add-btn" data-item-id="${item.id}">Add</button>
        </div>
    `;

    card.querySelector('.unsave-btn').addEventListener('click', () => toggleSave(item.id, card));
    card.querySelector('.view-btn').addEventListener('click', () => viewItem(item));
    card.querySelector('.add-btn').addEventListener('click', () => addToWorkspace(item));
    return card;
}

function toggleSave(itemId, card) {
    fetch('/api/item/unsave', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId })
    })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                showToast('Unsaved', 'success');
                card.closest('.col').remove();
                savedItems = savedItems.filter((item) => item.id !== itemId);
                pageRoot.querySelector('#countBadge').textContent = savedItems.length;
                if (!savedItems.length) {
                    renderSavedItems([]);
                }
            }
        });
}

function viewItem(item) {
    if (window.openViewer) window.openViewer(item);
}

function addToWorkspace(item) {
    fetch('/api/summarise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: item.source_url, title: item.title })
    })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                fetch('/api/workspace/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        item_id: item.id,
                        summary: result.summary,
                        bullets: result.bullets,
                        relevance: result.relevance,
                        citation_apa: 'APA citation',
                        citation_harvard: 'Harvard citation'
                    })
                }).then((r) => r.json()).then((addResult) => {
                    if (addResult.status) {
                        showToast('Added to workspace', 'success');
                    }
                });
            } else {
                showToast('Summarisation failed', 'danger');
            }
        });
}
