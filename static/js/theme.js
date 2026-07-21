(function () {
    const saved = localStorage.getItem("theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const theme = saved || preferred;
    document.documentElement.setAttribute("data-bs-theme", theme);

    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    let cursorGlow = null;
    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight * 0.3;
    let currentX = targetX;
    let currentY = targetY;
    let animationFrame = null;

    function emojiCursor(emoji, hotX, hotY) {
        var size = 32;
        var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '">' +
            '<text x="50%" y="50%" font-size="24" text-anchor="middle" dominant-baseline="central">' +
            emoji + '</text></svg>';
        return 'url("data:image/svg+xml,' + encodeURIComponent(svg) + '") ' + hotX + ' ' + hotY + ', auto';
    }

    function applyCursor() {
        if (!finePointer.matches) {
            document.body.style.cursor = 'auto';
            return;
        }
        var isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        document.body.style.cursor = isDark
            ? emojiCursor('\uD83D\uDD6F\uFE0F', 16, 6)
            : emojiCursor('\u2702\uFE0F', 4, 28);
    }

    function animateGlow() {
        currentX += (targetX - currentX) * 0.25;
        currentY += (targetY - currentY) * 0.25;
        cursorGlow.style.left = currentX + 'px';
        cursorGlow.style.top = currentY + 'px';
        var isMoving = Math.abs(targetX - currentX) > 0.5 || Math.abs(targetY - currentY) > 0.5;
        animationFrame = isMoving ? requestAnimationFrame(animateGlow) : null;
    }

    function trackPointer(event) {
        targetX = event.clientX;
        targetY = event.clientY;
        if (animationFrame === null) {
            animationFrame = requestAnimationFrame(animateGlow);
        }
    }

    function startGlow() {
        if (!cursorGlow || !finePointer.matches) return;
        window.addEventListener("pointermove", trackPointer, { passive: true });
    }

    function stopGlow() {
        window.removeEventListener("pointermove", trackPointer);
        if (animationFrame !== null) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
    }

    function syncGlow() {
        var isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        if (isDark && finePointer.matches) startGlow();
        else stopGlow();
    }

    function toggleTheme() {
        var current = document.documentElement.getAttribute("data-bs-theme");
        var newTheme = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-bs-theme", newTheme);
        localStorage.setItem("theme", newTheme);
        updateThemeButton();
        applyCursor();
        syncGlow();
    }

    function updateThemeButton() {
        var themeBtn = document.getElementById("themeToggle");
        if (!themeBtn) return;
        var isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
        themeBtn.innerHTML = isDark
            ? '<i class="bi bi-sun" aria-hidden="true"></i>'
            : '<i class="bi bi-moon-stars-fill" aria-hidden="true"></i>';
        themeBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    }

    document.addEventListener("DOMContentLoaded", function () {
        cursorGlow = document.querySelector(".candle-glow");
        var themeBtn = document.getElementById("themeToggle");
        if (themeBtn) {
            themeBtn.addEventListener("click", toggleTheme);
            updateThemeButton();
        }
        finePointer.addEventListener("change", function () { applyCursor(); syncGlow(); });
        applyCursor();
        syncGlow();
    });
})();
