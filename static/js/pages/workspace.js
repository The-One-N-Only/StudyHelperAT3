"use strict";

import { showToast } from '../toast.js';

let pageRoot = null;
let currentWorkspaceId = null;
let workspaces = [];
let currentWorkspaceItems = [];
let currentNoteId = null;

export function initWorkspace(root, data = {}) {
    pageRoot = root;
    currentWorkspaceId = null;
    loadWorkspaces();
}

function renderWorkspacePage() {
    pageRoot.innerHTML = `
        <div class="container-fluid py-4">
            <!-- Workspace Selector -->
            <div class="card mb-4">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">
                        <i class="bi bi-folder me-2"></i>
                        Workspaces
                    </h5>
                    <button class="btn btn-sm btn-primary" id="createWorkspaceBtn">
                        <i class="bi bi-plus-lg me-1"></i>
                        New Workspace
                    </button>
                </div>
                <div class="card-body">
                    <div id="workspaceList" class="row g-2"></div>
                </div>
            </div>

            <!-- Current Workspace View -->
            <div id="workspaceDetailContainer"></div>
        </div>
    `;

    renderWorkspaceList();
    attachCreateWorkspaceListener();

    if (workspaces.length > 0) {
        selectWorkspace(workspaces[0].id);
    }
}

function renderWorkspaceList() {
    const container = pageRoot.querySelector('#workspaceList');
    container.innerHTML = '';

    if (workspaces.length === 0) {
        container.innerHTML = '<p class="text-muted">No workspaces yet. Create one to get started!</p>';
        return;
    }

    workspaces.forEach((workspace) => {
        const isActive = workspace.id === currentWorkspaceId;
        const btn = document.createElement('button');
        btn.className = `btn btn-outline-primary position-relative ${isActive ? 'active' : ''}`;
        btn.innerHTML = `
            ${escapeHtml(workspace.name)}
            <span class="badge bg-secondary ms-2">${workspace.item_count}</span>
        `;
        btn.addEventListener('click', () => selectWorkspace(workspace.id));

        // Context menu
        btn.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            showWorkspaceContextMenu(workspace, e);
        });

        container.appendChild(btn);
    });
}

function showWorkspaceContextMenu(workspace, event) {
    const menu = document.createElement('div');
    menu.className = 'dropdown-menu show';
    menu.style.position = 'fixed';
    menu.style.left = event.pageX + 'px';
    menu.style.top = event.pageY + 'px';
    menu.innerHTML = `
        <button class="dropdown-item rename-workspace-btn" data-id="${workspace.id}">
            <i class="bi bi-pencil me-2"></i>Rename
        </button>
        <button class="dropdown-item text-danger delete-workspace-btn" data-id="${workspace.id}">
            <i class="bi bi-trash me-2"></i>Delete
        </button>
    `;

    document.body.appendChild(menu);

    menu.querySelector('.rename-workspace-btn').addEventListener('click', () => {
        document.body.removeChild(menu);
        renameWorkspaceDialog(workspace);
    });

    menu.querySelector('.delete-workspace-btn').addEventListener('click', () => {
        document.body.removeChild(menu);
        deleteWorkspaceDialog(workspace);
    });

    document.addEventListener('click', () => {
        if (document.body.contains(menu)) document.body.removeChild(menu);
    }, { once: true });
}

function selectWorkspace(workspaceId) {
    currentWorkspaceId = workspaceId;
    loadWorkspaceDetails();
}

function loadWorkspaceDetails() {
    fetch(`/api/workspace/items?workspace_id=${currentWorkspaceId}`)
        .then(r => r.json())
        .then(data => {
            currentWorkspaceItems = data.items || [];
            renderWorkspaceDetail();
        })
        .catch(() => showToast('Failed to load workspace items', 'danger'));
}

