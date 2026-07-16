import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import pytest
import soupsieve
from soupsieve.css_parser import PSEUDO_SIMPLE_NO_MATCH, css_unescape
from soupsieve.css_types import SelectorNull


ROOT = Path(__file__).resolve().parents[1]
SVG_NAMES = (
    "compass-rose.svg",
    "sextant.svg",
    "stacked-books.svg",
    "open-book.svg",
    "scrollwork-flourish.svg",
)
DARK_ROOT_SELECTOR = '[data-bs-theme="dark"]'
DARK_BODY_SELECTOR = '[data-bs-theme="dark"] body'
DARK_THEME_ATTRIBUTE_PATTERN = re.compile(
    r'''\[\s*data-bs-theme\s*=\s*(?:"dark"|'dark'|dark)\s*\]'''
)
OPEN_VIEWER_IMPORT_PATTERN = re.compile(
    r'''^[ \t]*import\s*\{\s*openViewer\s*\}\s*from\s*
    (?P<quote>['"])\.\/viewer\.js(?P=quote)\s*;?[ \t]*
    (?://[^\r\n]*|/\*[\s\S]*?\*/)?[ \t]*$''',
    flags=re.MULTILINE | re.VERBOSE,
)
FLAT_CSS_RULE_PATTERN = re.compile(
    r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}",
    flags=re.DOTALL,
)
CSS_TOKEN_PATTERN = re.compile(
    r'/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r"\\(?:[0-9a-fA-F]{1,6}[ \t\r\n\f]?|[^\r\n\f])|[{};,()\[\]]",
    flags=re.DOTALL,
)
APPROVED_FONT_STYLESHEET = (
    "https://fonts.googleapis.com/css2?family=Cinzel:wght@600"
    "&family=Crimson+Pro:wght@400;600&display=swap"
)
CUSTOM_CSS_STYLESHEET = "{{ url_for('static', filename='css/custom.css') }}"
EXPECTED_DARK_TOKENS = {
    "--bg-950": "#0A0A0A",
    "--bg-900": "#14100B",
    "--surface-800": "#22170B",
    "--surface-700": "#2E1F0F",
    "--surface-600": "#3D2914",
    "--surface-500": "#4D3319",
    "--gold-100": "#EDD9B5",
    "--gold-300": "#C9A876",
    "--gold-500": "#A9824F",
    "--gold-700": "#8A6635",
    "--gold-900": "#5C4423",
    "--text-primary": "#E7E1DA",
    "--text-secondary": "#A69A8C",
    "--text-disabled": "#6E6459",
    "--danger-rust": "#9C6242",
    "--info-slate": "#6E87A6",
    "--success-verdigris": "#6E9B7C",
    "--font-display": '"Cinzel", "Times New Roman", serif',
    "--font-body": '"Crimson Pro", "EB Garamond", Georgia, serif',
    "--text-display-lg": "32px",
    "--text-display-sm": "22px",
    "--text-body-lg": "16px",
    "--text-body": "14px",
    "--text-caption": "12px",
    "--radius-panel": "12px",
    "--radius-button": "8px",
    "--radius-pill": "999px",
    "--radius-input": "8px",
    "--shadow-warm-raised": (
        "0 2px 10px 0 hsl(28 60% 4% / 0.55), "
        "0 0 0 1px hsl(35 40% 40% / 0.06)"
    ),
    "--shadow-warm-glow": (
        "0 0 0 1px var(--gold-500), "
        "0 0 18px 2px hsl(35 70% 55% / 0.25)"
    ),
    "--z-bg-base": "0",
    "--z-bg-illustration": "1",
    "--z-content": "10",
    "--z-candle-glow": "40",
    "--z-overlay": "50",
}
EXPECTED_BOOTSTRAP_MAPPINGS = {
    "--bs-body-bg": "var(--bg-950)",
    "--bs-body-color": "var(--text-primary)",
    "--bs-body-font-family": "var(--font-body)",
    "--bs-secondary-color": "var(--text-secondary)",
    "--bs-border-color": "hsl(35 40% 45% / 0.18)",
    "--bs-tertiary-bg": "var(--surface-800)",
    "--bs-card-bg": "var(--surface-800)",
    "--bs-offcanvas-bg": "var(--surface-700)",
    "--bs-primary": "var(--gold-300)",
    "--bs-primary-rgb": "201, 168, 118",
    "--bs-secondary": "var(--surface-600)",
    "--bs-secondary-rgb": "61, 41, 20",
    "--bs-danger": "var(--danger-rust)",
    "--bs-link-color": "var(--gold-300)",
    "--bs-link-hover-color": "var(--gold-100)",
}
EXPECTED_DARK_ROOT_DECLARATIONS = {
    "color-scheme": "dark",
    **EXPECTED_DARK_TOKENS,
    **EXPECTED_BOOTSTRAP_MAPPINGS,
}
EXPECTED_DARK_BODY_DECLARATIONS = {
    "min-height": "100vh",
    "color": "var(--text-primary)",
    "background": (
        "radial-gradient(ellipse 60% 40% at 50% 0%, "
        "hsl(32 45% 18% / 0.5), transparent 60%), var(--bg-950)"
    ),
    "background-attachment": "fixed",
    "font-family": "var(--font-body)",
}
SHARED_REQUIRED_SELECTORS = (
    '[data-bs-theme="dark"] .surface-leather',
    '[data-bs-theme="dark"] .btn-secondary-wood',
    '[data-bs-theme="dark"] .btn-brass',
    '[data-bs-theme="dark"] .btn-ghost',
    '[data-bs-theme="dark"] .icon-button',
    '[data-bs-theme="dark"] .archive-dropdown',
    '[data-bs-theme="dark"] .archive-count-badge',
    '[data-bs-theme="dark"] .archive-category-badge',
    '[data-bs-theme="dark"] .archive-illustration',
)
TASK3_DARK_ONLY_CLASSES = (
    "surface-leather",
    "btn-secondary-wood",
    "btn-brass",
    "btn-ghost",
    "icon-button",
    "icon-button-danger",
    "archive-dropdown",
    "archive-count-badge",
    "archive-category-badge",
    "archive-illustration",
    "illustration-compass",
    "illustration-sextant",
    "illustration-books",
    "illustration-open-book",
    "illustration-flourish",
)
TASK4_NAVIGATION_CLASSES = (
    "archive-navbar",
    "archive-wordmark",
    "nav-sidebar-open",
    "nav-sidebar-overlay",
    "nav-sidebar",
)
TASK4_ALLOWED_THEME_NEUTRAL_SELECTOR_GROUPS = frozenset(
    {
        (".archive-wordmark",),
        ("body.nav-sidebar-open",),
        (".nav-sidebar-overlay",),
        (".nav-sidebar-overlay.d-none",),
        (".nav-sidebar",),
        (".nav-sidebar .list-group-item",),
    }
)
TASK5_DASHBOARD_CLASSES = (
    "archive-page",
    "archive-page-home",
    "archive-content",
    "archive-page-title",
    "home-search-group",
    "workspace-card",
    "workspace-card-add",
)
TASK5_ALLOWED_THEME_NEUTRAL_SELECTOR_GROUPS = frozenset(
    {
        (".workspace-card",),
        (".workspace-card:hover",),
        (".workspace-card-add",),
    }
)
EXPECTED_DARK_ICON_COLORS = {
    '[data-bs-theme="dark"] .icon-button': "var(--gold-300) !important",
    '[data-bs-theme="dark"] .icon-button:hover': "var(--gold-100) !important",
    '[data-bs-theme="dark"] .icon-button-danger:hover': (
        "var(--danger-rust) !important"
    ),
}
SHARED_CONTROL_MOTION_SELECTORS = (
    '[data-bs-theme="dark"] button',
    '[data-bs-theme="dark"] .btn',
    '[data-bs-theme="dark"] input',
    '[data-bs-theme="dark"] select',
    '[data-bs-theme="dark"] textarea',
    '[data-bs-theme="dark"] .btn-secondary-wood',
    '[data-bs-theme="dark"] .btn-brass',
    '[data-bs-theme="dark"] .btn-ghost',
    '[data-bs-theme="dark"] .icon-button',
    '[data-bs-theme="dark"] .archive-dropdown',
    '[data-bs-theme="dark"] .form-control',
    '[data-bs-theme="dark"] .form-select',
    '[data-bs-theme="dark"] .navbar-brand',
)
DROPDOWN_MENU_SELECTORS = (
    '[data-bs-theme="dark"] .dropdown-menu',
    '[data-bs-theme="dark"] .browse-dropdown-menu',
)
DROPDOWN_OPEN_SELECTORS = (
    '[data-bs-theme="dark"] .dropdown-menu.show',
    '[data-bs-theme="dark"] .browse-dropdown-menu.show',
)
REDUCED_MOTION_SELECTORS = (
    '[data-bs-theme="dark"] *',
    '[data-bs-theme="dark"] *::before',
    '[data-bs-theme="dark"] *::after',
)
EXPECTED_TOAST_ICON_MAP = {
    "success": "bi-check-circle text-success",
    "danger": "bi-x-circle text-danger",
    "warning": "bi-exclamation-triangle text-warning",
    "info": "bi-info-circle text-info",
}
TOAST_RUNTIME_HARNESS = r"""
const rendered = [];
const toastElement = { addEventListener() {}, remove() {} };
const container = {
  insertAdjacentHTML(position, html) {
    if (position !== "beforeend") throw new Error(`unexpected insertion: ${position}`);
    rendered.push(html);
  }
};
globalThis.document = {
  getElementById(id) {
    return id === "toastContainer" ? container : toastElement;
  }
};
globalThis.bootstrap = { Toast: class { show() {} } };
Date.now = () => 1700000000000;
const { showToast } = await import(process.argv[1]);
for (const type of ["success", "danger", "warning", "info"]) {
  const before = rendered.length;
  showToast(`message-${type}`, type);
  if (rendered.length !== before + 1) throw new Error(`no render for ${type}`);
}
process.stdout.write(JSON.stringify(rendered));
""".strip()
NAVIGATION_RUNTIME_HARNESS = r"""
const elements = new Map();
const documentListeners = new Map();

function invariant(condition, message) {
  if (!condition) throw new Error(message);
}

class FakeClassList {
  constructor(names = []) {
    this.names = new Set(names);
  }

  add(name) {
    this.names.add(name);
  }

  remove(name) {
    this.names.delete(name);
  }

  contains(name) {
    return this.names.has(name);
  }
}

class FakeElement {
  constructor(id, classNames = [], attributes = {}, inert = false) {
    this.id = id;
    this.classList = new FakeClassList(classNames);
    this.attributes = new Map(Object.entries(attributes));
    this.inert = inert;
    this.listeners = new Map();
    this.focusableElements = [];
    this.dialogElement = null;
  }

  addEventListener(type, callback) {
    const callbacks = this.listeners.get(type) || [];
    callbacks.push(callback);
    this.listeners.set(type, callbacks);
  }

  dispatch(type, init = {}) {
    const callbacks = this.listeners.get(type) || [];
    invariant(callbacks.length > 0, `missing ${type} listener on ${this.id}`);
    for (const callback of callbacks) {
      callback({ type, target: this, ...init });
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  focus() {
    document.activeElement = this;
  }

  querySelectorAll() {
    return this.focusableElements;
  }

  querySelector() {
    return this.dialogElement;
  }

  contains(element) {
    return element === this || this.focusableElements.includes(element);
  }
}

const brandMenuButton = new FakeElement(
  "brandMenuButton",
  [],
  { "aria-expanded": "false" },
);
const navOverlay = new FakeElement(
  "navSidebarOverlay",
  ["nav-sidebar-overlay", "d-none"],
  { "aria-hidden": "true" },
);
const closeButton = new FakeElement("closeNavSidebarBtn");
const navDialog = new FakeElement("navDialog", [], { "tabindex": "-1" });
const homeLink = new FakeElement("homeLink");
const browseLink = new FakeElement("browseLink");
const uploadLink = new FakeElement("uploadLink");
const overlayChild = new FakeElement("overlayChild");
navOverlay.focusableElements = [closeButton, homeLink, browseLink, uploadLink];
navOverlay.dialogElement = navDialog;

const navbar = new FakeElement("navbar");
const pageContent = new FakeElement("pageContent", [], {}, true);
const toastContainer = new FakeElement("toastContainer");
for (const element of [brandMenuButton, navOverlay, closeButton]) {
  elements.set(element.id, element);
}

globalThis.window = {};
globalThis.document = {
  activeElement: null,
  body: {
    children: [navbar, pageContent, toastContainer, navOverlay],
    classList: new FakeClassList(),
  },
  getElementById(id) {
    return elements.get(id) ?? null;
  },
  addEventListener(type, callback) {
    const callbacks = documentListeners.get(type) || [];
    callbacks.push(callback);
    documentListeners.set(type, callbacks);
  },
};

function dispatchDocument(type, init = {}) {
  const callbacks = documentListeners.get(type) || [];
  invariant(callbacks.length > 0, `missing document ${type} listener`);
  const event = {
    type,
    defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; },
    ...init,
  };
  for (const callback of callbacks) callback(event);
  return event;
}

function assertOpen(context, expectedFocus = closeButton) {
  invariant(!navOverlay.classList.contains("d-none"), `${context}: overlay hidden`);
  invariant(navOverlay.getAttribute("aria-hidden") === "false", `${context}: aria-hidden`);
  invariant(brandMenuButton.getAttribute("aria-expanded") === "true", `${context}: aria-expanded`);
  invariant(document.body.classList.contains("nav-sidebar-open"), `${context}: body class`);
  invariant(document.activeElement === expectedFocus, `${context}: initial focus`);
  invariant(navbar.inert, `${context}: navbar not inert`);
  invariant(pageContent.inert, `${context}: pre-inert content changed`);
  invariant(toastContainer.inert, `${context}: toast container not inert`);
}

function assertClosed(context) {
  invariant(navOverlay.classList.contains("d-none"), `${context}: overlay visible`);
  invariant(navOverlay.getAttribute("aria-hidden") === "true", `${context}: aria-hidden`);
  invariant(brandMenuButton.getAttribute("aria-expanded") === "false", `${context}: aria-expanded`);
  invariant(!document.body.classList.contains("nav-sidebar-open"), `${context}: body class`);
  invariant(document.activeElement === brandMenuButton, `${context}: wordmark focus`);
  invariant(!navbar.inert, `${context}: navbar inert state not restored`);
  invariant(pageContent.inert, `${context}: pre-inert content state not restored`);
  invariant(!toastContainer.inert, `${context}: toast inert state not restored`);
}

await import(process.argv[1]);
dispatchDocument("DOMContentLoaded");

brandMenuButton.dispatch("click");
assertOpen("open");

uploadLink.focus();
const forwardTab = dispatchDocument("keydown", { key: "Tab", shiftKey: false });
invariant(forwardTab.defaultPrevented, "forward Tab not contained");
invariant(document.activeElement === closeButton, "forward Tab did not wrap to first");

closeButton.focus();
const backwardTab = dispatchDocument("keydown", { key: "Tab", shiftKey: true });
invariant(backwardTab.defaultPrevented, "Shift+Tab not contained");
invariant(document.activeElement === uploadLink, "Shift+Tab did not wrap to last");

closeButton.dispatch("click");
assertClosed("close button");

brandMenuButton.dispatch("click");
navOverlay.dispatch("click", { target: overlayChild });
assertOpen("overlay child click");
navOverlay.dispatch("click", { target: navOverlay });
assertClosed("overlay click");

brandMenuButton.dispatch("click");
dispatchDocument("keydown", { key: "Enter" });
assertOpen("non-Escape key");
dispatchDocument("keydown", { key: "Escape" });
assertClosed("Escape");

navOverlay.focusableElements = [];
brandMenuButton.dispatch("click");
assertOpen("no focusable open", navDialog);
navbar.focus();
const noFocusableTab = dispatchDocument("keydown", { key: "Tab", shiftKey: false });
invariant(noFocusableTab.defaultPrevented, "no-focusable Tab not contained");
invariant(document.activeElement === navDialog, "no-focusable Tab did not refocus dialog");
dispatchDocument("keydown", { key: "Escape" });
assertClosed("no focusable Escape");

process.stdout.write("navigation runtime ok");
""".strip()
HOME_RUNTIME_HARNESS = r"""
function invariant(condition, message) {
  if (!condition) throw new Error(message);
}

function escapeText(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

class FakeElement {
  constructor(id = "") {
    this.id = id;
    this.className = "";
    this.children = [];
    this.listeners = new Map();
    this.cardTarget = null;
    this._innerHTML = "";
    this._textContent = null;
    this.value = "";
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this._textContent = null;
    this.children = [];
  }

  get innerHTML() {
    return this._textContent === null ? this._innerHTML : escapeText(this._textContent);
  }

  set textContent(value) {
    this._textContent = String(value);
  }

  get textContent() {
    return this._textContent ?? "";
  }

  addEventListener(type, callback) {
    const callbacks = this.listeners.get(type) || [];
    callbacks.push(callback);
    this.listeners.set(type, callbacks);
  }

  async dispatch(type, init = {}) {
    const callbacks = this.listeners.get(type) || [];
    invariant(callbacks.length > 0, `missing ${type} listener on ${this.id || "element"}`);
    const event = { type, target: this, ...init };
    for (const callback of callbacks) await callback(event);
  }

  querySelector(selector) {
    if (selector === "#workspaceSearch") return searchInput;
    if (selector === ".card") {
      this.cardTarget ||= new FakeElement("workspaceCardTarget");
      return this.cardTarget;
    }
    return null;
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }
}

const root = new FakeElement("root");
const searchInput = new FakeElement("workspaceSearch");
const workspaceCards = new FakeElement("workspaceCards");
const fetchCalls = [];
globalThis.toastCalls = [];
globalThis.window = { location: { href: "" } };
globalThis.prompt = (message, defaultValue) => {
  invariant(message === "Enter a name for the new workspace:", "prompt message changed");
  invariant(defaultValue === "New Workspace", "prompt default changed");
  return "New Workspace";
};
globalThis.document = {
  getElementById(id) {
    return id === "workspaceCards" ? workspaceCards : null;
  },
  createElement() {
    return new FakeElement();
  },
};
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (options?.method === "POST") {
    return {
      async json() {
        return {
          status: true,
          workspace: {
            id: 8,
            name: "Created <Workspace>",
            time_created: 0,
          },
        };
      },
    };
  }
  return {
    async json() {
      return {
        status: true,
        workspaces: [{
          id: 7,
          name: "<unsafe & name>",
          time_created: 0,
          item_count: 3,
          note_count: 0,
        }],
      };
    },
  };
};

const home = await import(process.argv[1]);
home.initHome(root);
await new Promise((resolve) => setTimeout(resolve, 0));

invariant(fetchCalls.length === 1, "initial load did not issue one request");
invariant(fetchCalls[0].url === "/api/workspaces", "initial API URL changed");
invariant(fetchCalls[0].options === undefined, "initial request options changed");
invariant(searchInput.listeners.get("input")?.length === 1, "search listener missing");
invariant(workspaceCards.children.length === 2, "initial cards did not render");

let addCard = workspaceCards.children[0];
invariant(addCard.innerHTML.includes("Create new workspace"), "add card label changed");
invariant(addCard.querySelector(".card").listeners.get("click")?.length === 1, "add listener missing");

let renderedCard = workspaceCards.children[1].innerHTML;
invariant(renderedCard.includes("&lt;unsafe &amp; name&gt;"), "workspace title not escaped");
invariant(!renderedCard.includes("<unsafe"), "unsafe workspace title rendered as markup");
invariant(renderedCard.includes("3 sources"), "source metadata changed");
invariant(renderedCard.includes("0 notes"), "note metadata changed");
invariant(renderedCard.includes("Created on Unknown"), "created date changed");
invariant(
  renderedCard.includes('class="stretched-link" href="/workspace/7"'),
  "workspace stretched link changed",
);

await searchInput.dispatch("input", { target: { value: "missing" } });
invariant(workspaceCards.children.length === 2, "filtered empty state shape changed");
invariant(
  workspaceCards.children[1].innerHTML.includes("No workspaces match your search"),
  "filtered empty state missing",
);

await searchInput.dispatch("input", { target: { value: "  UNSAFE  " } });
invariant(workspaceCards.children.length === 2, "search trim/lowercase behavior changed");
await searchInput.dispatch("input", { target: { value: "" } });

addCard = workspaceCards.children[0];
await addCard.querySelector(".card").dispatch("click");
invariant(fetchCalls.length === 2, "create did not issue one request");
const createCall = fetchCalls[1];
invariant(createCall.url === "/api/workspaces", "create API URL changed");
invariant(createCall.options.method === "POST", "create method changed");
invariant(
  createCall.options.headers["Content-Type"] === "application/json",
  "create content type changed",
);
invariant(JSON.parse(createCall.options.body).name === "New Workspace", "create body changed");
invariant(
  JSON.stringify(globalThis.toastCalls) === JSON.stringify([["Workspace created", "success"]]),
  "create toast changed",
);
invariant(window.location.href === "/workspace/8", "created workspace did not open");
invariant(workspaceCards.children.length === 3, "created workspace not prepended");
renderedCard = workspaceCards.children[1].innerHTML;
invariant(renderedCard.includes("Created &lt;Workspace&gt;"), "created title not escaped");
invariant(
  renderedCard.includes('class="stretched-link" href="/workspace/8"'),
  "created workspace stretched link changed",
);

process.stdout.write("home runtime ok");
""".strip()
EXPECTED_SHARED_RULES = (
    (
        SHARED_CONTROL_MOTION_SELECTORS,
        {
            "transition": (
                "background-color 150ms ease, border-color 150ms ease, "
                "color 150ms ease"
            ),
        },
    ),
    (
        ('[data-bs-theme="dark"] .surface-leather',),
        {
            "background-color": "var(--surface-800)",
            "background-image": (
                "linear-gradient(var(--surface-800), var(--surface-800)), "
                'url("/static/img/textures/leather-texture.png")'
            ),
            "background-blend-mode": "multiply",
            "background-position": "0 0",
            "background-repeat": "repeat, repeat",
            "background-size": "auto, 420px",
            "border": "1px solid hsl(35 40% 45% / 0.18)",
            "border-radius": "var(--radius-panel)",
            "box-shadow": "var(--shadow-warm-raised)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .btn-secondary-wood',),
        {
            "background-color": "var(--surface-700)",
            "background-image": (
                "linear-gradient(var(--surface-700), var(--surface-700)), "
                'url("/static/img/textures/wood-texture.png")'
            ),
            "background-blend-mode": "multiply",
            "background-position": "0 0",
            "background-repeat": "repeat, repeat",
            "background-size": "auto, 200px",
            "border": "1px solid hsl(35 40% 45% / 0.22)",
            "border-radius": "var(--radius-button)",
            "color": "var(--gold-300)",
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .btn-secondary-wood:hover',
            '[data-bs-theme="dark"] .btn-secondary-wood:active',
        ),
        {
            "border-color": "var(--gold-500)",
            "color": "var(--gold-100)",
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .btn-brass',
            '[data-bs-theme="dark"] .btn-primary',
        ),
        {
            "--bs-btn-color": "var(--bg-950)",
            "--bs-btn-bg": "var(--gold-300)",
            "--bs-btn-border-color": "transparent",
            "--bs-btn-hover-color": "var(--bg-950)",
            "--bs-btn-hover-bg": "var(--gold-100)",
            "--bs-btn-hover-border-color": "transparent",
            "--bs-btn-active-color": "var(--bg-950)",
            "--bs-btn-active-bg": "var(--gold-500)",
            "--bs-btn-active-border-color": "transparent",
            "background-image": (
                "linear-gradient(hsl(35 80% 75% / 0.25), transparent 40%)"
            ),
            "border-radius": "var(--radius-button)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .btn-ghost',),
        {
            "background": "transparent",
            "border": "1px solid transparent",
            "border-radius": "var(--radius-button)",
            "color": "var(--gold-300)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .btn-ghost:hover',),
        {
            "border-color": "var(--gold-700)",
            "color": "var(--gold-100)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .icon-button',),
        {
            "align-items": "center",
            "background": "transparent",
            "border": "0",
            "border-radius": "var(--radius-button)",
            "color": EXPECTED_DARK_ICON_COLORS[
                '[data-bs-theme="dark"] .icon-button'
            ],
            "display": "inline-flex",
            "justify-content": "center",
            "min-height": "2rem",
            "min-width": "2rem",
            "padding": "0.25rem",
        },
    ),
    (
        ('[data-bs-theme="dark"] .icon-button:hover',),
        {
            "background": "hsl(35 70% 55% / 0.08)",
            "color": EXPECTED_DARK_ICON_COLORS[
                '[data-bs-theme="dark"] .icon-button:hover'
            ],
        },
    ),
    (
        ('[data-bs-theme="dark"] .icon-button-danger:hover',),
        {
            "color": EXPECTED_DARK_ICON_COLORS[
                '[data-bs-theme="dark"] .icon-button-danger:hover'
            ]
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .archive-dropdown',
            '[data-bs-theme="dark"] .form-select',
        ),
        {
            "background-color": "var(--surface-700)",
            "border-color": "var(--gold-700)",
            "border-radius": "var(--radius-button)",
            "color": "var(--text-primary)",
        },
    ),
    (
        DROPDOWN_MENU_SELECTORS,
        {
            "background": "var(--surface-600)",
            "border-color": "hsl(35 40% 45% / 0.22)",
            "border-radius": "var(--radius-button)",
            "box-shadow": "var(--shadow-warm-raised)",
            "color": "var(--text-primary)",
            "display": "block",
            "opacity": "0",
            "pointer-events": "none",
            "transition": "opacity 180ms ease-in, visibility 0s linear 180ms",
            "visibility": "hidden",
        },
    ),
    (
        DROPDOWN_OPEN_SELECTORS,
        {
            "opacity": "1",
            "pointer-events": "auto",
            "transition": "opacity 180ms ease-out, visibility 0s linear 0s",
            "visibility": "visible",
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .form-control',
            '[data-bs-theme="dark"] .input-group-text',
        ),
        {
            "background": "var(--surface-800)",
            "border-color": "hsl(35 40% 45% / 0.3)",
            "border-radius": "var(--radius-input)",
            "color": "var(--text-primary)",
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .form-control::placeholder',
            '[data-bs-theme="dark"] textarea::placeholder',
        ),
        {
            "color": "var(--text-secondary)",
            "opacity": "1",
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .form-control:focus',
            '[data-bs-theme="dark"] .form-select:focus',
            '[data-bs-theme="dark"] .btn:focus-visible',
            '[data-bs-theme="dark"] .icon-button:focus-visible',
            '[data-bs-theme="dark"] .navbar-brand:focus-visible',
        ),
        {
            "border-color": "var(--gold-300)",
            "box-shadow": "var(--shadow-warm-glow)",
            "outline": "0",
        },
    ),
    (
        ('[data-bs-theme="dark"] .text-muted',),
        {"color": "var(--text-secondary) !important"},
    ),
    (
        ('[data-bs-theme="dark"] .archive-count-badge',),
        {
            "background": "var(--gold-900)",
            "border-radius": "var(--radius-pill)",
            "color": "var(--gold-100)",
            "font-size": "var(--text-caption)",
            "font-variant-numeric": "tabular-nums",
        },
    ),
    (
        ('[data-bs-theme="dark"] .archive-category-badge',),
        {
            "background": "hsl(35 40% 45% / 0.15)",
            "border-radius": "var(--radius-pill)",
            "color": "var(--gold-300)",
            "font-size": "var(--text-caption)",
            "letter-spacing": "0.04em",
            "text-transform": "uppercase",
        },
    ),
    (
        ('[data-bs-theme="dark"] .card',),
        {
            "--bs-card-bg": "var(--surface-800)",
            "--bs-card-border-color": "hsl(35 40% 45% / 0.18)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .offcanvas',),
        {"--bs-offcanvas-bg": "var(--surface-700)"},
    ),
    (
        ('[data-bs-theme="dark"] .bi',),
        {"color": "var(--gold-300)"},
    ),
    (
        ('[data-bs-theme="dark"] ::-webkit-scrollbar',),
        {"height": "10px", "width": "10px"},
    ),
    (
        ('[data-bs-theme="dark"] ::-webkit-scrollbar-track',),
        {"background": "transparent"},
    ),
    (
        ('[data-bs-theme="dark"] ::-webkit-scrollbar-thumb',),
        {
            "background": "var(--gold-700)",
            "border": "2px solid var(--surface-800)",
            "border-radius": "var(--radius-pill)",
        },
    ),
    (
        ('[data-bs-theme="dark"] *',),
        {
            "scrollbar-color": "var(--gold-700) transparent",
            "scrollbar-width": "thin",
        },
    ),
    (
        ('[data-bs-theme="dark"] .archive-illustration',),
        {
            "--illustration-image": "none",
            "background-color": "var(--gold-700)",
            "display": "block",
            "mask-image": "var(--illustration-image)",
            "mask-position": "center",
            "mask-repeat": "no-repeat",
            "mask-size": "contain",
            "opacity": "0.06",
            "pointer-events": "none",
            "position": "absolute",
            "z-index": "var(--z-bg-illustration)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .illustration-compass',),
        {"--illustration-image": 'url("/static/img/illustrations/compass-rose.svg")'},
    ),
    (
        ('[data-bs-theme="dark"] .illustration-sextant',),
        {"--illustration-image": 'url("/static/img/illustrations/sextant.svg")'},
    ),
    (
        ('[data-bs-theme="dark"] .illustration-books',),
        {"--illustration-image": 'url("/static/img/illustrations/stacked-books.svg")'},
    ),
    (
        ('[data-bs-theme="dark"] .illustration-open-book',),
        {"--illustration-image": 'url("/static/img/illustrations/open-book.svg")'},
    ),
    (
        ('[data-bs-theme="dark"] .illustration-flourish',),
        {
            "--illustration-image": (
                'url("/static/img/illustrations/scrollwork-flourish.svg")'
            )
        },
    ),
)
EXPECTED_REDUCED_MOTION_DECLARATIONS = {
    "animation-duration": "0.01ms !important",
    "animation-iteration-count": "1 !important",
    "scroll-behavior": "auto !important",
    "transition-delay": "0s !important",
    "transition-duration": "0.01ms !important",
}
EXPECTED_COARSE_POINTER_DECLARATIONS = {"opacity": "0.045"}
EXPECTED_NAVIGATION_NEUTRAL_RULES = (
    (
        (".archive-wordmark",),
        {
            "-webkit-appearance": "none",
            "appearance": "none",
            "background": "transparent",
            "border": "0",
            "cursor": "pointer",
            "padding-inline": "0",
        },
    ),
    (("body.nav-sidebar-open",), {"overflow": "hidden"}),
)
EXPECTED_NAVIGATION_DARK_RULES = (
    (
        ('[data-bs-theme="dark"] .archive-navbar',),
        {
            "background": "var(--surface-800) !important",
            "border-bottom-color": "hsl(35 40% 45% / 0.12) !important",
            "box-shadow": "0 4px 18px hsl(28 60% 4% / 0.35) !important",
        },
    ),
    (
        ('[data-bs-theme="dark"] .archive-wordmark',),
        {
            "color": "var(--gold-100)",
            "font-family": "var(--font-display)",
            "font-size": "1.25rem",
            "font-weight": "600",
            "letter-spacing": "0.06em",
            "padding": "0.35rem 0.5rem",
        },
    ),
    (
        ('[data-bs-theme="dark"] .archive-wordmark:hover',),
        {"color": "var(--gold-300)"},
    ),
    (
        ('[data-bs-theme="dark"] .archive-wordmark:focus-visible',),
        {
            "border-radius": "var(--radius-button)",
            "box-shadow": "var(--shadow-warm-glow)",
            "outline": "0",
        },
    ),
    (
        ('[data-bs-theme="dark"] .nav-sidebar-overlay',),
        {"background": "hsl(28 60% 4% / 0.72)"},
    ),
    (
        ('[data-bs-theme="dark"] .nav-sidebar',),
        {"border-radius": "0 var(--radius-panel) var(--radius-panel) 0"},
    ),
    (
        ('[data-bs-theme="dark"] .nav-sidebar .list-group-item',),
        {
            "background": "transparent",
            "border-color": "hsl(35 40% 45% / 0.12)",
            "color": "var(--text-primary)",
        },
    ),
    (
        (
            '[data-bs-theme="dark"] .nav-sidebar .list-group-item:hover',
            '[data-bs-theme="dark"] .nav-sidebar .list-group-item:focus-visible',
        ),
        {
            "background": "hsl(35 70% 55% / 0.1)",
            "color": "var(--gold-100)",
        },
    ),
)


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            self.links.append(dict(attrs))


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def parse_css_declarations(rule_body: str, context: str) -> dict[str, str]:
    declarations = {}
    for raw_declaration in rule_body.split(";"):
        raw_declaration = raw_declaration.strip()
        if not raw_declaration:
            continue
        property_name, value = raw_declaration.split(":", 1)
        property_name = property_name.strip()
        assert property_name not in declarations, f"duplicate {property_name!r} in {context}"
        declarations[property_name] = " ".join(value.split())
    return declarations


def css_rule_match(css: str, selector: str):
    css_without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rule_pattern = re.compile(
        rf"^[ \t]*{re.escape(selector)}[ \t]*\{{(?P<body>[^{{}}]*)\}}",
        flags=re.MULTILINE | re.DOTALL,
    )
    matches = list(rule_pattern.finditer(css_without_comments))
    assert len(matches) == 1, f"expected one {selector!r} rule, found {len(matches)}"
    return matches[0]


def css_rule_declarations(css: str, selector: str) -> dict[str, str]:
    rule_body = css_rule_match(css, selector).group("body")
    return parse_css_declarations(rule_body, repr(selector))


def css_rules(css: str):
    css_without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    for match in FLAT_CSS_RULE_PATTERN.finditer(css_without_comments):
        selectors = tuple(selector.strip() for selector in match.group("selectors").split(","))
        context = ", ".join(repr(selector) for selector in selectors)
        yield selectors, parse_css_declarations(match.group("body"), context)


def strip_css_comments(css: str) -> str:
    return CSS_TOKEN_PATTERN.sub(
        lambda match: " " if match[0].startswith("/*") else match[0],
        css,
    )


def css_structural_tokens(css: str):
    for match in CSS_TOKEN_PATTERN.finditer(css):
        token = match[0]
        if len(token) == 1 and token in "{};,()[]":
            yield match.start(), token


def split_css_components(text: str, separator: str) -> tuple[str, ...]:
    parts = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    closing_to_opening = {")": "(", "]": "[", "}": "{"}

    for index, token in css_structural_tokens(text):
        if token in depths:
            depths[token] += 1
        elif token in closing_to_opening:
            opening = closing_to_opening[token]
            depths[opening] = max(0, depths[opening] - 1)
        elif token == separator and not any(depths.values()):
            part = text[start:index].strip()
            if part:
                parts.append(part)
            start = index + 1

    part = text[start:].strip()
    if part:
        parts.append(part)
    return tuple(parts)


def css_rule_blocks(css: str):
    tokens = tuple(css_structural_tokens(css))
    token_index = 0
    rule_start = 0
    while token_index < len(tokens):
        parenthesis_depth = 0
        bracket_depth = 0
        delimiter = None
        while token_index < len(tokens):
            position, token = tokens[token_index]
            token_index += 1
            if token == "(":
                parenthesis_depth += 1
            elif token == ")":
                parenthesis_depth = max(0, parenthesis_depth - 1)
            elif token == "[":
                bracket_depth += 1
            elif token == "]":
                bracket_depth = max(0, bracket_depth - 1)
            elif token in ("{", ";") and parenthesis_depth == bracket_depth == 0:
                delimiter = (position, token)
                break

        if delimiter is None:
            break
        position, token = delimiter
        if token == ";":
            rule_start = position + 1
            continue

        block_depth = 1
        body_start = position + 1
        while token_index < len(tokens):
            block_end, token = tokens[token_index]
            token_index += 1
            if token == "{":
                block_depth += 1
            elif token == "}":
                block_depth -= 1
                if block_depth == 0:
                    header = strip_css_comments(css[rule_start:position]).strip()
                    if header:
                        yield header, css[body_start:block_end]
                    rule_start = block_end + 1
                    break
        else:
            raise AssertionError("unclosed CSS block")

    assert not strip_css_comments(css[rule_start:]).strip(), "incomplete CSS rule"


def selector_group(header: str) -> tuple[str, ...]:
    return tuple(" ".join(selector.split()) for selector in split_css_components(header, ","))


def parse_relevant_css_declarations(rule_body: str, context: str) -> dict[str, str]:
    declarations = {}
    for raw_declaration in split_css_components(strip_css_comments(rule_body), ";"):
        assert ":" in raw_declaration, f"invalid declaration in {context}: {raw_declaration!r}"
        property_name, value = raw_declaration.split(":", 1)
        property_name = property_name.strip()
        assert property_name not in declarations, f"duplicate {property_name!r} in {context}"
        declarations[property_name] = " ".join(value.split())
    return declarations


def css_rule_group_declarations(css: str, selectors: tuple[str, ...]) -> dict[str, str]:
    expected_selectors = frozenset(selectors)
    matches = []
    for header, body in css_rule_blocks(css):
        if header.startswith("@"):
            continue
        actual_selectors = selector_group(header)
        if len(actual_selectors) != len(selectors):
            continue
        if frozenset(actual_selectors) == expected_selectors:
            context = ", ".join(repr(selector) for selector in actual_selectors)
            matches.append(parse_relevant_css_declarations(body, context))
    assert len(matches) == 1, f"expected one {selectors!r} rule group, found {len(matches)}"
    return matches[0]


def css_block_body(css: str, header: str) -> str:
    expected_header = " ".join(header.split())
    matches = [
        body
        for actual_header, body in css_rule_blocks(css)
        if " ".join(actual_header.split()) == expected_header
    ]
    assert len(matches) == 1, f"expected one {header!r} block, found {len(matches)}"
    return matches[0]


def expand_nested_selector(selector: str, parent_selector: str | None) -> str:
    result = []
    index = 0
    quote = None
    found_nesting_reference = False

    while index < len(selector):
        character = selector[index]
        if character == "\\" and index + 1 < len(selector):
            result.extend((character, selector[index + 1]))
            index += 2
            continue
        if quote is not None:
            result.append(character)
            if character == quote:
                quote = None
        elif character in ('"', "'"):
            quote = character
            result.append(character)
        elif character == "&":
            assert parent_selector is not None, (
                f"unsupported top-level nesting selector: {selector!r}"
            )
            result.append(parent_selector)
            found_nesting_reference = True
        else:
            result.append(character)
        index += 1

    expanded = "".join(result)
    if parent_selector is not None and not found_nesting_reference:
        return f"{parent_selector} {expanded}"
    return expanded


def qualified_css_selector_groups(css: str, parent_selectors: tuple[str, ...] = ()):
    for header, body in css_rule_blocks(css):
        if header.startswith("@"):
            yield from qualified_css_selector_groups(body, parent_selectors)
            continue

        nested_selectors = selector_group(header)
        if parent_selectors:
            selectors = tuple(
                expand_nested_selector(nested_selector, parent_selector)
                for parent_selector in parent_selectors
                for nested_selector in nested_selectors
            )
        else:
            selectors = tuple(
                expand_nested_selector(nested_selector, None)
                for nested_selector in nested_selectors
            )

        yield selectors
        yield from qualified_css_selector_groups(body, selectors)


def qualified_css_selectors(css: str, parent_selectors: tuple[str, ...] = ()):
    for selectors in qualified_css_selector_groups(css, parent_selectors):
        yield from selectors


def semantic_selector_targets_classes(selector, class_names: tuple[str, ...]) -> bool:
    if any(name in class_names for name in selector.classes):
        return True

    for attribute in selector.attributes:
        if attribute.attribute != "class" or attribute.pattern is None:
            continue
        if any(attribute.pattern.fullmatch(name) for name in class_names):
            return True

    for nested_selector_list in selector.selectors:
        if nested_selector_list.is_not:
            continue
        if any(
            semantic_selector_targets_classes(nested_selector, class_names)
            for nested_selector in nested_selector_list.selectors
        ):
            return True

    return any(
        semantic_selector_targets_classes(relation, class_names)
        for relation in selector.relation.selectors
    )


def semantic_selector_targets_task3_class(selector) -> bool:
    return semantic_selector_targets_classes(selector, TASK3_DARK_ONLY_CLASSES)


def semantic_selector_component_has_dark_context(selector) -> bool:
    if any(
        attribute.attribute == "data-bs-theme"
        and attribute.pattern is not None
        and attribute.pattern.pattern == "^dark$"
        for attribute in selector.attributes
    ):
        return True

    return any(
        not nested_selector_list.is_not
        and nested_selector_list.selectors
        and all(
            semantic_selector_has_dark_ancestry(nested_selector)
            for nested_selector in nested_selector_list.selectors
        )
        for nested_selector_list in selector.selectors
    )


def semantic_selector_has_dark_ancestry(selector) -> bool:
    current = selector
    while True:
        if semantic_selector_component_has_dark_context(current):
            return True

        if len(current.relation.selectors) != 1:
            return False
        current = current.relation.selectors[0]
        if current.rel_type not in (" ", ">"):
            return False


def strip_trailing_static_dom_states(selector: str) -> str:
    while True:
        candidate = selector.rstrip()
        lowered = candidate.lower()
        for pseudo in PSEUDO_SIMPLE_NO_MATCH:
            if lowered.endswith(pseudo):
                selector = candidate[:-len(pseudo)]
                break
        else:
            return candidate


def assert_task3_selectors_are_dark_scoped(css: str) -> None:
    for selector in qualified_css_selectors(css):
        if not any(name in css_unescape(selector) for name in TASK3_DARK_ONLY_CLASSES):
            continue
        semantic_source = strip_trailing_static_dom_states(selector)
        try:
            semantic_selectors = soupsieve.compile(semantic_source).selectors.selectors
        except soupsieve.SelectorSyntaxError as error:
            raise AssertionError(
                f"unsupported relevant Task 3 selector: {selector!r}"
            ) from error

        for semantic_selector in semantic_selectors:
            if isinstance(semantic_selector, SelectorNull):
                raise AssertionError(
                    f"unsupported relevant Task 3 selector: {selector!r}"
                )
            if not semantic_selector_targets_task3_class(semantic_selector):
                continue
            assert semantic_selector_has_dark_ancestry(semantic_selector), (
                f"Task 3 selector {selector!r} is outside dark scope: "
                "lacks positive dark ancestry/root"
            )


def assert_task_selectors_are_dark_scoped(
    css: str,
    class_names: tuple[str, ...],
    allowed_theme_neutral_groups: frozenset[tuple[str, ...]],
    task_label: str,
    neutral_rule_description: str,
) -> None:
    for selectors in qualified_css_selector_groups(css):
        relevant_selectors = tuple(
            selector
            for selector in selectors
            if any(name in css_unescape(selector) for name in class_names)
        )
        if not relevant_selectors:
            continue

        normalized_group = tuple(" ".join(selector.split()) for selector in selectors)
        if normalized_group in allowed_theme_neutral_groups:
            continue

        for selector in relevant_selectors:
            semantic_source = strip_trailing_static_dom_states(selector)
            try:
                semantic_selectors = soupsieve.compile(semantic_source).selectors.selectors
            except soupsieve.SelectorSyntaxError as error:
                raise AssertionError(
                    f"unsupported relevant {task_label} selector: {selector!r}"
                ) from error

            for semantic_selector in semantic_selectors:
                if isinstance(semantic_selector, SelectorNull):
                    raise AssertionError(
                        f"unsupported relevant {task_label} selector: {selector!r}"
                    )
                if not semantic_selector_targets_classes(
                    semantic_selector,
                    class_names,
                ):
                    continue
                assert semantic_selector_has_dark_ancestry(semantic_selector), (
                    f"{task_label} selector {selector!r} is outside dark scope and is not "
                    f"{neutral_rule_description}"
                )


def assert_navigation_selectors_are_scoped(css: str) -> None:
    assert_task_selectors_are_dark_scoped(
        css,
        TASK4_NAVIGATION_CLASSES,
        TASK4_ALLOWED_THEME_NEUTRAL_SELECTOR_GROUPS,
        "Task 4",
        "an approved singleton theme-neutral baseline rule",
    )


def assert_toast_runtime_contract(toast: str) -> None:
    module_url = "data:text/javascript;base64," + base64.b64encode(
        toast.encode("utf-8")
    ).decode("ascii")
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", TOAST_RUNTIME_HARNESS, module_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, f"toast runtime harness failed: {result.stderr.strip()}"

    rendered = json.loads(result.stdout)
    assert len(rendered) == len(EXPECTED_TOAST_ICON_MAP), (
        f"expected {len(EXPECTED_TOAST_ICON_MAP)} toast renders, found {len(rendered)}"
    )
    for (status, expected), html in zip(
        EXPECTED_TOAST_ICON_MAP.items(), rendered, strict=True
    ):
        soup = BeautifulSoup(html, "html.parser")
        icons = soup.select(".toast-body > i.bi")
        assert len(icons) == 1, f"toast iconMap render for {status}: found {len(icons)} icons"
        classes = set(icons[0].get("class", ()))
        expected_classes = {"bi", *expected.split()}
        assert classes == expected_classes, (
            f"toast iconMap render for {status}: {classes!r} != {expected_classes!r}"
        )
        assert all("-fill" not in class_name for class_name in classes), (
            f"toast iconMap render for {status} uses filled icon: {classes!r}"
        )


def assert_navigation_runtime_contract(main: str) -> None:
    executable_main, import_count = OPEN_VIEWER_IMPORT_PATTERN.subn(
        "const openViewer = () => {};",
        main,
        count=1,
    )
    assert import_count == 1, "expected one openViewer import"
    module_url = "data:text/javascript;base64," + base64.b64encode(
        executable_main.encode("utf-8")
    ).decode("ascii")
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", NAVIGATION_RUNTIME_HARNESS, module_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, (
        f"navigation runtime harness failed: {result.stderr.strip()}"
    )
    assert result.stdout == "navigation runtime ok"


def assert_home_runtime_contract(home: str) -> None:
    toast_import = "import { showToast } from '../toast.js';"
    assert home.count(toast_import) == 1, "expected one showToast import"
    executable_home = home.replace(
        toast_import,
        "const showToast = (...args) => globalThis.toastCalls.push(args);",
        1,
    )
    module_url = "data:text/javascript;base64," + base64.b64encode(
        executable_home.encode("utf-8")
    ).decode("ascii")
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", HOME_RUNTIME_HARNESS, module_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, f"home runtime harness failed: {result.stderr.strip()}"
    assert result.stdout == "home runtime ok"


def main_with_viewer_import(viewer_import: str) -> str:
    main = read_text("static/js/main.js")
    body_marker = "window.openViewer = openViewer;"
    body_start = main.index(body_marker)
    return f'"use strict";\n\n{viewer_import}\n{main[body_start:]}'


def assert_dark_icon_color_contract(css: str) -> None:
    for selector, expected_color in EXPECTED_DARK_ICON_COLORS.items():
        declarations = css_rule_group_declarations(css, (selector,))
        assert declarations["color"] == expected_color


def assert_navigation_css_contract(css: str) -> None:
    assert_navigation_selectors_are_scoped(css)
    assert_dark_icon_color_contract(css)
    for selectors, expected_declarations in (
        *EXPECTED_NAVIGATION_NEUTRAL_RULES,
        *EXPECTED_NAVIGATION_DARK_RULES,
    ):
        assert css_rule_group_declarations(css, selectors) == expected_declarations


def assert_dashboard_selectors_are_scoped(css: str) -> None:
    assert_task_selectors_are_dark_scoped(
        css,
        TASK5_DASHBOARD_CLASSES,
        TASK5_ALLOWED_THEME_NEUTRAL_SELECTOR_GROUPS,
        "Task 5",
        "an unchanged light-mode dashboard baseline rule",
    )


def assert_dashboard_css_contract(css: str) -> None:
    assert_dashboard_selectors_are_scoped(css)
    expected_rules = (
        (
            (".workspace-card",),
            {
                "min-height": "200px",
                "transition": "transform 0.2s ease, box-shadow 0.2s ease",
            },
        ),
        (
            (".workspace-card:hover",),
            {
                "transform": "translateY(-2px)",
                "box-shadow": "0 20px 50px rgba(0, 0, 0, 0.08)",
            },
        ),
        (
            (".workspace-card-add",),
            {"border": "1px dashed rgba(13, 110, 253, 0.5)"},
        ),
        (
            ('[data-bs-theme="dark"] .archive-page',),
            {
                "min-height": "calc(100vh - 58px)",
                "overflow": "hidden",
                "position": "relative",
            },
        ),
        (
            ('[data-bs-theme="dark"] .archive-content',),
            {"position": "relative", "z-index": "var(--z-content)"},
        ),
        (
            ('[data-bs-theme="dark"] .archive-page-title',),
            {
                "color": "var(--gold-100)",
                "font-family": "var(--font-display)",
                "font-size": "var(--text-display-lg)",
                "font-weight": "600",
            },
        ),
        (
            ('[data-bs-theme="dark"] .home-search-group',),
            {"max-width": "560px", "width": "100%"},
        ),
        (
            ('[data-bs-theme="dark"] .workspace-card',),
            {
                "min-height": "220px",
                "transition": (
                    "border-color 150ms ease, box-shadow 150ms ease, "
                    "transform 150ms ease"
                ),
            },
        ),
        (
            ('[data-bs-theme="dark"] .workspace-card:not(.workspace-card-add):hover',),
            {
                "border-color": "hsl(35 50% 55% / 0.35)",
                "box-shadow": "var(--shadow-warm-glow)",
                "transform": "translateY(-2px)",
            },
        ),
        (
            ('[data-bs-theme="dark"] .workspace-card-add',),
            {
                "background": "transparent",
                "border": "2px dashed hsl(35 50% 55% / 0.35)",
                "border-radius": "var(--radius-panel)",
                "color": "var(--gold-300) !important",
                "cursor": "pointer",
            },
        ),
        (
            (
                '[data-bs-theme="dark"] .workspace-card-add:hover',
                '[data-bs-theme="dark"] .workspace-card-add:focus-within',
            ),
            {
                "background": "hsl(35 70% 55% / 0.05)",
                "border-color": "var(--gold-300)",
                "box-shadow": "var(--shadow-warm-glow)",
            },
        ),
        (
            ('[data-bs-theme="dark"] .archive-page-home .illustration-books',),
            {
                "bottom": "0",
                "left": "0",
                "height": "160px",
                "width": "240px",
            },
        ),
        (
            ('[data-bs-theme="dark"] .archive-page-home .illustration-flourish',),
            {
                "bottom": "0",
                "right": "0",
                "height": "180px",
                "transform": "scaleX(-1)",
                "width": "180px",
            },
        ),
    )
    for selectors, declarations in expected_rules:
        assert css_rule_group_declarations(css, selectors) == declarations

    mobile = css_block_body(css, "@media (max-width: 575.98px)")
    assert css_rule_group_declarations(
        mobile,
        ('[data-bs-theme="dark"] .archive-page-title',),
    ) == {"font-size": "1.65rem"}
    assert css_rule_group_declarations(
        mobile,
        ('[data-bs-theme="dark"] .workspace-card',),
    ) == {"min-height": "190px"}


def home_shell_markup(home: str) -> str:
    matches = re.findall(
        r"root\.innerHTML\s*=\s*`(?P<markup>.*?)`\s*;",
        home,
        flags=re.DOTALL,
    )
    assert len(matches) == 1, f"expected one home shell template, found {len(matches)}"
    return matches[0]


def assert_shared_dark_theme_contract(css: str, toast: str) -> None:
    assert_task3_selectors_are_dark_scoped(css)

    for selectors, expected_declarations in EXPECTED_SHARED_RULES:
        assert css_rule_group_declarations(css, selectors) == expected_declarations

    reduced_motion = css_block_body(css, "@media (prefers-reduced-motion: reduce)")
    assert (
        css_rule_group_declarations(reduced_motion, REDUCED_MOTION_SELECTORS)
        == EXPECTED_REDUCED_MOTION_DECLARATIONS
    )

    coarse_pointer = css_block_body(css, "@media (hover: none), (pointer: coarse)")
    assert css_rule_declarations(
        coarse_pointer,
        '[data-bs-theme="dark"] .archive-illustration',
    ) == EXPECTED_COARSE_POINTER_DECLARATIONS

    assert_toast_runtime_contract(toast)


def mark_dark_theme_attribute(selector: str) -> str | None:
    marked_selector, replacements = DARK_THEME_ATTRIBUTE_PATTERN.subn("__dark_theme__", selector)
    return marked_selector.strip() if replacements == 1 else None


def selector_targets_dark_root(selector: str) -> bool:
    marked_selector = mark_dark_theme_attribute(selector)
    return marked_selector is not None and not re.search(r"[\s>+~]", marked_selector)


def selector_targets_global_dark_body(selector: str) -> bool:
    marked_selector = mark_dark_theme_attribute(selector)
    if marked_selector is None:
        return False

    match = re.fullmatch(r"(?P<root>.+?)(?:\s*>\s*|\s+)body", marked_selector)
    if match is None:
        return False
    return not re.search(r"[\s>+~]", match.group("root"))


def assert_dark_root_contract(css: str) -> None:
    assert css_rule_declarations(css, DARK_ROOT_SELECTOR) == EXPECTED_DARK_ROOT_DECLARATIONS

    protected_properties = set(EXPECTED_DARK_ROOT_DECLARATIONS)
    for selectors, declarations in css_rules(css):
        for selector in selectors:
            if not selector_targets_dark_root(selector):
                continue
            if selector == DARK_ROOT_SELECTOR and declarations == EXPECTED_DARK_ROOT_DECLARATIONS:
                continue

            redeclared = protected_properties.intersection(declarations)
            assert not redeclared, (
                f"{selector!r} redeclares protected dark foundation properties: "
                f"{', '.join(sorted(redeclared))}"
            )


def assert_no_dark_global_body_font_size(css: str) -> None:
    for selectors, declarations in css_rules(css):
        if "font-size" not in declarations:
            continue
        offenders = [
            selector
            for selector in selectors
            if selector_targets_dark_root(selector) or selector_targets_global_dark_body(selector)
        ]
        assert not offenders, (
            f"{', '.join(repr(selector) for selector in offenders)} "
            "sets forbidden global body font-size"
        )


def test_dark_theme_instruction_points_to_source_spec():
    instruction = read_text(".github/instructions/dark-theme.instructions.md")
    assert 'applyTo: "static/css/**/*.css,static/js/**/*.js,templates/**/*.html"' in instruction
    assert "docs/design/dark-mode-ui-spec.md" in instruction
    assert "Do not touch light-mode styles" in instruction


@pytest.mark.parametrize("name", ("leather-texture.png", "wood-texture.png"))
def test_texture_assets_are_real_png_files(name):
    data = (ROOT / "static" / "img" / "textures" / name).read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("name", SVG_NAMES)
def test_illustration_assets_are_safe_line_art(name):
    text = read_text(f"static/img/illustrations/{name}")
    lowered = text.lower()
    assert "<script" not in lowered
    assert "<foreignobject" not in lowered
    assert not re.search(r"\son[a-z]+\s*=", lowered)
    assert not re.search(r"(?:href|src)\s*=\s*['\"](?:https?:|//|data:)", lowered)

    root = ET.fromstring(text)
    assert root.tag.rsplit("}", 1)[-1] == "svg"
    assert root.attrib.get("viewBox")
    assert root.attrib.get("aria-hidden") == "true"
    assert 'fill="none"' in text
    assert "currentColor" in text


def relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    light, dark = sorted((relative_luminance(foreground), relative_luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_dark_theme_root_has_exact_foundation_declarations():
    css = read_text("static/css/custom.css")
    assert_dark_root_contract(css)


def test_dark_theme_root_precedes_component_overrides():
    css = read_text("static/css/custom.css")
    root_rule = css_rule_match(css, DARK_ROOT_SELECTOR)
    first_component_rule = re.search(
        rf"^[ \t]*{re.escape(DARK_ROOT_SELECTOR)}(?![ \t]*\{{)",
        re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL),
        flags=re.MULTILINE,
    )
    assert first_component_rule is not None
    assert root_rule.start() < first_component_rule.start()


def test_dark_body_has_exact_vignette_declarations():
    css = read_text("static/css/custom.css")
    assert css_rule_declarations(css, DARK_BODY_SELECTOR) == EXPECTED_DARK_BODY_DECLARATIONS


def test_layout_loads_only_the_approved_dark_theme_fonts():
    layout = read_text("templates/layout.html")
    parser = LinkCollector()
    parser.feed(layout)

    font_stylesheets = [link for link in parser.links if "family=" in link.get("href", "")]
    assert font_stylesheets == [{"href": APPROVED_FONT_STYLESHEET, "rel": "stylesheet"}]

    stylesheet_hrefs = [link["href"] for link in parser.links if link.get("rel") == "stylesheet"]
    assert stylesheet_hrefs.count(APPROVED_FONT_STYLESHEET) == 1
    assert stylesheet_hrefs.count(CUSTOM_CSS_STYLESHEET) == 1
    assert stylesheet_hrefs.index(APPROVED_FONT_STYLESHEET) < stylesheet_hrefs.index(CUSTOM_CSS_STYLESHEET)


def test_dark_body_does_not_override_global_font_size():
    assert_no_dark_global_body_font_size(read_text("static/css/custom.css"))


def test_equivalent_dark_root_selector_cannot_redeclare_protected_token():
    css = read_text("static/css/custom.css")
    css += '\nhtml[data-bs-theme="dark"] { --bg-950: #FFFFFF; }\n'

    with pytest.raises(AssertionError, match="redeclares protected dark foundation properties"):
        assert_dark_root_contract(css)


def test_equivalent_dark_body_selector_cannot_set_global_font_size():
    css = read_text("static/css/custom.css")
    css += '\nhtml[data-bs-theme="dark"] body { font-size: 12px; }\n'

    with pytest.raises(AssertionError, match="sets forbidden global body font-size"):
        assert_no_dark_global_body_font_size(css)


@pytest.mark.parametrize(
    ("foreground", "background"),
    (
        ("#E7E1DA", "#0A0A0A"),
        ("#E7E1DA", "#22170B"),
        ("#A69A8C", "#0A0A0A"),
        ("#A69A8C", "#22170B"),
    ),
)
def test_core_text_pairs_meet_wcag_aa(foreground, background):
    assert contrast_ratio(foreground, background) >= 4.5


def test_shared_dark_theme_materials_and_controls_are_scoped():
    css = read_text("static/css/custom.css")
    toast = read_text("static/js/toast.js")
    assert_shared_dark_theme_contract(css, toast)


def test_shared_dark_theme_controls_use_spec_motion():
    css = read_text("static/css/custom.css")
    assert css_rule_group_declarations(css, SHARED_CONTROL_MOTION_SELECTORS) == {
        "transition": (
            "background-color 150ms ease, border-color 150ms ease, color 150ms ease"
        )
    }


def test_shared_dark_theme_dropdowns_animate_open_and_close():
    css = read_text("static/css/custom.css")
    assert css_rule_group_declarations(css, DROPDOWN_MENU_SELECTORS) == {
        "background": "var(--surface-600)",
        "border-color": "hsl(35 40% 45% / 0.22)",
        "border-radius": "var(--radius-button)",
        "box-shadow": "var(--shadow-warm-raised)",
        "color": "var(--text-primary)",
        "display": "block",
        "opacity": "0",
        "pointer-events": "none",
        "transition": "opacity 180ms ease-in, visibility 0s linear 180ms",
        "visibility": "hidden",
    }
    assert css_rule_group_declarations(css, DROPDOWN_OPEN_SELECTORS) == {
        "opacity": "1",
        "pointer-events": "auto",
        "transition": "opacity 180ms ease-out, visibility 0s linear 0s",
        "visibility": "visible",
    }


def test_reduced_motion_collapses_shared_transition_delay_and_duration():
    css = read_text("static/css/custom.css")
    media = css_block_body(css, "@media (prefers-reduced-motion: reduce)")
    assert (
        css_rule_group_declarations(media, REDUCED_MOTION_SELECTORS)
        == EXPECTED_REDUCED_MOTION_DECLARATIONS
    )


def test_shared_contract_rejects_light_scoped_rules_hidden_by_comments():
    css = read_text("static/css/custom.css").replace(
        DARK_ROOT_SELECTOR,
        '[data-bs-theme="light"]',
    )
    css += "\n/* " + " ".join(SHARED_REQUIRED_SELECTORS) + " */\n"

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_shared_contract_rejects_moved_material_declaration():
    css = read_text("static/css/custom.css").replace(
        "    background-size: auto, 420px;\n",
        "",
        1,
    )
    css += f"\n{DARK_ROOT_SELECTOR} .unrelated {{ background-size: auto, 420px; }}\n"

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_shared_contract_rejects_wrong_material_declaration():
    css = read_text("static/css/custom.css").replace(
        "background-blend-mode: multiply;",
        "background-blend-mode: screen;",
        1,
    )

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_shared_contract_rejects_wrong_toast_status_mapping_hidden_by_comment():
    toast = read_text("static/js/toast.js")
    for value in EXPECTED_TOAST_ICON_MAP.values():
        toast = toast.replace(value, "bi-question-circle text-muted")
    toast += "\n// " + " ".join(EXPECTED_TOAST_ICON_MAP.values()) + "\n"

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(read_text("static/css/custom.css"), toast)


@pytest.mark.parametrize(
    "selector",
    (
        '[data-bs-theme="light"] .surface-leather',
        ".surface-leather",
    ),
    ids=("light", "unscoped"),
)
def test_shared_contract_boundary_rejects_additive_non_dark_task_selector(selector):
    css = read_text("static/css/custom.css")
    css += f"\n{selector} {{ background-size: cover; }}\n"

    with pytest.raises(AssertionError, match="outside dark scope"):
        assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_shared_contract_boundary_rejects_hardcoded_rendered_toast_icon():
    toast = read_text("static/js/toast.js").replace(
        "${iconMap[type]}",
        "bi-question-circle-fill",
    )

    with pytest.raises(AssertionError, match="iconMap"):
        assert_shared_dark_theme_contract(read_text("static/css/custom.css"), toast)


def test_shared_contract_boundary_accepts_reordered_canonical_selector_group():
    css = read_text("static/css/custom.css")
    original_group = ",\n".join(SHARED_CONTROL_MOTION_SELECTORS)
    reordered_group = ",\n".join(reversed(SHARED_CONTROL_MOTION_SELECTORS))
    assert original_group in css

    css = css.replace(original_group, reordered_group, 1)
    assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_shared_contract_boundary_accepts_unrelated_quoted_css_content():
    css = read_text("static/css/custom.css")
    css += '\n.unrelated-content::before { content: "a;b{c}\\\"d"; }\n'

    assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_shared_contract_boundary_accepts_unrelated_duplicate_fallback_declarations():
    css = read_text("static/css/custom.css")
    css += (
        "\n.unrelated-fallback { "
        "color: rgb(255 0 0); color: color(display-p3 1 0 0); "
        "}\n"
    )

    assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


@pytest.mark.parametrize(
    "selector",
    (
        '.surface-leather:not([data-bs-theme="dark"])',
        r".surface\-leather",
        '[class~="surface-leather"]',
        "[data-probe='[data-bs-theme=\"dark\"]'] .surface-leather",
        ".unrelated { & .surface-leather",
    ),
    ids=(
        "negated-dark",
        "escaped-class",
        "class-token-attribute",
        "irrelevant-dark-text",
        "native-nesting",
    ),
)
def test_third_review_boundary_rejects_semantic_non_dark_task_selector(selector):
    css = read_text("static/css/custom.css")
    if selector.startswith(".unrelated"):
        css += f"\n{selector} {{ color: red; }} }}\n"
    else:
        css += f"\n{selector} {{ color: red; }}\n"

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_third_review_boundary_rejects_unused_toast_template_decoy():
    toast = read_text("static/js/toast.js").replace(
        "${iconMap[type]}",
        "bi-question-circle-fill",
        1,
    )
    toast = toast.replace(
        "const html = `",
        'const html = `<i class="bi ${iconMap[type]}"></i>`;\n'
        "    const renderedHtml = `",
        1,
    ).replace(
        'insertAdjacentHTML("beforeend", html)',
        'insertAdjacentHTML("beforeend", renderedHtml)',
        1,
    )

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(read_text("static/css/custom.css"), toast)


def test_third_review_boundary_rejects_commented_toast_icon_decoy():
    toast = read_text("static/js/toast.js").replace(
        '<i class="bi ${iconMap[type]}"></i>',
        '<!-- <i class="bi ${iconMap[type]}"></i> -->\n'
        '                    <i class="bi bi-question-circle-fill"></i>',
        1,
    )

    with pytest.raises(AssertionError):
        assert_shared_dark_theme_contract(read_text("static/css/custom.css"), toast)


def test_third_review_boundary_accepts_unrelated_task_text_in_attribute():
    css = read_text("static/css/custom.css")
    css += '\n[data-probe=".surface-leather"] { color: red; }\n'

    assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_third_review_boundary_accepts_positive_dark_ancestry_via_is():
    css = read_text("static/css/custom.css")
    css += '\n:is([data-bs-theme="dark"]) .surface-leather { color: red; }\n'

    assert_shared_dark_theme_contract(css, read_text("static/js/toast.js"))


def test_third_review_boundary_accepts_toast_template_variable_rename():
    toast = read_text("static/js/toast.js").replace(
        "const html = `",
        "const toastHtml = `",
        1,
    ).replace(
        'insertAdjacentHTML("beforeend", html)',
        'insertAdjacentHTML("beforeend", toastHtml)',
        1,
    )

    assert_shared_dark_theme_contract(read_text("static/css/custom.css"), toast)


def test_third_review_boundary_accepts_aria_hidden_toast_icon():
    toast = read_text("static/js/toast.js").replace(
        '<i class="bi ${iconMap[type]}"></i>',
        '<i aria-hidden="true" class="bi ${iconMap[type]}"></i>',
        1,
    )

    assert_shared_dark_theme_contract(read_text("static/css/custom.css"), toast)


def test_navigation_uses_wordmark_trigger_and_home_entry():
    layout = read_text("templates/layout.html")
    main = read_text("static/js/main.js")
    theme = read_text("static/js/theme.js")
    auth = read_text("static/js/auth.js")

    assert 'id="brandMenuButton"' in layout
    assert 'aria-controls="navSidebarOverlay"' in layout
    assert 'aria-expanded="false"' in layout
    assert 'id="navMenuButton"' not in layout
    assert '<a class="list-group-item list-group-item-action" href="/">Home</a>' in layout
    assert 'id="navSidebarOverlay"' in layout
    assert 'aria-hidden="true"' in layout

    assert "getElementById('brandMenuButton')" in main
    assert "event.key === 'Escape'" in main
    assert 'setAttribute("aria-expanded", "true")' in main
    assert 'setAttribute("aria-expanded", "false")' in main
    assert 'setAttribute("aria-hidden", "false")' in main
    assert 'setAttribute("aria-hidden", "true")' in main
    assert "brandMenuButton.focus()" in main

    assert "-fill" not in layout + theme + auth
    assert 'setAttribute("aria-label"' in theme
    assert 'setAttribute("aria-label"' in auth


def test_navigation_markup_has_accessible_dialog_relationships():
    soup = BeautifulSoup(read_text("templates/layout.html"), "html.parser")

    wordmark = soup.select_one("button#brandMenuButton")
    assert wordmark is not None
    assert wordmark.get_text(strip=True) == "StudyLib"
    assert wordmark.get("type") == "button"
    assert wordmark.get("aria-label") == "StudyLib, open navigation menu"
    assert wordmark.get("aria-controls") == "navSidebarOverlay"
    assert wordmark.get("aria-expanded") == "false"
    assert set(wordmark.get("class", ())) == {
        "navbar-brand",
        "archive-wordmark",
        "mb-0",
    }
    assert soup.select_one("#navMenuButton") is None

    overlay = soup.select_one("#navSidebarOverlay")
    assert overlay is not None
    assert "d-none" in overlay.get("class", ())
    assert overlay.get("aria-hidden") == "true"

    dialog = overlay.select_one(".nav-sidebar")
    assert dialog is not None
    assert dialog.get("role") == "dialog"
    assert dialog.get("aria-modal") == "true"
    assert dialog.get("aria-labelledby") == "navSidebarTitle"
    assert dialog.get("tabindex") == "-1"
    assert dialog.select_one("#navSidebarTitle") is not None

    close_button = dialog.select_one("button#closeNavSidebarBtn")
    assert close_button is not None
    assert close_button.get("type") == "button"
    assert close_button.get("aria-label") == "Close menu"
    assert set(close_button.get("class", ())) == {
        "btn",
        "btn-link",
        "text-reset",
        "icon-button",
    }

    links = [
        (link.get("href"), link.get_text(strip=True))
        for link in dialog.select(".list-group > a.list-group-item-action")
    ]
    assert links == [("/", "Home"), ("/browse", "Browse"), ("/upload", "Upload")]

    theme_button = soup.select_one("button#themeToggle")
    assert theme_button is not None
    assert theme_button.get("type") == "button"
    assert theme_button.get("aria-label") == "Switch to dark theme"
    assert set(theme_button.get("class", ())) == {
        "btn",
        "btn-link",
        "p-1",
        "icon-button",
    }
    assert theme_button.select_one('i.bi-moon-stars[aria-hidden="true"]') is not None


def test_navigation_runtime_keeps_visibility_aria_body_and_focus_in_sync():
    assert_navigation_runtime_contract(read_text("static/js/main.js"))


@pytest.mark.parametrize(
    "viewer_import",
    (
        'import {openViewer} from "./viewer.js"',
        'import {\n    openViewer\n}\nfrom\n    "./viewer.js";',
        "import { openViewer } from './viewer.js'; // viewer bridge",
        'import { openViewer } from "./viewer.js"; /* viewer bridge */',
    ),
    ids=("compact", "multiline", "line-comment", "block-comment"),
)
def test_navigation_runtime_import_transform_tolerates_equivalent_formatting(
    viewer_import: str,
):
    assert_navigation_runtime_contract(main_with_viewer_import(viewer_import))


def test_navigation_css_preserves_light_baseline_and_scopes_dark_visuals():
    assert_navigation_css_contract(read_text("static/css/custom.css"))


def test_navigation_dark_icon_colors_override_bootstrap_text_reset():
    layout = BeautifulSoup(read_text("templates/layout.html"), "html.parser")
    close_button = layout.select_one("button#closeNavSidebarBtn")
    assert close_button is not None
    assert {"text-reset", "icon-button"} <= set(close_button.get("class", ()))

    assert_dark_icon_color_contract(read_text("static/css/custom.css"))


@pytest.mark.parametrize(
    ("selector", "important_color"),
    EXPECTED_DARK_ICON_COLORS.items(),
)
def test_navigation_dark_icon_contract_rejects_nonimportant_color(
    selector: str,
    important_color: str,
):
    css = read_text("static/css/custom.css")
    assert_navigation_css_contract(css)
    declaration = f"color: {important_color};"
    assert declaration in css

    with pytest.raises(AssertionError):
        assert_navigation_css_contract(
            css.replace(
                declaration,
                f"color: {important_color.removesuffix(' !important')};",
                1,
            )
        )


@pytest.mark.parametrize(
    ("original", "mutation"),
    (
        (
            '[data-bs-theme="dark"] .archive-navbar {',
            '.archive-navbar {',
        ),
        (
            "body.nav-sidebar-open {\n    overflow: hidden;\n}",
            "body.nav-sidebar-open {\n    overflow: visible;\n}",
        ),
        (
            "    padding-inline: 0;\n",
            "    padding-inline: 0.5rem;\n",
        ),
        (
            "box-shadow: 0 4px 18px hsl(28 60% 4% / 0.35) !important;",
            "box-shadow: none !important;",
        ),
    ),
)
def test_navigation_css_contract_rejects_semantic_and_visual_mutations(
    original: str,
    mutation: str,
):
    css = read_text("static/css/custom.css")
    assert_navigation_css_contract(css)
    assert original in css

    with pytest.raises(AssertionError):
        assert_navigation_css_contract(css.replace(original, mutation, 1))


def test_navigation_css_contract_rejects_additive_unscoped_visual_rule():
    css = read_text("static/css/custom.css")
    assert_navigation_css_contract(css)

    with pytest.raises(AssertionError):
        assert_navigation_css_contract(
            css + "\n.archive-wordmark:hover { color: red; }\n"
        )


def test_navigation_css_contract_rejects_grouped_neutral_selector_contamination():
    css = read_text("static/css/custom.css")
    assert_navigation_selectors_are_scoped(css)

    with pytest.raises(AssertionError):
        assert_navigation_selectors_are_scoped(
            css + "\n.archive-wordmark, .probe-decoy { color: red; }\n"
        )


def test_dashboard_has_archive_hooks_without_changing_data_flow():
    home = read_text("static/js/pages/home.js")
    required = (
        "archive-page archive-page-home",
        "archive-content",
        "archive-page-title",
        "archive-illustration illustration-books",
        "archive-illustration illustration-flourish",
        "surface-leather workspace-card",
        "workspace-card-add",
        "archive-category-badge",
        ">WORKSPACE<",
        "loadWorkspaces()",
        "createWorkspaceDialog",
        "fetch('/api/workspaces')",
    )
    for marker in required:
        assert marker in home
    assert "WORRSPACE" not in home


def test_dashboard_shell_has_accessible_archive_structure():
    soup = BeautifulSoup(home_shell_markup(read_text("static/js/pages/home.js")), "html.parser")
    page = soup.select_one("div.container-fluid.archive-page.archive-page-home")
    assert page is not None

    direct_children = page.find_all(recursive=False)
    assert [child.name for child in direct_children] == ["span", "span", "div"]
    assert [set(child.get("class", ())) for child in direct_children] == [
        {"archive-illustration", "illustration-books"},
        {"archive-illustration", "illustration-flourish"},
        {"archive-content"},
    ]
    for decoration in direct_children[:2]:
        assert decoration.get("aria-hidden") == "true"

    content = direct_children[2]
    title = content.select_one("h1.archive-page-title")
    assert title is not None
    assert title.get_text(strip=True) == "Recent Workspaces"

    search_group = content.select_one(".input-group.home-search-group")
    assert search_group is not None
    assert search_group.get("style") == "max-width: 560px; width: 100%;"
    assert search_group.select_one('i.bi-search[aria-hidden="true"]') is not None
    search = search_group.select_one("input#workspaceSearch")
    assert search is not None
    assert search.get("type") == "search"
    assert search.get("autocomplete") == "off"

    cards = content.select_one("#workspaceCards")
    assert cards is not None
    assert set(cards.get("class", ())) == {
        "row",
        "row-cols-1",
        "row-cols-sm-2",
        "row-cols-lg-3",
        "g-3",
    }
    assert len(soup.select("#workspaceSearch")) == 1
    assert len(soup.select("#workspaceCards")) == 1


def test_dashboard_runtime_preserves_search_render_create_and_open_flow():
    assert_home_runtime_contract(read_text("static/js/pages/home.js"))


def test_dashboard_css_preserves_light_baseline_and_scopes_dark_visuals():
    assert_dashboard_css_contract(read_text("static/css/custom.css"))


def test_dashboard_css_contract_rejects_additive_unscoped_visual_rule():
    css = read_text("static/css/custom.css")
    assert_dashboard_css_contract(css)

    with pytest.raises(AssertionError, match="outside dark scope"):
        assert_dashboard_css_contract(
            css + "\n.archive-page-title { color: red; }\n"
        )
