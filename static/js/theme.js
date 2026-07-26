(function () {
    var savedTheme = localStorage.getItem("theme");
    var theme = savedTheme || "light";
    document.documentElement.setAttribute("data-bs-theme", theme);

    var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    var cursorGlow = null;
    var flameOffsetY = -5;
    var targetX = window.innerWidth / 2;
    var targetY = window.innerHeight * 0.3;
    var currentX = targetX;
    var currentY = targetY;
    var glowOpacity = 0.85;
    var targetOpacity = 0.85;
    var flickerTimer = 0;
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

    function drawCandleCursor() {
        var c = document.createElement('canvas');
        c.width = 32;
        c.height = 32;
        var ctx = c.getContext('2d');

        ctx.fillStyle = '#F5DEB3';
        ctx.beginPath();
        ctx.roundRect(12, 15, 8, 15, 1.5);
        ctx.fill();

        ctx.fillStyle = '#E8D5B7';
        ctx.beginPath();
        ctx.ellipse(16, 29.5, 4.5, 1.5, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#444';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(16, 15);
        ctx.lineTo(16, 11);
        ctx.stroke();

        var grad = ctx.createRadialGradient(16, 8, 1, 16, 8, 7);
        grad.addColorStop(0, '#FFF8E0');
        grad.addColorStop(0.25, '#FFB800');
        grad.addColorStop(0.55, '#E87800');
        grad.addColorStop(1, '#C85000');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(16, 1);
        ctx.quadraticCurveTo(21, 6, 16, 13);
        ctx.quadraticCurveTo(11, 6, 16, 1);
        ctx.fill();

        ctx.fillStyle = 'rgba(255, 248, 224, 0.5)';
        ctx.beginPath();
        ctx.ellipse(16, 7, 2.5, 4, 0, 0, Math.PI * 2);
        ctx.fill();

        return 'url(' + c.toDataURL('image/png') + ') 16 4, auto';
    }

    function drawQuillCursor() {
        var c = document.createElement('canvas');
        c.width = 32;
        c.height = 32;
        var ctx = c.getContext('2d');

        ctx.fillStyle = '#E8D5B7';
        ctx.strokeStyle = '#B8966A';
        ctx.lineWidth = 0.6;
        ctx.beginPath();
        ctx.moveTo(7, 30);
        ctx.quadraticCurveTo(12, 18, 24, 3);
        ctx.quadraticCurveTo(29, 4, 24, 9);
        ctx.quadraticCurveTo(15, 20, 7, 30);
        ctx.fill();
        ctx.stroke();

        ctx.strokeStyle = '#B8966A';
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        ctx.moveTo(7, 30);
        ctx.lineTo(24, 5);
        ctx.stroke();

        ctx.fillStyle = '#4A3520';
        ctx.beginPath();
        ctx.moveTo(7, 30);
        ctx.lineTo(5, 31);
        ctx.lineTo(9, 29);
        ctx.fill();

        return 'url(' + c.toDataURL('image/png') + ') 7 30, auto';
    }

    function applyCursor() {
        if (!finePointer.matches) {
            document.body.style.cursor = 'auto';
            return;
        }
        try {
            var isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
            document.body.style.cursor = isDark
                ? drawCandleCursor()
                : drawQuillCursor();
        } catch(e) {
            document.body.style.cursor = 'auto';
        }
    }

    function animateGlow() {
        if (!cursorGlow) return;
        
        currentX += (targetX - currentX) * 0.35;
        currentY += (targetY - currentY) * 0.35;
        
        flickerTimer++;
        if (flickerTimer % 3 === 0) {
            targetOpacity = 0.65 + Math.random() * 0.3;
        }
        glowOpacity += (targetOpacity - glowOpacity) * 0.2;
        
        var jitterX = (Math.random() - 0.5) * 6;
        var jitterY = (Math.random() - 0.5) * 8;
        
        cursorGlow.style.left = (currentX + jitterX) + 'px';
        cursorGlow.style.top = (currentY + jitterY + flameOffsetY) + 'px';
        cursorGlow.style.opacity = glowOpacity;
        
        animationFrame = requestAnimationFrame(animateGlow);
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
        if (animationFrame === null) {
            animationFrame = requestAnimationFrame(animateGlow);
        }
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
        if (isDark && finePointer.matches) {
            startGlow();
        } else {
            stopGlow();
            if (cursorGlow) {
                cursorGlow.style.opacity = 0;
            }
        }
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
        targetX = window.innerWidth / 2;
        targetY = window.innerHeight * 0.4;
        currentX = targetX;
        currentY = targetY;
        if (cursorGlow) {
            cursorGlow.style.left = currentX + 'px';
            cursorGlow.style.top = (currentY + flameOffsetY) + 'px';
        }
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
