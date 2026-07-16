(function () {
    const saved = localStorage.getItem("theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const theme = saved || preferred;
    document.documentElement.setAttribute("data-bs-theme", theme);

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-bs-theme");
        const newTheme = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-bs-theme", newTheme);
        localStorage.setItem("theme", newTheme);
        updateThemeButton();
    }

    function updateThemeButton() {
        const themeBtn = document.getElementById("themeToggle");
        if (!themeBtn) return;

        const current = document.documentElement.getAttribute("data-bs-theme");
        const isDark = current === "dark";
        themeBtn.innerHTML = isDark
            ? '<i class="bi bi-sun" aria-hidden="true"></i>'
            : '<i class="bi bi-moon-stars" aria-hidden="true"></i>';
        themeBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    }

    document.addEventListener("DOMContentLoaded", () => {
        const themeBtn = document.getElementById("themeToggle");
        if (themeBtn) {
            themeBtn.addEventListener("click", toggleTheme);
            updateThemeButton();
        }
    });
})();
