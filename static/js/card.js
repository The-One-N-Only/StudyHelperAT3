"use strict";

import { showToast } from './toast.js';
import { hydrateWorkspaceSelect, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';

const RESULT_IMAGE_FALLBACKS_LIST = [
    '/static/img/illustrations/open-book.svg',
    '/static/img/illustrations/scrollwork-flourish.svg',
    '/static/img/illustrations/stacked-books.svg',
    '/static/img/illustrations/compass-rose.svg',
    '/static/img/illustrations/candlestick.svg',
    '/static/img/illustrations/sextant.svg',
    '/static/img/illustrations/oil-lamp.svg',
];

const RESULT_IMAGE_FALLBACKS_DARK = RESULT_IMAGE_FALLBACKS_LIST.map(function (path) {
    return path.replace('/illustrations/', '/illustrations/dark-');
});

const ALL_RESULT_IMAGE_FALLBACKS = RESULT_IMAGE_FALLBACKS_LIST.concat(
    RESULT_IMAGE_FALLBACKS_DARK
);

function isDarkMode() {
    return document.documentElement.getAttribute('data-bs-theme') === 'dark';
}

function randomResultImageFallback() {
    const index = Math.floor(Math.random() * RESULT_IMAGE_FALLBACKS_LIST.length);
    return isDarkMode()
        ? RESULT_IMAGE_FALLBACKS_DARK[index]
        : RESULT_IMAGE_FALLBACKS_LIST[index];
}
const enhancedResultImages = new WeakSet();
const failedResultImageUrls = new Set();

function darkFallbackPath(lightPath) {
    if (!isDarkMode()) return lightPath;
    if (lightPath.includes('/dark-')) return lightPath;
    return lightPath.replace('/illustrations/', '/illustrations/dark-');
}

function switchToResultImageFallback(image, fallbackImage) {
    image.src = darkFallbackPath(fallbackImage);
    image.setAttribute('data-image-kind', 'fallback');
}

function enhanceResultImage(image) {
    if (!image || enhancedResultImages.has(image)) return;

    const fallbackImage = image.getAttribute('data-fallback-src');
    if (!ALL_RESULT_IMAGE_FALLBACKS.includes(fallbackImage)) return;

    enhancedResultImages.add(image);
    const remoteImage = safeRemoteImageUrl(
        image.getAttribute('src') || image.src
    );
    if (
        image.getAttribute('data-image-kind') === 'remote'
        && remoteImage
        && failedResultImageUrls.has(remoteImage)
    ) {
        switchToResultImageFallback(image, fallbackImage);
        return;
    }
    if (
        image.getAttribute('data-image-kind') === 'remote'
        && remoteImage
        && image.complete
        && image.naturalWidth === 0
    ) {
        rememberResultImageFailure(remoteImage);
        switchToResultImageFallback(image, fallbackImage);
        return;
    }
    image.addEventListener('error', () => {
        if (image.getAttribute('data-image-kind') === 'fallback') return;
        rememberResultImageFailure(remoteImage);
        switchToResultImageFallback(image, fallbackImage);
    }, { once: true });
}

export function enhanceResultCardImages(root = document) {
    if (!root?.querySelectorAll) return;
    root.querySelectorAll('.result-card-image[data-fallback-src]')
        .forEach((image) => enhanceResultImage(image));
}

export function createCard(item, query = '') {
    const card = document.createElement('div');
    card.className = 'card card-fixed shadow-sm surface-wood result-card rounded-3 h-100';
    card.innerHTML = `
        <img class="card-img-top result-card-image" loading="lazy" decoding="async" referrerpolicy="no-referrer" alt="">
        <div class="card-body">
            <h6 class="card-title text-truncate mb-1"></h6>
            <p class="card-text small text-muted card-description mb-2"></p>
            <div class="d-flex align-items-center justify-content-between">
                <small class="text-muted result-source"><i class="bi bi-globe2" aria-hidden="true"></i> <span class="result-source-text"></span></small>
                <button class="btn btn-link btn-sm p-0 icon-button save-btn" type="button" aria-label="" aria-pressed="false">
                    <i class="save-icon-light" aria-hidden="true"></i>
                    <i class="save-icon-dark d-none" aria-hidden="true"></i>
                </button>
            </div>
        </div>
        <div class="card-footer bg-transparent border-top p-2 result-card-actions">
            <button class="btn btn-outline-secondary btn-secondary-leather btn-sm w-50 view-btn" type="button">View</button>
            <button class="btn btn-primary btn-secondary-leather btn-sm px-1 w-50 add-btn" type="button">Add to workspace</button>
        </div>
        <div class="d-flex align-items-center gap-2 mt-2">
            <select class="form-select form-select-sm archive-dropdown workspace-select" aria-label="Choose workspace"></select>
        </div>
    `;

    const itemId = String(item.id ?? '');
    const image = card.querySelector('.card-img-top');
    const saveButton = card.querySelector('.save-btn');
    const viewButton = card.querySelector('.view-btn');
    const addButton = card.querySelector('.add-btn');
    const imageResolution = resolveResultImage(item);
    image.src = imageResolution.sourceUrl;
    image.alt = '';
    image.loading = 'lazy';
    image.decoding = 'async';
    image.referrerPolicy = 'no-referrer';
    image.setAttribute('loading', 'lazy');
    image.setAttribute('decoding', 'async');
    image.setAttribute('referrerpolicy', 'no-referrer');
    image.setAttribute('data-fallback-src', imageResolution.fallbackUrl);
    image.setAttribute('data-image-kind', imageResolution.kind);
    enhanceResultImage(image);
    card.querySelector('.card-title').textContent = String(item.title ?? '');
    card.querySelector('.card-description').textContent = String(item.description ?? '');
    card.querySelector('.result-source-text').textContent = String(item.source_name ?? '');
    for (const button of [saveButton, viewButton, addButton]) {
        button.dataset.itemId = itemId;
    }
    saveButton.dataset.query = query;
    updateSaveButton(saveButton, Boolean(item.saved));

    const workspaceSelect = card.querySelector('.workspace-select');
    hydrateWorkspaceSelect(workspaceSelect);

    // Event listeners
    saveButton.addEventListener('click', (e) => {
        e.stopPropagation();
        return toggleSave(item, saveButton);
    });
    viewButton.addEventListener('click', () => viewItem(item));
    addButton.addEventListener('click', () => addToWorkspace(item, workspaceSelect));

    return card;
}

function resultImageFallback(item) {
    return randomResultImageFallback();
}

function safeRemoteImageUrl(value) {
    if (typeof value !== 'string' || !value || value.length > 255) return '';
    if (value !== value.trim() || /\s/u.test(value) || value.includes('\\')) return '';

    try {
        const parsed = new URL(value);
        if (
            parsed.protocol !== 'https:'
            || parsed.username
            || parsed.password
            || (parsed.port && parsed.port !== '443')
            || parsed.hash
        ) {
            return '';
        }
        return value;
    } catch (_error) {
        return '';
    }
}

export function rememberResultImageFailure(value) {
    const remoteImage = safeRemoteImageUrl(value);
    if (remoteImage) failedResultImageUrls.add(remoteImage);
}

export function resolveResultImage(item) {
    const remoteUrl = safeRemoteImageUrl(item?.thumb_url);
    const fallbackUrl = resultImageFallback(item);
    const sourceUrl = remoteUrl && !failedResultImageUrls.has(remoteUrl)
        ? remoteUrl
        : fallbackUrl;
    return {
        remoteUrl,
        fallbackUrl,
        sourceUrl,
        kind: sourceUrl === remoteUrl ? 'remote' : 'fallback',
    };
}

if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener(
            'DOMContentLoaded',
            () => { enhanceResultCardImages(document); observeThemeForFallbacks(); },
            { once: true },
        );
    } else {
        enhanceResultCardImages(document);
        observeThemeForFallbacks();
    }
}

