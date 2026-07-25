"use strict";

import { showToast } from '../toast.js';
import { showEmptyState } from '../components/empty-state.js';
import { showUndoToast } from '../undo-toast.js';

let allWorkspaces = [];
let allFolders = [];
let activeTab = 'active';
let expandedFolders = JSON.parse(localStorage.getItem('expandedFolders') || '[]');
let debounceTimer = null;

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
                        <h1 class="archive-page-title mb-1">Workspaces</h1>
                        <p class="text-muted mb-0">Manage your study workspaces, folders, and archived projects.</p>
                    </div>
                    <div class="input-group home-search-group" style="max-width: 420px; width: 100%;">
                        <span class="input-group-text"><i class="bi bi-search" aria-hidden="true"></i></span>
                        <input id="workspaceSearch" type="search" class="form-control" placeholder="Search workspaces..." autocomplete="off">
                    </div>
                </div>

                <div class="d-flex align-items-center gap-2 mb-3 flex-wrap">
                    <ul class="nav nav-pills me-auto" id="workspaceTabs">
                        <li class="nav-item"><button class="nav-link active" data-tab="active">Active</button></li>
                        <li class="nav-item"><button class="nav-link" data-tab="archived">Archived</button></li>
                        <li class="nav-item"><button class="nav-link" data-tab="trash">Trash</button></li>
                    </ul>
                    <button class="btn btn-outline-secondary btn-sm" id="newFolderBtn"><i class="bi bi-folder-plus me-1"></i>New Folder</button>
                    <button class="btn btn-primary btn-sm" id="newWorkspaceBtn"><i class="bi bi-plus-lg me-1"></i>New Workspace</button>
                </div>

                <div id="workspaceCards" class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3"></div>
            </div>
        </div>
    `;

    const searchInput = root.querySelector('#workspaceSearch');
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const q = searchInput.value.trim().toLowerCase();
            if (q.length >= 2) {
                performCrossWorkspaceSearch(q);
            } else {
                loadWorkspaces();
            }
        }, 300);
    });

    // Tab switching
    root.querySelectorAll('#workspaceTabs .nav-link').forEach(btn => {
        btn.addEventListener('click', () => {
            root.querySelectorAll('#workspaceTabs .nav-link').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeTab = btn.dataset.tab;
            loadWorkspaces();
        });
    });

    root.querySelector('#newFolderBtn').addEventListener('click', showCreateFolderDialog);
    root.querySelector('#newWorkspaceBtn').addEventListener('click', () => startInlineWorkspaceCreate(document.querySelector('.workspace-card-add')?.closest('.col')));

    loadWorkspaces();
    setupWorkspaceMenuDelegation();
}

async function loadWorkspaces() {
    const container = document.getElementById('workspaceCards');
    if (container) {
        container.innerHTML = '';
        for (let i = 0; i < 3; i++) {
            const col = document.createElement('div');
            col.className = 'col';
            col.innerHTML = `<div class="card h-100 surface-wood" aria-hidden="true"><div class="card-body"><div class="skeleton-line" style="height:14px;width:60%;background:var(--bs-tertiary-bg);border-radius:4px;margin-bottom:12px;"></div><div class="skeleton-line" style="height:12px;width:40%;background:var(--bs-tertiary-bg);border-radius:4px;margin-bottom:8px;"></div><div class="skeleton-line" style="height:12px;width:30%;background:var(--bs-tertiary-bg);border-radius:4px;"></div></div></div>`;
            container.appendChild(col);
        }
    }

    try {
        if (activeTab === 'active') {
            const [wsResp, treeResp] = await Promise.all([
                fetch('/api/workspaces'),
                fetch('/workspace/tree')
            ]);
            const wsData = await wsResp.json();
            const treeData = await treeResp.json();
            if (!wsData.status) throw new Error('Unable to load');
            allWorkspaces = wsData.workspaces || [];
            allFolders = treeData.status ? (treeData.tree?.folders || []) : [];
            renderActiveWorkspaces();
        } else if (activeTab === 'archived') {
            const resp = await fetch('/workspace/archived');
            const data = await resp.json();
            allWorkspaces = data.status ? (data.workspaces || []) : [];
            renderArchivedWorkspaces();
        } else if (activeTab === 'trash') {
            const resp = await fetch('/workspace/trash');
            const data = await resp.json();
            allWorkspaces = data.status ? (data.workspaces || []) : [];
            renderTrashWorkspaces();
        }
    } catch (error) {
        showToast('Unable to load workspaces', 'danger');
    }
}

// ── Render Functions ──

function renderActiveWorkspaces() {
    const container = document.getElementById('workspaceCards');
    container.innerHTML = '';

    const addCard = document.createElement('div');
    addCard.className = 'col';
    addCard.innerHTML = `<div class="card h-100 workspace-card workspace-card-add text-center text-muted" role="button" tabindex="0"><div class="card-body d-flex flex-column justify-content-center align-items-center py-5"><div class="display-6 mb-3">+</div><h5>Create new workspace</h5><p class="small text-muted mb-0">Start a fresh workspace for your next study session.</p></div></div>`;
    addCard.querySelector('.card').addEventListener('click', () => showTemplateDialog());
    addCard.querySelector('.card').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showTemplateDialog(); } });
    container.appendChild(addCard);

    const rootWorkspaces = allWorkspaces.filter(w => !w.folder_id && !w.archived);

    if (rootWorkspaces.length === 0 && allFolders.length === 0) {
        const col = document.createElement('div');
        col.className = 'col-12';
        const emptyContainer = document.createElement('div');
        col.appendChild(emptyContainer);
        container.appendChild(col);
        showEmptyState(emptyContainer, {
            icon: 'workspace',
            title: 'Create your first workspace',
            description: 'Create a new workspace to get started.'
        });
        return;
    }

    // Render folders
    allFolders.forEach(folder => {
        const isExpanded = expandedFolders.includes(folder.id);
        const folderWorkspaces = allWorkspaces.filter(w => w.folder_id === folder.id && !w.archived);
        const folderDiv = document.createElement('div');
        folderDiv.className = 'col-12';
        folderDiv.innerHTML = `
            <div class="card surface-wood mb-3 folder-card">
                <div class="card-header d-flex align-items-center justify-content-between py-2 folder-header" data-folder-id="${folder.id}" role="button">
                    <div class="d-flex align-items-center gap-2">
                        <i class="bi bi-folder${isExpanded ? '-open' : ''} text-warning folder-icon"></i>
                        <span class="fw-semibold folder-name-text">${escapeHtml(folder.name)}</span>
                        <span class="badge bg-secondary bg-opacity-10 text-secondary">${folderWorkspaces.length}</span>
                    </div>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-link text-muted folder-menu-btn" type="button" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><button class="dropdown-item rename-folder-btn" data-folder-id="${folder.id}"><i class="bi bi-pencil me-2"></i>Rename</button></li>
                            <li><button class="dropdown-item text-danger delete-folder-btn" data-folder-id="${folder.id}"><i class="bi bi-trash me-2"></i>Delete</button></li>
                        </ul>
                    </div>
                </div>
                <div class="card-body${isExpanded ? '' : ' d-none'}" data-folder-body="${folder.id}">
                    <div class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3">
                        ${folderWorkspaces.map(ws => workspaceCardHtml(ws)).join('')}
                        <div class="col">
                            <div class="card h-100 workspace-card workspace-card-add text-center text-muted border-dashed" role="button" tabindex="0" data-folder-id="${folder.id}">
                                <div class="card-body d-flex flex-column justify-content-center align-items-center py-3"><i class="bi bi-plus-circle fs-4 mb-1"></i><small>Add to folder</small></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Folder header toggle
        folderDiv.querySelector('.folder-header').addEventListener('click', (e) => {
            if (e.target.closest('.dropdown') || e.target.closest('.folder-menu-btn')) return;
            const body = folderDiv.querySelector(`[data-folder-body="${folder.id}"]`);
            const icon = folderDiv.querySelector('.folder-icon');
            body.classList.toggle('d-none');
            const nowExpanded = !body.classList.contains('d-none');
            icon.className = `bi bi-folder${nowExpanded ? '-open' : ''} text-warning folder-icon`;
            if (nowExpanded) {
                if (!expandedFolders.includes(folder.id)) expandedFolders.push(folder.id);
            } else {
                expandedFolders = expandedFolders.filter(id => id !== folder.id);
            }
            localStorage.setItem('expandedFolders', JSON.stringify(expandedFolders));
        });

        // Rename folder
        folderDiv.querySelector('.rename-folder-btn').addEventListener('click', () => {
            const newName = prompt('Rename folder:', folder.name);
            if (newName && newName.trim()) {
                fetch('/workspace/rename-folder', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({folder_id: folder.id, name: newName.trim()})
                }).then(r => r.json()).then(d => {
                    if (d.status) { showToast('Folder renamed', 'success'); loadWorkspaces(); }
                    else showToast(d.error || 'Failed', 'danger');
                });
            }
        });

        // Delete folder
        folderDiv.querySelector('.delete-folder-btn').addEventListener('click', () => {
            if (confirm(`Delete folder "${folder.name}"? Contents will be moved to parent.`)) {
                fetch('/workspace/delete-folder', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({folder_id: folder.id})
                }).then(r => r.json()).then(d => {
                    if (d.status) { showToast('Folder deleted', 'success'); loadWorkspaces(); }
                    else showToast(d.error || 'Failed', 'danger');
                });
            }
        });

        // Add to folder card
        folderDiv.querySelector('.workspace-card-add').addEventListener('click', () => showTemplateDialog(folder.id));

        // Drag/drop on folder body
        const folderBody = folderDiv.querySelector('[data-folder-body]');
        if (folderBody) {
            folderBody.addEventListener('dragover', (e) => { e.preventDefault(); folderBody.classList.add('drag-over'); });
            folderBody.addEventListener('dragleave', () => folderBody.classList.remove('drag-over'));
            folderBody.addEventListener('drop', (e) => {
                e.preventDefault();
                folderBody.classList.remove('drag-over');
                const wsId = e.dataTransfer.getData('text/workspace-id');
                if (wsId) moveWorkspaceToFolder(parseInt(wsId), folder.id);
            });
        }

        container.appendChild(folderDiv);
    });

    // Render root workspaces (not in any folder)
    if (rootWorkspaces.length > 0) {
        const rootSection = document.createElement('div');
        rootSection.className = 'col-12';
        rootSection.innerHTML = rootWorkspaces.map(ws => workspaceCardHtml(ws)).join('');
        container.appendChild(rootSection);
    }
}

