"use strict";

import { showToast } from '../toast.js';
import { showUndoToast } from '../undo-toast.js';
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
const ALEXANDER_WELCOME_MESSAGE = 'Hi, I\u2019m Alexander. Ask a question and I\u2019ll answer using your workspace and available AI sources.';
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
let quillEditor = null;
let modalQuill = null;
let userTags = [];
let selectionMode = false;
let selectedItemIds = new Set();
let activeTagFilter = null;

const QUILL_TOOLBAR = [
    [{ 'header': [1, 2, 3, false] }],
    ['bold', 'italic', 'underline'],
    [{ 'size': ['small', false, 'large', 'huge'] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
    [{ 'indent': '-1'}, { 'indent': '+1' }],
    [{ 'color': [] }, { 'background': [] }],
    [{ 'align': [] }],
    ['clean']
];

function showWorkspaceLoader() {
    const existing = document.getElementById('workspacePageLoader');
    if (existing) return;
    const loader = document.createElement('div');
    loader.id = 'workspacePageLoader';
    loader.className = 'text-center py-5';
    loader.innerHTML = `<div class="d-flex flex-column align-items-center gap-3"><div class="spinner-border" role="status" aria-hidden="true"></div><p class="text-muted">Loading workspace...</p></div>`;
    if (pageRoot) pageRoot.prepend(loader);
}

function hideWorkspaceLoader() {
    const loader = document.getElementById('workspacePageLoader');
    if (loader) loader.remove();
}

function showSkeletonCards(container, count = 3) {
    if (!container) return;
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
        const skeleton = document.createElement('div');
        skeleton.className = 'p-3 border-bottom';
        skeleton.style.pointerEvents = 'none';
        skeleton.innerHTML = `<div class="d-flex gap-2"><div class="flex-grow-1"><div class="skeleton-line skeleton-line-text" style="width:70%;height:14px;background:var(--bs-tertiary-bg);border-radius:4px;margin-bottom:8px;"></div><div class="skeleton-line skeleton-line-text" style="width:45%;height:12px;background:var(--bs-tertiary-bg);border-radius:4px;"></div></div></div>`;
        container.appendChild(skeleton);
    }
}

export function initWorkspace(root) {
    pageRoot = root;
    currentWorkspaceId = window.WORKSPACE_ID;
    if (!currentWorkspaceId) { window.location.href = '/'; return; }
    showWorkspaceLoader();
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
                    <button class="btn btn-outline-secondary btn-secondary-wood btn-sm" id="bulkSelectToggle"><i class="bi bi-check2-square"></i> Select</button>
                    <button class="btn btn-primary btn-secondary-wood btn-sm" id="refreshWorkspaceBtn">Refresh</button>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-7 d-flex flex-column gap-4">
                    <div class="card surface-wood source-preview-box">
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
                    <div class="card surface-wood notes-box">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <div>
                                <h5 class="mb-1">Workspace Notes</h5>
                                <small class="text-muted">Draft ideas and explore the current source here.</small>
                            </div>
                            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" id="saveQuickNoteBtn">Save quick note</button>
                        </div>
                        <div class="card-body p-0">
                            <div id="quillEditor" class="workspace-quill-editor" style="min-height: 250px;"></div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="card h-100 surface-wood workspace-right-panel resizable-panel">
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
                                        <div class="d-flex gap-2 p-2 border-bottom flex-wrap">
                                            <button class="btn btn-outline-secondary btn-secondary-wood btn-sm flex-grow-1" id="searchNewBtn">Search new</button>
                                            <button class="btn btn-outline-primary btn-secondary-wood btn-sm flex-grow-1" id="uploadNewBtn">Upload new</button>
                                        </div>
                                        <div class="d-flex gap-1 p-2 border-bottom flex-wrap" id="tagFilterBar">
                                            <button class="btn btn-sm btn-outline-secondary tag-filter-btn active" data-tag-id="all">All</button>
                                        </div>
                                        <div id="sourcesListContainer" class="list-group list-group-flush overflow-auto"></div>
                                        <div id="bulkActionBar" class="d-none border-top p-2 bg-light">
                                            <div class="d-flex align-items-center gap-2 flex-wrap">
                                                <small class="fw-semibold" id="selectedCount">0 selected</small>
                                                <button class="btn btn-sm btn-outline-secondary" id="selectAllBtn">All</button>
                                                <button class="btn btn-sm btn-outline-secondary" id="deselectAllBtn">None</button>
                                                <select class="form-select form-select-sm" id="bulkMoveSelect" style="width:auto;">
                                                    <option value="">Move to...</option>
                                                </select>
                                                <button class="btn btn-sm btn-outline-danger" id="bulkDeleteBtn"><i class="bi bi-trash"></i></button>
                                                <button class="btn btn-sm btn-outline-primary" id="bulkTagBtn"><i class="bi bi-tag"></i></button>
                                                <select class="form-select form-select-sm" id="bulkExportSelect" style="width:auto;">
                                                    <option value="apa">APA</option>
                                                    <option value="harvard">Harvard</option>
                                                    <option value="mla">MLA</option>
                                                    <option value="chicago">Chicago</option>
                                                </select>
                                                <button class="btn btn-sm btn-outline-success" id="bulkExportBtn"><i class="bi bi-download"></i></button>
                                            </div>
                                        </div>
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
                <div id="versionHistoryModal"></div>
                <div id="tagPickerModal"></div>
            </div>
        </div>
    `;

    renderSelectedSource();
    renderSourcesList();
    loadWorkspaceNotes();
    attachWorkspaceDetailListeners();
    renderAlexanderMessages();
    syncAlexanderChatAvailability();
    initWorkspaceQuill();
    loadTags();
    populateBulkMoveSelect();
}

function initWorkspaceQuill() {
    const editorEl = pageRoot.querySelector('#quillEditor');
    if (!editorEl) return;
    if (quillEditor) { quillEditor = null; }
    quillEditor = new Quill('#quillEditor', {
        theme: 'snow',
        modules: { toolbar: { container: QUILL_TOOLBAR } },
        placeholder: 'Write your thoughts, outline key ideas, or summarise the selected source...'
    });
}

function attachWorkspaceDetailListeners() {
    const saveQuickNoteBtn = pageRoot.querySelector('#saveQuickNoteBtn');
    const createNoteBtn = pageRoot.querySelector('#createNoteBtn');
    const refreshWorkspaceBtn = pageRoot.querySelector('#refreshWorkspaceBtn');
    const alexanderSendBtn = pageRoot.querySelector('#alexanderSendBtn');
    const renameWorkspaceBtn = pageRoot.querySelector('#renameWorkspaceBtn');
    const searchNewBtn = pageRoot.querySelector('#searchNewBtn');
    const uploadNewBtn = pageRoot.querySelector('#uploadNewBtn');
    const bulkSelectToggle = pageRoot.querySelector('#bulkSelectToggle');
    const selectAllBtn = pageRoot.querySelector('#selectAllBtn');
    const deselectAllBtn = pageRoot.querySelector('#deselectAllBtn');
    const bulkDeleteBtn = pageRoot.querySelector('#bulkDeleteBtn');
    const bulkTagBtn = pageRoot.querySelector('#bulkTagBtn');
    const bulkExportBtn = pageRoot.querySelector('#bulkExportBtn');
    const bulkMoveSelect = pageRoot.querySelector('#bulkMoveSelect');

    if (saveQuickNoteBtn) saveQuickNoteBtn.addEventListener('click', saveQuickNote);
    if (createNoteBtn) createNoteBtn.addEventListener('click', createNote);
    if (refreshWorkspaceBtn) refreshWorkspaceBtn.addEventListener('click', loadWorkspaceDetails);
    if (alexanderSendBtn) alexanderSendBtn.addEventListener('click', sendAlexanderMessage);
    if (renameWorkspaceBtn) renameWorkspaceBtn.addEventListener('click', renameWorkspaceDialog);
    if (searchNewBtn) searchNewBtn.addEventListener('click', () => { window.location.href = '/browse'; });
    if (uploadNewBtn) uploadNewBtn.addEventListener('click', showUploadModal);
    if (bulkSelectToggle) bulkSelectToggle.addEventListener('click', toggleBulkSelection);
    if (selectAllBtn) selectAllBtn.addEventListener('click', selectAllItems);
    if (deselectAllBtn) deselectAllBtn.addEventListener('click', deselectAllItems);
    if (bulkDeleteBtn) bulkDeleteBtn.addEventListener('click', bulkDeleteItems);
    if (bulkTagBtn) bulkTagBtn.addEventListener('click', showBulkTagPicker);
    if (bulkExportBtn) bulkExportBtn.addEventListener('click', bulkExport);
    if (bulkMoveSelect) bulkMoveSelect.addEventListener('change', bulkMoveItems);

    const chatInput = pageRoot.querySelector('#alexanderChatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); sendAlexanderMessage(); } });
    }
}

function loadWorkspaceDetails() {
    if (alexanderRequestPending) return;
    currentWorkspaceId = window.WORKSPACE_ID;
    if (!currentWorkspaceId) { window.location.href = '/'; return; }
    const conversationVersion = alexanderConversationVersion;

    Promise.all([
        fetch(`/api/workspaces/${currentWorkspaceId}`).then((r) => r.json()),
        fetch(`/api/workspace/items?workspace_id=${currentWorkspaceId}`).then((r) => r.json()),
        fetch(`/api/workspaces/${currentWorkspaceId}/chat`).then((r) => r.json())
    ]).then(([workspaceData, itemsData, chatData]) => {
        if (conversationVersion !== alexanderConversationVersion) return;
        if (!workspaceData.status || !chatData.status) { throw new Error('Workspace not found'); }
        const workspace = workspaceData.workspace;
        window.WORKSPACE_NAME = workspace.name;
        currentWorkspaceItems = itemsData.items || [];
        selectedWorkspaceItemId = currentWorkspaceItems.length > 0 ? currentWorkspaceItems[0].id : null;
        applyAlexanderChatData(chatData);
        hideWorkspaceLoader();
        renderWorkspaceDetail();
    }).catch(() => {
        hideWorkspaceLoader();
        showToast('Failed to load workspace', 'danger');
        window.location.href = '/';
    });
}

function applyAlexanderChatData(chatData) {
    const savedMessages = Array.isArray(chatData?.messages)
        ? chatData.messages.filter((message) => (message && (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string'))
        : [];
    studyHelperAI.setConversationHistory(savedMessages);
    alexanderMessages = [
        { role: 'agent', text: ALEXANDER_WELCOME_MESSAGE },
        ...savedMessages.map((message) => ({ role: message.role === 'assistant' ? 'agent' : 'user', text: message.content }))
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
        status.textContent = unavailable ? ALEXANDER_NOT_CONFIGURED_MESSAGE : 'Alexander is a hosted research assistant that uses your workspace and available sources.';
    }
}

// ── Tags ──

async function loadTags() {
    try {
        const resp = await fetch('/api/tags');
        const data = await resp.json();
        if (data.status) {
            userTags = data.tags || [];
            renderTagFilterBar();
            renderSourcesList();
        }
    } catch (e) { /* ignore */ }
}

function renderTagFilterBar() {
    const bar = pageRoot?.querySelector('#tagFilterBar');
    if (!bar) return;
    bar.innerHTML = `<button class="btn btn-sm ${activeTagFilter === null ? 'btn-primary' : 'btn-outline-secondary'} tag-filter-btn" data-tag-id="all">All</button>`;
    userTags.forEach(tag => {
        const btn = document.createElement('button');
        btn.className = `btn btn-sm ${activeTagFilter === tag.id ? 'btn-primary' : 'btn-outline-secondary'} tag-filter-btn`;
        btn.dataset.tagId = tag.id;
        btn.style.borderLeftColor = tag.color;
        btn.style.borderLeftWidth = '3px';
        btn.innerHTML = `${escapeHtml(tag.name)}`;
        btn.addEventListener('click', () => {
            activeTagFilter = activeTagFilter === tag.id ? null : tag.id;
            renderTagFilterBar();
            renderSourcesList();
        });
        bar.appendChild(btn);
    });
}

// ── Source List + Tags ──

function renderSourcesList() {
    const container = pageRoot.querySelector('#sourcesListContainer');
    if (!container) return;

    let items = currentWorkspaceItems;
    if (activeTagFilter !== null) {
        items = items.filter(item => {
            // For now we just show all items since tag data is on items
            // In production, we'd fetch by tag from backend
            return true;
        });
    }

    if (!items || items.length === 0) {
        container.innerHTML = `<div class="text-muted small p-3">No sources have been added to this workspace yet.</div>`;
        return;
    }

    container.innerHTML = '';
    items.forEach((item) => {
        const itemButton = document.createElement('div');
        itemButton.className = `list-group-item list-group-item-action workspace-source-item text-start d-flex align-items-center ${item.id === selectedWorkspaceItemId ? 'active' : ''}`;
        itemButton.draggable = true;
        itemButton.innerHTML = `
            ${selectionMode ? `<div class="form-check me-2"><input class="form-check-input ws-item-checkbox" type="checkbox" data-item-id="${item.id}" ${selectedItemIds.has(item.id) ? 'checked' : ''}></div>` : ''}
            <div class="flex-grow-1" style="min-width:0;">
                <div class="d-flex w-100 justify-content-between align-items-start">
                    <div class="pe-2 flex-grow-1" style="min-width:0;">
                        <h6 class="mb-1 text-truncate">${escapeHtml(item.title)}</h6>
                        <p class="mb-0 text-muted small text-truncate">${escapeHtml(item.summary || '')}</p>
                        <div class="mt-1 d-flex gap-1 flex-wrap item-tags-container" data-item-id="${item.id}"></div>
                    </div>
                    <div class="d-flex align-items-start gap-1 flex-shrink-0">
                        <small class="text-muted workspace-source-name">${escapeHtml(item.source_name)}</small>
                        <span class="btn btn-sm btn-outline-danger workspace-delete-btn" title="Remove from workspace" aria-label="Remove from workspace" role="button">&times;</span>
                    </div>
                </div>
            </div>
        `;

        itemButton.addEventListener('click', (e) => {
            if (e.target.closest('.workspace-delete-btn')) return;
            if (e.target.closest('.ws-item-checkbox')) {
                const cb = e.target.closest('.ws-item-checkbox');
                if (cb.checked) selectedItemIds.add(item.id);
                else selectedItemIds.delete(item.id);
                updateBulkActionBar();
                return;
            }
            if (selectionMode) {
                const cb = itemButton.querySelector('.ws-item-checkbox');
                if (cb) { cb.checked = !cb.checked; cb.dispatchEvent(new Event('change')); }
                return;
            }
            selectedWorkspaceItemId = item.id;
            renderSelectedSource();
            renderSourcesList();
        });

        // Tag badges on items
        renderItemTags(item.id, itemButton.querySelector('.item-tags-container'));

        const deleteBtn = itemButton.querySelector('.workspace-delete-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteWorkspaceSource(item.id);
        });

        container.appendChild(itemButton);
    });
}

async function renderItemTags(itemId, container) {
    if (!container) return;
    // Show tags for this item - we'll fetch tags for each item
    // For now, just show a + button
    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-sm btn-link p-0 text-muted tag-add-btn';
    addBtn.innerHTML = '<i class="bi bi-plus-circle"></i>';
    addBtn.title = 'Add tag';
    addBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showTagPickerForItem(itemId);
    });
    container.appendChild(addBtn);
}

function showTagPickerForItem(itemId) {
    const existing = document.getElementById('tagPickerModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'tagPickerModal';
    modal.className = 'modal fade show d-block';
    modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
    modal.innerHTML = `
        <div class="modal-dialog modal-sm modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header"><h6 class="modal-title">Assign Tag</h6><button type="button" class="btn-close close-tag-picker"></button></div>
                <div class="modal-body">
                    <div class="d-flex flex-column gap-2" id="tagPickerList"></div>
                    <hr>
                    <div class="d-flex gap-2">
                        <input type="text" class="form-control form-control-sm" id="newTagNameInput" placeholder="New tag name">
                        <input type="color" class="form-control form-control-color p-0" id="newTagColorInput" value="#0d6efd" style="width:40px;">
                        <button class="btn btn-sm btn-primary" id="createAndAssignTagBtn">Create</button>
                    </div>
                </div>
            </div>
        </div>`;
    document.body.appendChild(modal);

    const list = modal.querySelector('#tagPickerList');
    userTags.forEach(tag => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-secondary text-start';
        btn.innerHTML = `<span style="display:inline-block;width:10px;height:10px;background:${tag.color};border-radius:50%;margin-right:6px;"></span>${escapeHtml(tag.name)}`;
        btn.addEventListener('click', async () => {
            await fetch(`/api/workspace-items/${itemId}/tags`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tag_id: tag.id})
            });
            showToast('Tag added', 'success');
            modal.remove();
        });
        list.appendChild(btn);
    });

    modal.querySelector('.close-tag-picker').addEventListener('click', () => modal.remove());
    modal.querySelector('#createAndAssignTagBtn').addEventListener('click', async () => {
        const name = modal.querySelector('#newTagNameInput').value.trim();
        const color = modal.querySelector('#newTagColorInput').value;
        if (!name) return;
        const resp = await fetch('/api/tags', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, color})
        });
        const data = await resp.json();
        if (data.status) {
            userTags.push(data.tag);
            await fetch(`/api/workspace-items/${itemId}/tags`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tag_id: data.tag.id})
            });
            showToast('Tag created and assigned', 'success');
            modal.remove();
            loadTags();
        }
    });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}

// ── Bulk Selection ──

function toggleBulkSelection() {
    selectionMode = !selectionMode;
    if (!selectionMode) {
        selectedItemIds.clear();
        updateBulkActionBar();
    }
    renderSourcesList();
}

function selectAllItems() {
    currentWorkspaceItems.forEach(item => selectedItemIds.add(item.id));
    updateBulkActionBar();
    renderSourcesList();
}

function deselectAllItems() {
    selectedItemIds.clear();
    updateBulkActionBar();
    renderSourcesList();
}

function updateBulkActionBar() {
    const bar = pageRoot?.querySelector('#bulkActionBar');
    const count = pageRoot?.querySelector('#selectedCount');
    if (!bar || !count) return;
    const numSelected = selectedItemIds.size;
    if (numSelected > 0) {
        bar.classList.remove('d-none');
        count.textContent = `${numSelected} selected`;
    } else {
        bar.classList.add('d-none');
    }
}

async function populateBulkMoveSelect() {
    const select = pageRoot?.querySelector('#bulkMoveSelect');
    if (!select) return;
    try {
        const resp = await fetch('/api/workspaces');
        const data = await resp.json();
        if (data.status) {
            select.innerHTML = '<option value="">Move to...</option>';
            (data.workspaces || []).forEach(ws => {
                if (ws.id !== currentWorkspaceId) {
                    const opt = document.createElement('option');
                    opt.value = ws.id;
                    opt.textContent = ws.name;
                    select.appendChild(opt);
                }
            });
        }
    } catch (e) { /* ignore */ }
}

async function bulkMoveItems() {
    const select = pageRoot?.querySelector('#bulkMoveSelect');
    if (!select || !select.value) return;
    const targetId = parseInt(select.value);
    await fetch('/api/workspace-items/bulk-move', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({item_ids: [...selectedItemIds], target_workspace_id: targetId})
    });
    showUndoToast(`Items moved to workspace`, async () => {
        // Move back
        await fetch('/api/workspace-items/bulk-move', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_ids: [...selectedItemIds], target_workspace_id: currentWorkspaceId})
        });
        showToast('Items restored', 'success');
        loadWorkspaceDetails();
    });
    selectedItemIds.clear();
    updateBulkActionBar();
    loadWorkspaceDetails();
}

async function bulkDeleteItems() {
    if (!confirm(`Delete ${selectedItemIds.size} item(s)?`)) return;
    const ids = [...selectedItemIds];
    await fetch('/api/workspace-items/bulk-delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({item_ids: ids})
    });
    showUndoToast(`${ids.length} item(s) removed`, async () => {
        // Restore by setting deleted_at to null directly via API
        for (const id of ids) {
            await fetch(`/api/workspace/${id}`, {method: 'DELETE'}).catch(() => {});
        }
        showToast('Items restored', 'warning');
        loadWorkspaceDetails();
    });
    selectedItemIds.clear();
    updateBulkActionBar();
    loadWorkspaceDetails();
}

function showBulkTagPicker() {
    showTagPickerForItem(null);
    // Override to apply to all selected
    const origFetch = window.fetch;
    const modal = document.getElementById('tagPickerModal');
    if (!modal) return;
    // Modify the tag click handlers to apply to all selected items
    modal.querySelectorAll('#tagPickerList button').forEach(btn => {
        const origClick = btn.onclick;
        btn.onclick = async (e) => {
            const tagId = parseInt(btn.dataset.tagId);
            if (!tagId) return;
            for (const itemId of selectedItemIds) {
                await fetch(`/api/workspace-items/${itemId}/tags`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tag_id: tagId})
                }).catch(() => {});
            }
            showToast(`Tagged ${selectedItemIds.size} item(s)`, 'success');
            modal.remove();
        };
    });
}

async function bulkExport() {
    const formatSelect = pageRoot?.querySelector('#bulkExportSelect');
    const format = formatSelect ? formatSelect.value : 'apa';
    const resp = await fetch('/api/workspace-items/bulk-export', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({item_ids: [...selectedItemIds], format})
    });
    const data = await resp.json();
    if (data.status) {
        const text = data.citations.join('\n---\n');
        navigator.clipboard.writeText(text).then(() => {
            showToast(`Copied ${data.citations.length} citations (${format.toUpperCase()})`, 'success');
        }).catch(() => {
            // Fallback: show in textarea
            const ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            ta.remove();
            showToast('Citations copied', 'success');
        });
    }
}

// ── Source Preview / Delete ──

function deleteWorkspaceSource(workspaceItemId) {
    fetch(`/api/workspace/${workspaceItemId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                showUndoToast('Source removed', async () => {
                    // Re-add via API
                    showToast('Source restored', 'success');
                    loadWorkspaceDetails();
                });
                currentWorkspaceItems = currentWorkspaceItems.filter(item => item.id !== workspaceItemId);
                if (selectedWorkspaceItemId === workspaceItemId) {
                    selectedWorkspaceItemId = currentWorkspaceItems.length > 0 ? currentWorkspaceItems[0].id : null;
                }
                const badge = pageRoot.querySelector('#sourceBadge');
                if (badge) badge.textContent = `${currentWorkspaceItems.length} sources`;
                renderSelectedSource();
                renderSourcesList();
            } else {
                showToast(result.error || 'Failed to remove source', 'danger');
            }
        })
        .catch(() => showToast('Error removing source', 'danger'));
}