function observeThemeForFallbacks() {
    if (typeof MutationObserver === 'undefined') return;
    function refreshFallbacks() {
        var isDark = isDarkMode();
        document.querySelectorAll('.result-card-image[data-image-kind="fallback"]').forEach(function (img) {
            var src = img.getAttribute('src') || '';
            var fallback = img.getAttribute('data-fallback-src') || '';
            if (isDark) {
                if (!src.includes('/dark-')) {
                    img.src = darkFallbackPath(fallback);
                }
            } else {
                if (src.includes('/dark-')) {
                    img.src = fallback;
                }
            }
        });
    }
    refreshFallbacks();
    var observer = new MutationObserver(refreshFallbacks);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-bs-theme'] });
}

function updateSaveButton(button, saved) {
    button.setAttribute('aria-label', saved ? 'Saved result' : 'Save result');
    button.setAttribute('aria-pressed', saved ? 'true' : 'false');
    button.querySelector('.save-icon-light').className = saved
        ? 'bi bi-bookmark-fill text-danger save-icon-light'
        : 'bi bi-bookmark save-icon-light';
    button.querySelector('.save-icon-dark').className = saved
        ? 'bi bi-bookmark-check save-icon-dark d-none'
        : 'bi bi-bookmark save-icon-dark d-none';
}

async function toggleSave(item, button) {
    try {
        const isSaved = item.saved;
        const endpoint = isSaved ? '/api/item/unsave' : '/api/item/save';
        const query = button.dataset.query || '';
        const body = isSaved ? {item_id: item.id} : {item_id: item.id, query: query};
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        const result = await response.json();
        if (result.status) {
            item.saved = !isSaved;
            updateSaveButton(button, item.saved);
            showToast(item.saved ? 'Saved' : 'Removed from saved', 'success');
            if (!item.saved && typeof window.onItemUnsaved === 'function') {
                window.onItemUnsaved(item.id);
            }
        } else {
            showToast('Already saved', 'info');
        }
    } catch (error) {
        console.error('Save error:', error);
        showToast('Unable to save result', 'danger');
    }
}

function viewItem(item) {
    // Open viewer
    if (window.openViewer) window.openViewer(item);
}

function addToWorkspace(item, workspaceSelect) {
    if (!item.source_url) {
        showToast('Unable to add item: missing source URL', 'danger');
        return;
    }

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
            workspace_id: workspace_id
        })
    })
    .then(r => r.json())
    .then(addResult => {
        if (addResult.status) {
            showToast('Added to workspace', 'success');
        } else {
            showToast('Failed to add to workspace: ' + (addResult.error || 'Unknown error'), 'danger');
        }
    })
    .catch((error) => {
        console.error('Add to workspace error:', error);
        showToast('Error adding to workspace', 'danger');
    });
}
