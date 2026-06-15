"use strict";

import { showToast } from '../toast.js';

let pageRoot = null;
let workspaceItems = [];
let currentNoteId = null;
let quill = null;

export function initWorkspace(root, data = {}) {
    pageRoot = root;
    workspaceItems = Array.isArray(data.workspace_items) ? data.workspace_items : [];

    pageRoot.innerHTML = `
        <div class="container-fluid py-4">
            <ul class="nav nav-tabs mb-4" id="workspaceTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="compilation-tab" data-bs-toggle="tab" data-bs-target="#compilation" type="button" role="tab">Compilation</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="notes-tab" data-bs-toggle="tab" data-bs-target="#notes" type="button" role="tab">Notes</button>
                </li>
            </ul>
            <div class="tab-content" id="workspaceTabsContent">
                <div class="tab-pane fade show active" id="compilation" role="tabpanel">
                    <div class="row g-4">
                        <div class="col-lg-8">
                            <h4 class="mb-4">Compilation Workspace</h4>
                            <div id="workspaceContainer"></div>
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
                                    <button class="btn btn-outline-primary w-100" id="exportDocxBtn">
                                        <i class="bi bi-file-word me-2"></i>
                                        Export DOCX
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="tab-pane fade" id="notes" role="tabpanel">
                    <div class="row g-4">
                        <div class="col-lg-8">
                            <h4 class="mb-4">Notes</h4>
                            <div id="notesContainer"></div>
                            <button class="btn btn-primary mt-3" id="createNoteBtn">
                                <i class="bi bi-plus-circle me-2"></i>
                                Create New Note
                            </button>
                        </div>
                        <div class="col-lg-4">
                            <div class="card sticky-top">
                                <div class="card-header">
                                    <i class="bi bi-info-circle me-2"></i>
                                    Notes Info
                                </div>
                                <div class="card-body">
                                    <p>Use this space to write notes, add code snippets, and upload images. Notes are saved automatically.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    renderWorkspaceItems(workspaceItems);
    attachWorkspaceListeners();
    registerWorkspaceActions();
    registerNotesActions();
}

function renderWorkspaceItems(items) {
    const container = pageRoot.querySelector('#workspaceContainer');
    if (!items.length) {
        container.innerHTML = `
            <div class="empty-state text-center p-5 border rounded-3">
                <i class="bi bi-collection display-4 text-muted"></i>
                <h5 class="mt-3">Your workspace is empty</h5>
                <p class="text-muted">Add sources from the Browse page to build your compilation.</p>
                <a href="/browse" class="btn btn-primary mt-3">Browse Sources</a>
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    items.forEach((item) => {
        container.appendChild(createWorkspaceCard(item));
    });
}

function createWorkspaceCard(item) {
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
    return card;
}

function attachWorkspaceListeners() {
    const removeButtons = pageRoot.querySelectorAll('.remove-btn');
    removeButtons.forEach((btn) => {
        btn.addEventListener('click', () => removeFromWorkspace(btn.dataset.id));
    });
}

function registerWorkspaceActions() {
    const exportPdfBtn = pageRoot.querySelector('#exportPdfBtn');
    const exportDocxBtn = pageRoot.querySelector('#exportDocxBtn');
    exportPdfBtn.addEventListener('click', () => exportWorkspace('pdf'));
    exportDocxBtn.addEventListener('click', () => exportWorkspace('docx'));
}

function removeFromWorkspace(id) {
    if (!confirm('Remove from workspace?')) return;
    fetch(`/api/workspace/${id}`, { method: 'DELETE' })
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                showToast('Removed', 'success');
                loadWorkspaceData();
            }
        });
}

function loadWorkspaceData() {
    fetch('/api/workspace/items')
        .then((r) => r.json())
        .then((result) => {
            if (result.status) {
                workspaceItems = result.items || [];
                renderWorkspaceItems(workspaceItems);
                attachWorkspaceListeners();
            }
        });
}

