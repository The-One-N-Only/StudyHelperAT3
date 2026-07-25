"use strict";

var EMPTY_STATE_ICONS = {
    sources: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="8" width="48" height="48" rx="4" stroke="currentColor" stroke-width="2" fill="none"/><line x1="20" y1="24" x2="44" y2="24" stroke="currentColor" stroke-width="2"/><line x1="20" y1="32" x2="44" y2="32" stroke="currentColor" stroke-width="2"/><line x1="20" y1="40" x2="36" y2="40" stroke="currentColor" stroke-width="2"/></svg>',
    notes: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="12" y="6" width="40" height="52" rx="3" stroke="currentColor" stroke-width="2" fill="none"/><line x1="20" y1="20" x2="44" y2="20" stroke="currentColor" stroke-width="2"/><line x1="20" y1="28" x2="44" y2="28" stroke="currentColor" stroke-width="2"/><line x1="20" y1="36" x2="44" y2="36" stroke="currentColor" stroke-width="2"/><path d="M20 44 L28 44" stroke="currentColor" stroke-width="2"/><path d="M20 50 L36 50" stroke="currentColor" stroke-width="2"/></svg>',
    chat: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="32" cy="32" r="24" stroke="currentColor" stroke-width="2" fill="none"/><path d="M20 26 L44 26" stroke="currentColor" stroke-width="2"/><path d="M20 34 L38 34" stroke="currentColor" stroke-width="2"/><path d="M20 42 L32 42" stroke="currentColor" stroke-width="2"/></svg>',
    workspace: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="12" width="48" height="40" rx="4" stroke="currentColor" stroke-width="2" fill="none"/><rect x="8" y="12" width="48" height="12" rx="4" stroke="currentColor" stroke-width="2" fill="none"/><line x1="20" y1="32" x2="44" y2="32" stroke="currentColor" stroke-width="2"/><line x1="20" y1="40" x2="36" y2="40" stroke="currentColor" stroke-width="2"/></svg>',
    saved: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 8 L48 8 L48 56 L32 44 L16 56 Z" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
    search: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="28" cy="28" r="14" stroke="currentColor" stroke-width="2" fill="none"/><line x1="38" y1="38" x2="50" y2="50" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    trash: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="16" y="18" width="32" height="38" rx="3" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="18" x2="52" y2="18" stroke="currentColor" stroke-width="2"/><path d="M24 18 L24 10 L40 10 L40 18" stroke="currentColor" stroke-width="2" fill="none"/></svg>',
    default: '<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="32" cy="32" r="20" stroke="currentColor" stroke-width="2" fill="none"/><line x1="32" y1="24" x2="32" y2="36" stroke="currentColor" stroke-width="2"/><circle cx="32" cy="42" r="1.5" fill="currentColor"/></svg>'
};

export function showEmptyState(container, options) {
    if (!container) return;
    var icon = options.icon || "default";
    var iconSvg = EMPTY_STATE_ICONS[icon] || EMPTY_STATE_ICONS.default;
    var actionHtml = "";
    if (options.action) {
        actionHtml = '<button class="btn btn-primary btn-sm mt-3 empty-state-action">' + escapeHtml(options.action.label) + '</button>';
    }

    container.innerHTML =
        '<div class="empty-state text-center py-5 px-3" style="opacity:0.7;">' +
            '<div class="mb-3 empty-state-icon" style="color:var(--bs-secondary-color);">' + iconSvg + '</div>' +
            '<h5 class="empty-state-title">' + escapeHtml(options.title || "") + '</h5>' +
            (options.description ? '<p class="text-muted small mb-0 empty-state-desc">' + escapeHtml(options.description) + '</p>' : "") +
            actionHtml +
        '</div>';

    if (options.action && options.action.onClick) {
        var btn = container.querySelector(".empty-state-action");
        if (btn) btn.addEventListener("click", options.action.onClick);
    }
}

function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
