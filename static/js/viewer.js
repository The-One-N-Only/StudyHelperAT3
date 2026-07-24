"use strict";

import { showToast } from './toast.js';
import { rememberResultImageFailure, resolveResultImage } from './card.js';
import { createWorkspaceSelectElement, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';

const GOOGLE_BOOKS_API_URL = 'https://www.google.com/books/jsapi.js';
const GOOGLE_BOOKS_RENDER_TIMEOUT_MS = 12000;
const GOOGLE_BOOKS_API_READY_TIMEOUT_MS = 10000;
const GOOGLE_BOOKS_API_POLL_INTERVAL_MS = 50;
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

function truncateText(value, maxLen) {
    const str = textValue(value);
    if (str.length <= maxLen) return str;
    return str.substring(0, maxLen) + '\u2026';
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

export function resetGoogleBooksViewerState() {
    if (googleBooksResizeObserver) {
        googleBooksResizeObserver.disconnect();
        googleBooksResizeObserver = undefined;
    }
    activeGoogleBooksViewer = undefined;
}

function renderViewerHeader(header, item) {
    header.replaceChildren();

    const infoBox = document.createElement('div');
    infoBox.className = 'border rounded p-2 mb-2 site-info-box';

    const summary = document.createElement('div');
    summary.className = 'd-flex align-items-center gap-2';

    const details = document.createElement('div');
    details.className = 'flex-grow-1 min-w-0';
    appendTextElement(
        details,
        'h6',
        truncateText(item?.title, 60),
        'fw-semibold text-truncate mb-1',
    );

    const metadata = document.createElement('div');
    metadata.className = 'd-flex flex-wrap gap-2 align-items-center min-w-0';
    appendTextElement(
        metadata,
        'span',
        item?.source_name,
        'badge bg-secondary rounded-pill flex-shrink-0',
    );

    const sourceUrl = safeHttpUrl(item?.source_url);
    if (sourceUrl) {
        const urlLink = document.createElement('a');
        urlLink.className = 'small text-muted text-truncate d-inline-block source-link-truncate';
        urlLink.style.maxWidth = '100%';
        urlLink.href = sourceUrl;
        urlLink.target = '_blank';
        urlLink.rel = 'noopener noreferrer';
        urlLink.textContent = truncateText(sourceUrl, 55);
        urlLink.title = sourceUrl;
        metadata.appendChild(urlLink);
    }
    details.appendChild(metadata);
    summary.appendChild(details);
    infoBox.appendChild(summary);
    header.appendChild(infoBox);

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

export function renderViewerNotice(body, message, variant, linkUrl = '', linkLabel = '') {
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

export function isGoogleBooksResult(item) {
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

export function googleBooksVolumeId(item) {
    const explicitVolumeId = normalizedGoogleBooksVolumeId(
        item?.google_books_volume_id
    );
    if (explicitVolumeId) return explicitVolumeId;

    const sourceId = normalizedGoogleBooksVolumeId(item?.source_id);
    if (sourceId) {
        return sourceId;
    }

    for (const candidate of [item?.source_url, item?.source_id]) {
        const safeUrl = safeHttpUrl(candidate);
        if (!safeUrl) continue;

        const parsed = new URL(safeUrl);
        if (parsed.hostname.toLowerCase() !== 'books.google.com') continue;

        const queryId = normalizedGoogleBooksVolumeId(
            parsed.searchParams.get('id')
        );
        if (queryId) return queryId;

        const editionMatch = parsed.pathname.match(/\/books\/edition\/[^/]+\/([^/]+)$/u);
        if (editionMatch?.[1]) {
            try {
                return normalizedGoogleBooksVolumeId(
                    decodeURIComponent(editionMatch[1])
                );
            } catch (_err) {
                return normalizedGoogleBooksVolumeId(editionMatch[1]);
            }
        }
    }

    return '';
}

function normalizedGoogleBooksVolumeId(value) {
    return typeof value === 'string' && /^[A-Za-z0-9_-]{1,220}$/u.test(value)
        ? value
        : '';
}

export function loadGoogleBooksApi() {
    const readyApi = window.google?.books;
    if (readyApi?.DefaultViewer) return Promise.resolve(readyApi);
    if (googleBooksApiPromise) return googleBooksApiPromise;

    let script;
    const loaderPromise = new Promise((resolve, reject) => {
        let readinessPollId;
        let readinessWatchdogId;
        let settled = false;

        const cleanup = () => {
            if (readinessPollId !== undefined) {
                clearInterval(readinessPollId);
                readinessPollId = undefined;
            }
            if (readinessWatchdogId !== undefined) {
                clearTimeout(readinessWatchdogId);
                readinessWatchdogId = undefined;
            }
            if (script) {
                script.onload = null;
                script.onerror = null;
            }
        };

        const resolveIfReady = () => {
            if (settled) return true;
            const booksApi = window.google?.books;
            if (!booksApi?.DefaultViewer) return false;

            settled = true;
            cleanup();
            resolve(booksApi);
            return true;
        };

        const rejectLoader = (error) => {
            if (settled || resolveIfReady()) return;

            settled = true;
            cleanup();
            if (script?.parentNode) script.remove();
            reject(error);
        };

        readinessWatchdogId = setTimeout(() => {
            rejectLoader(new Error('Google Books API readiness timed out'));
        }, GOOGLE_BOOKS_API_READY_TIMEOUT_MS);

        script = document.createElement('script');
        script.src = GOOGLE_BOOKS_API_URL;
        script.async = true;
        script.onload = () => {
            const booksApi = window.google?.books;
            if (!booksApi?.load || !booksApi?.setOnLoadCallback) {
                rejectLoader(new Error('Google Books API loader unavailable'));
                return;
            }

            try {
                booksApi.load();
                booksApi.setOnLoadCallback(() => {
                    resolveIfReady();
                });
            } catch {
                rejectLoader(new Error('Google Books API initialization failed'));
                return;
            }

            if (resolveIfReady() || settled) return;
            readinessPollId = setInterval(
                resolveIfReady,
                GOOGLE_BOOKS_API_POLL_INTERVAL_MS,
            );
        };
        script.onerror = () => {
            rejectLoader(new Error('Google Books API script failed'));
        };
        document.head.appendChild(script);
    });

    const retryablePromise = loaderPromise.catch((error) => {
        if (googleBooksApiPromise === retryablePromise) {
            googleBooksApiPromise = undefined;
        }
        throw error;
    });
    googleBooksApiPromise = retryablePromise;
    return googleBooksApiPromise;
}

function numberAsEnglishWords(value) {
    const smallNumbers = [
        'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
        'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
        'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
    ];
    if (Number.isInteger(value) && value >= 0 && value < smallNumbers.length) {
        return smallNumbers[value];
    }
    return String(value);
}

function googleBooksRenderTimeoutLabel() {
    const seconds = GOOGLE_BOOKS_RENDER_TIMEOUT_MS / 1000;
    const unit = seconds === 1 ? 'second' : 'seconds';
    return `${numberAsEnglishWords(seconds)} ${unit}`;
}

export function renderGoogleBooksFallback(body, item, reason) {
    body.replaceChildren();
    const fallback = document.createElement('div');
    fallback.className = 'google-books-fallback';

    appendGoogleBooksFallbackCover(fallback, item);

    const metadata = document.createElement('div');
    metadata.className = 'google-books-fallback-metadata';
    appendTextElement(metadata, 'h5', item?.title || 'Google Books preview');
    if (item?.description) {
        appendTextElement(metadata, 'p', item.description, 'google-books-description');
    }
    appendTextElement(metadata, 'p', reason, 'google-books-fallback-reason');

    const linkUrl = safeHttpUrl(item?.accessInfo?.webReaderLink)
        || safeHttpUrl(item?.source_url);
    const link = createExternalLink(
        linkUrl,
        'Open Google Books',
        'btn btn-primary btn-sm',
    );
    if (link) metadata.appendChild(link);

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
        previewStatus ? `Preview status: ${previewStatus}` : 'Preview status not available from this search result.',
        'google-books-preview-status',
    );
    fallback.appendChild(metadata);
    body.appendChild(fallback);
}

function appendGoogleBooksFallbackCover(fallback, item) {
    const imageResolution = resolveResultImage(item);
    const cover = document.createElement('img');
    cover.src = imageResolution.sourceUrl;
    cover.alt = textValue(item?.title)
        ? `Cover of ${textValue(item.title)}`
        : 'Book cover';
    cover.setAttribute('data-image-kind', imageResolution.kind);

    let imageKind = imageResolution.kind;
    const onError = () => {
        if (imageKind === 'remote') {
            rememberResultImageFailure(imageResolution.remoteUrl);
            imageKind = 'fallback';
            cover.setAttribute('data-image-kind', imageKind);
            cover.src = imageResolution.fallbackUrl;
            return;
        }
        cover.removeEventListener('error', onError);
        cover.remove();
    };
    cover.addEventListener('error', onError);
    fallback.appendChild(cover);
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
                    `The embedded Google Books preview timed out after ${googleBooksRenderTimeoutLabel()}.`,
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

export function renderProxyContent(body, result) {
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

    const isScholar = textValue(item?.source_name).toLowerCase() === 'scholar'
        || textValue(item?.source_name).toLowerCase() === 'google scholar'
        || textValue(item?.source_url).includes('scholar.google.com');
    if (isScholar) {
        renderViewerNotice(
            body,
            'Google Scholar blocks proxy access.',
            'warning',
            item?.source_url,
            'Open Google Scholar in new tab',
        );
        return;
    }

    const isJSTOR = textValue(item?.source_url).includes('jstor.org');
    if (isJSTOR) {
        renderViewerNotice(
            body,
            'JSTOR content is subscription-based and cannot be previewed here.',
            'warning',
            item?.source_url,
            'Open JSTOR in new tab',
        );
        return;
    }

    const isScienceDirect = textValue(item?.source_url).includes('sciencedirect.com');
    if (isScienceDirect) {
        renderViewerNotice(
            body,
            'ScienceDirect content requires a subscription.',
            'warning',
            item?.source_url,
            'Open ScienceDirect in new tab',
        );
        return;
    }

    const isSpringer = textValue(item?.source_url).includes('link.springer.com');
    if (isSpringer) {
        renderViewerNotice(
            body,
            'Springer content requires a subscription.',
            'warning',
            item?.source_url,
            'Open Springer in new tab',
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
            if (addResult.duplicate) {
                showToast('Already in this workspace', 'warning');
            } else {
                showToast('Added to workspace', 'success');
                clearWorkspaceCache();
                viewerOffcanvas.hide();
            }
        } else {
            showToast('Failed to add to workspace: ' + (addResult.error || 'Unknown error'), 'danger');
        }
    }).catch((error) => {
        console.error('Add to workspace error:', error);
        showToast('Error adding to workspace', 'danger');
    });
}
