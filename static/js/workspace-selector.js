"use strict";

import { showToast } from './toast.js';

let workspaceCache = null;
let workspacePromise = null;

export function loadWorkspaces() {
    if (workspaceCache) {
        return Promise.resolve(workspaceCache);
    }
    if (workspacePromise) {
        return workspacePromise;
    }

    workspacePromise = fetch('/api/workspaces')
        .then((response) => response.json())
        .then((data) => {
            if (!data.status) {
                throw new Error(data.error || 'Failed to load workspaces');
            }
            workspaceCache = data.workspaces || [];
            return workspaceCache;
        })
        .catch((error) => {
            console.error('Workspace load failed:', error);
            showToast('Failed to load workspaces', 'danger');
            workspaceCache = [];
            return workspaceCache;
        })
        .finally(() => {
            workspacePromise = null;
        });

    return workspacePromise;
}

export function populateWorkspaceSelect(select, workspaces, selectedId = null) {
    select.innerHTML = '';
    if (!workspaces.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No workspaces';
        select.appendChild(option);
        select.disabled = true;
        return;
    }

    workspaces.forEach((workspace, index) => {
        const option = document.createElement('option');
        option.value = workspace.id;
        option.textContent = `${workspace.name} (${workspace.item_count})`;
        if (selectedId !== null) {
            option.selected = workspace.id === selectedId;
        } else if (index === 0) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    select.disabled = false;
}

export function hydrateWorkspaceSelect(select, selectedId = null) {
    if (!select) return;
    select.innerHTML = '<option>Loading workspaces…</option>';
    select.disabled = true;

    loadWorkspaces().then((workspaces) => {
        populateWorkspaceSelect(select, workspaces, selectedId);
    });
}

export function getSelectedWorkspaceId(select) {
    if (!select || !select.value) {
        return null;
    }
    return parseInt(select.value, 10) || null;
}

export function createWorkspaceSelectElement(selectedId = null) {
    const select = document.createElement('select');
    select.className = 'workspace-select form-select form-select-sm';
    hydrateWorkspaceSelect(select, selectedId);
    return select;
}

export function clearWorkspaceCache() {
    workspaceCache = null;
}
