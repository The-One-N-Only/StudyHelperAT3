"use strict";

import { showToast } from '../toast.js';
import { studyHelperAI } from '../ai-prompt.js';
import {
    isGoogleBooksResult,
    googleBooksVolumeId,
    loadGoogleBooksApi,
    resetGoogleBooksViewerState,
    renderGoogleBooksFallback,
    renderViewerNotice,
} from '../viewer.js';

const WORKSPACE_IFRAME_SANDBOX = 'allow-popups allow-popups-to-escape-sandbox';
const ALEXANDER_WELCOME_MESSAGE = 'Hi, I’m Alexander. Ask a question and I’ll answer using your workspace and available AI sources.';
const ALEXANDER_NOT_CONFIGURED_MESSAGE = 'Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib.';

let pageRoot = null;
let currentWorkspaceId = null;
let currentWorkspaceItems = [];
let currentNoteId = null;
let selectedWorkspaceItemId = null;
let alexanderMessages = [{ role: 'agent', text: ALEXANDER_WELCOME_MESSAGE }];
let alexanderAIConfigured = true;
let alexanderRequestPending = false;
let alexanderConversationVersion = 0;
let workspaceUploadSelectedFile = null;

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
                    <h3 class="archive-page-title mb-1">${escapeHtml(workspaceName)}</h3>
                    <p class="text-muted mb-0">Use the workspace page to take notes, preview your selected source, and manage your studio.</p>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-outline-secondary btn-secondary-wood btn-sm" id="renameWorkspaceBtn">Rename</button>
                    <button class="btn btn-primary btn-secondary-wood btn-sm" id="refreshWorkspaceBtn">Refresh</button>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-7 d-flex flex-column gap-4">
                    <div class="card surface-leather source-preview-box">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="mb-1">Selected source preview</h5>
                                <small class="text-muted">Choose a source from the studio and review it inline.</small>
                            </div>
                            <span id="sourceBadge" class="badge bg-secondary archive-count-badge">${currentWorkspaceItems.length} sources</span>
                        </div>
                        <div class="card-body">
                            <div id="selectedSourceViewer" class="border rounded p-2 source-preview-shell" style="min-height: 320px;"></div>
                        </div>
                    </div>
                    <div class="card surface-leather notes-box">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="mb-1">Workspace Notes</h5>
                                <small class="text-muted">Draft ideas and explore the current source here.</small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" id="saveQuickNoteBtn">Save quick note</button>
                        </div>
                        <div class="card-body">
                            <textarea id="quickNoteInput" class="form-control quick-note-input" rows="10" placeholder="Write your thoughts, outline key ideas, or summarise the selected source..."></textarea>
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
                                        <div class="d-flex gap-2 p-2 border-bottom">
                                            <button class="btn btn-outline-secondary btn-secondary-wood btn-sm flex-grow-1" id="searchNewBtn">Search new</button>
                                            <button class="btn btn-outline-primary btn-secondary-wood btn-sm flex-grow-1" id="uploadNewBtn">Upload new</button>
                                        </div>
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
                                            <input id="alexanderChatInput" type="text" class="form-control chat-input" placeholder="Ask Alexander a question..."${alexanderAIConfigured ? '' : ' disabled'}>
                                            <button class="btn btn-primary btn-brass" id="alexanderSendBtn" type="button"${alexanderAIConfigured ? '' : ' disabled'}>Send</button>
                                        </div>
                                        <small class="text-muted mt-2" id="alexanderChatStatus" aria-live="polite">${alexanderAIConfigured ? 'Alexander is a hosted research assistant that uses your workspace and available sources.' : ALEXANDER_NOT_CONFIGURED_MESSAGE}</small>
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
    syncAlexanderChatAvailability();
}

