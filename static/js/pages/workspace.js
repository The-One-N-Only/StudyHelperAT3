"use strict";

import { showToast } from '../toast.js';
import { studyHelperAI } from '../ai-prompt.js';

let pageRoot = null;
let currentWorkspaceId = null;
let currentWorkspaceItems = [];
let currentNoteId = null;
let selectedWorkspaceItemId = null;
let alexanderMessages = [
    { role: 'agent', text: 'Hi, I’m Alexander. Ask a question and I’ll answer using your workspace and available AI sources.' }
];

let alexanderRequestPending = false;

export function initWorkspace(root) {
    pageRoot = root;
    currentWorkspaceId = window.WORKSPACE_ID;
    if (!currentWorkspaceId) {
        window.location.href = '/';
        return;
    }

    loadWorkspaceDetails();
}

function renderWorkspaceDetail() {
    const workspaceName = window.WORKSPACE_NAME || 'Workspace';

    pageRoot.innerHTML = `
        <div class="container-fluid py-4 archive-page archive-page-workspace">
            <span class="archive-illustration illustration-books" aria-hidden="true"></span>
            <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
            <div class="archive-content">
            <div class="d-flex flex-column flex-md-row align-items-start align-items-md-center justify-content-between gap-3 mb-4">
                <div>
                    <h3 class="archive-page-title mb-1">${escapeHtml(workspaceName)}</h3>
                    <p class="text-muted mb-0">Use the workspace page to take notes, preview your selected source, and manage your studio.</p>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-outline-secondary btn-secondary-wood btn-sm" id="renameWorkspaceBtn">Rename</button>
                    <button class="btn btn-primary btn-secondary-wood btn-sm" id="refreshWorkspaceBtn">Refresh</button>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-7">
                    <div class="card h-100 surface-leather workspace-main-panel">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="mb-1">Workspace Notes</h5>
                                <small class="text-muted">Draft ideas and explore the current source here.</small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" id="saveQuickNoteBtn">Save quick note</button>
                        </div>
                        <div class="card-body d-flex flex-column gap-4">
                            <div>
                                <textarea id="quickNoteInput" class="form-control quick-note-input h-100" rows="10" placeholder="Write your thoughts, outline key ideas, or summarise the selected source..."></textarea>
                            </div>
                            <div>
                                <div class="d-flex align-items-center justify-content-between mb-2">
                                    <div>
                                        <h6 class="mb-0">Selected source preview</h6>
                                        <small class="text-muted">Choose a source from the studio and review it inline.</small>
                                    </div>
                                    <span id="sourceBadge" class="badge bg-secondary archive-count-badge">${currentWorkspaceItems.length} sources</span>
                                </div>
                                <div id="selectedSourceViewer" class="border rounded p-2 bg-body-secondary source-preview-shell" style="min-height: 320px;"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="card h-100 surface-leather workspace-right-panel resizable-panel">
                        <div class="card-body d-flex flex-column h-100">
                            <div class="d-flex align-items-center justify-content-between mb-3">
                                <div>
                                    <h6 class="mb-0">Workspace Studio</h6>
                                    <small class="text-muted">Sources, notes, and Alexander chat.</small>
                                </div>
                            </div>
                            <div class="workspace-tabs nav nav-pills mb-3" id="studioTabList" role="tablist">
                                <button class="nav-link active" id="studio-sources-tab" data-bs-toggle="pill" data-bs-target="#studio-sources" type="button" role="tab">Sources</button>
                                <button class="nav-link" id="studio-notes-tab" data-bs-toggle="pill" data-bs-target="#studio-notes" type="button" role="tab">Notes</button>
                                <button class="nav-link" id="studio-chat-tab" data-bs-toggle="pill" data-bs-target="#studio-chat" type="button" role="tab">Alexander</button>
                            </div>

                            <div class="tab-content flex-grow-1 overflow-hidden" id="studioTabContent">
                                <div class="tab-pane fade show active h-100" id="studio-sources" role="tabpanel">
                                    <div class="h-100 d-flex flex-column">
                                        <div id="sourcesListContainer" class="list-group list-group-flush overflow-auto"></div>
                                    </div>
                                </div>
                                <div class="tab-pane fade h-100" id="studio-notes" role="tabpanel">
                                    <div class="d-flex flex-column h-100">
                                        <div class="mb-3 d-flex align-items-center justify-content-between">
                                            <h6 class="mb-0">Past notes</h6>
                                            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" id="createNoteBtn">Add note</button>
                                        </div>
                                        <div id="notesListContainer" class="overflow-auto"></div>
                                    </div>
                                </div>
                                <div class="tab-pane fade h-100" id="studio-chat" role="tabpanel">
                                    <div class="d-flex flex-column h-100">
                                        <div id="alexanderChatMessages" class="border rounded p-3 mb-3 overflow-auto chat-messages" style="min-height: 220px;"></div>
                                        <div class="input-group">
                                            <input id="alexanderChatInput" type="text" class="form-control chat-input" placeholder="Ask Alexander a question...">
                                            <button class="btn btn-primary btn-brass" id="alexanderSendBtn" type="button">Send</button>
                                        </div>
                                        <small class="text-muted mt-2">Alexander is a hosted research assistant that uses your workspace and available sources.</small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
                <div id="noteEditorModal"></div>
            </div>
        </div>
    `;

    renderSelectedSource();
    renderSourcesList();
    loadWorkspaceNotes();
    attachWorkspaceDetailListeners();
    renderAlexanderMessages();
}