function renderWorkspaceDetail() {
    const workspace = workspaces.find(w => w.id === currentWorkspaceId);
    if (!workspace) return;

    const container = pageRoot.querySelector('#workspaceDetailContainer');
    container.innerHTML = `
        <div class="row g-4">
            <div class="col-lg-8">
                <div class="row g-3">
                    <div class="col-12">
                        <h4>${escapeHtml(workspace.name)} - Compilation</h4>
                    </div>
                    <div class="col-12">
                        <div id="workspaceItemsContainer"></div>
                    </div>
                </div>
            </div>
            <div class="col-lg-4">
                <div class="card sticky-top">
                    <div class="card-header">
                        <i class="bi bi-gear me-2"></i>
                        Compilation Settings
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <label for="atnInput" class="form-label">Assessment Task</label>
                            <input type="text" class="form-control" id="atnInput" placeholder="Optional assessment task...">
                            <div class="form-text">This will be included in the exported document</div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Citation Format</label>
                            <div class="btn-group w-100" role="group">
                                <input type="radio" class="btn-check" name="citationFormat" id="apaRadio" value="apa" checked>
                                <label class="btn btn-outline-primary" for="apaRadio">APA</label>
                                <input type="radio" class="btn-check" name="citationFormat" id="harvardRadio" value="harvard">
                                <label class="btn btn-outline-primary" for="harvardRadio">Harvard</label>
                            </div>
                        </div>
                        <hr>
                        <button class="btn btn-outline-danger w-100 mb-2" id="exportPdfBtn">
                            <i class="bi bi-file-pdf me-2"></i>
                            Export PDF
                        </button>
                        <button class="btn btn-outline-primary w-100 mb-3" id="exportDocxBtn">
                            <i class="bi bi-file-word me-2"></i>
                            Export DOCX
                        </button>
                        <hr>
                        <h6>Notes for this Workspace</h6>
                        <div id="notesListContainer" class="mb-3"></div>
                        <button class="btn btn-sm btn-primary w-100" id="createNoteBtn">
                            <i class="bi bi-plus-lg me-1"></i>
                            Add Note
                        </button>
                    </div>
                </div>
            </div>
        </div>
        <div id="noteEditorModal"></div>
    `;

    renderWorkspaceItems();
    loadWorkspaceNotes();
    attachWorkspaceDetailListeners();
}

function renderWorkspaceItems() {
    const container = pageRoot.querySelector('#workspaceItemsContainer');
    if (!currentWorkspaceItems || currentWorkspaceItems.length === 0) {
        container.innerHTML = `<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>No items in this workspace yet. Add sources from the Browse page.</div>`;
        return;
    }

    container.innerHTML = '';
    currentWorkspaceItems.forEach((item) => {
        const card = document.createElement('div');
        card.className = 'card mb-3';
        card.innerHTML = `
            <div class="card-header d-flex align-items-center">
                <h6 class="fw-semibold mb-0 text-truncate">${escapeHtml(item.title)}</h6>
                <span class="badge bg-secondary ms-2">${escapeHtml(item.source_name)}</span>
                <button class="btn btn-outline-danger btn-sm ms-auto remove-btn" data-id="${item.id}">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
            <div class="card-body">
                <p>${escapeHtml(item.summary)}</p>
                <button class="btn btn-link btn-sm p-0 toggle-bullets" data-bs-toggle="collapse" data-bs-target="#bullets-${item.id}">
                    Key Points ▾
                </button>
                <div class="collapse mt-2" id="bullets-${item.id}">
                    <ul>
                        ${Array.isArray(item.bullets)
                            ? item.bullets.map((b) => `<li>${escapeHtml(b)}</li>`).join('')
                            : ''}
                    </ul>
                </div>
                ${item.relevance ? `<div class="alert alert-info mt-2"><i class="bi bi-lightbulb"></i> ${escapeHtml(item.relevance)}</div>` : ''}
            </div>
            <div class="card-footer bg-transparent">
                <small class="font-monospace text-muted">${escapeHtml(item.citation_apa)}</small>
            </div>
        `;
        container.appendChild(card);
    });

    container.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', () => removeFromWorkspace(btn.dataset.id));
    });
}

function loadWorkspaceNotes() {
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`)
        .then(r => r.json())
        .then(data => {
            if (data.status) {
                renderWorkspaceNotes(data.notes || []);
            }
        })
        .catch(() => showToast('Failed to load notes', 'danger'));
}

function renderWorkspaceNotes(notes) {
    const container = pageRoot.querySelector('#notesListContainer');
    container.innerHTML = '';

    if (notes.length === 0) {
        container.innerHTML = '<p class="text-muted small">No notes yet</p>';
        return;
    }

    notes.forEach((note) => {
        const noteBtn = document.createElement('button');
        noteBtn.className = 'btn btn-sm btn-outline-secondary w-100 text-start mb-2 text-truncate edit-note-btn';
        noteBtn.dataset.id = note.id;
        noteBtn.title = note.title;
        noteBtn.textContent = '📝 ' + note.title;
        container.appendChild(noteBtn);

        noteBtn.addEventListener('click', () => editNote(note.id));
    });
}

function attachWorkspaceDetailListeners() {
    const exportPdfBtn = pageRoot.querySelector('#exportPdfBtn');
    const exportDocxBtn = pageRoot.querySelector('#exportDocxBtn');
    const createNoteBtn = pageRoot.querySelector('#createNoteBtn');

    if (exportPdfBtn) exportPdfBtn.addEventListener('click', () => exportWorkspace('pdf'));
    if (exportDocxBtn) exportDocxBtn.addEventListener('click', () => exportWorkspace('docx'));
    if (createNoteBtn) createNoteBtn.addEventListener('click', () => createNote());
}

function attachCreateWorkspaceListener() {
    const btn = pageRoot.querySelector('#createWorkspaceBtn');
    if (btn) btn.addEventListener('click', createWorkspaceDialog);
}

function removeFromWorkspace(itemId) {
    if (!confirm('Remove from workspace?')) return;
    fetch(`/api/workspace/${itemId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                showToast('Removed', 'success');
                loadWorkspaceDetails();
            }
        });
}