function exportWorkspace(format) {
    fetch('/api/workspace/items')
        .then((r) => r.json())
        .then((result) => {
            const items = result.items || [];
            const atn = pageRoot.querySelector('#atnInput').value;
            const citation_format = pageRoot.querySelector('input[name="citationFormat"]:checked').value;
            return fetch(`/api/export/${format}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items, citation_format, atn })
            });
        })
        .then((r) => {
            if (!r || !r.ok) return null;
            return r.blob();
        })
        .then((blob) => {
            if (!blob) return;
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `StudyLib_Compilation.${format}`;
            a.click();
            URL.revokeObjectURL(url);
            showToast(`Exported as ${format.toUpperCase()}`, 'success');
        });
}

function registerNotesActions() {
    const notesTab = pageRoot.querySelector('#notes-tab');
    const createNoteBtn = pageRoot.querySelector('#createNoteBtn');

    if (notesTab) {
        notesTab.addEventListener('shown.bs.tab', loadNotes);
    }

    if (createNoteBtn) {
        createNoteBtn.addEventListener('click', createNote);
    }
}

function loadNotes() {
    fetch('/api/notes')
        .then((r) => r.json())
        .then((data) => {
            if (data.status) {
                displayNotes(data.notes);
            } else {
                showToast('Failed to load notes', 'danger');
            }
        })
        .catch(() => {
            showToast('Error loading notes', 'danger');
        });
}

function displayNotes(notes) {
    const container = pageRoot.querySelector('#notesContainer');
    container.innerHTML = '';
    if (!notes.length) {
        container.innerHTML = '<p class="text-muted">No notes yet. Create your first note!</p>';
        return;
    }

    notes.forEach((note) => {
        const noteCard = document.createElement('div');
        noteCard.className = 'card mb-3';
        noteCard.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${escapeHtml(note.title)}</h5>
                <p class="card-text text-muted small">Updated: ${new Date(note.time_updated * 1000).toLocaleString()}</p>
                <div class="btn-group">
                    <button class="btn btn-sm btn-outline-primary edit-note-btn" data-id="${note.id}">Edit</button>
                    <button class="btn btn-sm btn-outline-danger delete-note-btn" data-id="${note.id}">Delete</button>
                </div>
            </div>
        `;
        container.appendChild(noteCard);
    });

    pageRoot.querySelectorAll('.edit-note-btn').forEach((btn) => {
        btn.addEventListener('click', () => editNote(btn.dataset.id));
    });
    pageRoot.querySelectorAll('.delete-note-btn').forEach((btn) => {
        btn.addEventListener('click', () => deleteNote(btn.dataset.id));
    });
}

function createNote() {
    currentNoteId = null;
    showNoteEditor('', '');
}

function editNote(noteId) {
    fetch(`/api/notes/${noteId}`)
        .then((r) => r.json())
        .then((data) => {
            if (data.status) {
                currentNoteId = noteId;
                showNoteEditor(data.note.title, data.note.content);
            } else {
                showToast('Failed to load note', 'danger');
            }
        })
        .catch(() => {
            showToast('Error loading note', 'danger');
        });
}

function showNoteEditor(title, content) {
    const container = pageRoot.querySelector('#notesContainer');
    container.innerHTML = `
        <div class="card">
            <div class="card-header">
                <input type="text" id="noteTitle" class="form-control" placeholder="Note Title" value="${escapeHtml(title)}">
            </div>
            <div class="card-body">
                <div id="editor" style="height: 400px;"></div>
            </div>
            <div class="card-footer">
                <button class="btn btn-success me-2" id="saveNoteBtn">Save</button>
                <button class="btn btn-secondary" id="cancelNoteBtn">Cancel</button>
            </div>
        </div>
    `;

    quill = new Quill('#editor', {
        theme: 'snow',
        modules: {
            toolbar: {
                container: [
                    [{ header: [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline'],
                    ['link', 'image'],
                    [{ list: 'ordered' }, { list: 'bullet' }],
                    ['blockquote', 'code-block'],
                    [{ color: [] }, { background: [] }],
                    ['clean']
                ],
                handlers: {
                    image: imageHandler
                }
            }
        }
    });

    if (content) {
        quill.root.innerHTML = content;
    }

    pageRoot.querySelector('#saveNoteBtn').addEventListener('click', saveNote);
    pageRoot.querySelector('#cancelNoteBtn').addEventListener('click', loadNotes);
}

function saveNote() {
    const title = pageRoot.querySelector('#noteTitle').value.trim();
    const content = quill.root.innerHTML;
    if (!title) {
        showToast('Title is required', 'warning');
        return;
    }

    const method = currentNoteId ? 'PUT' : 'POST';
    const url = currentNoteId ? `/api/notes/${currentNoteId}` : '/api/notes';

    fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content })
    })
        .then((r) => r.json())
        .then((data) => {
            if (data.status) {
                showToast(currentNoteId ? 'Note updated' : 'Note created', 'success');
                loadNotes();
            } else {
                showToast('Failed to save note', 'danger');
            }
        })
        .catch(() => {
            showToast('Error saving note', 'danger');
        });
}

function deleteNote(noteId) {
    if (!confirm('Delete note?')) return;
    fetch(`/api/notes/${noteId}`, { method: 'DELETE' })
        .then((r) => r.json())
        .then((data) => {
            if (data.status) {
                showToast('Note deleted', 'success');
                loadNotes();
            }
        });
}

function imageHandler() {
    const input = document.createElement('input');
    input.setAttribute('type', 'file');
    input.setAttribute('accept', 'image/*');
    input.click();
    input.onchange = () => {
        const file = input.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('file', file);
        fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.status && quill) {
                    const range = quill.getSelection();
                    quill.insertEmbed(range.index, 'image', data.url);
                } else {
                    showToast('Failed to upload image', 'danger');
                }
            })
            .catch(() => {
                showToast('Error uploading image', 'danger');
            });
    };
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value;
    return div.innerHTML;
}