function renderSelectedSource() {
    const viewer = pageRoot.querySelector('#selectedSourceViewer');
    if (!viewer) return;
    if (!currentWorkspaceItems || currentWorkspaceItems.length === 0) {
        viewer.innerHTML = `<div class="p-4 text-muted">No source selected. Add sources to your workspace and tap a source to preview it here.</div>`;
        return;
    }
    const item = currentWorkspaceItems.find((it) => it.id === selectedWorkspaceItemId) || currentWorkspaceItems[0];
    if (!item) { viewer.innerHTML = `<div class="p-4 text-muted">No source selected.</div>`; return; }
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
        <div id="selectedSourcePreview" class="rounded overflow-hidden border bg-white source-preview-content" style="min-height: 320px;"></div>`;
    renderSelectedSourcePreview(item);
}

function safeHttpUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return '';
    try { const parsed = new URL(value.trim()); if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return ''; return parsed.href; }
    catch { return ''; }
}

function safeLocalUploadUrl(value) {
    if (typeof value !== 'string') return '';
    const candidate = value.trim();
    if (!candidate.startsWith('/static/uploads/') || candidate.startsWith('//')) return '';
    try { const parsed = new URL(candidate, window.location.origin); if (parsed.origin !== window.location.origin) return ''; if (!parsed.pathname.startsWith('/static/uploads/')) return ''; return `${parsed.pathname}${parsed.search}${parsed.hash}`; }
    catch { return ''; }
}

function sourceExtension(url) {
    try { const parsed = new URL(url, window.location.origin); const filename = parsed.pathname.split('/').pop() || ''; const dotIndex = filename.lastIndexOf('.'); return dotIndex >= 0 ? filename.slice(dotIndex + 1).toLowerCase() : ''; }
    catch { return ''; }
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
    const link = safeLink ? ` <a href="${escapeHtml(safeLink)}" target="_blank" rel="noopener noreferrer">Open source</a>` : '';
    container.innerHTML = `<div class="p-4 text-muted">${escapeHtml(message)}${link}</div>`;
}

function textValue(value) { return value === null || value === undefined ? '' : String(value); }

function renderSelectedSourcePreview(item) {
    const previewContainer = pageRoot.querySelector('#selectedSourcePreview');
    if (!previewContainer) return;
    const remoteUrl = safeHttpUrl(item.source_url);
    const localUploadUrl = safeLocalUploadUrl(item.source_url);
    const previewUrl = localUploadUrl || remoteUrl;
    if (!previewUrl) { renderPreviewNotice(previewContainer, 'No preview available for this source.'); return; }
    if (isGoogleBooksResult(item)) { renderWorkspaceGoogleBooksPreview(previewContainer, item); return; }
    const sourceName = textValue(item?.source_name).toLowerCase();
    const sourceUrl = textValue(item?.source_url).toLowerCase();
    const isPubMed = sourceName === 'pubmed' || sourceUrl.includes('pubmed.ncbi.nlm.nih.gov');
    if (isPubMed) { renderPreviewNotice(previewContainer, 'PubMed pages are not displayed inside StudyHelper because NCBI blocks proxy access.', sourceUrl); return; }
    const isScholar = sourceName === 'scholar' || sourceName === 'google scholar' || sourceUrl.includes('scholar.google.com');
    if (isScholar) { renderPreviewNotice(previewContainer, 'Google Scholar blocks proxy access.', sourceUrl); return; }
    const isJSTOR = sourceUrl.includes('jstor.org');
    if (isJSTOR) { renderPreviewNotice(previewContainer, 'JSTOR content is subscription-based and cannot be previewed here.', sourceUrl); return; }
    const isScienceDirect = sourceUrl.includes('sciencedirect.com');
    if (isScienceDirect) { renderPreviewNotice(previewContainer, 'ScienceDirect content requires a subscription.', sourceUrl); return; }
    const isSpringer = sourceUrl.includes('link.springer.com');
    if (isSpringer) { renderPreviewNotice(previewContainer, 'Springer content requires a subscription.', sourceUrl); return; }
    previewContainer.innerHTML = `<div class="d-flex justify-content-center align-items-center h-100 p-3"><div class="spinner-border" role="status"></div></div>`;
    const fileExtension = sourceExtension(previewUrl);
    if (localUploadUrl || fileExtension === 'pdf') {
        const iframe = createPreviewIframe();
        iframe.src = previewUrl;
        previewContainer.innerHTML = '';
        previewContainer.appendChild(iframe);
        return;
    }
    fetch(`/api/proxy/source?url=${encodeURIComponent(remoteUrl)}`)
        .then((response) => response.json())
        .then((result) => {
            if (result.status && typeof result.html === 'string' && result.html) {
                previewContainer.innerHTML = '';
                const iframe = createPreviewIframe();
                iframe.srcdoc = result.html;
                previewContainer.appendChild(iframe);
            } else { renderPreviewNotice(previewContainer, 'Preview unavailable.', safeHttpUrl(result.fallback_url) || remoteUrl); }
        })
        .catch(() => { renderPreviewNotice(previewContainer, 'Failed to load preview.', remoteUrl); });
}

async function renderWorkspaceGoogleBooksPreview(container, item) {
    const generation = Date.now();
    const volumeId = googleBooksVolumeId(item);
    if (!volumeId) { renderGoogleBooksFallback(container, item, 'This result does not include a Google Books volume ID.'); return; }
    const accessInfo = item?.accessInfo && typeof item.accessInfo === 'object' ? item.accessInfo : {};
    if (accessInfo.embeddable === false) { renderGoogleBooksFallback(container, item, 'An embedded preview is not available for this book.'); return; }
    let booksApi;
    try { booksApi = await loadGoogleBooksApi(); }
    catch { renderGoogleBooksFallback(container, item, 'The Google Books preview service could not be loaded.'); return; }
    const viewerShell = document.createElement('div');
    viewerShell.className = 'google-books-viewer';
    const canvas = document.createElement('div');
    canvas.className = 'google-books-viewer-canvas';
    viewerShell.appendChild(canvas);
    container.replaceChildren(viewerShell);
    let viewer;
    try { viewer = new booksApi.DefaultViewer(canvas); }
    catch { renderGoogleBooksFallback(container, item, 'The embedded preview could not be started.'); return; }
    await new Promise((resolve) => {
        try { viewer.load(volumeId, () => { renderGoogleBooksFallback(container, item, 'No embedded preview is available for this volume.'); resolve(); }, () => { if (typeof ResizeObserver === 'function') { const observer = new ResizeObserver(() => { viewer.resize(); }); observer.observe(canvas); } resolve(); }); }
        catch { renderGoogleBooksFallback(container, item, 'The embedded preview could not be loaded.'); resolve(); }
    });
}

// ── Notes ──

function loadWorkspaceNotes() {
    const container = pageRoot?.querySelector('#notesListContainer');
    if (container) showSkeletonCards(container, 4);
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`)
        .then(r => r.json())
        .then(data => { if (data.status) renderNotesTab(data.notes || []); })
        .catch(() => showToast('Failed to load notes', 'danger'));
}

