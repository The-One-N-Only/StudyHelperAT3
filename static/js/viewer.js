"use strict";

import { showToast } from './toast.js';
import { hydrateWorkspaceSelect, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';

let viewerOffcanvas;
let googleBooksScriptLoadPromise = null;
let googleBooksScriptLoaded = false;
const GOOGLE_BOOKS_JSAPI_URL = 'https://www.google.com/books/jsapi.js';

function ensureViewerOffcanvas() {
    if (!viewerOffcanvas) {
        const offcanvasElement = document.getElementById('viewerOffcanvas');
        if (!offcanvasElement) {
            throw new Error('Viewer offcanvas markup not found');
        }
        viewerOffcanvas = new bootstrap.Offcanvas(offcanvasElement);
    }
    return viewerOffcanvas;
}

function renderGoogleBooksFallback(url) {
    return `
        <div class="proxy-google-books p-4">
            <h5>Google Books preview</h5>
            <p>Book preview pages are not rendered directly inside StudyHelper.</p>
            <a href="${url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">Open Google Books</a>
        </div>
    `;
}

function loadGoogleBooksScript() {
    if (googleBooksScriptLoaded) {
        return Promise.resolve();
    }
    if (googleBooksScriptLoadPromise) {
        return googleBooksScriptLoadPromise;
    }
    const scriptSrc = GOOGLE_BOOKS_JSAPI_URL;
    googleBooksScriptLoadPromise = new Promise((resolve, reject) => {
        const existingScript = Array.from(document.scripts).find(script => script.src.startsWith(GOOGLE_BOOKS_JSAPI_URL));
        if (existingScript) {
            if (window.google && window.google.books) {
                googleBooksScriptLoaded = true;
                resolve();
                return;
            }
            existingScript.addEventListener('load', () => {
                googleBooksScriptLoaded = true;
                resolve();
            });
            existingScript.addEventListener('error', () => reject(new Error('Failed to load Google Books script')));
            return;
        }

        const script = document.createElement('script');
        script.src = scriptSrc;
        script.async = true;
        script.onload = () => {
            googleBooksScriptLoaded = true;
            resolve();
        };
        script.onerror = () => reject(new Error('Failed to load Google Books script'));
        document.head.appendChild(script);
    });

    return googleBooksScriptLoadPromise;
}

function openGoogleBooksViewer(item, body) {
    body.classList.remove('viewer-mode-reader');
    body.innerHTML = '<div class="text-center py-5"><div class="spinner-border" role="status"></div><p>Loading Google Books preview...</p></div>';

    fetch('/api/config/google-books-key')
        .then(r => r.json())
        .then(result => {
            if (!result.status || !result.google_books_api_key) {
                throw new Error('Google Books API key unavailable');
            }
            const apiKey = result.google_books_api_key;
            return loadGoogleBooksScript().then(() => apiKey);
        })
        .then(apiKey => {
            if (!window.google || !google.books || typeof google.books.load !== 'function') {
                throw new Error('Google Books API not available');
            }

            google.books.load({ apiKey });
            google.books.setOnLoadCallback(() => {
                try {
                    body.innerHTML = '';
                    const viewer = new google.books.DefaultViewer(body);
                    viewer.load(item.source_id);
                } catch (error) {
                    throw error;
                }
            });
        })
        .catch((error) => {
            console.error('Google Books viewer error:', error);
            body.innerHTML = renderGoogleBooksFallback(item.source_url);
        });
}

export function openViewer(item) {
    const header = document.getElementById('viewerHeader');
    const body = document.getElementById('viewerBody');
    const addBtn = document.getElementById('addToWorkspaceBtn');

    if (!header || !body || !addBtn) {
        showToast('Viewer markup not available', 'danger');
        return;
    }

    header.innerHTML = `
        <div class="d-flex align-items-center gap-2">
            <div class="flex-grow-1 overflow-hidden">
                <h6 class="fw-semibold text-truncate mb-1">${item.title}</h6>
                <div class="d-flex flex-wrap gap-2 align-items-center">
                    <span class="badge bg-secondary rounded-pill">${item.source_name}</span>
                    <small class="text-muted text-truncate" style="max-width:100%;">
                        <a href="${item.source_url}" target="_blank" rel="noopener noreferrer" class="text-muted text-decoration-none d-inline-block text-truncate" style="max-width:100%;">${item.source_url}</a>
                    </small>
                </div>
            </div>
        </div>
    `;

    const actionRow = document.createElement('div');
    actionRow.className = 'mb-2 d-flex align-items-center gap-2';
    actionRow.innerHTML = `
        <select id="viewerWorkspaceSelect" class="form-select form-select-sm"></select>
    `;
    header.appendChild(actionRow);

    const workspaceSelect = actionRow.querySelector('#viewerWorkspaceSelect');
    hydrateWorkspaceSelect(workspaceSelect);

    addBtn.onclick = () => addToWorkspaceFromViewer(item, workspaceSelect);

    body.innerHTML = '<div class="text-center py-5"><div class="spinner-border" role="status"></div><p>Loading source...</p></div>';
    try {
        ensureViewerOffcanvas().show();
    } catch (error) {
        showToast('Failed to open viewer', 'danger');
        console.error(error);
        return;
    }

    const isPubMed = item.source_name?.toLowerCase() === 'pubmed' || item.source_url?.includes('pubmed.ncbi.nlm.nih.gov');
    const isGoogleBooks = item.source_name?.toLowerCase() === 'gbooks' || item.source_name?.toLowerCase() === 'google books';

    if (isPubMed) {
        body.innerHTML = `
            <div class="alert alert-warning m-3">
                <i class="bi bi-exclamation-triangle"></i>
                PubMed pages are not displayed inside StudyHelper because NCBI blocks proxy access.
                <div class="mt-3">
                    <a href="${item.source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">Open PubMed in new tab</a>
                </div>
            </div>
        `;
        return;
    }

    if (isGoogleBooks) {
        openGoogleBooksViewer(item, body);
        return;
    }

    fetch(`/api/proxy/source?url=${encodeURIComponent(item.source_url)}`)
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                body.innerHTML = '';
                const mode = result.mode || 'iframe';

                if (mode === 'iframe') {
                    const iframe = document.createElement('iframe');
                    iframe.className = 'viewer-iframe';
                    iframe.srcdoc = result.html;
                    body.appendChild(iframe);
                } else if (mode === 'reader') {
                    body.classList.add('viewer-mode-reader');
                    body.innerHTML = `<div class="viewer-reader">${result.html}</div>`;
                } else {
                    body.classList.remove('viewer-mode-reader');
                    body.innerHTML = result.html;
                }
            } else {
                const fallback = result.fallback_url || item.source_url;
                body.innerHTML = `
                    <div class="alert alert-warning m-3">
                        <i class="bi bi-exclamation-triangle"></i>
                        ${result.error}
                        <div class="mt-3">
                            <a href="${fallback}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">Open directly in new tab</a>
                        </div>
                    </div>
                `;
            }
        })
        .catch(() => {
            body.innerHTML = '<div class="alert alert-danger m-3">Failed to load source</div>';
            showToast('Failed to load source', 'danger');
        });

    addBtn.onclick = () => addToWorkspaceFromViewer(item, workspaceSelect);
}

function addToWorkspaceFromViewer(item, workspaceSelect) {
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
            citation_harvard: 'Harvard citation'
            , workspace_id: workspace_id
        })
    }).then(r => r.json()).then(addResult => {
        if (addResult.status) {
            showToast('Added to workspace', 'success');
            clearWorkspaceCache();
            viewerOffcanvas.hide();
        } else {
            showToast('Failed to add to workspace: ' + (addResult.error || 'Unknown error'), 'danger');
        }
    }).catch((error) => {
        console.error('Add to workspace error:', error);
        showToast('Error adding to workspace', 'danger');
    });
}