(function () {
    const saved = localStorage.getItem("theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const theme = saved || preferred;
    document.documentElement.setAttribute("data-bs-theme", theme);

    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    let cursorGlow = null;
    let isTracking = false;

    function trackPointer(event) {
        cursorGlow.style.left = `${event.clientX}px`;
        cursorGlow.style.top = `${event.clientY}px`;
    }

    function startGlow() {
        if (!cursorGlow || isTracking || !finePointer.matches) return;
        isTracking = true;
        window.addEventListener("pointermove", trackPointer, { passive: true });
    }

    function stopGlow() {
        if (!isTracking) return;
        window.removeEventListener("pointermove", trackPointer);
        isTracking = false;
    }

    function syncGlow() {
        const shouldTrack = document.documentElement.getAttribute("data-bs-theme") === "dark"
            && finePointer.matches;
        if (shouldTrack) startGlow();
        else stopGlow();
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-bs-theme");
        const newTheme = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-bs-theme", newTheme);
        localStorage.setItem("theme", newTheme);
        updateThemeButton();
        syncGlow();
    }

    function updateThemeButton() {
        const themeBtn = document.getElementById("themeToggle");
        if (!themeBtn) return;

        const current = document.documentElement.getAttribute("data-bs-theme");
        const isDark = current === "dark";
        themeBtn.innerHTML = isDark
            ? '<i class="bi bi-sun" aria-hidden="true"></i>'
            : '<i class="bi bi-moon-stars-fill" aria-hidden="true"></i>';
        themeBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    }

    document.addEventListener("DOMContentLoaded", () => {
        cursorGlow = document.querySelector(".candle-glow");
        const themeBtn = document.getElementById("themeToggle");
        if (themeBtn) {
            themeBtn.addEventListener("click", toggleTheme);
            updateThemeButton();
        }
        finePointer.addEventListener("change", syncGlow);
        syncGlow();
    });
})();