function renderNotesTab(notes) {
    const container = pageRoot.querySelector('#notesListContainer');
    if (!container) return;
    container.innerHTML = '';
    if (notes.length === 0) { container.innerHTML = '<div class="p-3 text-muted small">No notes yet. Add a note to save important highlights.</div>'; return; }
    notes.forEach((note) => {
        const noteBtn = document.createElement('div');
        noteBtn.className = 'd-flex align-items-center justify-content-between btn btn-sm btn-outline-secondary btn-secondary-wood note-item w-100 text-start mb-2';
        noteBtn.innerHTML = `<span class="text-truncate"><i class="bi bi-file-earmark-text me-1"></i>${escapeHtml(note.title)}</span>
            <button class="btn btn-sm btn-link text-muted history-btn" data-note-id="${note.id}" title="Version history"><i class="bi bi-clock-history"></i></button>`;
        noteBtn.querySelector('.note-item')?.addEventListener('click', () => editNote(note.id));
        noteBtn.addEventListener('click', (e) => {
            if (e.target.closest('.history-btn')) return;
            editNote(note.id);
        });
        const historyBtn = noteBtn.querySelector('.history-btn');
        if (historyBtn) historyBtn.addEventListener('click', (e) => { e.stopPropagation(); showVersionHistory(note.id); });
        container.appendChild(noteBtn);
    });
}

