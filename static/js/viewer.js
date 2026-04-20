"use strict";

import { showToast } from './main.js';

let viewerOffcanvas;

document.addEventListener('DOMContentLoaded', () => {
    viewerOffcanvas = new bootstrap.Offcanvas(document.getElementById('viewerOffcanvas'));
});

export function openViewer(item) {
    const header = document.getElementById('viewerHeader');
    const body = document.getElementById('viewerBody');
    
    header.innerHTML = `
        <h6 class="fw-semibold text-truncate me-2">${item.title}</h6>
        <span class="badge bg-secondary rounded-pill">${item.source_name}</span>
        <small class="text-muted text-truncate">${item.source_url}</small>
        <a href="${item.source_url}" target="_blank" class="btn btn-link btn-sm p-0 ms-auto">
            <i class="bi bi-box-arrow-up-right"></i>
        </a>
    `;
    
    body.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p>Loading source...</p></div>';
    viewerOffcanvas.show();
    
    fetch(`/api/proxy/source?url=${encodeURIComponent(item.source_url)}`)
        .then(r => r.json())
        .then(result => {
            if (result.status) {
                body.innerHTML = `<iframe srcdoc="${result.html.replace(/"/g, '&quot;')}" class="viewer-iframe"></iframe>`;
            } else {
                body.innerHTML = `
                    <div class="alert alert-warning m-3">
                        <i class="bi bi-exclamation-triangle"></i>
                        ${result.error}
                        <a href="${item.source_url}" target="_blank" class="btn btn-outline-primary btn-sm ms-2">Open in new tab</a>
                    </div>
                `;
            }
        })
        .catch(() => {
            body.innerHTML = '<div class="alert alert-danger m-3">Failed to load source</div>';
            showToast('Failed to load source', 'danger');
        });
    
    // Add to workspace button
    document.getElementById('addToWorkspaceBtn').onclick = () => addToWorkspaceFromViewer(item);
}

function addToWorkspaceFromViewer(item) {
    fetch('/api/summarise', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({url: item.source_url, title: item.title})
    }).then(r => r.json()).then(result => {
        if (result.status) {
            fetch('/api/workspace/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    item_id: item.id,
                    summary: result.summary,
                    bullets: result.bullets,
                    relevance: result.relevance,
                    citation_apa: 'APA citation',
                    citation_harvard: 'Harvard citation'
                })
            }).then(r => r.json()).then(addResult => {
                if (addResult.status) {
                    showToast('Added to workspace', 'success');
                    viewerOffcanvas.hide();
                }
            });
        } else {
            showToast('Summarisation failed', 'danger');
        }
    });
}