function workspaceCardHtml(workspace) {
    return `
        <div class="col" draggable="true" data-workspace-id="${workspace.id}">
            <div class="card h-100 surface-wood workspace-card position-relative">
                <div class="card-body d-flex flex-column">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <div class="badge bg-primary bg-opacity-10 text-primary archive-category-badge">Workspace</div>
                        <div class="workspace-menu">
                            <button class="workspace-menu-btn" type="button" data-workspace-id="${workspace.id}" aria-label="Workspace actions" tabindex="0"><i class="bi bi-three-dots-vertical"></i></button>
                            <div class="workspace-menu-dropdown d-none">
                                <button class="dropdown-item rename-workspace" data-workspace-id="${workspace.id}"><i class="bi bi-pencil me-2"></i>Rename</button>
                                <button class="dropdown-item archive-workspace" data-workspace-id="${workspace.id}"><i class="bi bi-archive me-2"></i>Archive</button>
                                <div class="dropdown-divider"></div>
                                <button class="dropdown-item text-danger delete-workspace" data-workspace-id="${workspace.id}"><i class="bi bi-trash me-2"></i>Delete</button>
                            </div>
                        </div>
                    </div>
                    <div class="mb-4">
                        <h5 class="card-title mb-1 text-truncate">${escapeHtml(workspace.name)}</h5>
                        <p class="text-muted small mb-0">${workspace.item_count} sources · ${workspace.note_count} notes</p>
                    </div>
                    <div class="mt-auto text-muted small">Created on ${formatDate(workspace.time_created)}</div>
                </div>
                <a class="stretched-link" href="/workspace/${workspace.id}" aria-label="Open ${escapeHtmlAttribute(workspace.name)} workspace"></a>
            </div>
        </div>`;
}