function exportWorkspace(format) {
    const atn = pageRoot.querySelector('#atnInput')?.value || '';
    const citation_format = pageRoot.querySelector('input[name="citationFormat"]:checked')?.value || 'apa';

    fetch(`/api/export/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: currentWorkspaceItems, citation_format, atn })
    })
    .then(r => r.blob())
    .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `StudyLib_Compilation.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        showToast(`Exported as ${format.toUpperCase()}`, 'success');
    })
    .catch(() => showToast('Export failed', 'danger'));
}

function createWorkspaceDialog() {
    const name = prompt('Enter workspace name:', 'New Workspace');
    if (!name) return;

    fetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    })
    .then(r => r.json())
    .then(result => {
        if (result.status) {
            showToast('Workspace created', 'success');
            loadWorkspaces();
        }
    })
    .catch(() => showToast('Failed to create workspace', 'danger'));
}

function renameWorkspaceDialog(workspace) {
    const newName = prompt('Enter new name:', workspace.name);
    if (!newName) return;

    fetch(`/api/workspaces/${workspace.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName })
    })
    .then(r => r.json())
    .then(result => {
        if (result.status) {
            showToast('Workspace renamed', 'success');
            loadWorkspaces();
        }
    })
    .catch(() => showToast('Failed to rename workspace', 'danger'));
}

function deleteWorkspaceDialog(workspace) {
    if (!confirm(`Delete "${workspace.name}" and all its items?`)) return;

    fetch(`/api/workspaces/${workspace.id}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                showToast('Workspace deleted', 'success');
                currentWorkspaceId = null;
                loadWorkspaces();
            }
        })
        .catch(() => showToast('Failed to delete workspace', 'danger'));
}

function createNote() {
    currentNoteId = null;
    showNoteEditor('', '');
}

function editNote(noteId) {
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`)
        .then(r => r.json())
        .then(data => {
            const note = data.notes.find(n => n.id === parseInt(noteId));
            if (note) {
                currentNoteId = noteId;
                showNoteEditor(note.title, note.content);
            }
        });
}

function showNoteEditor(title, content) {
    const modal = pageRoot.querySelector('#noteEditorModal');
    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${currentNoteId ? 'Edit Note' : 'New Note'}</h5>
                        <button type="button" class="btn-close" id="closeModalBtn"></button>
                    </div>
                    <div class="modal-body">
                        <input type="text" class="form-control mb-3" id="noteTitleInput" placeholder="Note title" value="${escapeHtml(title)}">
                        <textarea class="form-control" id="noteContentInput" rows="10" placeholder="Note content">${escapeHtml(content)}</textarea>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="cancelNoteBtn">Cancel</button>
                        <button type="button" class="btn btn-primary" id="saveNoteBtn">${currentNoteId ? 'Update' : 'Create'}</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    modal.querySelector('#closeModalBtn').addEventListener('click', closeNoteEditor);
    modal.querySelector('#cancelNoteBtn').addEventListener('click', closeNoteEditor);
    modal.querySelector('#saveNoteBtn').addEventListener('click', saveNote);
}

function saveNote() {
    const title = pageRoot.querySelector('#noteTitleInput').value.trim();
    const content = pageRoot.querySelector('#noteContentInput').value.trim();

    if (!title) {
        showToast('Please enter a note title', 'warning');
        return;
    }

    if (currentNoteId) {
        fetch(`/api/notes/${currentNoteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        })
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                showToast('Note updated', 'success');
                closeNoteEditor();
                loadWorkspaceNotes();
            }
        })
        .catch(() => showToast('Failed to update note', 'danger'));
    } else {
        fetch(`/api/workspaces/${currentWorkspaceId}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content })
        })
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                showToast('Note created', 'success');
                closeNoteEditor();
                loadWorkspaceNotes();
            }
        })
        .catch(() => showToast('Failed to create note', 'danger'));
    }
}

function closeNoteEditor() {
    const modal = pageRoot.querySelector('#noteEditorModal');
    if (modal) modal.innerHTML = '';
    currentNoteId = null;
}

function loadWorkspaces() {
    fetch('/api/workspaces')
        .then(r => r.json())
        .then(data => {
            if (data.status) {
                workspaces = data.workspaces || [];
                renderWorkspacePage();
            }
        })
        .catch(() => showToast('Failed to load workspaces', 'danger'));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
