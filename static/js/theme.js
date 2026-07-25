(function () {
    var savedTheme = localStorage.getItem("theme");
    var theme = savedTheme || "light";
    document.documentElement.setAttribute("data-bs-theme", theme);

    var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    var cursorGlow = null;
    var targetX = window.innerWidth / 2;
    var targetY = window.innerHeight * 0.3;
    var currentX = targetX;
    var currentY = targetY;
    var animationFrame = null;

    // ── Font Size ──
    var savedFontSize = localStorage.getItem("font_size") || "default";
    var fontScaleMap = { small: 0.9, default: 1.0, large: 1.3 };

    function applyFontSize() {
        var scale = fontScaleMap[savedFontSize] || 1.0;
        document.documentElement.style.setProperty("--font-size-modifier", scale);
        localStorage.setItem("font_size", savedFontSize);
    }

    // ── Dyslexic Font ──
    var savedDyslexic = localStorage.getItem("dyslexic_font") === "true";

    function applyDyslexicFont() {
        if (savedDyslexic) {
            document.documentElement.style.setProperty("--font-body", "var(--font-dyslexic)");
            document.documentElement.style.setProperty("--font-display", "var(--font-dyslexic)");
        } else {
            document.documentElement.style.removeProperty("--font-body");
            document.documentElement.style.removeProperty("--font-display");
        }
        localStorage.setItem("dyslexic_font", savedDyslexic);
    }

    // ── High Contrast ──
    var savedHighContrast = localStorage.getItem("high_contrast") === "true";

    function applyHighContrast() {
        var existing = document.getElementById("highContrastCSS");
        if (savedHighContrast) {
            if (!existing) {
                var link = document.createElement("link");
                link.id = "highContrastCSS";
                link.rel = "stylesheet";
                link.href = "/static/css/high-contrast.css";
                document.head.appendChild(link);
            }
        } else {
            if (existing) existing.remove();
        }
        localStorage.setItem("high_contrast", savedHighContrast);
    }

    applyFontSize();
    applyDyslexicFont();
    applyHighContrast();

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
            : emojiCursor('\uD83E\uDEB6', 4, 28);
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

    // ── Display Settings Panel ──
    function toggleDisplaySettings(event) {
        event.stopPropagation();
        var panel = document.getElementById("displaySettingsPanel");
        if (panel) panel.remove();

        var btn = document.getElementById("displaySettingsBtn");
        var rect = btn.getBoundingClientRect();
        panel = document.createElement("div");
        panel.id = "displaySettingsPanel";
        panel.className = "display-settings-panel";
        panel.style.cssText = "position:fixed;top:" + (rect.bottom + 8) + "px;right:" + (window.innerWidth - rect.right) + "px;z-index:10000;background:var(--bs-body-bg);border:1px solid var(--bs-border-color);border-radius:12px;padding:16px;min-width:240px;box-shadow:0 8px 32px rgba(0,0,0,0.15);";
        panel.innerHTML =
            '<div class="d-flex justify-content-between align-items-center mb-3"><h6 class="mb-0">Display Settings</h6><button class="btn-close btn-sm" id="closeDisplayPanel"></button></div>' +
            '<div class="mb-3">' +
                '<label class="form-label small fw-semibold">Font Size</label>' +
                '<div class="d-flex gap-2">' +
                    '<button class="btn btn-sm btn-outline-secondary font-size-btn" data-size="small">A-</button>' +
                    '<button class="btn btn-sm btn-outline-secondary font-size-btn" data-size="default">A</button>' +
                    '<button class="btn btn-sm btn-outline-secondary font-size-btn" data-size="large">A+</button>' +
                '</div>' +
            '</div>' +
            '<div class="mb-3">' +
                '<div class="form-check form-switch">' +
                    '<input class="form-check-input" type="checkbox" id="dyslexicToggle" ' + (savedDyslexic ? "checked" : "") + '>' +
                    '<label class="form-check-label" for="dyslexicToggle">Dyslexia-friendly font</label>' +
                '</div>' +
            '</div>' +
            '<div class="mb-0">' +
                '<div class="form-check form-switch">' +
                    '<input class="form-check-input" type="checkbox" id="highContrastToggle" ' + (savedHighContrast ? "checked" : "") + '>' +
                    '<label class="form-check-label" for="highContrastToggle">High contrast mode</label>' +
                '</div>' +
            '</div>';

        document.body.appendChild(panel);

        document.getElementById("closeDisplayPanel").addEventListener("click", function () { panel.remove(); });
        panel.addEventListener("click", function (e) { e.stopPropagation(); });

        panel.querySelectorAll(".font-size-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                savedFontSize = this.dataset.size;
                applyFontSize();
                panel.querySelectorAll(".font-size-btn").forEach(function (b) { b.classList.remove("active"); });
                this.classList.add("active");
            });
        });

        var dyslexicCheck = document.getElementById("dyslexicToggle");
        dyslexicCheck.addEventListener("change", function () {
            savedDyslexic = this.checked;
            applyDyslexicFont();
        });

        var hcCheck = document.getElementById("highContrastToggle");
        hcCheck.addEventListener("change", function () {
            savedHighContrast = this.checked;
            applyHighContrast();
        });

        var activeBtn = panel.querySelector('.font-size-btn[data-size="' + savedFontSize + '"]');
        if (activeBtn) activeBtn.classList.add("active");

        setTimeout(function () { document.addEventListener("click", function closePanel(e) { if (!panel.contains(e.target) && e.target.id !== "displaySettingsBtn") { panel.remove(); document.removeEventListener("click", closePanel); } }); }, 0);
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

        var displayBtn = document.getElementById("displaySettingsBtn");
        if (displayBtn) displayBtn.addEventListener("click", toggleDisplaySettings);
    });
})();