function attachWorkspaceDetailListeners() {
    const saveQuickNoteBtn = pageRoot.querySelector('#saveQuickNoteBtn');
    const createNoteBtn = pageRoot.querySelector('#createNoteBtn');
    const refreshWorkspaceBtn = pageRoot.querySelector('#refreshWorkspaceBtn');
    const alexanderSendBtn = pageRoot.querySelector('#alexanderSendBtn');
    const renameWorkspaceBtn = pageRoot.querySelector('#renameWorkspaceBtn');
    const searchNewBtn = pageRoot.querySelector('#searchNewBtn');
    const uploadNewBtn = pageRoot.querySelector('#uploadNewBtn');

    if (saveQuickNoteBtn) saveQuickNoteBtn.addEventListener('click', saveQuickNote);
    if (createNoteBtn) createNoteBtn.addEventListener('click', createNote);
    if (refreshWorkspaceBtn) refreshWorkspaceBtn.addEventListener('click', loadWorkspaceDetails);
    if (alexanderSendBtn) alexanderSendBtn.addEventListener('click', sendAlexanderMessage);
    if (renameWorkspaceBtn) renameWorkspaceBtn.addEventListener('click', renameWorkspaceDialog);
    if (searchNewBtn) searchNewBtn.addEventListener('click', () => { window.location.href = '/browse'; });
    if (uploadNewBtn) uploadNewBtn.addEventListener('click', showUploadModal);

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
    if (alexanderRequestPending) return;

    currentWorkspaceId = window.WORKSPACE_ID;
    if (!currentWorkspaceId) {
        window.location.href = '/';
        return;
    }
    const conversationVersion = alexanderConversationVersion;

    Promise.all([
        fetch(`/api/workspaces/${currentWorkspaceId}`).then((r) => r.json()),
        fetch(`/api/workspace/items?workspace_id=${currentWorkspaceId}`).then((r) => r.json()),
        fetch(`/api/workspaces/${currentWorkspaceId}/chat`).then((r) => r.json())
    ]).then(([workspaceData, itemsData, chatData]) => {
        if (conversationVersion !== alexanderConversationVersion) return;
        if (!workspaceData.status || !chatData.status) {
            throw new Error('Workspace not found');
        }

        const workspace = workspaceData.workspace;
        window.WORKSPACE_NAME = workspace.name;
        currentWorkspaceItems = itemsData.items || [];
        selectedWorkspaceItemId = currentWorkspaceItems.length > 0 ? currentWorkspaceItems[0].id : null;
        applyAlexanderChatData(chatData);
        renderWorkspaceDetail();
    }).catch(() => {
        showToast('Failed to load workspace', 'danger');
        window.location.href = '/';
    });
}

function applyAlexanderChatData(chatData) {
    const savedMessages = Array.isArray(chatData?.messages)
        ? chatData.messages.filter((message) => (
            message
            && (message.role === 'user' || message.role === 'assistant')
            && typeof message.content === 'string'
        ))
        : [];

    studyHelperAI.setConversationHistory(savedMessages);
    alexanderMessages = [
        { role: 'agent', text: ALEXANDER_WELCOME_MESSAGE },
        ...savedMessages.map((message) => ({
            role: message.role === 'assistant' ? 'agent' : 'user',
            text: message.content
        }))
    ];
    alexanderAIConfigured = chatData?.ai_configured === true;
}

