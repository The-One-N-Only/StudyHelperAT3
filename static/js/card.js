"use strict";

import { showToast } from './toast.js';
import { hydrateWorkspaceSelect, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';

export function createCard(item) {
    const card = document.createElement('div');
    card.className = 'card card-fixed shadow-sm surface-leather result-card rounded-3 h-100';
    card.innerHTML = `
        <img src="${item.thumb_url || '/static/img/placeholder.png'}" class="card-img-top" style="height: 130px; object-fit: contain; background-color: var(--bs-body-secondary);" alt="">
        <div class="card-body">
            <h6 class="card-title text-truncate mb-1">${item.title}</h6>
            <p class="card-text small text-muted card-description mb-2">${item.description}</p>
            <div class="d-flex align-items-center justify-content-between">
                <small class="text-muted result-source"><i class="bi bi-globe2" aria-hidden="true"></i> ${item.source_name}</small>
                <button class="btn btn-link btn-sm p-0 icon-button save-btn" data-item-id="${item.id}" type="button" aria-label="${item.saved ? 'Remove saved result' : 'Save result'}" aria-pressed="${item.saved ? 'true' : 'false'}">
                    <i class="bi ${item.saved ? 'bi-bookmark-check' : 'bi-bookmark'}" aria-hidden="true"></i>
                </button>
            </div>
        </div>
        <div class="card-footer bg-transparent border-top p-2 result-card-actions">
            <button class="btn btn-outline-secondary btn-secondary-wood btn-sm w-50 view-btn" data-item-id="${item.id}" type="button">View</button>
            <button class="btn btn-primary btn-secondary-wood btn-sm w-50 add-btn" data-item-id="${item.id}" type="button">Add</button>
        </div>
        <div class="d-flex align-items-center gap-2 mt-2">
            <select class="form-select form-select-sm archive-dropdown workspace-select" aria-label="Choose workspace"></select>
        </div>
    `;
    
    const workspaceSelect = card.querySelector('.workspace-select');
    hydrateWorkspaceSelect(workspaceSelect);

    // Event listeners
    card.querySelector('.save-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSave(item.id);
    });
    card.querySelector('.view-btn').addEventListener('click', () => viewItem(item));
    card.querySelector('.add-btn').addEventListener('click', () => addToWorkspace(item, workspaceSelect));
    
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

function addToWorkspace(item, workspaceSelect) {
    if (!item.source_url) {
        showToast('Unable to add item: missing source URL', 'danger');
        return;
    }

    const workspace_id = getSelectedWorkspaceId(workspaceSelect);
    if (!workspace_id) {
        showToast('Please select a workspace before adding', 'warning');
        return;
    }

    fetch('/api/workspace/add', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            item_id: item.id,
            summary: '',
            bullets: [],
            relevance: '',
            citation_apa: 'APA citation',
            citation_harvard: 'Harvard citation',
            workspace_id: workspace_id
        })
    })
    .then(r => r.json())
    .then(addResult => {
        if (addResult.status) {
            showToast('Added to workspace', 'success');
        } else {
            showToast('Failed to add to workspace: ' + (addResult.error || 'Unknown error'), 'danger');
        }
    })
    .catch((error) => {
        console.error('Add to workspace error:', error);
        showToast('Error adding to workspace', 'danger');
    });
}
