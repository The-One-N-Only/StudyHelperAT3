"use strict";

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value;
    return div.innerHTML;
}

function renderGlobalSearch() {
    const root = document.getElementById('pageRoot');
    if (!root) return;

    const query = window.GLOBAL_SEARCH_QUERY || '';
    const results = window.GLOBAL_SEARCH_RESULTS || {};

    const categoryLabels = {
        sources: { icon: 'bi-globe2', label: 'Sources' },
        files: { icon: 'bi-file-earmark', label: 'Files' },
        notes: { icon: 'bi-file-earmark-text', label: 'Notes' },
        workspaces: { icon: 'bi-folder', label: 'Workspaces' },
    };

    const categoryColors = {
        sources: 'primary',
        files: 'success',
        notes: 'info',
        workspaces: 'warning',
    };

    let html = `
        <div class="container-fluid py-4 archive-page">
            <div class="archive-content">
                <div class="mb-4">
                    <h3 class="archive-page-title mb-2">Global Search</h3>
                    <form class="d-flex gap-2" action="/browse/global-search" method="GET" role="search">
                        <div class="input-group" style="max-width: 500px;">
                            <input type="text" class="form-control" name="q" value="${escapeHtml(query)}" placeholder="Search everything..." aria-label="Search query">
                            <button class="btn btn-primary btn-brass" type="submit"><i class="bi bi-search me-1"></i>Search</button>
                        </div>
                    </form>
        `;

    if (!query) {
        html += `<p class="text-muted mt-3">Enter a search term to find sources, files, notes, and workspaces.</p></div></div></div>`;
        root.innerHTML = html;
        return;
    }

    html += `</div>`;

    let hasResults = false;
    for (const [category, items] of Object.entries(results)) {
        if (!items || items.length === 0) continue;
        hasResults = true;
        const info = categoryLabels[category] || { icon: 'bi-search', label: category };
        const color = categoryColors[category] || 'secondary';

        html += `
            <div class="card surface-wood mb-4">
                <div class="card-header d-flex align-items-center gap-2">
                    <i class="bi ${info.icon}" aria-hidden="true"></i>
                    <h5 class="mb-0">${info.label}</h5>
                    <span class="badge bg-${color} rounded-pill ms-auto">${items.length}</span>
                </div>
                <div class="list-group list-group-flush">
        `;

        items.forEach((item) => {
            const title = item.title || item.filename || item.name || 'Untitled';
            const subtitle = item.source_name || item.file_type || '';
            const url = item.source_url || (item.id ? `/workspace/${item.id}` : '#');
            html += `
                <a href="${escapeHtml(url)}" class="list-group-item list-group-item-action d-flex align-items-center gap-3">
                    <div class="flex-grow-1">
                        <div class="fw-semibold">${escapeHtml(title)}</div>
                        ${subtitle ? `<small class="text-muted">${escapeHtml(subtitle)}</small>` : ''}
                    </div>
                    <span class="badge bg-${color} archive-category-badge">${info.label}</span>
                </a>
            `;
        });

        html += `</div></div>`;
    }

    if (!hasResults) {
        html += `
            <div class="text-center py-5">
                <i class="bi bi-search display-4 text-muted" aria-hidden="true"></i>
                <h5 class="mt-3">No results found for "${escapeHtml(query)}"</h5>
                <p class="text-muted">Try a different search term.</p>
            </div>
        `;
    }

    html += `</div></div>`;
    root.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', renderGlobalSearch);
