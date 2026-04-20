"use strict";

export function showToast(message, type = "success") {
    const container = document.getElementById("toastContainer");
    const id = "toast-" + Date.now();
    const iconMap = {
        success: "bi-check-circle-fill text-success",
        danger: "bi-x-circle-fill text-danger",
        warning: "bi-exclamation-triangle-fill text-warning",
        info: "bi-info-circle-fill text-info"
    };
    const html = `
        <div id="${id}" class="toast align-items-center border-0 shadow" role="alert" aria-live="assertive">
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center gap-2">
                    <i class="bi ${iconMap[type]}"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>`;
    container.insertAdjacentHTML("beforeend", html);
    const toastEl = document.getElementById(id);
    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
    toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}