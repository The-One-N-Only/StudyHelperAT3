"use strict";

const undoToasts = [];

export function showUndoToast(message, onUndo, duration = 5000) {
    const container = document.getElementById("toastContainer");
    const id = "undo-toast-" + Date.now();
    const html = `
        <div id="${id}" class="toast align-items-center border-0 shadow" role="alert" aria-live="assertive">
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center gap-2 flex-grow-1">
                    <i class="bi bi-arrow-counterclockwise text-primary"></i>
                    <span class="flex-grow-1">${message}</span>
                    <button type="button" class="btn btn-sm btn-outline-primary undo-action-btn" data-toast-id="${id}">Undo</button>
                </div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>`;
    container.insertAdjacentHTML("beforeend", html);
    const toastEl = document.getElementById(id);
    const toast = new bootstrap.Toast(toastEl, { delay: duration });
    toast.show();

    const undoBtn = toastEl.querySelector('.undo-action-btn');
    undoBtn.addEventListener('click', () => {
        onUndo();
        toast.hide();
    });

    toastEl.addEventListener("hidden.bs.toast", () => {
        toastEl.remove();
        const idx = undoToasts.indexOf(toastEl);
        if (idx !== -1) undoToasts.splice(idx, 1);
    });

    undoToasts.push(toastEl);

    // Stack positioning
    undoToasts.forEach((t, i) => {
        t.style.marginTop = (i * 60) + 'px';
    });
}

export function clearUndoToasts() {
    undoToasts.forEach(t => {
        const instance = bootstrap.Toast.getInstance(t);
        if (instance) instance.hide();
        t.remove();
    });
    undoToasts.length = 0;
}