function renderArchivedWorkspaces() {
    const container = document.getElementById('workspaceCards');
    container.innerHTML = '';
    if (allWorkspaces.length === 0) {
        container.innerHTML = '<div class="col-12"><div class="alert alert-secondary mb-0">No archived workspaces.</div></div>';
        return;
    }
    allWorkspaces.forEach(ws => {
        const col = document.createElement('div');
        col.className = 'col';
        col.innerHTML = `
            <div class="card h-100 surface-wood workspace-card opacity-75 position-relative">
                <div class="card-body d-flex flex-column">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <div class="badge bg-secondary bg-opacity-10 text-secondary">Archived</div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-primary unarchive-ws-btn" data-ws-id="${ws.id}"><i class="bi bi-arrow-return-left"></i> Restore</button>
                        </div>
                    </div>
                    <h5 class="card-title mb-1 text-truncate">${escapeHtml(ws.name)}</h5>
                    <p class="text-muted small mb-0">${ws.item_count} sources</p>
                </div>
            </div>`;
        col.querySelector('.unarchive-ws-btn').addEventListener('click', async () => {
            const r = await fetch(`/workspace/${ws.id}/unarchive`, {method: 'POST'});
            const d = await r.json();
            if (d.status) { showToast('Workspace restored', 'success'); loadWorkspaces(); }
        });
        container.appendChild(col);
    });
}