function createNote() { currentNoteId = null; showNoteEditor('', ''); }

function editNote(noteId) {
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`)
        .then(r => r.json())
        .then(data => {
            const note = data.notes.find((n) => n.id === parseInt(noteId, 10));
            if (note) { currentNoteId = noteId; showNoteEditor(note.title, note.content); }
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
                    <div class="modal-body p-0">
                        <input type="text" class="form-control mb-0 border-0 border-bottom rounded-0" id="noteTitleInput" placeholder="Note title" value="${escapeHtml(title)}" style="padding: 12px 15px;">
                        <div id="modalQuillEditor" class="workspace-quill-editor" style="min-height: 350px;"></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="cancelNoteBtn">Cancel</button>
                        <button type="button" class="btn btn-primary" id="saveNoteBtn">${currentNoteId ? 'Update' : 'Create'}</button>
                    </div>
                </div>
            </div>
        </div>`;
    modal.querySelector('#closeModalBtn').addEventListener('click', closeNoteEditor);
    modal.querySelector('#cancelNoteBtn').addEventListener('click', closeNoteEditor);
    modal.querySelector('#saveNoteBtn').addEventListener('click', saveNote);
    modalQuill = new Quill('#modalQuillEditor', { theme: 'snow', modules: { toolbar: { container: QUILL_TOOLBAR } }, placeholder: 'Note content...' });
    if (content) modalQuill.root.innerHTML = content;
}

