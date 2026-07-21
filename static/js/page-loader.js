"use strict";

async function bootstrapPage() {
    const root = document.getElementById('pageRoot');
    if (!root) return;

    const page = root.dataset.page;
    const data = window.PAGE_DATA || {};

    try {
        switch (page) {
            case 'home': {
                const module = await import('./pages/home.js');
                module.initHome(root, data);
                break;
            }
            case 'browse': {
                const module = await import('./pages/browse.js');
                module.initBrowse(root);
                break;
            }
            case 'workspace': {
                const module = await import('./pages/workspace.js');
                module.initWorkspace(root);
                break;
            }
            case 'saved': {
                const module = await import('./pages/saved.js');
                module.initSaved(root);
                break;
            }
            default:
                break;
        }
    } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Page bootstrap failed', error);
    }
}

document.addEventListener('DOMContentLoaded', bootstrapPage);