function attachWorkspaceDetailListeners() {
    const saveQuickNoteBtn = pageRoot.querySelector('#saveQuickNoteBtn');
    const createNoteBtn = pageRoot.querySelector('#createNoteBtn');
    const refreshWorkspaceBtn = pageRoot.querySelector('#refreshWorkspaceBtn');
    const alexanderSendBtn = pageRoot.querySelector('#alexanderSendBtn');
    const renameWorkspaceBtn = pageRoot.querySelector('#renameWorkspaceBtn');

    if (saveQuickNoteBtn) saveQuickNoteBtn.addEventListener('click', saveQuickNote);
    if (createNoteBtn) createNoteBtn.addEventListener('click', createNote);
    if (refreshWorkspaceBtn) refreshWorkspaceBtn.addEventListener('click', loadWorkspaceDetails);
    if (alexanderSendBtn) alexanderSendBtn.addEventListener('click', sendAlexanderMessage);
    if (renameWorkspaceBtn) renameWorkspaceBtn.addEventListener('click', renameWorkspaceDialog);

    const chatInput = pageRoot.querySelector('#alexanderChatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                sendAlexanderMessage();
            }
        });
    }
}

function loadWorkspaceDetails() {
    currentWorkspaceId = window.WORKSPACE_ID;
    if (!currentWorkspaceId) {
        window.location.href = '/';
        return;
    }

    Promise.all([
        fetch(`/api/workspaces/${currentWorkspaceId}`).then((r) => r.json()),
        fetch(`/api/workspace/items?workspace_id=${currentWorkspaceId}`).then((r) => r.json())
    ]).then(([workspaceData, itemsData]) => {
        if (!workspaceData.status) {
            throw new Error('Workspace not found');
        }

        const workspace = workspaceData.workspace;
        window.WORKSPACE_NAME = workspace.name;
        currentWorkspaceItems = itemsData.items || [];
        selectedWorkspaceItemId = currentWorkspaceItems.length > 0 ? currentWorkspaceItems[0].id : null;
        renderWorkspaceDetail();
    }).catch(() => {
        showToast('Failed to load workspace', 'danger');
        window.location.href = '/';
    });
}