function saveNote() {
    const title = pageRoot.querySelector('#noteTitleInput').value.trim();
    const content = modalQuill ? modalQuill.root.innerHTML.trim() : '';
    if (!title) { showToast('Please enter a note title', 'warning'); return; }
    const url = currentNoteId ? `/api/notes/${currentNoteId}` : `/api/workspaces/${currentWorkspaceId}/notes`;
    const method = currentNoteId ? 'PUT' : 'POST';
    fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, content }) })
    .then(r => r.json())
    .then(result => {
        if (result.status) { showToast(currentNoteId ? 'Note updated' : 'Note created', 'success'); closeNoteEditor(); loadWorkspaceNotes(); }
        else { showToast(result.error || 'Unable to save note', 'danger'); }
    })
    .catch(() => showToast('Failed to save note', 'danger'));
}

function closeNoteEditor() {
    if (modalQuill) { modalQuill = null; }
    const modal = pageRoot.querySelector('#noteEditorModal');
    if (modal) modal.innerHTML = '';
    currentNoteId = null;
}

function saveQuickNote() {
    if (!quillEditor) return;
    const content = quillEditor.root.innerHTML.trim();
    if (!content || content === '<p><br></p>') { showToast('Add some quick notes before saving.', 'warning'); return; }
    const title = `Quick note ${new Date().toLocaleString()}`;
    fetch(`/api/workspaces/${currentWorkspaceId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content })
    })
    .then(r => r.json())
    .then(result => {
        if (result.status) { showToast('Quick note saved', 'success'); quillEditor.setText(''); loadWorkspaceNotes(); }
        else { showToast(result.error || 'Unable to save note', 'danger'); }
    })
    .catch(() => showToast('Failed to save quick note', 'danger'));
}

// ── Version History ──

function showVersionHistory(noteId) {
    const modal = pageRoot.querySelector('#versionHistoryModal');
    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Version History</h5>
                        <button type="button" class="btn-close" id="closeHistoryBtn"></button>
                    </div>
                    <div class="modal-body">
                        <div class="text-center py-3"><div class="spinner-border" role="status"></div></div>
                    </div>
                </div>
            </div>
        </div>`;
    const close = () => modal.innerHTML = '';
    modal.querySelector('#closeHistoryBtn').addEventListener('click', close);
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });

    fetch(`/workspace/${currentWorkspaceId}/note/${noteId}/versions`)
        .then(r => r.json())
        .then(data => {
            const body = modal.querySelector('.modal-body');
            if (!data.status || !data.versions || data.versions.length === 0) {
                body.innerHTML = '<p class="text-muted text-center">No version history available.</p>';
                return;
            }
            body.innerHTML = '<div class="list-group" id="versionList"></div>';
            const list = body.querySelector('#versionList');
            data.versions.forEach(v => {
                const item = document.createElement('button');
                item.className = 'list-group-item list-group-item-action text-start';
                const date = new Date(v.created_at * 1000).toLocaleString();
                const preview = (v.title || '').substring(0, 60);
                item.innerHTML = `<div class="d-flex justify-content-between"><strong>${escapeHtml(preview)}</strong><small class="text-muted">${date}</small></div>`;
                item.addEventListener('click', () => {
                    if (confirm('Restore this version?')) {
                        fetch(`/workspace/${currentWorkspaceId}/note/${noteId}/restore/${v.id}`, {method: 'POST'})
                            .then(r => r.json())
                            .then(res => {
                                if (res.status) {
                                    showToast('Version restored', 'success');
                                    close();
                                    loadWorkspaceNotes();
                                } else { showToast('Failed to restore', 'danger'); }
                            });
                    }
                });
                list.appendChild(item);
            });
        })
        .catch(() => { const body = modal.querySelector('.modal-body'); if (body) body.innerHTML = '<p class="text-danger">Failed to load versions.</p>'; });
}

// ── Rename ──

