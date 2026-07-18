(function () {
    const saved = localStorage.getItem("theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    const theme = saved || preferred;
    document.documentElement.setAttribute("data-bs-theme", theme);

    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    let candleLayer = null;
    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight * 0.3;
    let currentX = targetX;
    let currentY = targetY;
    let animationFrame = null;
    let isTracking = false;

    function animateCandle() {
        currentX += (targetX - currentX) * 0.15;
        currentY += (targetY - currentY) * 0.15;
        candleLayer.style.setProperty("--candle-x", `${currentX}px`);
        candleLayer.style.setProperty("--candle-y", `${currentY}px`);

        const isMoving = Math.abs(targetX - currentX) > 0.5 || Math.abs(targetY - currentY) > 0.5;
        animationFrame = isMoving ? requestAnimationFrame(animateCandle) : null;
    }

    function trackPointer(event) {
        targetX = event.clientX;
        targetY = event.clientY;
        if (animationFrame === null) {
            animationFrame = requestAnimationFrame(animateCandle);
        }
    }

    function startCandle() {
        if (!candleLayer || isTracking || !finePointer.matches) return;
        isTracking = true;
        window.addEventListener("pointermove", trackPointer, { passive: true });
    }

    function stopCandle() {
        if (!isTracking) return;
        window.removeEventListener("pointermove", trackPointer);
        if (animationFrame !== null) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
        isTracking = false;
    }

    function syncCandle() {
        const shouldTrack = document.documentElement.getAttribute("data-bs-theme") === "dark"
            && finePointer.matches;
        if (shouldTrack) startCandle();
        else stopCandle();
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-bs-theme");
        const newTheme = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-bs-theme", newTheme);
        localStorage.setItem("theme", newTheme);
        updateThemeButton();
        syncCandle();
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
        candleLayer = document.querySelector(".candle-glow");
        const themeBtn = document.getElementById("themeToggle");
        if (themeBtn) {
            themeBtn.addEventListener("click", toggleTheme);
            updateThemeButton();
        }
        finePointer.addEventListener("change", syncCandle);
        syncCandle();
    });
})();