function renderTrashWorkspaces() {
    const container = document.getElementById('workspaceCards');
    container.innerHTML = '';
    if (allWorkspaces.length === 0) {
        container.innerHTML = '<div class="col-12"><div class="alert alert-secondary mb-0">Trash is empty.</div></div>';
        return;
    }
    allWorkspaces.forEach(ws => {
        const col = document.createElement('div');
        col.className = 'col';
        col.innerHTML = `
            <div class="card h-100 surface-wood workspace-card border-danger border-opacity-25 position-relative">
                <div class="card-body d-flex flex-column">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <div class="badge bg-danger bg-opacity-10 text-danger">Deleted</div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-success restore-ws-btn" data-ws-id="${ws.id}"><i class="bi bi-arrow-counterclockwise"></i> Restore</button>
                            <button class="btn btn-sm btn-outline-danger perm-delete-ws-btn" data-ws-id="${ws.id}"><i class="bi bi-x-lg"></i> Delete Forever</button>
                        </div>
                    </div>
                    <h5 class="card-title mb-1 text-truncate">${escapeHtml(ws.name)}</h5>
                    <p class="text-muted small mb-0">Deleted ${formatDate(ws.deleted_at)}</p>
                </div>
            </div>`;
        col.querySelector('.restore-ws-btn').addEventListener('click', async () => {
            const r = await fetch(`/workspace/${ws.id}/restore`, {method: 'POST'});
            const d = await r.json();
            if (d.status) { showToast('Workspace restored', 'success'); loadWorkspaces(); }
        });
        col.querySelector('.perm-delete-ws-btn').addEventListener('click', async () => {
            if (!confirm(`Permanently delete "${ws.name}"? This cannot be undone.`)) return;
            const r = await fetch(`/api/workspaces/${ws.id}`, {method: 'DELETE'});
            const d = await r.json();
            if (d.status) { showToast('Workspace permanently deleted', 'success'); loadWorkspaces(); }
        });
        container.appendChild(col);
    });
}

// ── Template Dialog ──