function syncAlexanderChatAvailability() {
    const input = pageRoot?.querySelector('#alexanderChatInput');
    const sendButton = pageRoot?.querySelector('#alexanderSendBtn');
    const refreshButton = pageRoot?.querySelector('#refreshWorkspaceBtn');
    const status = pageRoot?.querySelector('#alexanderChatStatus');
    const unavailable = !alexanderAIConfigured;

    if (input) input.disabled = unavailable || alexanderRequestPending;
    if (sendButton) sendButton.disabled = unavailable || alexanderRequestPending;
    if (refreshButton) refreshButton.disabled = alexanderRequestPending;
    if (status) {
        status.textContent = unavailable
            ? ALEXANDER_NOT_CONFIGURED_MESSAGE
            : 'Alexander is a hosted research assistant that uses your workspace and available sources.';
    }
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
    const sourceUrl = safeHttpUrl(item.source_url);
    viewer.innerHTML = `
        <div class="mb-3">
            <div class="d-flex align-items-start justify-content-between gap-3">
                <div>
                    <h5 class="mb-1 text-truncate">${escapeHtml(item.title)}</h5>
                    <p class="text-muted small mb-0">${escapeHtml(item.source_name)} • ${escapeHtml(item.source_url || '')}</p>
                </div>
                ${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-secondary-wood btn-sm">Open</a>` : ''}
            </div>
        </div>
        <div id="selectedSourcePreview" class="rounded overflow-hidden border bg-white source-preview-content" style="min-height: 320px;"></div>
    `;

    renderSelectedSourcePreview(item);
}

function safeHttpUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return '';
    try {
        const parsed = new URL(value.trim());
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
        return parsed.href;
    } catch {
        return '';
    }
}

function safeLocalUploadUrl(value) {
    if (typeof value !== 'string') return '';
    const candidate = value.trim();
    if (!candidate.startsWith('/static/uploads/') || candidate.startsWith('//')) return '';
    try {
        const parsed = new URL(candidate, window.location.origin);
        if (parsed.origin !== window.location.origin) return '';
        if (!parsed.pathname.startsWith('/static/uploads/')) return '';
        return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch {
        return '';
    }
}

function sourceExtension(url) {
    try {
        const parsed = new URL(url, window.location.origin);
        const filename = parsed.pathname.split('/').pop() || '';
        const dotIndex = filename.lastIndexOf('.');
        return dotIndex >= 0 ? filename.slice(dotIndex + 1).toLowerCase() : '';
    } catch {
        return '';
    }
}

function createPreviewIframe() {
    const iframe = document.createElement('iframe');
    iframe.className = 'w-100 h-100';
    iframe.style.minHeight = '320px';
    iframe.style.border = 'none';
    iframe.setAttribute('sandbox', WORKSPACE_IFRAME_SANDBOX);
    iframe.setAttribute('referrerpolicy', 'no-referrer');
    return iframe;
}

function renderPreviewNotice(container, message, linkUrl = '') {
    const safeLink = safeHttpUrl(linkUrl);
    const link = safeLink
        ? ` <a href="${escapeHtml(safeLink)}" target="_blank" rel="noopener noreferrer">Open source</a>`
        : '';
    container.innerHTML = `<div class="p-4 text-muted">${escapeHtml(message)}${link}</div>`;
}

function textValue(value) {
    return value === null || value === undefined ? '' : String(value);
}

function renderSelectedSourcePreview(item) {
    const previewContainer = pageRoot.querySelector('#selectedSourcePreview');
    if (!previewContainer) return;

    const remoteUrl = safeHttpUrl(item.source_url);
    const localUploadUrl = safeLocalUploadUrl(item.source_url);
    const previewUrl = localUploadUrl || remoteUrl;
    if (!previewUrl) {
        renderPreviewNotice(previewContainer, 'No preview available for this source.');
        return;
    }

    // Source-type detection matching browse sidebar viewer behavior
    if (isGoogleBooksResult(item)) {
        renderWorkspaceGoogleBooksPreview(previewContainer, item);
        return;
    }

    const sourceName = textValue(item?.source_name).toLowerCase();
    const sourceUrl = textValue(item?.source_url).toLowerCase();

    const isPubMed = sourceName === 'pubmed' || sourceUrl.includes('pubmed.ncbi.nlm.nih.gov');
    if (isPubMed) {
        renderPreviewNotice(previewContainer, 'PubMed pages are not displayed inside StudyHelper because NCBI blocks proxy access.', sourceUrl);
        return;
    }

    const isScholar = sourceName === 'scholar' || sourceName === 'google scholar' || sourceUrl.includes('scholar.google.com');
    if (isScholar) {
        renderPreviewNotice(previewContainer, 'Google Scholar blocks proxy access.', sourceUrl);
        return;
    }

    const isJSTOR = sourceUrl.includes('jstor.org');
    if (isJSTOR) {
        renderPreviewNotice(previewContainer, 'JSTOR content is subscription-based and cannot be previewed here.', sourceUrl);
        return;
    }

    const isScienceDirect = sourceUrl.includes('sciencedirect.com');
    if (isScienceDirect) {
        renderPreviewNotice(previewContainer, 'ScienceDirect content requires a subscription.', sourceUrl);
        return;
    }

    const isSpringer = sourceUrl.includes('link.springer.com');
    if (isSpringer) {
        renderPreviewNotice(previewContainer, 'Springer content requires a subscription.', sourceUrl);
        return;
    }

    const isNationalGeo = sourceUrl.includes('nationalgeographic.com');
    if (isNationalGeo) {
        renderPreviewNotice(previewContainer, 'National Geographic content requires a subscription.', sourceUrl);
        return;
    }

    previewContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100 p-3"><div class="spinner-border" role="status"></div></div>`;

    const fileExtension = sourceExtension(previewUrl);
    if (localUploadUrl || fileExtension === 'pdf') {
        const iframe = createPreviewIframe();
        iframe.src = previewUrl;
        previewContainer.innerHTML = '';
        previewContainer.appendChild(iframe);
        return;
    }

    // Remote HTML, including .html/.htm URLs, only enters through sanitized srcdoc.
    fetch(`/api/proxy/source?url=${encodeURIComponent(remoteUrl)}`)
        .then((response) => response.json())
        .then((result) => {
            if (result.status && typeof result.html === 'string' && result.html) {
                previewContainer.innerHTML = '';
                const iframe = createPreviewIframe();
                iframe.srcdoc = result.html;
                previewContainer.appendChild(iframe);
            } else {
                renderPreviewNotice(
                    previewContainer,
                    'Preview unavailable.',
                    safeHttpUrl(result.fallback_url) || remoteUrl,
                );
            }
        })
        .catch(() => {
            renderPreviewNotice(previewContainer, 'Failed to load preview.', remoteUrl);
        });
}

