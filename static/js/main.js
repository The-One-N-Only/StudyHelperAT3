"use strict";

import { openViewer } from './viewer.js';
window.openViewer = openViewer;

function initSwipeToClose(offcanvasElement) {
    let startX = 0;
    let startY = 0;
    let swiping = false;

    offcanvasElement.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        startX = touch.clientX;
        startY = touch.clientY;
        swiping = true;
    }, { passive: true });

    offcanvasElement.addEventListener('touchmove', (e) => {
        if (!swiping) return;
        const touch = e.touches[0];
        const diffX = touch.clientX - startX;
        const diffY = touch.clientY - startY;
        if (Math.abs(diffX) > Math.abs(diffY) && diffX < -50) {
            swiping = false;
            const instance = bootstrap.Offcanvas.getInstance(offcanvasElement);
            if (instance) instance.hide();
        }
    }, { passive: true });

    offcanvasElement.addEventListener('touchend', () => { swiping = false; }, { passive: true });
}

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
        document.body.classList.add('offcanvas-push');
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
        document.body.classList.remove('offcanvas-push');
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

function initWorkspacesDropdown() {
    const dropdownContainer = document.querySelector('#navSidebarOffcanvas .workspaces-dropdown');
    const toggle = dropdownContainer?.querySelector('.workspaces-dropdown-toggle');
    const menu = document.getElementById('workspacesDropdownMenu');

    if (!toggle || !menu) return;

    fetch('/api/workspaces')
        .then((r) => r.json())
        .then((data) => {
            if (!data.status || !data.workspaces || data.workspaces.length === 0) return;

            menu.innerHTML = '';
            data.workspaces.forEach((ws) => {
                const link = document.createElement('a');
                link.className = 'workspace-link';
                link.href = `/workspace/${ws.id}`;
                link.textContent = ws.name;
                menu.appendChild(link);
            });
        })
        .catch(() => {});

    toggle.addEventListener('click', () => {
        const expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', String(!expanded));
        menu.classList.toggle('show', !expanded);
    });

    menu.addEventListener('click', (e) => {
        if (e.target.classList.contains('workspace-link')) {
            toggle.setAttribute('aria-expanded', 'false');
            menu.classList.remove('show');
        }
    });

    document.addEventListener('click', (e) => {
        if (!dropdownContainer.contains(e.target)) {
            toggle.setAttribute('aria-expanded', 'false');
            menu.classList.remove('show');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSwipeToClose(document.getElementById('navSidebarOffcanvas'));
    initWorkspacesDropdown();
    const sidebarBrowseLink = document.querySelector('#navSidebarOffcanvas a[href="/browse"]');
    if (sidebarBrowseLink) {
        sidebarBrowseLink.addEventListener('click', () => {
            sessionStorage.setItem('browse_from_sidebar', 'true');
        });
    }
});