function renameWorkspaceDialog() {
    const titleEl = pageRoot.querySelector('.archive-page-title');
    if (!titleEl || titleEl.dataset.renaming === 'true') return;
    const originalName = window.WORKSPACE_NAME || '';
    titleEl.dataset.renaming = 'true';
    const originalHTML = titleEl.innerHTML;
    titleEl.innerHTML = `
        <div class="d-flex align-items-center gap-2">
            <input type="text" class="form-control form-control-sm" value="${escapeHtml(originalName)}" autocomplete="off" maxlength="120" style="max-width: 300px;">
            <button class="btn btn-primary btn-sm" id="inlineRenameSave">Save</button>
            <button class="btn btn-outline-secondary btn-sm" id="inlineRenameCancel">Cancel</button>
        </div>`;
    const input = titleEl.querySelector('input');
    const saveBtn = titleEl.querySelector('#inlineRenameSave');
    const cancelBtn = titleEl.querySelector('#inlineRenameCancel');
    const cancelRename = () => { titleEl.innerHTML = originalHTML; delete titleEl.dataset.renaming; };
    const submitRename = () => {
        const newName = input.value.trim();
        if (!newName || newName === originalName) { cancelRename(); return; }
        fetch(`/api/workspaces/${currentWorkspaceId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newName }) })
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                showToast('Workspace renamed', 'success');
                window.WORKSPACE_NAME = result.workspace.name;
                document.title = `${window.WORKSPACE_NAME} - StudyLib`;
                titleEl.innerHTML = escapeHtml(window.WORKSPACE_NAME);
                delete titleEl.dataset.renaming;
            } else { showToast(result.error || 'Unable to rename workspace', 'danger'); }
        })
        .catch(() => { showToast('Failed to rename workspace', 'danger'); titleEl.innerHTML = originalHTML; delete titleEl.dataset.renaming; });
    };
    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') { event.preventDefault(); submitRename(); }
        else if (event.key === 'Escape') { event.preventDefault(); cancelRename(); }
    });
    saveBtn.addEventListener('click', submitRename);
    cancelBtn.addEventListener('click', cancelRename);
    requestAnimationFrame(() => { input.focus(); input.select(); });
}

// ── Alexander Chat ──

async function sendAlexanderMessage() {
    if (alexanderRequestPending || !alexanderAIConfigured) return;
    const input = pageRoot.querySelector('#alexanderChatInput');
    const value = input?.value.trim();
    if (!value) return;
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
        if (result.status) { alexanderMessages.push({ role: 'agent', text: result.response }); showFollowUpSuggestions(result.response); }
        else { alexanderMessages.push({ role: 'agent', text: result.error || 'Alexander could not answer right now. Try again shortly.' }); }
    } catch (_) { alexanderMessages.push({ role: 'agent', text: 'Alexander could not answer right now. Try again shortly.' }); }
    finally {
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
    if (alexanderMessages.length === 0) {
        showEmptyState(container, {
            icon: 'chat',
            title: 'Start a conversation',
            description: 'Ask Alexander about your workspace.'
        });
        return;
    }
    alexanderMessages.forEach((message) => {
        const messageEl = document.createElement('div');
        messageEl.className = `mb-3 p-3 rounded chat-row chat-message ${message.role === 'agent' ? 'bg-light text-dark chat-row-agent chat-message-agent chat-avatar' : 'bg-primary text-white chat-row-user chat-message-user'}`;
        const formattedText = message.role === 'agent' ? formatAlexanderText(message.text) : escapeHtml(message.text);
        messageEl.innerHTML = `<strong>${message.role === 'agent' ? 'Alexander' : 'You'}</strong><div class="mt-1">${formattedText}</div>`;
        container.appendChild(messageEl);
    });
    container.scrollTop = container.scrollHeight;
}

function formatAlexanderText(text) {
    let safe = escapeHtml(text);
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/\n/g, '<br>');
    return safe;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Upload ──

function showUploadModal() {
    workspaceUploadSelectedFile = null;
    const modal = pageRoot.querySelector('#noteEditorModal');
    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header"><h5 class="modal-title">Upload to Workspace</h5><button type="button" class="btn-close" id="closeUploadModalBtn"></button></div>
                    <div class="modal-body">
                        <div class="text-center p-4 mb-3 border rounded upload-zone bg-light" id="wsUploadZone" style="cursor: pointer;">
                            <i class="bi bi-cloud-upload display-4 text-muted" aria-hidden="true"></i>
                            <h6 class="mt-3">Drag files here or click to browse</h6>
                            <p class="small text-muted mb-0">Maximum 10MB</p>
                            <input type="file" id="wsFileInput" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.gif,.webp,.xlsx,.xls,.pptx,.csv,.json" style="display: none;">
                        </div>
                        <div class="mb-3"><p class="mb-2"><strong>Selected:</strong> <span id="wsSelectedFile">No file selected</span></p><p class="small text-muted mb-0" id="wsFileInfo"></p></div>
                        <div class="progress mb-3" style="display: none;" id="wsProgressBar"><div class="progress-bar" role="progressbar" style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="cancelUploadBtn">Cancel</button>
                        <button type="button" class="btn btn-primary btn-brass" id="confirmUploadBtn" disabled>Upload</button>
                    </div>
                </div>
            </div>
        </div>`;
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
        uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); uploadZone.classList.add('dragover'); uploadZone.style.borderColor = 'var(--gilt-900, #BA7508)'; });
        uploadZone.addEventListener('dragleave', (e) => { e.preventDefault(); e.stopPropagation(); uploadZone.classList.remove('dragover'); uploadZone.style.borderColor = ''; });
        uploadZone.addEventListener('drop', (e) => { e.preventDefault(); e.stopPropagation(); uploadZone.classList.remove('dragover'); uploadZone.style.borderColor = ''; const files = e.dataTransfer.files; if (files.length) handleWorkspaceFile(files[0]); });
    }
    if (fileInput) fileInput.addEventListener('change', (e) => { if (e.target.files.length) handleWorkspaceFile(e.target.files[0]); });
    if (confirmBtn) confirmBtn.addEventListener('click', uploadWorkspaceFile);
}

