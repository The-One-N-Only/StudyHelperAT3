export function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        const tag = document.activeElement?.tagName?.toLowerCase();
        const isInput = tag === 'input' || tag === 'textarea' || tag === 'select';

        if (e.key === 'Escape') {
            const offcanvases = document.querySelectorAll('.offcanvas.show');
            offcanvases.forEach((el) => {
                const instance = bootstrap.Offcanvas.getInstance(el);
                if (instance) instance.hide();
            });
            const modals = document.querySelectorAll('.modal.show');
            modals.forEach((el) => {
                const instance = bootstrap.Modal.getInstance(el);
                if (instance) instance.hide();
            });
            const dropdowns = document.querySelectorAll('.browse-dropdown-menu.show, .workspace-menu-dropdown:not(.d-none)');
            dropdowns.forEach((el) => el.classList.remove('show'));
            return;
        }

        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('searchInput');
            if (searchInput) { searchInput.focus(); searchInput.select(); }
            return;
        }

        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
            e.preventDefault();
            const globalSearchInput = document.querySelector('form[action*="global-search"] input[name="q"]');
            if (globalSearchInput) { globalSearchInput.focus(); globalSearchInput.select(); }
            return;
        }

        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            const createNoteBtn = document.getElementById('createNoteBtn');
            if (createNoteBtn) createNoteBtn.click();
            return;
        }

        if (e.key === '?' && !isInput) {
            e.preventDefault();
            showShortcutsHelp();
            return;
        }

        if (e.key === 't' && !isInput) {
            e.preventDefault();
            const themeBtn = document.getElementById('themeToggle');
            if (themeBtn) themeBtn.click();
            return;
        }

        if (e.key === 's' && !isInput) {
            e.preventDefault();
            const studioSourcesTab = document.getElementById('studio-sources-tab');
            if (studioSourcesTab) {
                const tab = new bootstrap.Tab(studioSourcesTab);
                tab.show();
            }
            const searchNewBtn = document.getElementById('searchNewBtn');
            if (searchNewBtn) searchNewBtn.focus();
            return;
        }
    });
}

function showShortcutsHelp() {
    const existing = document.getElementById('shortcutsHelpModal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'shortcutsHelpModal';
    overlay.className = 'modal fade show d-block';
    overlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Keyboard shortcuts');
    overlay.innerHTML = `
        <div class="modal-dialog modal-dialog-centered modal-sm">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Keyboard Shortcuts</h5>
                    <button type="button" class="btn-close" id="shortcutsCloseBtn" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <dl class="mb-0">
                        <div class="d-flex justify-content-between mb-2"><dt><kbd>Esc</kbd></dt><dd>Close panels</dd></div>
                        <div class="d-flex justify-content-between mb-2"><dt><kbd>Ctrl+K</kbd></dt><dd>Focus search</dd></div>
                        <div class="d-flex justify-content-between mb-2"><dt><kbd>Ctrl+N</kbd></dt><dd>New note</dd></div>
                        <div class="d-flex justify-content-between mb-2"><dt><kbd>?</kbd></dt><dd>This help</dd></div>
                        <div class="d-flex justify-content-between mb-2"><dt><kbd>T</kbd></dt><dd>Toggle theme</dd></div>
                        <div class="d-flex justify-content-between mb-2"><dt><kbd>S</kbd></dt><dd>Focus sources</dd></div>
                    </dl>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="shortcutsGotItBtn">Got it</button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    const close = () => overlay.remove();
    overlay.querySelector('#shortcutsCloseBtn').addEventListener('click', close);
    overlay.querySelector('#shortcutsGotItBtn').addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    overlay.querySelector('#shortcutsGotItBtn').focus();
}
