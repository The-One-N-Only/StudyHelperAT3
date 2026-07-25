"use strict";

var ONBOARDING_STEPS = [
    {
        title: "Welcome to StudyLib!",
        description: "Your academic research assistant.",
        target: ".archive-wordmark",
        placement: "bottom"
    },
    {
        title: "Browse Sources",
        description: "Search across trusted academic sources.",
        target: 'a[href="/browse"]',
        placement: "right"
    },
    {
        title: "Workspaces",
        description: "Organize your research in workspaces.",
        target: '.workspaces-dropdown-toggle',
        placement: "right"
    },
    {
        title: "Alexander AI",
        description: "Ask Alexander to help analyze your sources.",
        target: '#alexanderChatInput',
        placement: "left"
    },
    {
        title: "Theme Toggle",
        description: "Switch between Old Book and Candlelit Archive themes.",
        target: '#themeToggle',
        placement: "bottom"
    }
];

var onboardingOverlay = null;
var currentStep = 0;

function createOverlay() {
    onboardingOverlay = document.createElement("div");
    onboardingOverlay.id = "onboardingOverlay";
    onboardingOverlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:100000;pointer-events:none;";
    document.body.appendChild(onboardingOverlay);
}

function showStep(index) {
    if (index >= ONBOARDING_STEPS.length) {
        finishOnboarding();
        return;
    }

    currentStep = index;
    var step = ONBOARDING_STEPS[index];
    var targetEl = document.querySelector(step.target);
    if (!targetEl) {
        showStep(index + 1);
        return;
    }

    var rect = targetEl.getBoundingClientRect();
    var tooltip = document.createElement("div");
    tooltip.className = "onboarding-tooltip";
    tooltip.style.cssText = "position:fixed;z-index:100001;background:var(--bs-body-bg,#fff);color:var(--bs-body-color,#000);border:1px solid var(--bs-border-color,#ddd);border-radius:12px;padding:16px;max-width:320px;box-shadow:0 8px 40px rgba(0,0,0,0.2);pointer-events:auto;";

    var top, left;
    if (step.placement === "bottom") {
        top = rect.bottom + 12;
        left = rect.left + rect.width / 2 - 160;
    } else if (step.placement === "right") {
        top = rect.top + rect.height / 2 - 40;
        left = rect.right + 12;
    } else if (step.placement === "left") {
        top = rect.top + rect.height / 2 - 40;
        left = rect.left - 328;
    } else {
        top = rect.bottom + 12;
        left = rect.left;
    }

    top = Math.max(8, Math.min(top, window.innerHeight - 200));
    left = Math.max(8, Math.min(left, window.innerWidth - 328));

    tooltip.style.top = top + "px";
    tooltip.style.left = left + "px";

    var isLast = index === ONBOARDING_STEPS.length - 1;
    tooltip.innerHTML =
        '<div class="d-flex justify-content-between align-items-center mb-2"><strong>' + escapeHtml(step.title) + '</strong><span class="small text-muted">' + (index + 1) + '/' + ONBOARDING_STEPS.length + '</span></div>' +
        '<p class="small mb-3">' + escapeHtml(step.description) + '</p>' +
        '<div class="d-flex justify-content-between align-items-center">' +
            '<button class="btn btn-sm btn-link text-muted p-0" id="onboardingSkip">Skip</button>' +
            '<button class="btn btn-sm btn-primary" id="onboardingNext">' + (isLast ? 'Finish' : 'Next') + '</button>' +
        '</div>';

    // Highlight target
    targetEl.style.outline = "2px solid var(--bs-primary, #0d6efd)";
    targetEl.style.outlineOffset = "4px";
    targetEl.style.borderRadius = "4px";

    // Remove previous tooltip
    var oldTooltip = document.querySelector(".onboarding-tooltip");
    if (oldTooltip) oldTooltip.remove();

    // Remove previous highlight
    document.querySelectorAll(".onboarding-highlight").forEach(function(el) {
        el.style.outline = "";
        el.style.outlineOffset = "";
    });
    targetEl.classList.add("onboarding-highlight");

    onboardingOverlay.appendChild(tooltip);

    document.getElementById("onboardingNext").addEventListener("click", function() {
        targetEl.style.outline = "";
        targetEl.style.outlineOffset = "";
        tooltip.remove();
        showStep(index + 1);
    });

    document.getElementById("onboardingSkip").addEventListener("click", function() {
        targetEl.style.outline = "";
        targetEl.style.outlineOffset = "";
        finishOnboarding();
    });

    // Click outside to dismiss
    var outsideClickHandler = function(e) {
        if (!tooltip.contains(e.target) && e.target !== targetEl) {
            targetEl.style.outline = "";
            targetEl.style.outlineOffset = "";
            tooltip.remove();
            document.removeEventListener("click", outsideClickHandler);
            finishOnboarding();
        }
    };
    setTimeout(function() { document.addEventListener("click", outsideClickHandler); }, 100);
}

function finishOnboarding() {
    document.querySelectorAll(".onboarding-highlight").forEach(function(el) {
        el.style.outline = "";
        el.style.outlineOffset = "";
    });
    if (onboardingOverlay) {
        onboardingOverlay.remove();
        onboardingOverlay = null;
    }
    var oldTooltip = document.querySelector(".onboarding-tooltip");
    if (oldTooltip) oldTooltip.remove();
    localStorage.setItem("onboarding_completed", "true");
}

export function startOnboarding() {
    if (onboardingOverlay) finishOnboarding();
    createOverlay();
    showStep(0);
}

function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