function showTemplateDialog(folderId = null) {
    const existing = document.getElementById('templateDialog');
    if (existing) existing.remove();

    const dialog = document.createElement('div');
    dialog.id = 'templateDialog';
    dialog.className = 'modal fade show d-block';
    dialog.style.backgroundColor = 'rgba(0,0,0,0.5)';
    dialog.innerHTML = `
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Choose a template</h5>
                    <button type="button" class="btn-close" id="templateDialogClose"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Subject (optional)</label>
                        <select class="form-select" id="subjectSelect">
                            <option value="">No subject</option>
                        </select>
                    </div>
                    <p class="text-muted">Select a template to pre-populate your workspace with organized sections.</p>
                    <div class="row g-3" id="templateCards"></div>
                    <hr>
                    <div class="text-center">
                        <button class="btn btn-outline-secondary" id="blankWorkspaceBtn">Start with blank workspace</button>
                    </div>
                </div>
            </div>
        </div>`;
    document.body.appendChild(dialog);

    dialog.querySelector('#templateDialogClose').addEventListener('click', () => dialog.remove());
    dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.remove(); });

    // Load subjects
    const subjectSelect = dialog.querySelector('#subjectSelect');
    fetch('/api/nesa/courses').then(r => r.json()).then(data => {
        if (data.status) {
            data.courses.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = `${c.course_name} (${c.kla})`;
                subjectSelect.appendChild(opt);
            });
        }
    });

    const cardsContainer = dialog.querySelector('#templateCards');

    fetch('/workspace/templates')
        .then(r => r.json())
        .then(data => {
            if (!data.status || !data.templates) return;
            data.templates.forEach(tmpl => {
                const card = document.createElement('div');
                card.className = 'col-md-4';
                card.innerHTML = `
                    <div class="card h-100 template-card text-center p-3" role="button" data-template-id="${tmpl.id}">
                        <div class="card-body">
                            <div class="fs-1 mb-2"><i class="${tmpl.icon}"></i></div>
                            <h6>${escapeHtml(tmpl.name)}</h6>
                            <p class="small text-muted mb-0">${escapeHtml(tmpl.description)}</p>
                        </div>
                    </div>`;
                card.querySelector('.template-card').addEventListener('click', () => {
                    const courseId = subjectSelect.value ? parseInt(subjectSelect.value) : null;
                    dialog.remove();
                    createWorkspaceWithTemplate(tmpl, folderId, courseId);
                });
                cardsContainer.appendChild(card);
            });
        });

    dialog.querySelector('#blankWorkspaceBtn').addEventListener('click', () => {
        const courseId = subjectSelect.value ? parseInt(subjectSelect.value) : null;
        dialog.remove();
        createBlankWorkspace(folderId, courseId);
    });
}

async function createWorkspaceWithTemplate(template, folderId, courseId = null) {
    const name = prompt('Workspace name:', template.name);
    if (!name) return;
    try {
        const resp = await fetch('/api/workspaces', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, parent_id: folderId, course_id: courseId})
        });
        const data = await resp.json();
        if (!data.status) throw new Error('Failed');
        const ws = data.workspace;
        await fetch(`/workspace/${ws.id}/apply-template`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({template_id: template.id})
        });
        showToast('Workspace created with template', 'success');
        window.location.href = `/workspace/${ws.id}`;
    } catch (e) {
        showToast('Failed to create workspace', 'danger');
    }
}

function createBlankWorkspace(folderId, courseId = null) {
    startInlineWorkspaceCreate(document.querySelector('.workspace-card-add')?.closest('.col'), folderId, courseId);
}

function startInlineWorkspaceCreate(cardElement, folderId = null, courseId = null) {
    if (!cardElement) { showTemplateDialog(folderId); return; }
    if (cardElement.dataset.editing === 'true') return;
    cardElement.dataset.editing = 'true';
    const cardBody = cardElement.querySelector('.card-body');
    const originalHTML = cardBody.innerHTML;
    cardBody.innerHTML = `
        <div class="d-flex flex-column justify-content-center align-items-center gap-3 w-100">
            <label for="inlineWorkspaceName" class="h5 mb-0">Create new workspace</label>
            <input type="text" id="inlineWorkspaceName" class="form-control text-center" placeholder="Enter workspace name..." autocomplete="off" maxlength="25">
            <div class="d-flex gap-2">
                <button class="btn btn-primary btn-sm" id="inlineCreateBtn" type="button">Create</button>
                <button class="btn btn-outline-secondary btn-sm" id="inlineCancelBtn" type="button">Cancel</button>
            </div>
        </div>`;
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
                body: JSON.stringify({ name, parent_id: folderId, course_id: courseId })
            });
            const data = await response.json();
            if (!data.status) throw new Error('Create failed');
            showToast('Workspace created', 'success');
            window.location.href = `/workspace/${data.workspace.id}`;
        } catch (error) {
            showToast('Unable to create workspace', 'danger');
            cardBody.innerHTML = originalHTML;
            cardElement.dataset.editing = 'false';
        }
    };
    const cancelEdit = () => { cardBody.innerHTML = originalHTML; cardElement.dataset.editing = 'false'; };
    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') { event.preventDefault(); submitCreate(); }
        else if (event.key === 'Escape') { event.preventDefault(); cancelEdit(); }
    });
    createBtn.addEventListener('click', submitCreate);
    cancelBtn.addEventListener('click', cancelEdit);
    requestAnimationFrame(() => input.focus());
}

