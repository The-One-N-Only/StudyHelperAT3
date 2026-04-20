"use strict";

import { showToast } from './main.js';

document.addEventListener('DOMContentLoaded', () => {
    attachWorkspaceListeners();
    
    document.getElementById('exportPdfBtn').addEventListener('click', () => exportWorkspace('pdf'));
    document.getElementById('exportDocxBtn').addEventListener('click', () => exportWorkspace('docx'));
});

function attachWorkspaceListeners() {
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.id;
            removeFromWorkspace(id);
        });
    });
    // Add other listeners if needed
}

function loadWorkspace() {
    fetch('/api/workspace/items')
        .then(r => r.json())
        .then(result => {
            const container = document.getElementById('workspaceContainer');
            if (result.items.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="bi bi-collection display-4 text-muted"></i>
                        <h5>Your workspace is empty</h5>
                        <p class="text-muted">Add sources from the Browse page</p>
                        <a href="/browse" class="btn btn-primary">Browse Sources</a>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = '';
            result.items.forEach(item => {
                const card = createWorkspaceCard(item);
                container.appendChild(card);
            });
            attachWorkspaceListeners();
        });
}

function createWorkspaceCard(item) {
    const card = document.createElement('div');
    card.className = 'card mb-3';
    card.innerHTML = `
        <div class="card-header d-flex align-items-center">
            <h6 class="fw-semibold mb-0 text-truncate">${item.title}</h6>
            <span class="badge bg-secondary ms-2">${item.source_name}</span>
            <button class="btn btn-outline-danger btn-sm ms-auto remove-btn" data-id="${item.id}">
                <i class="bi bi-trash"></i>
            </button>
        </div>
        <div class="card-body">
            <p>${item.summary}</p>
            <button class="btn btn-link btn-sm p-0 toggle-bullets" data-bs-toggle="collapse" data-bs-target="#bullets-${item.id}">
                Key Points ▾
            </button>
            <div class="collapse mt-2" id="bullets-${item.id}">
                <ul>
                    ${item.bullets.map(b => `<li>${b}</li>`).join('')}
                </ul>
            </div>
            ${item.relevance ? `<div class="alert alert-info mt-2"><i class="bi bi-lightbulb"></i> ${item.relevance}</div>` : ''}
        </div>
        <div class="card-footer bg-transparent">
            <small class="font-monospace text-muted">${item.citation_apa}</small>
        </div>
    `;
    
    card.querySelector('.remove-btn').addEventListener('click', () => removeFromWorkspace(item.id));
    
    return card;
}

function removeFromWorkspace(id) {
    if (confirm('Remove from workspace?')) {
        fetch(`/api/workspace/${id}`, {method: 'DELETE'})
            .then(r => r.json())
            .then(result => {
                if (result.status) {
                    showToast('Removed', 'success');
                    // Remove the card
                    const card = document.querySelector(`[data-id="${id}"]`).closest('.card');
                    card.remove();
                }
            });
    }
}

function exportWorkspace(format) {
    fetch('/api/workspace/items')
        .then(r => r.json())
        .then(result => {
            const items = result.items;
            const atn = document.getElementById('atnInput').value;
            const citation_format = document.querySelector('input[name="citationFormat"]:checked').value;
            fetch(`/api/export/${format}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({items, citation_format, atn})
            }).then(r => {
                if (r.ok) {
                    return r.blob();
                }
            }).then(blob => {
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `StudyLib_Compilation.${format}`;
                a.click();
                URL.revokeObjectURL(url);
                showToast(`Exported as ${format.toUpperCase()}`, 'success');
            });
        });
}
