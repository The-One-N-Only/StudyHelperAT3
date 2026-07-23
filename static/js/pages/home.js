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

    setupWorkspaceMenuDelegation();
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
                        <div class="workspace-menu">
                            <button class="workspace-menu-btn" type="button" data-workspace-id="${workspace.id}" aria-label="Workspace actions" tabindex="0">
                                <i class="bi bi-three-dots-vertical"></i>
                            </button>
                            <div class="workspace-menu-dropdown d-none">
                                <button class="dropdown-item rename-workspace" data-workspace-id="${workspace.id}">
                                    <i class="bi bi-pencil me-2"></i>Rename
                                </button>
                                <div class="dropdown-divider"></div>
                                <button class="dropdown-item text-danger delete-workspace" data-workspace-id="${workspace.id}">
                                    <i class="bi bi-trash me-2"></i>Delete
                                </button>
                            </div>
                        </div>
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

/* ── Workspace context menu (three dots) ── */

function setupWorkspaceMenuDelegation() {
    const container = document.getElementById('workspaceCards');
    if (!container) return;

    container.addEventListener('click', function (e) {
        const menuBtn = e.target.closest('.workspace-menu-btn');
        if (menuBtn) {
            e.preventDefault();
            e.stopPropagation();
            const menu = menuBtn.parentElement.querySelector('.workspace-menu-dropdown');
            container.querySelectorAll('.workspace-menu-dropdown').forEach(m => {
                if (m !== menu) m.classList.add('d-none');
            });
            menu.classList.toggle('d-none');
            return;
        }

        const renameBtn = e.target.closest('.rename-workspace');
        if (renameBtn) {
            e.preventDefault();
            e.stopPropagation();
            renameBtn.closest('.workspace-menu-dropdown').classList.add('d-none');
            const id = parseInt(renameBtn.dataset.workspaceId);
            const card = renameBtn.closest('.workspace-card');
            if (card) startInlineRename(card, id);
            return;
        }

        const deleteBtn = e.target.closest('.delete-workspace');
        if (deleteBtn) {
            e.preventDefault();
            e.stopPropagation();
            deleteBtn.closest('.workspace-menu-dropdown').classList.add('d-none');
            const id = parseInt(deleteBtn.dataset.workspaceId);
            showDeleteConfirmation(id);
            return;
        }

        if (!e.target.closest('.workspace-menu')) {
            container.querySelectorAll('.workspace-menu-dropdown').forEach(m => {
                m.classList.add('d-none');
            });
        }
    });
}

document.addEventListener('click', function (e) {
    if (!e.target.closest('.workspace-menu')) {
        document.querySelectorAll('.workspace-menu-dropdown').forEach(m => {
            m.classList.add('d-none');
        });
    }
});

/* ── Inline rename (within the card) ── */

function startInlineRename(cardElement, workspaceId) {
    if (cardElement.dataset.renaming === 'true') return;
    cardElement.dataset.renaming = 'true';

    const ws = allWorkspaces.find(w => w.id === workspaceId);
    if (!ws) {
        delete cardElement.dataset.renaming;
        return;
    }

    const cardBody = cardElement.querySelector('.card-body');
    const originalHTML = cardBody.innerHTML;

    cardBody.innerHTML = `
        <div class="d-flex flex-column justify-content-center align-items-center gap-3 w-100 h-100 py-3">
            <label class="h5 mb-0">Rename workspace</label>
            <input type="text" class="form-control text-center" value="${escapeHtml(ws.name)}" autocomplete="off" maxlength="120">
            <div class="d-flex gap-2">
                <button class="btn btn-primary btn-sm" id="inlineRenameSave">Save</button>
                <button class="btn btn-outline-secondary btn-sm" id="inlineRenameCancel">Cancel</button>
            </div>
        </div>
    `;

    const stretchedLink = cardElement.querySelector('.stretched-link');
    if (stretchedLink) stretchedLink.style.display = 'none';

    const input = cardBody.querySelector('input');
    const saveBtn = cardBody.querySelector('#inlineRenameSave');
    const cancelBtn = cardBody.querySelector('#inlineRenameCancel');

    const submitRename = async () => {
        const name = input.value.trim();
        if (!name) return;
        if (name === ws.name) {
            cardBody.innerHTML = originalHTML;
            cardElement.dataset.renaming = 'false';
            if (stretchedLink) stretchedLink.style.display = '';
            return;
        }
        await renameWorkspace(workspaceId, name);
    };

    const cancelRename = () => {
        cardBody.innerHTML = originalHTML;
        cardElement.dataset.renaming = 'false';
        if (stretchedLink) stretchedLink.style.display = '';
    };

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            submitRename();
        } else if (event.key === 'Escape') {
            event.preventDefault();
            cancelRename();
        }
    });
    saveBtn.addEventListener('click', submitRename);
    cancelBtn.addEventListener('click', cancelRename);

    requestAnimationFrame(() => input.focus());
}

/* ── Rename API ── */

async function renameWorkspace(id, name) {
    try {
        const response = await fetch(`/api/workspaces/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        const data = await response.json();
        if (!data.status) throw new Error('Rename failed');
        showToast('Workspace renamed', 'success');
        const ws = allWorkspaces.find(w => w.id === id);
        if (ws) ws.name = name;
        renderWorkspaceCards();
    } catch (error) {
        showToast('Unable to rename workspace', 'danger');
    }
}

/* ── Delete confirmation modal ── */

function showDeleteConfirmation(workspaceId) {
    const ws = allWorkspaces.find(w => w.id === workspaceId);
    if (!ws) return;

    const existing = document.getElementById('deleteWorkspaceModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'deleteWorkspaceModal';
    modal.className = 'modal fade show d-block';
    modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Delete Workspace</h5>
                    <button type="button" class="btn-close" id="deleteModalClose" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p>Are you sure you want to delete <strong>${escapeHtml(ws.name)}</strong>?</p>
                    <p class="text-danger fw-semibold mb-0"><i class="bi bi-exclamation-triangle-fill me-1"></i>This action cannot be undone.</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="deleteModalCancel">Cancel</button>
                    <button type="button" class="btn btn-danger" id="deleteModalConfirm"><i class="bi bi-trash me-1"></i>Continue</button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    const close = () => modal.remove();

    modal.querySelector('#deleteModalClose').addEventListener('click', close);
    modal.querySelector('#deleteModalCancel').addEventListener('click', close);
    modal.querySelector('#deleteModalConfirm').addEventListener('click', async () => {
        await deleteWorkspace(workspaceId);
        close();
    });
    modal.addEventListener('click', (e) => {
        if (e.target === modal) close();
    });
}

async function deleteWorkspace(id) {
    try {
        const response = await fetch(`/api/workspaces/${id}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (!data.status) throw new Error('Delete failed');
        showToast('Workspace deleted', 'success');
        allWorkspaces = allWorkspaces.filter(w => w.id !== id);
        renderWorkspaceCards();
    } catch (error) {
        showToast('Unable to delete workspace', 'danger');
    }
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
