"use strict";

import { showToast } from '../toast.js';

let allWorkspaces = [];

export function initHome(root) {
    root.innerHTML = `
        <div class="container-fluid py-4 archive-page archive-page-home">
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
                        <h1 class="archive-page-title mb-1">Recent Workspaces</h1>
                        <p class="text-muted mb-0">Jump back into your most recent work or search for academic sources.</p>
                    </div>
                    <div class="input-group home-search-group" style="max-width: 560px; width: 100%;">
                        <span class="input-group-text"><i class="bi bi-search" aria-hidden="true"></i></span>
                        <input id="workspaceSearch" type="search" class="form-control" placeholder="Search academic sources..." autocomplete="off">
                        <button class="btn btn-primary" id="homeSearchBtn" type="button">Search</button>
                    </div>
                </div>
                <div id="workspaceCards" class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3"></div>
            </div>
        </div>
    `;

    const searchInput = root.querySelector('#workspaceSearch');
    const searchButton = root.querySelector('#homeSearchBtn');
    const submitSearch = (event) => {
        event?.preventDefault();
        const query = searchInput.value.trim();
        if (!query) return;
        window.location.href = `/browse?q=${encodeURIComponent(query)}`;
    };
    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') submitSearch(event);
    });
    searchButton.addEventListener('click', submitSearch);

    loadWorkspaces();
}

async function loadWorkspaces() {
    try {
        const response = await fetch('/api/workspaces');
        const data = await response.json();
        if (!data.status) {
            throw new Error('Unable to load workspaces');
        }
        allWorkspaces = data.workspaces || [];
        renderWorkspaceCards();
    } catch (error) {
        showToast('Unable to load recent workspaces', 'danger');
    }
}

function renderWorkspaceCards() {
    const container = document.getElementById('workspaceCards');
    container.innerHTML = '';

    const addCard = document.createElement('div');
    addCard.className = 'col';
    addCard.innerHTML = `
        <div class="card h-100 workspace-card workspace-card-add text-center text-muted" role="button" tabindex="0">
            <div class="card-body d-flex flex-column justify-content-center align-items-center py-5">
                <div class="display-6 mb-3">+</div>
                <h5>Create new workspace</h5>
                <p class="small text-muted mb-0">Start a fresh workspace for your next study session.</p>
            </div>
        </div>
    `;
    const addCardTarget = addCard.querySelector('.card');
    addCardTarget.addEventListener('click', () => startInlineWorkspaceCreate(addCardTarget));
    addCardTarget.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') {
            return;
        }
        if (event.key === ' ') {
            event.preventDefault();
        }
        startInlineWorkspaceCreate(addCardTarget);
    });
    container.appendChild(addCard);

    if (allWorkspaces.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'col-12';
        empty.innerHTML = `<div class="alert alert-secondary mb-0">Create a new workspace to get started.</div>`;
        container.appendChild(empty);
        return;
    }

    allWorkspaces.forEach((workspace) => {
        const card = document.createElement('div');
        card.className = 'col';
        card.innerHTML = `
            <div class="card h-100 surface-wood workspace-card position-relative">
                <div class="card-body d-flex flex-column">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <div class="badge bg-primary bg-opacity-10 text-primary archive-category-badge">Workspace</div>
                        <span class="icon-button" aria-hidden="true"><i class="bi bi-three-dots-vertical text-muted"></i></span>
                    </div>
                    <div class="mb-4">
                        <h5 class="card-title mb-1 text-truncate">${escapeHtml(workspace.name)}</h5>
                        <p class="text-muted small mb-0">${workspace.item_count} sources · ${workspace.note_count} notes</p>
                    </div>
                    <div class="mt-auto text-muted small">
                        Created on ${formatDate(workspace.time_created)}
                    </div>
                </div>
                <a class="stretched-link" href="/workspace/${workspace.id}" aria-label="Open ${escapeHtmlAttribute(workspace.name)} workspace"></a>
            </div>
        `;
        container.appendChild(card);
    });
}

function startInlineWorkspaceCreate(cardElement) {
    if (cardElement.dataset.editing === 'true') return;
    cardElement.dataset.editing = 'true';

    const cardBody = cardElement.querySelector('.card-body');
    const originalHTML = cardBody.innerHTML;
    cardBody.innerHTML = `
        <div class="d-flex flex-column justify-content-center align-items-center gap-3 w-100">
            <label for="inlineWorkspaceName" class="h5 mb-0">Create new workspace</label>
            <input type="text" id="inlineWorkspaceName" class="form-control text-center" placeholder="Enter workspace name..." autocomplete="off" maxlength="120">
            <div class="d-flex gap-2">
                <button class="btn btn-primary btn-sm" id="inlineCreateBtn" type="button">Create</button>
                <button class="btn btn-outline-secondary btn-sm" id="inlineCancelBtn" type="button">Cancel</button>
            </div>
        </div>
    `;

    const input = cardBody.querySelector('#inlineWorkspaceName');
    const createBtn = cardBody.querySelector('#inlineCreateBtn');
    const cancelBtn = cardBody.querySelector('#inlineCancelBtn');

    const submitCreate = async () => {
        const name = input.value.trim();
        if (!name) return;

        try {
            const response = await fetch('/api/workspaces', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            const data = await response.json();
            if (!data.status) {
                throw new Error('Create failed');
            }
            showToast('Workspace created', 'success');
            allWorkspaces.unshift({
                id: data.workspace.id,
                name: data.workspace.name,
                time_created: data.workspace.time_created,
                item_count: 0,
                note_count: 0
            });
            renderWorkspaceCards();
            openWorkspace(data.workspace.id);
        } catch (error) {
            showToast('Unable to create workspace', 'danger');
            cardBody.innerHTML = originalHTML;
            cardElement.dataset.editing = 'false';
        }
    };

    const cancelEdit = () => {
        cardBody.innerHTML = originalHTML;
        cardElement.dataset.editing = 'false';
    };

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            submitCreate();
        } else if (event.key === 'Escape') {
            event.preventDefault();
            cancelEdit();
        }
    });
    createBtn.addEventListener('click', submitCreate);
    cancelBtn.addEventListener('click', cancelEdit);

    requestAnimationFrame(() => input.focus());
}

function openWorkspace(workspaceId) {
    window.location.href = `/workspace/${workspaceId}`;
}

function formatDate(timestamp) {
    if (!timestamp) {
        return 'Unknown';
    }
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeHtmlAttribute(text) {
    return escapeHtml(text).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
