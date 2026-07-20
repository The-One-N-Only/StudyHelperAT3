"use strict";

import { openViewer } from './viewer.js';
window.openViewer = openViewer;

function initNavigation() {
    const brandMenuButton = document.getElementById('brandMenuButton');
    const navOffcanvasElement = document.getElementById('navSidebarOffcanvas');
    const outsideInertStates = new Map();

    if (!brandMenuButton || !navOffcanvasElement) return;

    const existing = bootstrap.Offcanvas.getInstance(navOffcanvasElement);
    if (existing) existing.dispose();

    const navOffcanvas = new bootstrap.Offcanvas(navOffcanvasElement, {
        backdrop: true,
        scroll: false,
    });

    const makeOutsideContentInert = () => {
        outsideInertStates.clear();
        for (const element of document.body.children) {
            if (element === navOffcanvasElement) continue;
            if (element.classList.contains('offcanvas-backdrop')) continue;
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

    navOffcanvasElement.addEventListener('show.bs.offcanvas', () => {
        makeOutsideContentInert();
        brandMenuButton.setAttribute("aria-label", "Navigation menu open.");
    });

    navOffcanvasElement.addEventListener('shown.bs.offcanvas', () => {
        brandMenuButton.setAttribute("aria-expanded", "true");
        const first = navOffcanvasElement.querySelector('a, button');
        if (first) first.focus();
    });

    navOffcanvasElement.addEventListener('hide.bs.offcanvas', () => {
        brandMenuButton.setAttribute("aria-expanded", "false");
        brandMenuButton.setAttribute("aria-label", "Open navigation menu");
    });

    navOffcanvasElement.addEventListener('hidden.bs.offcanvas', () => {
        restoreOutsideContent();
        brandMenuButton.focus();
    });

    brandMenuButton.addEventListener('click', () => {
        navOffcanvas.show();
    });

    navOffcanvasElement.querySelectorAll('.list-group a[href]').forEach((link) => {
        link.addEventListener('click', () => {
            navOffcanvas.hide();
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    const sidebarBrowseLink = document.querySelector('#navSidebarOverlay a[href="/browse"]');
    if (sidebarBrowseLink) {
        sidebarBrowseLink.addEventListener('click', () => {
            sessionStorage.setItem('browse_from_sidebar', 'true');
        });
    }
});
