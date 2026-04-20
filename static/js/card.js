"use strict";

import { showToast } from './main.js';

export function createCard(item) {
    const card = document.createElement('div');
    card.className = 'card card-fixed shadow-sm rounded-3 h-100';
    card.innerHTML = `
        <img src="${item.thumb_url || '/static/img/placeholder.png'}" class="card-img-top" style="height: 130px; object-fit: contain; background-color: var(--bs-body-secondary);" alt="">
        <div class="card-body">
            <h6 class="card-title text-truncate mb-1">${item.title}</h6>
            <p class="card-text small text-muted card-description mb-2">${item.description}</p>
            <div class="d-flex align-items-center justify-content-between">
                <small class="text-muted"><i class="bi bi-globe2"></i> ${item.source_name}</small>
                <button class="btn btn-link btn-sm p-0 save-btn" data-item-id="${item.id}">
                    <i class="bi bi-bookmark${item.saved ? '-fill text-danger' : ''}"></i>
                </button>
            </div>
        </div>
        <div class="card-footer bg-transparent border-top p-2">
            <button class="btn btn-outline-secondary btn-sm w-50 view-btn" data-item-id="${item.id}">View</button>
            <button class="btn btn-primary btn-sm w-50 add-btn" data-item-id="${item.id}">Add</button>
        </div>
    `;
    
    // Event listeners
    card.querySelector('.save-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSave(item.id);
    });
    card.querySelector('.view-btn').addEventListener('click', () => viewItem(item));
    card.querySelector('.add-btn').addEventListener('click', () => addToWorkspace(item));
    
    return card;
}

function toggleSave(itemId) {
    fetch('/api/item/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({item_id: itemId})
    }).then(r => r.json()).then(result => {
        if (result.status) {
            showToast('Saved', 'success');
            // Update icon
        } else {
            showToast('Already saved', 'info');
        }
    });
}

function viewItem(item) {
    // Open viewer
    if (window.openViewer) window.openViewer(item);
}

function addToWorkspace(item) {
    // Summarise and add
    fetch('/api/summarise', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: item.source_url, title: item.title})
    }).then(r => r.json()).then(result => {
        if (result.status) {
            // Add to workspace
            fetch('/api/workspace/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    item_id: item.id,
                    summary: result.summary,
                    bullets: result.bullets,
                    relevance: result.relevance,
                    citation_apa: 'APA citation', // Generate
                    citation_harvard: 'Harvard citation'
                })
            }).then(r => r.json()).then(addResult => {
                if (addResult.status) {
                    showToast('Added to workspace', 'success');
                }
            });
        } else {
            showToast('Summarisation failed', 'danger');
        }
    });
}