// ── Context Menu ──

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
            e.preventDefault(); e.stopPropagation();
            renameBtn.closest('.workspace-menu-dropdown').classList.add('d-none');
            const id = parseInt(renameBtn.dataset.workspaceId);
            const card = renameBtn.closest('.workspace-card');
            if (card) startInlineRename(card, id);
            return;
        }

        const archiveBtn = e.target.closest('.archive-workspace');
        if (archiveBtn) {
            e.preventDefault(); e.stopPropagation();
            archiveBtn.closest('.workspace-menu-dropdown').classList.add('d-none');
            const id = parseInt(archiveBtn.dataset.workspaceId);
            archiveWS(id);
            return;
        }

        const deleteBtn = e.target.closest('.delete-workspace');
        if (deleteBtn) {
            e.preventDefault(); e.stopPropagation();
            deleteBtn.closest('.workspace-menu-dropdown').classList.add('d-none');
            const id = parseInt(deleteBtn.dataset.workspaceId);
            showDeleteConfirmation(id);
            return;
        }

        if (!e.target.closest('.workspace-menu')) {
            container.querySelectorAll('.workspace-menu-dropdown').forEach(m => m.classList.add('d-none'));
        }
    });

    // Drag start
    container.addEventListener('dragstart', (e) => {
        const card = e.target.closest('[draggable="true"]');
        if (card) {
            e.dataTransfer.setData('text/workspace-id', card.dataset.workspaceId);
            e.dataTransfer.effectAllowed = 'move';
        }
    });
}

document.addEventListener('click', function (e) {
    if (!e.target.closest('.workspace-menu')) {
        document.querySelectorAll('.workspace-menu-dropdown').forEach(m => m.classList.add('d-none'));
    }
});

// ── Archive ──

async function archiveWS(workspaceId) {
    try {
        const r = await fetch(`/workspace/${workspaceId}/archive`, {method: 'POST'});
        const d = await r.json();
        if (d.status) {
            showUndoToast('Workspace archived', async () => {
                await fetch(`/workspace/${workspaceId}/unarchive`, {method: 'POST'});
                showToast('Workspace restored', 'success');
                loadWorkspaces();
            });
            loadWorkspaces();
        }
    } catch (e) {
        showToast('Failed to archive', 'danger');
    }
}

// ── Move to folder ──

function moveWorkspaceToFolder(workspaceId, folderId) {
    fetch('/workspace/move-to-folder', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({workspace_id: workspaceId, folder_id: folderId})
    }).then(r => r.json()).then(d => {
        if (d.status) {
            showUndoToast('Workspace moved to folder', () => {
                fetch('/workspace/move-to-folder', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({workspace_id: workspaceId, folder_id: null})
                });
            });
            loadWorkspaces();
        }
    });
}

// ── Inline rename ──