async function renderWorkspaceGoogleBooksPreview(container, item) {
    const generation = Date.now();
    const volumeId = googleBooksVolumeId(item);
    if (!volumeId) {
        renderGoogleBooksFallback(container, item, 'This result does not include a Google Books volume ID.');
        return;
    }

    const accessInfo = item?.accessInfo && typeof item.accessInfo === 'object' ? item.accessInfo : {};
    if (accessInfo.embeddable === false) {
        renderGoogleBooksFallback(container, item, 'An embedded preview is not available for this book.');
        return;
    }

    let booksApi;
    try {
        booksApi = await loadGoogleBooksApi();
    } catch {
        renderGoogleBooksFallback(container, item, 'The Google Books preview service could not be loaded.');
        return;
    }

    const viewerShell = document.createElement('div');
    viewerShell.className = 'google-books-viewer';
    const canvas = document.createElement('div');
    canvas.className = 'google-books-viewer-canvas';
    viewerShell.appendChild(canvas);
    container.replaceChildren(viewerShell);

    let viewer;
    try {
        viewer = new booksApi.DefaultViewer(canvas);
    } catch {
        renderGoogleBooksFallback(container, item, 'The embedded preview could not be started.');
        return;
    }

    await new Promise((resolve) => {
        try {
            viewer.load(
                volumeId,
                () => {
                    renderGoogleBooksFallback(container, item, 'No embedded preview is available for this volume.');
                    resolve();
                },
                () => {
                    if (typeof ResizeObserver === 'function') {
                        const observer = new ResizeObserver(() => {
                            viewer.resize();
                        });
                        observer.observe(canvas);
                    }
                    resolve();
                },
            );
        } catch {
            renderGoogleBooksFallback(container, item, 'The embedded preview could not be loaded.');
            resolve();
        }
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
    if (alexanderRequestPending || !alexanderAIConfigured) {
        return;
    }

    const input = pageRoot.querySelector('#alexanderChatInput');
    const value = input?.value.trim();
    if (!value) {
        return;
    }

    alexanderRequestPending = true;
    alexanderConversationVersion += 1;
    syncAlexanderChatAvailability();

    alexanderMessages.push({ role: 'user', text: value });
    renderAlexanderMessages();
    input.value = '';

    const loadingMessage = { role: 'agent', text: 'Alexander is thinking...' };
    alexanderMessages.push(loadingMessage);
    renderAlexanderMessages();

    try {
        const result = await studyHelperAI.chat(value, { workspaceId: currentWorkspaceId });
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
        syncAlexanderChatAvailability();
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

function showUploadModal() {
    workspaceUploadSelectedFile = null;
    const modal = pageRoot.querySelector('#noteEditorModal');
    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Upload to Workspace</h5>
                        <button type="button" class="btn-close" id="closeUploadModalBtn"></button>
                    </div>
                    <div class="modal-body">
                        <div class="text-center p-4 mb-3 border rounded upload-zone bg-light" id="wsUploadZone" style="cursor: pointer;">
                            <i class="bi bi-cloud-upload display-4 text-muted" aria-hidden="true"></i>
                            <h6 class="mt-3">Drag files here or click to browse</h6>
                            <p class="small text-muted mb-0">Maximum 10MB</p>
                            <input type="file" id="wsFileInput" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.gif,.webp,.xlsx,.xls" style="display: none;">
                        </div>
                        <div class="mb-3">
                            <p class="mb-2"><strong>Selected:</strong> <span id="wsSelectedFile">No file selected</span></p>
                        </div>
                        <div class="progress mb-3" style="display: none;" id="wsProgressBar">
                            <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="cancelUploadBtn">Cancel</button>
                        <button type="button" class="btn btn-primary btn-brass" id="confirmUploadBtn" disabled>Upload</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    setupUploadModalListeners();
}

function setupUploadModalListeners() {
    const uploadZone = pageRoot.querySelector('#wsUploadZone');
    const fileInput = pageRoot.querySelector('#wsFileInput');
    const confirmBtn = pageRoot.querySelector('#confirmUploadBtn');
    const closeBtn = pageRoot.querySelector('#closeUploadModalBtn');
    const cancelBtn = pageRoot.querySelector('#cancelUploadBtn');

    if (closeBtn) closeBtn.addEventListener('click', closeUploadModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeUploadModal);

    if (uploadZone) {
        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length) handleWorkspaceFile(files[0]);
        });
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleWorkspaceFile(e.target.files[0]);
        });
    }

    if (confirmBtn) confirmBtn.addEventListener('click', uploadWorkspaceFile);
}

