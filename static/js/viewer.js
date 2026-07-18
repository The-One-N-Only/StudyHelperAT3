"use strict";

import { showToast } from './toast.js';
import { createWorkspaceSelectElement, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';

const GOOGLE_BOOKS_API_URL = 'https://www.google.com/books/jsapi.js';
const GOOGLE_BOOKS_RENDER_TIMEOUT_MS = 8000;
const PROXY_IFRAME_SANDBOX = 'allow-popups allow-popups-to-escape-sandbox';

let viewerOffcanvas;
let googleBooksApiPromise;
let activeGoogleBooksViewer;
let googleBooksResizeObserver;
let viewerRequestGeneration = 0;

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

function waitForOffcanvasShown(element) {
    if (element.classList.contains('show')) {
        return { promise: Promise.resolve(), cancel() {} };
    }

    let onShown;
    const promise = new Promise((resolve) => {
        onShown = () => resolve();
        element.addEventListener('shown.bs.offcanvas', onShown, { once: true });
    });
    return {
        promise,
        cancel() {
            element.removeEventListener('shown.bs.offcanvas', onShown);
        },
    };
}

function textValue(value) {
    return value === null || value === undefined ? '' : String(value);
}

function appendTextElement(parent, tagName, value, className = '') {
    const element = document.createElement(tagName);
    element.className = className;
    element.textContent = textValue(value);
    parent.appendChild(element);
    return element;
}

function createExternalLink(url, label, className = '') {
    const safeUrl = safeHttpUrl(url);
    if (!safeUrl) return null;

    const link = document.createElement('a');
    link.className = className;
    link.href = safeUrl;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    if (label) link.textContent = label;
    return link;
}

function resetGoogleBooksViewerState() {
    if (googleBooksResizeObserver) {
        googleBooksResizeObserver.disconnect();
        googleBooksResizeObserver = undefined;
    }
    activeGoogleBooksViewer = undefined;
}

function renderViewerHeader(header, item) {
    header.replaceChildren();

    const summary = document.createElement('div');
    summary.className = 'd-flex align-items-center gap-2';

    const details = document.createElement('div');
    details.className = 'flex-grow-1';
    appendTextElement(
        details,
        'h6',
        item?.title,
        'fw-semibold text-truncate mb-1',
    );

    const metadata = document.createElement('div');
    metadata.className = 'd-flex flex-wrap gap-2 align-items-center';
    appendTextElement(
        metadata,
        'span',
        item?.source_name,
        'badge bg-secondary rounded-pill',
    );
    appendTextElement(
        metadata,
        'small',
        item?.source_url,
        'text-muted text-truncate',
    );
    details.appendChild(metadata);
    summary.appendChild(details);

    const sourceLink = createExternalLink(
        item?.source_url,
        '',
        'btn btn-link btn-sm p-0 ms-auto',
    );
    if (sourceLink) {
        sourceLink.setAttribute('aria-label', 'Open source in new tab');
        const icon = document.createElement('i');
        icon.className = 'bi bi-box-arrow-up-right';
        icon.setAttribute('aria-hidden', 'true');
        sourceLink.appendChild(icon);
        summary.appendChild(sourceLink);
    }
    header.appendChild(summary);

    const actionRow = document.createElement('div');
    actionRow.className = 'mb-2 d-flex align-items-center gap-2';
    const workspaceSelect = createWorkspaceSelectElement();
    workspaceSelect.id = 'viewerWorkspaceSelect';
    workspaceSelect.className = 'form-select form-select-sm';
    workspaceSelect.setAttribute('aria-label', 'Choose workspace');
    actionRow.appendChild(workspaceSelect);
    header.appendChild(actionRow);
    return workspaceSelect;
}

function renderLoading(body) {
    body.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'text-center py-5';
    const spinner = document.createElement('div');
    spinner.className = 'spinner-border';
    spinner.setAttribute('role', 'status');
    loading.appendChild(spinner);
    appendTextElement(loading, 'p', 'Loading source...');
    body.appendChild(loading);
}

function renderViewerNotice(body, message, variant, linkUrl = '', linkLabel = '') {
    body.replaceChildren();
    const panel = document.createElement('div');
    panel.className = `alert alert-${variant} m-3`;
    appendTextElement(panel, 'p', message, 'mb-0');

    const link = createExternalLink(
        linkUrl,
        linkLabel,
        'btn btn-primary btn-sm mt-3',
    );
    if (link) panel.appendChild(link);
    body.appendChild(panel);
}

function isGoogleBooksResult(item) {
    const sourceName = textValue(item?.source_name).trim().toLowerCase();
    if (sourceName === 'gbooks' || sourceName === 'google books') return true;

    const sourceUrl = safeHttpUrl(item?.source_url);
    if (!sourceUrl) return false;
    return new URL(sourceUrl).hostname.toLowerCase() === 'books.google.com';
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

function googleBooksVolumeId(item) {
    const sourceId = textValue(item?.source_id).trim();
    if (sourceId && !safeHttpUrl(sourceId) && /^[A-Za-z0-9._-]+$/u.test(sourceId)) {
        return sourceId;
    }

    for (const candidate of [item?.source_url, item?.source_id]) {
        const safeUrl = safeHttpUrl(candidate);
        if (!safeUrl) continue;

        const parsed = new URL(safeUrl);
        if (parsed.hostname.toLowerCase() !== 'books.google.com') continue;

        const queryId = (parsed.searchParams.get('id') || '').trim();
        if (queryId) return queryId;

        const editionMatch = parsed.pathname.match(/\/books\/edition\/[^/]+\/([^/]+)$/u);
        if (editionMatch?.[1]) {
            try {
                return decodeURIComponent(editionMatch[1]);
            } catch (_err) {
                return editionMatch[1];
            }
        }
    }

    return '';
}

function loadGoogleBooksApi() {
    if (googleBooksApiPromise) return googleBooksApiPromise;

    googleBooksApiPromise = new Promise((resolve, reject) => {
        if (window.google?.books?.DefaultViewer) {
            resolve(window.google.books);
            return;
        }

        const script = document.createElement('script');
        script.src = GOOGLE_BOOKS_API_URL;
        script.async = true;
        script.onload = () => {
            const booksApi = window.google?.books;
            if (!booksApi?.load || !booksApi?.setOnLoadCallback) {
                reject(new Error('Google Books API loader unavailable'));
                return;
            }

            try {
                booksApi.load();
                booksApi.setOnLoadCallback(() => {
                    const loadedApi = window.google?.books;
                    if (!loadedApi?.DefaultViewer) {
                        reject(new Error('Google Books viewer unavailable'));
                        return;
                    }
                    resolve(loadedApi);
                });
            } catch {
                reject(new Error('Google Books API initialization failed'));
            }
        };
        script.onerror = () => reject(new Error('Google Books API script failed'));
        document.head.appendChild(script);
    });

    return googleBooksApiPromise;
}

function renderGoogleBooksFallback(body, item, reason) {
    body.replaceChildren();
    const fallback = document.createElement('div');
    fallback.className = 'google-books-fallback';

    const coverUrl = safeHttpUrl(item?.thumb_url);
    if (coverUrl) {
        const cover = document.createElement('img');
        cover.src = coverUrl;
        cover.alt = textValue(item?.title)
            ? `Cover of ${textValue(item.title)}`
            : 'Book cover';
        fallback.appendChild(cover);
    }

    const metadata = document.createElement('div');
    metadata.className = 'google-books-fallback-metadata';
    appendTextElement(metadata, 'h5', item?.title || 'Google Books preview');
    if (item?.description) {
        appendTextElement(metadata, 'p', item.description, 'google-books-description');
    }
    appendTextElement(metadata, 'p', reason, 'google-books-fallback-reason');

    const accessInfo = item?.accessInfo && typeof item.accessInfo === 'object'
        ? item.accessInfo
        : {};
    const previewStatus = [accessInfo.viewability, accessInfo.accessViewStatus]
        .map(textValue)
        .filter(Boolean)
        .join(' / ');
    appendTextElement(
        metadata,
        'p',
        `Preview status: ${previewStatus || 'UNKNOWN'}`,
        'google-books-preview-status',
    );

    const linkUrl = safeHttpUrl(accessInfo.webReaderLink)
        || safeHttpUrl(item?.source_url);
    const link = createExternalLink(
        linkUrl,
        'Open Google Books',
        'btn btn-primary btn-sm',
    );
    if (link) metadata.appendChild(link);
    fallback.appendChild(metadata);
    body.appendChild(fallback);
}

async function renderGoogleBooksViewer(body, item, generation) {
    const accessInfo = item?.accessInfo && typeof item.accessInfo === 'object'
        ? item.accessInfo
        : {};
    if (accessInfo.embeddable === false) {
        renderGoogleBooksFallback(
            body,
            item,
            'An embedded preview is not available for this book.',
        );
        return;
    }

    const volumeId = googleBooksVolumeId(item);
    if (!volumeId) {
        renderGoogleBooksFallback(
            body,
            item,
            'This result does not include a Google Books volume ID.',
        );
        return;
    }

    let booksApi;
    try {
        booksApi = await loadGoogleBooksApi();
    } catch {
        if (generation === viewerRequestGeneration) {
            renderGoogleBooksFallback(
                body,
                item,
                'The Google Books preview service could not be loaded.',
            );
        }
        return;
    }
    if (generation !== viewerRequestGeneration) return;

    const viewerShell = document.createElement('div');
    viewerShell.className = 'google-books-viewer';
    const canvas = document.createElement('div');
    canvas.className = 'google-books-viewer-canvas';
    viewerShell.appendChild(canvas);
    body.replaceChildren(viewerShell);

    let viewer;
    try {
        viewer = new booksApi.DefaultViewer(canvas);
    } catch {
        renderGoogleBooksFallback(
            body,
            item,
            'The embedded preview could not be started.',
        );
        return;
    }

    await new Promise((resolve) => {
        try {
            viewer.load(
                volumeId,
                () => {
                    if (generation === viewerRequestGeneration) {
                        renderGoogleBooksFallback(
                            body,
                            item,
                            'No embedded preview is available for this volume.',
                        );
                    }
                    resolve();
                },
                () => {
                    if (generation !== viewerRequestGeneration) {
                        resolve();
                        return;
                    }

                    activeGoogleBooksViewer = viewer;
                    if (typeof ResizeObserver === 'function') {
                        googleBooksResizeObserver = new ResizeObserver(() => {
                            if (
                                generation !== viewerRequestGeneration
                                || activeGoogleBooksViewer !== viewer
                            ) {
                                return;
                            }
                            viewer.resize();
                        });
                        googleBooksResizeObserver.observe(canvas);
                    }
                    resolve();
                },
            );
        } catch {
            if (generation === viewerRequestGeneration) {
                renderGoogleBooksFallback(
                    body,
                    item,
                    'The embedded preview could not be loaded.',
                );
            }
            resolve();
        }
    });
}

async function renderGoogleBooksViewerWithTimeout(body, item, generation) {
    let timeoutId;
    const timeout = new Promise((resolve) => {
        timeoutId = setTimeout(() => {
            if (generation === viewerRequestGeneration) {
                viewerRequestGeneration += 1;
                resetGoogleBooksViewerState();
                renderGoogleBooksFallback(
                    body,
                    item,
                    'The embedded Google Books preview timed out after eight seconds.',
                );
            }
            resolve();
        }, GOOGLE_BOOKS_RENDER_TIMEOUT_MS);
    });

    try {
        await Promise.race([
            renderGoogleBooksViewer(body, item, generation),
            timeout,
        ]);
    } finally {
        clearTimeout(timeoutId);
    }
}

function renderProxyContent(body, result) {
    body.replaceChildren();
    const mode = result.mode || 'iframe';
    if (mode === 'reader') {
        body.classList.add('viewer-mode-reader');
    }

    const iframe = document.createElement('iframe');
    iframe.className = mode === 'reader'
        ? 'viewer-iframe viewer-reader'
        : 'viewer-iframe';
    iframe.setAttribute('sandbox', PROXY_IFRAME_SANDBOX);
    iframe.setAttribute('referrerpolicy', 'no-referrer');
    iframe.srcdoc = textValue(result.html);
    body.appendChild(iframe);
}

export async function openViewer(item) {
    const generation = ++viewerRequestGeneration;
    resetGoogleBooksViewerState();

    const header = document.getElementById('viewerHeader');
    const body = document.getElementById('viewerBody');
    const addBtn = document.getElementById('addToWorkspaceBtn');
    if (!header || !body || !addBtn) {
        showToast('Viewer markup not available', 'danger');
        return;
    }

    body.classList.remove('viewer-mode-reader');
    const workspaceSelect = renderViewerHeader(header, item);
    addBtn.onclick = () => addToWorkspaceFromViewer(item, workspaceSelect);
    renderLoading(body);

    const isGoogleBooks = isGoogleBooksResult(item);
    const offcanvasElement = document.getElementById('viewerOffcanvas');
    const shown = isGoogleBooks
        ? waitForOffcanvasShown(offcanvasElement)
        : { promise: Promise.resolve(), cancel() {} };

    try {
        ensureViewerOffcanvas().show();
    } catch {
        shown.cancel();
        showToast('Failed to open viewer', 'danger');
        return;
    }

    if (isGoogleBooks) {
        await shown.promise;
        if (generation !== viewerRequestGeneration) return;
        await renderGoogleBooksViewerWithTimeout(body, item, generation);
        return;
    }

    const isPubMed = textValue(item?.source_name).toLowerCase() === 'pubmed'
        || textValue(item?.source_url).includes('pubmed.ncbi.nlm.nih.gov');
    if (isPubMed) {
        renderViewerNotice(
            body,
            'PubMed pages are not displayed inside StudyHelper because NCBI blocks proxy access.',
            'warning',
            item?.source_url,
            'Open PubMed in new tab',
        );
        return;
    }

    try {
        const response = await fetch(
            `/api/proxy/source?url=${encodeURIComponent(textValue(item?.source_url))}`,
        );
        const result = await response.json();
        if (generation !== viewerRequestGeneration) return;

        if (result.status) {
            renderProxyContent(body, result);
            return;
        }

        renderViewerNotice(
            body,
            result.error || 'Failed to load source',
            'warning',
            safeHttpUrl(result.fallback_url) || safeHttpUrl(item?.source_url),
            'Open directly in new tab',
        );
    } catch {
        if (generation !== viewerRequestGeneration) return;
        renderViewerNotice(body, 'Failed to load source', 'danger');
        showToast('Failed to load source', 'danger');
    }
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
            citation_harvard: 'Harvard citation',
            workspace_id: workspace_id,
        }),
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
