"use strict";

import { openViewer } from './viewer.js';
window.openViewer = openViewer;

function initNavigation() {
    const navMenuButton = document.getElementById('navMenuButton');
    const navOverlay = document.getElementById('navSidebarOverlay');
    const closeButton = document.getElementById('closeNavSidebarBtn');

    if (!navMenuButton || !navOverlay) return;

    navMenuButton.addEventListener('click', () => {
        navOverlay.classList.remove('d-none');
        document.body.classList.add('nav-sidebar-open');
    });

    const closeSidebar = () => {
        navOverlay.classList.add('d-none');
        document.body.classList.remove('nav-sidebar-open');
    };

    if (closeButton) {
        closeButton.addEventListener('click', closeSidebar);
    }

    navOverlay.addEventListener('click', (event) => {
        if (event.target === navOverlay) {
            closeSidebar();
        }
    });
}

document.addEventListener('DOMContentLoaded', initNavigation);