function renderSourcesList() {
    const container = pageRoot.querySelector('#sourcesListContainer');
    if (!container) return;
    if (!currentWorkspaceItems || currentWorkspaceItems.length === 0) {
        container.innerHTML = `<div class="text-muted small p-3">No sources have been added to this workspace yet.</div>`;
        return;
    }

    container.innerHTML = '';
    currentWorkspaceItems.forEach((item) => {
        const itemButton = document.createElement('button');
        itemButton.type = 'button';
        itemButton.className = `list-group-item list-group-item-action workspace-source-item text-start ${item.id === selectedWorkspaceItemId ? 'active' : ''}`;
        itemButton.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <div class="pe-2">
                    <h6 class="mb-1 text-truncate">${escapeHtml(item.title)}</h6>
                    <p class="mb-0 text-muted small text-truncate">${escapeHtml(item.summary || '')}</p>
                </div>
                <small class="text-muted workspace-source-name align-self-start">${escapeHtml(item.source_name)}</small>
            </div>
        `;
        itemButton.addEventListener('click', () => {
            selectedWorkspaceItemId = item.id;
            renderSelectedSource();
            renderSourcesList();
        });
        container.appendChild(itemButton);
    });
}

function renderSelectedSource() {
    const viewer = pageRoot.querySelector('#selectedSourceViewer');
    if (!viewer) return;

    if (!currentWorkspaceItems || currentWorkspaceItems.length === 0) {
        viewer.innerHTML = `<div class="p-4 text-muted">No source selected. Add sources to your workspace and tap a source to preview it here.</div>`;
        return;
    }

    const item = currentWorkspaceItems.find((it) => it.id === selectedWorkspaceItemId) || currentWorkspaceItems[0];
    if (!item) {
        viewer.innerHTML = `<div class="p-4 text-muted">No source selected.</div>`;
        return;
    }

    selectedWorkspaceItemId = item.id;
    viewer.innerHTML = `
        <div class="mb-3">
            <div class="d-flex align-items-start justify-content-between gap-3">
                <div>
                    <h5 class="mb-1 text-truncate">${escapeHtml(item.title)}</h5>
                    <p class="text-muted small mb-0">${escapeHtml(item.source_name)} • ${escapeHtml(item.source_url || '')}</p>
                </div>
                ${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-secondary-wood btn-sm">Open</a>` : ''}
            </div>
        </div>
        <div id="selectedSourcePreview" class="rounded overflow-hidden border bg-white source-preview-content" style="min-height: 320px;"></div>
    `;

    renderSelectedSourcePreview(item);
}

function renderSelectedSourcePreview(item) {
    const previewContainer = pageRoot.querySelector('#selectedSourcePreview');
    if (!previewContainer) return;

    const url = item.source_url;
    if (!url) {
        previewContainer.innerHTML = `<div class="p-4 text-muted">No preview available for this source.</div>`;
        return;
    }

    previewContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100 p-3"><div class="spinner-border" role="status"></div></div>`;

    const fileExtension = (url.split('.').pop() || '').toLowerCase();
    const directPreviewExtensions = ['pdf', 'htm', 'html'];
    if (directPreviewExtensions.includes(fileExtension) || url.includes('/static/uploads/')) {
        const iframe = document.createElement('iframe');
        iframe.className = 'w-100 h-100';
        iframe.style.minHeight = '320px';
        iframe.style.border = 'none';
        iframe.src = url;
        previewContainer.innerHTML = '';
        previewContainer.appendChild(iframe);
        return;
    }

    fetch(`/api/proxy/source?url=${encodeURIComponent(url)}`)
        .then((response) => response.json())
        .then((result) => {
            if (result.status && result.html) {
                previewContainer.innerHTML = '';
                const iframe = document.createElement('iframe');
                iframe.className = 'w-100 h-100';
                iframe.style.minHeight = '320px';
                iframe.style.border = 'none';
                iframe.srcdoc = result.html;
                previewContainer.appendChild(iframe);
            } else {
                previewContainer.innerHTML = `<div class="p-4 text-muted">Preview unavailable. <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open source</a></div>`;
            }
        })
        .catch(() => {
            previewContainer.innerHTML = `<div class="p-4 text-muted">Failed to load preview. <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open source</a></div>`;
        });
}

function loadWorkspaceNotes() {
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`)
        .then(r => r.json())
        .then(data => {
            if (data.status) {
                renderNotesTab(data.notes || []);
            }
        })
        .catch(() => showToast('Failed to load notes', 'danger'));
}

function renderNotesTab(notes) {
    const container = pageRoot.querySelector('#notesListContainer');
    if (!container) return;
    container.innerHTML = '';

    if (notes.length === 0) {
        container.innerHTML = '<div class="p-3 text-muted small">No notes yet. Add a note to save important highlights.</div>';
        return;
    }

    notes.forEach((note) => {
        const noteBtn = document.createElement('button');
        noteBtn.className = 'btn btn-sm btn-outline-secondary btn-secondary-wood note-item w-100 text-start mb-2 text-truncate';
        noteBtn.dataset.id = note.id;
        noteBtn.title = note.title;
        noteBtn.innerHTML = '<i class="bi bi-file-earmark-text note-icon-dark d-none me-2" aria-hidden="true"></i><span class="note-icon-light">📝 </span>' + escapeHtml(note.title);
        noteBtn.addEventListener('click', () => editNote(note.id));
        container.appendChild(noteBtn);
    });
}

function createNote() {
    currentNoteId = null;
    showNoteEditor('', '');
}

function editNote(noteId) {
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`)
        .then(r => r.json())
        .then(data => {
            const note = data.notes.find((n) => n.id === parseInt(noteId, 10));
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

    const url = currentNoteId ? `/api/notes/${currentNoteId}` : `/api/workspaces/${currentWorkspaceId}/notes`;
    const method = currentNoteId ? 'PUT' : 'POST';

    fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content })
    })
    .then(r => r.json())
    .then(result => {
        if (result.status) {
            showToast(currentNoteId ? 'Note updated' : 'Note created', 'success');
            closeNoteEditor();
            loadWorkspaceNotes();
        } else {
            showToast(result.error || 'Unable to save note', 'danger');
        }
    })
    .catch(() => showToast('Failed to save note', 'danger'));
}