function handleWorkspaceFile(file) {
    const allowedTypes = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'application/x-msexcel',
        'application/x-excel'
    ];

    if (!allowedTypes.includes(file.type)) {
        showToast('Invalid file type', 'danger');
        return;
    }
    if (file.size > 10 * 1024 * 1024) {
        showToast('File too large (max 10MB)', 'danger');
        return;
    }

    workspaceUploadSelectedFile = file;
    const selectedLabel = pageRoot.querySelector('#wsSelectedFile');
    if (selectedLabel) selectedLabel.textContent = file.name;
    const confirmBtn = pageRoot.querySelector('#confirmUploadBtn');
    if (confirmBtn) confirmBtn.disabled = false;
}

function uploadWorkspaceFile() {
    if (!workspaceUploadSelectedFile) return;

    const formData = new FormData();
    formData.append('file', workspaceUploadSelectedFile);

    const progressBar = pageRoot.querySelector('#wsProgressBar');
    if (progressBar) progressBar.style.display = 'block';

    const confirmBtn = pageRoot.querySelector('#confirmUploadBtn');
    if (confirmBtn) confirmBtn.disabled = true;

    fetch('/api/files/upload', {
        method: 'POST',
        body: formData
    })
        .then((r) => r.json())
        .then((result) => {
            if (progressBar) progressBar.style.display = 'none';
            if (result.status) {
                return fetch(`/api/workspaces/${currentWorkspaceId}/add-file`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ file_id: result.file_id })
                }).then((r) => r.json());
            } else {
                showToast(result.error || 'Upload failed', 'danger');
                if (confirmBtn) confirmBtn.disabled = false;
                throw new Error('Upload failed');
            }
        })
        .then((addResult) => {
            if (addResult && addResult.status) {
                showToast('Uploaded successfully', 'success');
                closeUploadModal();
                loadWorkspaceDetails();
            } else {
                showToast(addResult?.error || 'Failed to add to workspace', 'danger');
                if (confirmBtn) confirmBtn.disabled = false;
            }
        })
        .catch((err) => {
            if (progressBar) progressBar.style.display = 'none';
            if (err.message !== 'Upload failed') {
                showToast('Upload failed', 'danger');
                if (confirmBtn) confirmBtn.disabled = false;
            }
        });
}

function closeUploadModal() {
    workspaceUploadSelectedFile = null;
    const modal = pageRoot.querySelector('#noteEditorModal');
    if (modal) modal.innerHTML = '';
}