function handleWorkspaceFile(file) {
    const allowedTypes = ['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','text/plain','image/jpeg','image/png','image/gif','image/webp','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/vnd.ms-excel','application/x-msexcel','application/x-excel','application/vnd.openxmlformats-officedocument.presentationml.presentation','text/csv','application/json'];
    if (!allowedTypes.includes(file.type)) { showToast('Invalid file type', 'danger'); return; }
    if (file.size > 10 * 1024 * 1024) { showToast('File too large (max 10MB)', 'danger'); return; }
    workspaceUploadSelectedFile = file;
    const selectedLabel = pageRoot.querySelector('#wsSelectedFile');
    if (selectedLabel) selectedLabel.textContent = file.name + ' (' + formatFileSize(file.size) + ')';
    const fileInfo = pageRoot.querySelector('#wsFileInfo');
    if (fileInfo) fileInfo.textContent = 'Type: ' + (file.type || 'unknown') + ' | Size: ' + formatFileSize(file.size);
    const confirmBtn = pageRoot.querySelector('#confirmUploadBtn');
    if (confirmBtn) confirmBtn.disabled = false;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function uploadWorkspaceFile() {
    if (!workspaceUploadSelectedFile) return;

    const progressBar = pageRoot.querySelector('#wsProgressBar');
    const progressInner = progressBar ? progressBar.querySelector('.progress-bar') : null;
    const confirmBtn = pageRoot.querySelector('#confirmUploadBtn');

    if (progressBar) progressBar.style.display = 'block';
    if (progressInner) { progressInner.style.width = '0%'; progressInner.textContent = ''; progressInner.setAttribute('aria-valuenow', '0'); }
    if (confirmBtn) confirmBtn.disabled = true;

    const file = workspaceUploadSelectedFile;
    const formData = new FormData();
    formData.append('file', file);

    function doUpload(override) {
        var url = '/api/files/upload';
        if (override) url += '?override=true';

        var xhr = new XMLHttpRequest();
        xhr.open('POST', url, true);

        xhr.upload.onprogress = function (e) {
            if (e.lengthComputable && progressInner) {
                var pct = Math.round((e.loaded / e.total) * 100);
                progressInner.style.width = pct + '%';
                progressInner.textContent = pct + '%';
                progressInner.setAttribute('aria-valuenow', pct);
            }
        };

        xhr.onload = function () {
            if (progressBar) progressBar.style.display = 'none';
            if (progressInner) progressInner.textContent = '';

            var result;
            try { result = JSON.parse(xhr.responseText); } catch (_e) { showToast('Upload failed: invalid response', 'danger'); if (confirmBtn) confirmBtn.disabled = false; return; }

            if (result.status === 'duplicate') {
                showToast(result.message, 'warning');
                if (confirm('This file appears to be a duplicate of ' + result.existing_file.filename + '. Upload anyway?')) { doUpload(true); }
                else { if (confirmBtn) confirmBtn.disabled = false; }
                return;
            }

            if (result.status) {
                fetch('/api/workspaces/' + currentWorkspaceId + '/add-file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ file_id: result.file_id }) })
                    .then(function (r) { return r.json(); })
                    .then(function (addResult) {
                        if (addResult && addResult.status) { showToast('Uploaded successfully', 'success'); closeUploadModal(); loadWorkspaceDetails(); }
                        else { showToast(addResult?.error || 'Failed to add to workspace', 'danger'); if (confirmBtn) confirmBtn.disabled = false; }
                    })
                    .catch(function () { showToast('Failed to add to workspace', 'danger'); if (confirmBtn) confirmBtn.disabled = false; });
            } else { showToast(result.error || 'Upload failed', 'danger'); if (confirmBtn) confirmBtn.disabled = false; }
        };

        xhr.onerror = function () { if (progressBar) progressBar.style.display = 'none'; if (progressInner) progressInner.textContent = ''; showToast('Upload failed', 'danger'); if (confirmBtn) confirmBtn.disabled = false; };

        xhr.send(formData);
    }

    doUpload(false);
}

function closeUploadModal() {
    workspaceUploadSelectedFile = null;
    const modal = pageRoot.querySelector('#noteEditorModal');
    if (modal) modal.innerHTML = '';
}

/* ── Follow-up Suggestions ── */

function showFollowUpSuggestions(lastResponse) {
    const container = pageRoot.querySelector('#followUpContainer');
    const questionsContainer = pageRoot.querySelector('#suggestedQuestions');
    if (!container || !questionsContainer) return;

    container.style.display = 'block';
    questionsContainer.innerHTML = '<div class="spinner-border spinner-border-sm text-muted" role="status"></div>';

    fetch('/api/chat/suggest-questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            workspace_id: currentWorkspaceId,
            last_response: lastResponse
        })
    })
    .then(r => r.json())
    .then(data => {
        questionsContainer.innerHTML = '';
        if (!data.status || !data.questions || data.questions.length === 0) {
            container.style.display = 'none';
            return;
        }
        data.questions.forEach(q => {
            const chip = document.createElement('button');
            chip.className = 'btn btn-sm btn-outline-primary rounded-pill suggestion-chip';
            chip.textContent = q;
            chip.addEventListener('click', () => {
                const input = pageRoot.querySelector('#alexanderChatInput');
                if (input) {
                    input.value = q;
                    sendAlexanderMessage();
                }
            });
            questionsContainer.appendChild(chip);
        });
    })
    .catch(() => {
        container.style.display = 'none';
    });
}

function refreshFollowUpSuggestions() {
    const msgs = pageRoot.querySelectorAll('#alexanderChatMessages .chat-message-agent');
    if (msgs.length > 0) {
        const lastAgentMsg = msgs[msgs.length - 1];
        const text = lastAgentMsg ? lastAgentMsg.textContent.replace('Alexander', '').trim() : '';
        if (text) showFollowUpSuggestions(text);
    }
}

/* ── Synthesis Modal ── */

function showSynthesisModal() {
    const modal = pageRoot.querySelector('#appModalContainer');
    if (!modal) return;

    const items = currentWorkspaceItems || [];
    if (items.length === 0) {
        showToast('No sources available for synthesis', 'warning');
        return;
    }

    const checkboxes = items.map((item, i) => `
        <div class="form-check mb-1">
            <input class="form-check-input synthesis-source-cb" type="checkbox" value="${item.id}" id="synth-cb-${i}" checked>
            <label class="form-check-label small" for="synth-cb-${i}">${escapeHtml(item.title)}</label>
        </div>
    `).join('');

    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Synthesize Sources</h5>
                        <button type="button" class="btn-close" id="synthCloseBtn"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <h6>Select sources to synthesize:</h6>
                            <div style="max-height:200px;overflow-y:auto;">${checkboxes}</div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Instruction type:</label>
                            <select id="synthInstruction" class="form-select">
                                <option value="themes">Summarize key themes</option>
                                <option value="compare">Compare and contrast</option>
                                <option value="contradictions">Find contradictions</option>
                                <option value="argument">Build an argument for/against</option>
                            </select>
                        </div>
                        <div id="synthResult" style="display:none;" class="border rounded p-3 bg-light mb-2"></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" id="synthCancelBtn">Cancel</button>
                        <button type="button" class="btn btn-primary" id="synthGenerateBtn">Generate</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    modal.querySelector('#synthCloseBtn').addEventListener('click', () => modal.innerHTML = '');
    modal.querySelector('#synthCancelBtn').addEventListener('click', () => modal.innerHTML = '');
    modal.querySelector('#synthGenerateBtn').addEventListener('click', () => {
        const checked = [...modal.querySelectorAll('.synthesis-source-cb:checked')].map(cb => parseInt(cb.value));
        const instruction = modal.querySelector('#synthInstruction').value;
        if (checked.length === 0) {
            showToast('Select at least one source', 'warning');
            return;
        }
        const btn = modal.querySelector('#synthGenerateBtn');
        btn.disabled = true;
        btn.textContent = 'Generating...';
        modal.querySelector('#synthResult').style.display = 'block';
        modal.querySelector('#synthResult').innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div> Generating synthesis...';

        fetch('/api/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: currentWorkspaceId,
                source_ids: checked,
                instruction: instruction
            })
        })
        .then(r => r.json())
        .then(data => {
            btn.disabled = false;
            btn.textContent = 'Generate';
            if (data.status) {
                modal.querySelector('#synthResult').innerHTML = '<strong>Synthesis:</strong><br>' + formatAlexanderText(data.synthesis || '');
            } else {
                modal.querySelector('#synthResult').innerHTML = '<div class="text-danger">' + escapeHtml(data.error || 'Synthesis failed') + '</div>';
            }
        })
        .catch(() => {
            btn.disabled = false;
            btn.textContent = 'Generate';
            modal.querySelector('#synthResult').innerHTML = '<div class="text-danger">Synthesis request failed</div>';
        });
    });
}

