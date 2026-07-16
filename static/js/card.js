"use strict";

import { showToast } from './toast.js';
import { hydrateWorkspaceSelect, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';

export function createCard(item) {
    const card = document.createElement('div');
    card.className = 'card card-fixed shadow-sm surface-leather result-card rounded-3 h-100';
    card.innerHTML = `
        <img class="card-img-top" style="height: 130px; object-fit: contain; background-color: var(--bs-body-secondary);" alt="">
        <div class="card-body">
            <h6 class="card-title text-truncate mb-1"></h6>
            <p class="card-text small text-muted card-description mb-2"></p>
            <div class="d-flex align-items-center justify-content-between">
                <small class="text-muted result-source"><i class="bi bi-globe2" aria-hidden="true"></i> <span class="result-source-text"></span></small>
                <button class="btn btn-link btn-sm p-0 icon-button save-btn" type="button" aria-label="" aria-pressed="false">
                    <i class="save-icon-light" aria-hidden="true"></i>
                    <i class="save-icon-dark d-none" aria-hidden="true"></i>
                </button>
            </div>
        </div>
        <div class="card-footer bg-transparent border-top p-2 result-card-actions">
            <button class="btn btn-outline-secondary btn-secondary-wood btn-sm w-50 view-btn" type="button">View</button>
            <button class="btn btn-primary btn-secondary-wood btn-sm w-50 add-btn" type="button">Add</button>
        </div>
        <div class="d-flex align-items-center gap-2 mt-2">
            <select class="form-select form-select-sm archive-dropdown workspace-select" aria-label="Choose workspace"></select>
        </div>
    `;

    const itemId = String(item.id ?? '');
    const image = card.querySelector('.card-img-top');
    const saveButton = card.querySelector('.save-btn');
    const viewButton = card.querySelector('.view-btn');
    const addButton = card.querySelector('.add-btn');
    image.src = safeImageUrl(item.thumb_url);
    image.alt = '';
    card.querySelector('.card-title').textContent = String(item.title ?? '');
    card.querySelector('.card-description').textContent = String(item.description ?? '');
    card.querySelector('.result-source-text').textContent = String(item.source_name ?? '');
    for (const button of [saveButton, viewButton, addButton]) {
        button.dataset.itemId = itemId;
    }
    updateSaveButton(saveButton, Boolean(item.saved));

    const workspaceSelect = card.querySelector('.workspace-select');
    hydrateWorkspaceSelect(workspaceSelect);

    // Event listeners
    saveButton.addEventListener('click', (e) => {
        e.stopPropagation();
        return toggleSave(item, saveButton);
    });
    viewButton.addEventListener('click', () => viewItem(item));
    addButton.addEventListener('click', () => addToWorkspace(item, workspaceSelect));

    return card;
}

function safeImageUrl(value) {
    const fallback = '/static/img/placeholder.png';
    if (!value) return fallback;

    try {
        const candidate = String(value);
        const parsed = new URL(candidate, document.baseURI);
        return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? candidate : fallback;
    } catch (_error) {
        return fallback;
    }
}

function updateSaveButton(button, saved) {
    button.setAttribute('aria-label', saved ? 'Remove saved result' : 'Save result');
    button.setAttribute('aria-pressed', saved ? 'true' : 'false');
    button.querySelector('.save-icon-light').className = saved
        ? 'bi bi-bookmark-fill text-danger save-icon-light'
        : 'bi bi-bookmark save-icon-light';
    button.querySelector('.save-icon-dark').className = saved
        ? 'bi bi-bookmark-check save-icon-dark d-none'
        : 'bi bi-bookmark save-icon-dark d-none';
}

async function toggleSave(item, button) {
    const wasSaved = Boolean(item.saved);
    const endpoint = wasSaved ? '/api/item/unsave' : '/api/item/save';

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_id: item.id})
        });
        const result = await response.json();
        if (result.status) {
            item.saved = !wasSaved;
            updateSaveButton(button, item.saved);
            showToast(item.saved ? 'Saved' : 'Removed from saved', 'success');
        } else {
            showToast(wasSaved ? 'Unable to remove saved result' : 'Already saved', 'info');
        }
    } catch (error) {
        console.error('Save toggle error:', error);
        showToast('Unable to update saved result', 'danger');
    }
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
