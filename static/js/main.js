"use strict";

import { openViewer } from './viewer.js';
window.openViewer = openViewer;

function initNavigation() {
    const brandMenuButton = document.getElementById('brandMenuButton');
    const navOverlay = document.getElementById('navSidebarOverlay');
    const closeButton = document.getElementById('closeNavSidebarBtn');

    if (!brandMenuButton || !navOverlay) return;

    const openSidebar = () => {
        navOverlay.classList.remove('d-none');
        navOverlay.setAttribute("aria-hidden", "false");
        brandMenuButton.setAttribute("aria-expanded", "true");
        document.body.classList.add('nav-sidebar-open');
        closeButton?.focus();
    };

    const closeSidebar = () => {
        navOverlay.classList.add('d-none');
        navOverlay.setAttribute("aria-hidden", "true");
        brandMenuButton.setAttribute("aria-expanded", "false");
        document.body.classList.remove('nav-sidebar-open');
        brandMenuButton.focus();
    };

    brandMenuButton.addEventListener('click', openSidebar);
    closeButton?.addEventListener('click', closeSidebar);

    navOverlay.addEventListener('click', (event) => {
        if (event.target === navOverlay) closeSidebar();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !navOverlay.classList.contains('d-none')) {
            closeSidebar();
        }
    });
}

document.addEventListener('DOMContentLoaded', initNavigation);
