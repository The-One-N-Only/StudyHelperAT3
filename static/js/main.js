"use strict";

import { openViewer } from './viewer.js';
window.openViewer = openViewer;

function initNavigation() {
    const brandMenuButton = document.getElementById('brandMenuButton');
    const navOverlay = document.getElementById('navSidebarOverlay');
    const closeButton = document.getElementById('closeNavSidebarBtn');
    const focusableSelector = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled]):not([type="hidden"])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
    ].join(',');
    const outsideInertStates = new Map();

    if (!brandMenuButton || !navOverlay) return;

    const dialog = navOverlay.querySelector('[role="dialog"]');
    const isSidebarOpen = () => !navOverlay.classList.contains('d-none');

    const getFocusableElements = () => Array.from(
        navOverlay.querySelectorAll(focusableSelector)
    ).filter((element) => element.getAttribute('aria-hidden') !== 'true');

    const makeOutsideContentInert = () => {
        outsideInertStates.clear();
        for (const element of document.body.children) {
            if (element === navOverlay) continue;
            outsideInertStates.set(element, element.inert);
            element.inert = true;
        }
    };

    const restoreOutsideContent = () => {
        for (const [element, wasInert] of outsideInertStates) {
            element.inert = wasInert;
        }
        outsideInertStates.clear();
    };

    const openSidebar = () => {
        if (isSidebarOpen()) return;

        // The dialog owns modality and restores every outside element's prior state.
        makeOutsideContentInert();
        navOverlay.classList.remove('d-none');
        navOverlay.setAttribute("aria-hidden", "false");
        brandMenuButton.setAttribute("aria-expanded", "true");
        document.body.classList.add('nav-sidebar-open');
        (getFocusableElements()[0] || dialog)?.focus();
    };

    const closeSidebar = () => {
        if (!isSidebarOpen()) return;

        navOverlay.classList.add('d-none');
        navOverlay.setAttribute("aria-hidden", "true");
        brandMenuButton.setAttribute("aria-expanded", "false");
        document.body.classList.remove('nav-sidebar-open');
        restoreOutsideContent();
        brandMenuButton.focus();
    };

    const containTabFocus = (event) => {
        const focusableElements = getFocusableElements();
        if (focusableElements.length === 0) {
            event.preventDefault();
            dialog?.focus();
            return;
        }

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        const focusIsOutside = !navOverlay.contains(document.activeElement);

        if (event.shiftKey && (document.activeElement === firstElement || focusIsOutside)) {
            event.preventDefault();
            lastElement.focus();
        } else if (!event.shiftKey && (
            document.activeElement === lastElement || focusIsOutside
        )) {
            event.preventDefault();
            firstElement.focus();
        }
    };

    brandMenuButton.addEventListener('click', openSidebar);
    closeButton?.addEventListener('click', closeSidebar);

    navOverlay.addEventListener('click', (event) => {
        if (event.target === navOverlay) closeSidebar();
    });

    document.addEventListener('keydown', (event) => {
        if (!isSidebarOpen()) return;

        if (event.key === 'Escape') {
            closeSidebar();
        } else if (event.key === 'Tab') {
            containTabFocus(event);
        }
    });
}

document.addEventListener('DOMContentLoaded', initNavigation);