function startInlineRename(cardElement, workspaceId) {
    if (cardElement.dataset.renaming === 'true') return;
    cardElement.dataset.renaming = 'true';
    const ws = allWorkspaces.find(w => w.id === workspaceId);
    if (!ws) { delete cardElement.dataset.renaming; return; }
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
        </div>`;
    const stretchedLink = cardElement.querySelector('.stretched-link');
    if (stretchedLink) stretchedLink.style.display = 'none';
    const input = cardBody.querySelector('input');
    const saveBtn = cardBody.querySelector('#inlineRenameSave');
    const cancelBtn = cardBody.querySelector('#inlineRenameCancel');
    const submitRename = async () => {
        const name = input.value.trim();
        if (!name) return;
        if (name === ws.name) { cardBody.innerHTML = originalHTML; cardElement.dataset.renaming = 'false'; if (stretchedLink) stretchedLink.style.display = ''; return; }
        await renameWorkspace(workspaceId, name);
    };
    const cancelRename = () => { cardBody.innerHTML = originalHTML; cardElement.dataset.renaming = 'false'; if (stretchedLink) stretchedLink.style.display = ''; };
    input.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); submitRename(); } else if (event.key === 'Escape') { event.preventDefault(); cancelRename(); } });
    saveBtn.addEventListener('click', submitRename);
    cancelBtn.addEventListener('click', cancelRename);
    requestAnimationFrame(() => input.focus());
}

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
        loadWorkspaces();
    } catch (error) {
        showToast('Unable to rename workspace', 'danger');
    }
}

// ── Delete ──

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
                    <p class="text-muted mb-0 small">It will be moved to trash and can be restored later.</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="deleteModalCancel">Cancel</button>
                    <button type="button" class="btn btn-danger" id="deleteModalConfirm"><i class="bi bi-trash me-1"></i>Move to Trash</button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(modal);
    const close = () => modal.remove();
    modal.querySelector('#deleteModalClose').addEventListener('click', close);
    modal.querySelector('#deleteModalCancel').addEventListener('click', close);
    modal.querySelector('#deleteModalConfirm').addEventListener('click', async () => {
        await deleteWorkspace(workspaceId);
        showUndoToast('Workspace moved to trash', async () => {
            await fetch(`/workspace/${workspaceId}/restore`, {method: 'POST'});
            showToast('Workspace restored', 'success');
            loadWorkspaces();
        });
        close();
    });
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
}

async function deleteWorkspace(id) {
    try {
        const response = await fetch(`/api/workspaces/${id}`, { method: 'DELETE' });
        const data = await response.json();
        if (!data.status) throw new Error('Delete failed');
        allWorkspaces = allWorkspaces.filter(w => w.id !== id);
        loadWorkspaces();
    } catch (error) {
        showToast('Unable to delete workspace', 'danger');
    }
}

function showCreateFolderDialog() {
    const name = prompt('Folder name:');
    if (name && name.trim()) {
        fetch('/workspace/create-folder', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name.trim()})
        }).then(r => r.json()).then(d => {
            if (d.status) { showToast('Folder created', 'success'); loadWorkspaces(); }
            else showToast(d.error || 'Failed', 'danger');
        });
    }
}

// ── Cross-workspace search ──

async function performCrossWorkspaceSearch(query) {
    const container = document.getElementById('workspaceCards');
    container.innerHTML = '<div class="col-12"><div class="text-center py-4"><div class="spinner-border" role="status"></div></div></div>';
    try {
        const resp = await fetch(`/api/search-all-workspaces?q=${encodeURIComponent(query)}`);
        const data = await resp.json();
        if (!data.status || !data.results || data.results.length === 0) {
            container.innerHTML = '<div class="col-12"><div class="alert alert-secondary">No matches found.</div></div>';
            return;
        }
        container.innerHTML = '';
        data.results.forEach(group => {
            const section = document.createElement('div');
            section.className = 'col-12 mb-3';
            section.innerHTML = `<div class="card surface-wood"><div class="card-header"><strong>${escapeHtml(group.workspace.name)}</strong></div><div class="card-body">`;
            if (group.items.length > 0) {
                section.innerHTML += `<p class="mb-1 fw-semibold">Sources (${group.items.length})</p>`;
                group.items.forEach(item => {
                    section.innerHTML += `<div class="d-flex justify-content-between align-items-center py-1 border-bottom"><span>${escapeHtml(item.title)}</span><a href="/workspace/${group.workspace.id}" class="btn btn-sm btn-outline-secondary">Open</a></div>`;
                });
            }
            if (group.notes.length > 0) {
                section.innerHTML += `<p class="mb-1 mt-2 fw-semibold">Notes (${group.notes.length})</p>`;
                group.notes.forEach(note => {
                    section.innerHTML += `<div class="py-1 border-bottom"><strong>${escapeHtml(note.title)}</strong></div>`;
                });
            }
            section.innerHTML += `</div></div>`;
            container.appendChild(section);
        });
    } catch (e) {
        showToast('Search failed', 'danger');
    }
}

// ── Utilities ──

function formatDate(timestamp) {
    if (!timestamp) return 'Unknown';
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

// Expose for inline create from template dialog
window.startInlineWorkspaceCreate = startInlineWorkspaceCreate;