function closeNoteEditor() {
    const modal = pageRoot.querySelector('#noteEditorModal');
    if (modal) modal.innerHTML = '';
    currentNoteId = null;
}

function saveQuickNote() {
    const content = pageRoot.querySelector('#quickNoteInput')?.value.trim();
    if (!content) {
        showToast('Add some quick notes before saving.', 'warning');
        return;
    }

    const title = `Quick note ${new Date().toLocaleString()}`;
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content })
    })
    .then(r => r.json())
    .then(result => {
        if (result.status) {
            showToast('Quick note saved', 'success');
            pageRoot.querySelector('#quickNoteInput').value = '';
            loadWorkspaceNotes();
        } else {
            showToast(result.error || 'Unable to save note', 'danger');
        }
    })
    .catch(() => showToast('Failed to save quick note', 'danger'));
}

function renameWorkspaceDialog() {
    const workspaceName = window.WORKSPACE_NAME || '';
    const newName = prompt('Enter a new name for this workspace:', workspaceName);
    if (!newName || !newName.trim()) return;

    fetch(`/api/workspaces/${currentWorkspaceId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() })
    })
    .then(r => r.json())
    .then(result => {
        if (result.status) {
            showToast('Workspace renamed', 'success');
            window.WORKSPACE_NAME = result.workspace.name;
            document.title = `${window.WORKSPACE_NAME} - StudyLib`;
            renderWorkspaceDetail();
        } else {
            showToast(result.error || 'Unable to rename workspace', 'danger');
        }
    })
    .catch(() => showToast('Failed to rename workspace', 'danger'));
}

async function sendAlexanderMessage() {
    if (alexanderRequestPending) {
        return;
    }

    const input = pageRoot.querySelector('#alexanderChatInput');
    const sendButton = pageRoot.querySelector('#alexanderSendBtn');
    const value = input?.value.trim();
    if (!value) {
        return;
    }

    alexanderRequestPending = true;
    input.disabled = true;
    if (sendButton) sendButton.disabled = true;

    alexanderMessages.push({ role: 'user', text: value });
    renderAlexanderMessages();
    input.value = '';

    const loadingMessage = { role: 'agent', text: 'Alexander is thinking...' };
    alexanderMessages.push(loadingMessage);
    renderAlexanderMessages();

    try {
        const result = await studyHelperAI.chat(value);
        if (result.status) {
            alexanderMessages.push({ role: 'agent', text: result.response });
        } else {
            alexanderMessages.push({
                role: 'agent',
                text: result.error || 'Alexander could not answer right now. Try again shortly.'
            });
        }
    } catch (_) {
        alexanderMessages.push({
            role: 'agent',
            text: 'Alexander could not answer right now. Try again shortly.'
        });
    } finally {
        alexanderMessages = alexanderMessages.filter((message) => message !== loadingMessage);
        alexanderRequestPending = false;
        input.disabled = false;
        if (sendButton) sendButton.disabled = false;
        renderAlexanderMessages();
    }
}

function renderAlexanderMessages() {
    const container = pageRoot.querySelector('#alexanderChatMessages');
    if (!container) return;
    container.innerHTML = '';
    alexanderMessages.forEach((message) => {
        const messageEl = document.createElement('div');
        messageEl.className = `mb-3 p-3 rounded chat-row chat-message ${message.role === 'agent' ? 'bg-light text-dark chat-row-agent chat-message-agent chat-avatar' : 'bg-primary text-white chat-row-user chat-message-user'}`;
        messageEl.innerHTML = `<strong>${message.role === 'agent' ? 'Alexander' : 'You'}</strong><div class="mt-1">${escapeHtml(message.text)}</div>`;
        container.appendChild(messageEl);
    });
    container.scrollTop = container.scrollHeight;
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
            window.location.href = `/workspace/${result.workspace.id}`;
        } else {
            showToast(result.error || 'Unable to create workspace', 'danger');
        }
    })
    .catch(() => showToast('Failed to create workspace', 'danger'));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