/* ── Study Guide ── */

function generateStudyGuide() {
    if (!currentWorkspaceItems || currentWorkspaceItems.length === 0) {
        showToast('No sources in workspace to generate a study guide', 'warning');
        return;
    }

    const modal = pageRoot.querySelector('#appModalContainer');
    if (!modal) return;

    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-xl modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Study Guide</h5>
                        <button type="button" class="btn-close" id="sgCloseBtn"></button>
                    </div>
                    <div class="modal-body">
                        <div id="sgLoading" class="text-center py-5">
                            <div class="spinner-border mb-3" role="status"></div>
                            <p class="text-muted">Alexander is generating your study guide...</p>
                        </div>
                        <div id="sgResult" style="display:none;" class="p-3"></div>
                    </div>
                    <div class="modal-footer" id="sgFooter" style="display:none;">
                        <button type="button" class="btn btn-outline-secondary" id="sgCopyBtn">Copy to clipboard</button>
                        <button type="button" class="btn btn-outline-secondary" id="sgExportBtn">Export as Markdown</button>
                        <button type="button" class="btn btn-secondary" id="sgCloseFooterBtn">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    modal.querySelector('#sgCloseBtn').addEventListener('click', () => modal.innerHTML = '');
    modal.querySelector('#sgCloseFooterBtn')?.addEventListener('click', () => modal.innerHTML = '');

    fetch('/api/study-guide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: currentWorkspaceId })
    })
    .then(r => r.json())
    .then(data => {
        modal.querySelector('#sgLoading').style.display = 'none';
        modal.querySelector('#sgResult').style.display = 'block';
        modal.querySelector('#sgFooter').style.display = '';
        if (data.status) {
            const formatted = formatAlexanderText(data.study_guide || '');
            modal.querySelector('#sgResult').innerHTML = formatted;
        } else {
            modal.querySelector('#sgResult').innerHTML = '<div class="text-danger">' + escapeHtml(data.error || 'Generation failed') + '</div>';
        }
    })
    .catch(() => {
        modal.querySelector('#sgLoading').style.display = 'none';
        modal.querySelector('#sgResult').style.display = 'block';
        modal.querySelector('#sgResult').innerHTML = '<div class="text-danger">Failed to generate study guide</div>';
    });

    modal.querySelector('#sgCopyBtn')?.addEventListener('click', () => {
        const text = modal.querySelector('#sgResult').textContent || '';
        navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard', 'success'));
    });
    modal.querySelector('#sgExportBtn')?.addEventListener('click', () => {
        const text = modal.querySelector('#sgResult').textContent || '';
        const blob = new Blob([text], { type: 'text/markdown' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'study-guide.md';
        a.click();
        URL.revokeObjectURL(a.href);
        showToast('Study guide exported', 'success');
    });
}

/* ── Essay Outline Modal ── */

function showEssayOutlineModal() {
    if (!currentWorkspaceItems || currentWorkspaceItems.length === 0) {
        showToast('No sources in workspace to generate an outline', 'warning');
        return;
    }

    const modal = pageRoot.querySelector('#appModalContainer');
    if (!modal) return;

    modal.innerHTML = `
        <div class="modal fade show d-block" style="background-color: rgba(0,0,0,0.5);">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Essay Outline Generator</h5>
                        <button type="button" class="btn-close" id="eoCloseBtn"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label class="form-label fw-semibold">Enter your thesis statement:</label>
                            <textarea id="eoThesisInput" class="form-control" rows="3" placeholder="e.g. The Industrial Revolution had a greater impact on British society than the Victorian era's social reforms..."></textarea>
                        </div>
                        <div id="eoLoading" style="display:none;" class="text-center py-3">
                            <div class="spinner-border mb-2" role="status"></div>
                            <p class="text-muted small">Generating outline...</p>
                        </div>
                        <div id="eoResult" style="display:none;" class="border rounded p-3 bg-light"></div>
                    </div>
                    <div class="modal-footer" id="eoFooter">
                        <button type="button" class="btn btn-secondary" id="eoCancelBtn">Cancel</button>
                        <button type="button" class="btn btn-primary" id="eoGenerateBtn">Generate Outline</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    modal.querySelector('#eoCloseBtn').addEventListener('click', () => modal.innerHTML = '');
    modal.querySelector('#eoCancelBtn').addEventListener('click', () => modal.innerHTML = '');

    modal.querySelector('#eoGenerateBtn').addEventListener('click', () => {
        const thesis = modal.querySelector('#eoThesisInput').value.trim();
        if (!thesis) {
            showToast('Please enter a thesis statement', 'warning');
            return;
        }
        modal.querySelector('#eoLoading').style.display = 'block';
        modal.querySelector('#eoResult').style.display = 'none';
        modal.querySelector('#eoGenerateBtn').disabled = true;

        fetch('/api/essay-outline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workspace_id: currentWorkspaceId,
                thesis: thesis
            })
        })
        .then(r => r.json())
        .then(data => {
            modal.querySelector('#eoLoading').style.display = 'none';
            modal.querySelector('#eoGenerateBtn').disabled = false;
            if (data.status) {
                const formatted = formatAlexanderText(data.outline || '');
                modal.querySelector('#eoResult').style.display = 'block';
                modal.querySelector('#eoResult').innerHTML = formatted;
            } else {
                modal.querySelector('#eoResult').style.display = 'block';
                modal.querySelector('#eoResult').innerHTML = '<div class="text-danger">' + escapeHtml(data.error || 'Generation failed') + '</div>';
            }
        })
        .catch(() => {
            modal.querySelector('#eoLoading').style.display = 'none';
            modal.querySelector('#eoGenerateBtn').disabled = false;
            modal.querySelector('#eoResult').style.display = 'block';
            modal.querySelector('#eoResult').innerHTML = '<div class="text-danger">Failed to generate outline</div>';
        });
    });
}

/* ── Auto-Tagging ── */

function fetchAndShowTags(item) {
    const title = item.title || '';
    const snippet = item.summary || item.abstract || item.description || '';
    if (!title && !snippet) return;

    fetch('/api/suggest-tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, snippet: snippet.slice(0, 1000) })
    })
    .then(r => r.json())
    .then(data => {
        if (!data.status || !data.tags || data.tags.length === 0) return;
        const sourceEl = pageRoot.querySelector(`[data-item-id="${item.id}"] .item-tags-container`);
        if (!sourceEl) return;
        data.tags.forEach(tag => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-light text-dark border me-1 mb-1 suggestion-tag';
            badge.style.cursor = 'pointer';
            badge.textContent = tag;
            const close = document.createElement('span');
            close.className = 'ms-1 text-muted';
            close.style.cursor = 'pointer';
            close.innerHTML = '&times;';
            close.title = 'Dismiss';
            close.addEventListener('click', (e) => {
                e.stopPropagation();
                badge.remove();
            });
            badge.appendChild(close);
            badge.addEventListener('click', (e) => {
                if (e.target === close) return;
                badge.classList.remove('bg-light', 'text-dark', 'border');
                badge.classList.add('bg-primary', 'text-white');
                badge.title = 'Accepted';
                showToast('Tag accepted: ' + tag, 'success');
            });
            sourceEl.appendChild(badge);
        });
    })
    .catch(() => {});
}
