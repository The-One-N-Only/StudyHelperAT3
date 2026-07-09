"use strict";

import { showToast } from '../toast.js';

let allWorkspaces = [];
let currentFilter = '';

export function initHome(root) {
    root.innerHTML = `
        <div class="container-fluid py-4">
            <div class="d-flex flex-column flex-md-row align-items-start align-items-md-center justify-content-between gap-3 mb-4">
                <div>
                    <h1 class="mb-1">Recent Workspaces</h1>
                    <p class="text-muted mb-0">Jump back into your most recent work or search for the right workspace.</p>
                </div>
                <div class="input-group home-search-group" style="max-width: 560px; width: 100%;">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input id="workspaceSearch" type="search" class="form-control" placeholder="Search workspaces..." autocomplete="off">
                </div>
            </div>

            <div id="workspaceCards" class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3"></div>
        </div>
    `;

    root.querySelector('#workspaceSearch').addEventListener('input', (event) => {
        currentFilter = event.target.value.trim().toLowerCase();
        renderWorkspaceCards();
    });

    loadWorkspaces();
}

async function loadWorkspaces() {
    try {
        const response = await fetch('/api/workspaces');
        const data = await response.json();
        if (!data.status) {
            throw new Error('Unable to load workspaces');
        }
        allWorkspaces = data.workspaces || [];
        renderWorkspaceCards();
    } catch (error) {
        showToast('Unable to load recent workspaces', 'danger');
    }
}

function renderWorkspaceCards() {
    const container = document.getElementById('workspaceCards');
    container.innerHTML = '';

    const addCard = document.createElement('div');
    addCard.className = 'col';
    addCard.innerHTML = `
        <div class="card h-100 border-dashed workspace-card workspace-card-add text-center text-muted">
            <div class="card-body d-flex flex-column justify-content-center align-items-center py-5">
                <div class="display-6 mb-3">+</div>
                <h5>Create new workspace</h5>
                <p class="small text-muted mb-0">Start a fresh workspace for your next study session.</p>
            </div>
        </div>
    `;
    addCard.querySelector('.card').addEventListener('click', createWorkspaceDialog);
    container.appendChild(addCard);

    const filtered = allWorkspaces.filter((workspace) => {
        return !currentFilter || workspace.name.toLowerCase().includes(currentFilter);
    });

    if (filtered.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'col-12';
        empty.innerHTML = `<div class="alert alert-secondary mb-0">No workspaces match your search. Create a new workspace to get started.</div>`;
        container.appendChild(empty);
        return;
    }

    filtered.forEach((workspace) => {
        const card = document.createElement('div');
        card.className = 'col';
        card.innerHTML = `
            <div class="card h-100 workspace-card position-relative">
                <div class="card-body d-flex flex-column">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <div class="badge bg-primary bg-opacity-10 text-primary">Workspace</div>
                        <i class="bi bi-three-dots-vertical text-muted"></i>
                    </div>
                    <div class="mb-4">
                        <h5 class="card-title mb-1 text-truncate">${escapeHtml(workspace.name)}</h5>
                        <p class="text-muted small mb-0">${workspace.item_count} sources · ${workspace.note_count} notes</p>
                    </div>
                    <div class="mt-auto text-muted small">
                        Created on ${formatDate(workspace.time_created)}
                    </div>
                </div>
                <a class="stretched-link" href="/workspace/${workspace.id}"></a>
            </div>
        `;
        container.appendChild(card);
    });
}

async function createWorkspaceDialog() {
    const name = prompt('Enter a name for the new workspace:', 'New Workspace');
    if (!name) {
        return;
    }

    try {
        const response = await fetch('/api/workspaces', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        const data = await response.json();
        if (!data.status) {
            throw new Error('Create failed');
        }
        showToast('Workspace created', 'success');
        allWorkspaces.unshift({
            id: data.workspace.id,
            name: data.workspace.name,
            time_created: data.workspace.time_created,
            item_count: 0,
            note_count: 0
        });
        renderWorkspaceCards();
        openWorkspace(data.workspace.id);
    } catch (error) {
        showToast('Unable to create workspace', 'danger');
    }
}

function openWorkspace(workspaceId) {
    window.location.href = `/workspace/${workspaceId}`;
}

function formatDate(timestamp) {
    if (!timestamp) {
        return 'Unknown';
    }
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
