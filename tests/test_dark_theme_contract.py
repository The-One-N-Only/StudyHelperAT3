import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
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
    "--candle-x": "50%", "--candle-y": "30%", "--candle-radius": "380px",
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
EXPECTED_DASHBOARD_CARD_HEADER_RULES = (
    (
        ('[data-bs-theme="dark"] .archive-category-badge',),
        {
            "background": "hsl(35 40% 45% / 0.15) !important",
            "border-radius": "var(--radius-pill)",
            "color": "var(--gold-300) !important",
            "font-size": "var(--text-caption)",
            "letter-spacing": "0.04em",
            "text-transform": "uppercase",
        },
    ),
    (
        ('[data-bs-theme="dark"] .icon-button .text-muted',),
        {"color": "inherit !important"},
    ),
)
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
EXPECTED_LIGHT_TOAST_ICON_MAP = {
    "success": "bi-check-circle-fill text-success",
    "danger": "bi-x-circle-fill text-danger",
    "warning": "bi-exclamation-triangle-fill text-warning",
    "info": "bi-info-circle-fill text-info",
}
TOAST_RUNTIME_HARNESS = r"""
const rendered = { dark: [], light: [] };
let currentTheme = "dark";
const toastElement = { addEventListener() {}, remove() {} };
const container = {
  insertAdjacentHTML(position, html) {
    if (position !== "beforeend") throw new Error(`unexpected insertion: ${position}`);
    rendered[currentTheme].push(html);
  }
};
globalThis.document = {
  documentElement: {
    getAttribute(name) {
      if (name !== "data-bs-theme") throw new Error(`unexpected attribute: ${name}`);
      return currentTheme;
    }
  },
  getElementById(id) {
    return id === "toastContainer" ? container : toastElement;
  }
};
globalThis.bootstrap = { Toast: class { show() {} } };
Date.now = () => 1700000000000;
const { showToast } = await import(process.argv[1]);
for (const theme of ["dark", "light"]) {
  currentTheme = theme;
  for (const type of ["success", "danger", "warning", "info"]) {
    const before = rendered[theme].length;
    showToast(`message-${type}`, type);
    if (rendered[theme].length !== before + 1) throw new Error(`no ${theme} render for ${type}`);
  }
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
    this.cardTarget = null;
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
    const event = { type, target: this, defaultPrevented: false, ...init };
    event.preventDefault = () => { event.defaultPrevented = true; };
    for (const callback of callbacks) await callback(event);
    return event;
  }

  querySelector(selector) {
    if (selector === "#workspaceSearch") return searchInput;
    if (selector === ".card") {
      const hasCardClass = [...this._innerHTML.matchAll(/\bclass=(["'])([^"']*)\1/g)]
        .some(([, , classes]) => classes.split(/\s+/).includes("card"));
      if (!hasCardClass) return null;
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
const promptResponses = [null, null, "New Workspace"];
let promptCalls = 0;
globalThis.toastCalls = [];
globalThis.window = { location: { href: "" } };
globalThis.prompt = (message, defaultValue) => {
  invariant(message === "Enter a name for the new workspace:", "prompt message changed");
  invariant(defaultValue === "New Workspace", "prompt default changed");
  promptCalls += 1;
  return promptResponses.shift();
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
          name: '<unsafe "quoted" & name>',
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
let addCardTarget = addCard.querySelector(".card");
invariant(addCardTarget.listeners.get("click")?.length === 1, "add listener missing");
invariant(addCardTarget.listeners.get("keydown")?.length === 1, "add keyboard listener missing");

await addCardTarget.dispatch("keydown", { key: "Enter" });
invariant(promptCalls === 1, "Enter did not open create dialog");
const spaceEvent = await addCardTarget.dispatch("keydown", { key: " " });
invariant(promptCalls === 2, "Space did not open create dialog");
invariant(spaceEvent.defaultPrevented, "Space did not prevent page scroll");

let renderedCard = workspaceCards.children[1].innerHTML;
invariant(renderedCard.includes('&lt;unsafe "quoted" &amp; name&gt;'), "workspace title not escaped");
invariant(!renderedCard.includes("<unsafe"), "unsafe workspace title rendered as markup");
invariant(renderedCard.includes("3 sources"), "source metadata changed");
invariant(renderedCard.includes("0 notes"), "note metadata changed");
invariant(renderedCard.includes("Created on Unknown"), "created date changed");
invariant(
  renderedCard.includes('class="stretched-link" href="/workspace/7"'),
  "workspace stretched link changed",
);
invariant(
  renderedCard.includes(
    'aria-label="Open &lt;unsafe &quot;quoted&quot; &amp; name&gt; workspace"',
  ),
  "workspace link name missing or unsafe",
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
addCardTarget = addCard.querySelector(".card");
await addCardTarget.dispatch("click");
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
            '[data-bs-theme="dark"] .btn-primary:not(.btn-secondary-wood)',
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
            "background": "var(--gold-900) !important",
            "border-radius": "var(--radius-pill)",
            "color": "var(--gold-100)",
            "font-size": "var(--text-caption)",
            "font-variant-numeric": "tabular-nums",
        },
    ),
    *EXPECTED_DASHBOARD_CARD_HEADER_RULES,
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
    expected_by_theme = {
        "dark": EXPECTED_TOAST_ICON_MAP,
        "light": EXPECTED_LIGHT_TOAST_ICON_MAP,
    }
    assert set(rendered) == set(expected_by_theme)
    for theme, expected_map in expected_by_theme.items():
        assert len(rendered[theme]) == len(expected_map)
        for (status, expected), html in zip(
            expected_map.items(), rendered[theme], strict=True
        ):
            soup = BeautifulSoup(html, "html.parser")
            icons = soup.select(".toast-body > i.bi")
            assert len(icons) == 1, (
                f"{theme} toast iconMap render for {status}: found {len(icons)} icons"
            )
            classes = set(icons[0].get("class", ()))
            expected_classes = {"bi", *expected.split()}
            assert classes == expected_classes, (
                f"{theme} toast iconMap render for {status}: "
                f"{classes!r} != {expected_classes!r}"
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
        *EXPECTED_DASHBOARD_CARD_HEADER_RULES,
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
            (
                '[data-bs-theme="dark"] .workspace-card:not(.workspace-card-add):hover',
                '[data-bs-theme="dark"] .workspace-card:not(.workspace-card-add):focus-within',
            ),
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


def assigned_template_markup(source: str, target: str) -> str:
    matches = re.findall(
        rf"\b{re.escape(target)}\.innerHTML\s*=\s*`(?P<markup>.*?)`\s*;",
        source,
        flags=re.DOTALL,
    )
    assert len(matches) == 1, f"expected one {target} template, found {len(matches)}"
    return matches[0]


def home_shell_markup(home: str) -> str:
    return assigned_template_markup(home, "root")


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

    for script in (theme, auth):
        assert "? '<i class=\"bi bi-sun\" aria-hidden=\"true\"></i>'" in script
        assert ": '<i class=\"bi bi-moon-stars-fill\" aria-hidden=\"true\"></i>'" in script
        assert 'setAttribute("aria-label"' in script


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
    assert theme_button.select_one('i.bi-moon-stars-fill[aria-hidden="true"]') is not None


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
        ">Workspace<",
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


def test_dashboard_card_markup_preserves_light_and_accessible_semantics():
    home = read_text("static/js/pages/home.js")
    add_card = BeautifulSoup(
        assigned_template_markup(home, "addCard"), "html.parser"
    ).select_one(".workspace-card-add")
    assert add_card is not None
    assert (add_card.get("role"), add_card.get("tabindex")) == ("button", "0")

    card = BeautifulSoup(assigned_template_markup(home, "card"), "html.parser")

    badge = card.select_one(".archive-category-badge")
    assert badge is not None
    assert set(badge.get("class", ())) == {
        "badge",
        "bg-primary",
        "bg-opacity-10",
        "text-primary",
        "archive-category-badge",
    }

    icon_hook = card.select_one('.icon-button[aria-hidden="true"]')
    assert icon_hook is not None
    icon = icon_hook.select_one("i")
    assert icon is not None
    assert set(icon.get("class", ())) == {
        "bi",
        "bi-three-dots-vertical",
        "text-muted",
    }

    link = card.select_one("a.stretched-link")
    assert link is not None
    assert link.get("aria-label") == (
        "Open ${escapeHtmlAttribute(workspace.name)} workspace"
    )


def test_dashboard_runtime_preserves_search_render_create_and_open_flow():
    assert_home_runtime_contract(read_text("static/js/pages/home.js"))


def test_dashboard_runtime_rejects_missing_add_card_target():
    home = read_text("static/js/pages/home.js")
    card = 'class="card h-100 workspace-card workspace-card-add'
    panel = 'class="panel h-100 workspace-card workspace-card-add'
    assert home.count(card) == 1

    with pytest.raises(AssertionError, match="home runtime harness failed"):
        assert_home_runtime_contract(home.replace(card, panel, 1))


def test_dashboard_css_preserves_light_baseline_and_scopes_dark_visuals():
    assert_dashboard_css_contract(read_text("static/css/custom.css"))


def test_dashboard_css_contract_rejects_additive_unscoped_visual_rule():
    css = read_text("static/css/custom.css")
    assert_dashboard_css_contract(css)

    with pytest.raises(AssertionError, match="outside dark scope"):
        assert_dashboard_css_contract(
            css + "\n.archive-page-title { color: red; }\n"
        )


def run_task6_module_harness(
    source: str,
    replacements: tuple[tuple[str, str], ...],
    harness: str,
    label: str,
) -> dict:
    executable = source
    for original, replacement in replacements:
        assert executable.count(original) == 1
        executable = executable.replace(original, replacement, 1)

    module_url = "data:text/javascript;base64," + base64.b64encode(
        executable.encode("utf-8")
    ).decode("ascii")
    runner = (
        f"globalThis.__task6ModuleUrl = {json.dumps(module_url)};\n"
        + harness.replace("process.argv[1]", "globalThis.__task6ModuleUrl")
    )
    result = subprocess.run(
        ["node", "--input-type=module"],
        input=runner,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, f"{label} runtime harness failed: {result.stderr.strip()}"
    return json.loads(result.stdout)


TASK6_RUNTIME_BASE = r"""
function invariant(condition, message) {
  if (!condition) throw new Error(message);
}

class FakeClassList {
  constructor(owner) {
    this.owner = owner;
    this.values = new Set((owner.className || "").split(/\s+/).filter(Boolean));
  }
  sync() {
    this.owner.className = Array.from(this.values).join(" ");
  }
  toggle(name) {
    const added = !this.values.has(name);
    if (added) this.values.add(name);
    else this.values.delete(name);
    this.sync();
    return added;
  }
  remove(name) {
    this.values.delete(name);
    this.sync();
  }
  contains(name) {
    return this.values.has(name);
  }
}

class FakeElement {
  constructor(name, className = "") {
    this.name = name;
    this.className = className;
    this.classList = new FakeClassList(this);
    this.listeners = new Map();
    this.attributes = new Map();
    this.dataset = {};
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.src = "";
    this.alt = "";
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  addEventListener(type, callback) {
    const callbacks = this.listeners.get(type) || [];
    callbacks.push(callback);
    this.listeners.set(type, callbacks);
  }
  async dispatch(type, init = {}) {
    const callbacks = this.listeners.get(type) || [];
    invariant(callbacks.length === 1, this.name + ": expected one " + type + " listener");
    for (const callback of callbacks) {
      await callback({ type, target: this, stopPropagation() {}, ...init });
    }
  }
  querySelector() {
    return null;
  }
  querySelectorAll() {
    return [];
  }
  focus() {}
}
"""


CARD_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const createdCards = [];
const fetchCalls = [];
const hydrateCalls = [];
const toastCalls = [];
const saveStatuses = [true, false, true, false];

function makeCard() {
  const card = new FakeElement("card");
  const nodes = new Map([
    [".card-img-top", new FakeElement("image", "card-img-top")],
    [".card-title", new FakeElement("title", "card-title text-truncate mb-1")],
    [".card-description", new FakeElement("description", "card-text small text-muted card-description mb-2")],
    [".result-source-text", new FakeElement("source", "result-source-text")],
    [".save-btn", new FakeElement("save", "btn btn-link btn-sm p-0 icon-button save-btn")],
    [".save-icon-light", new FakeElement("light icon")],
    [".save-icon-dark", new FakeElement("dark icon")],
    [".view-btn", new FakeElement("view", "btn btn-outline-secondary btn-secondary-wood btn-sm w-50 view-btn")],
    [".add-btn", new FakeElement("add", "btn btn-primary btn-secondary-wood btn-sm w-50 add-btn")],
    [".workspace-select", new FakeElement("workspace", "form-select form-select-sm archive-dropdown workspace-select")],
  ]);
  for (const selector of [".save-btn", ".view-btn", ".add-btn"]) {
    nodes.get(selector).setAttribute("type", "button");
  }
  nodes.get(".workspace-select").setAttribute("aria-label", "Choose workspace");
  nodes.get(".save-btn").querySelector = (selector) => {
    const icon = nodes.get(selector);
    invariant(icon, "unexpected save selector: " + selector);
    return icon;
  };
  card.querySelector = (selector) => {
    const node = nodes.get(selector);
    invariant(node, "unexpected card selector: " + selector);
    return node;
  };
  card.nodes = nodes;
  createdCards.push(card);
  return card;
}

globalThis.document = {
  baseURI: "https://study.test/browse",
  createElement(tag) {
    invariant(tag === "div", "unexpected card element: " + tag);
    return makeCard();
  },
};
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/api/item/save" || url === "/api/item/unsave") {
    const status = saveStatuses.shift();
    return { async json() { return { status }; } };
  }
  invariant(url === "/api/workspace/add", "unexpected endpoint: " + url);
  return { async json() { return { status: true }; } };
};
globalThis.window = { openViewer(item) { globalThis.viewedItem = item; } };
globalThis.hydrateCalls = hydrateCalls;
globalThis.toastCalls = toastCalls;

const { createCard } = await import(process.argv[1]);
const attack = '"><img src=x onerror=alert(1)>';
const hostileItem = {
  id: '17" autofocus onfocus="alert(1)',
  title: attack,
  description: attack,
  thumb_url: "javascript:alert(1)",
  source_name: attack,
  source_url: "https://example.test/source",
  saved: false,
};
const hostileCard = createCard(hostileItem);
const hostileNodes = hostileCard.nodes;
invariant(!hostileCard.innerHTML.includes(attack), "untrusted fields reached innerHTML");
invariant(hostileNodes.get(".card-title").textContent === attack, "title was not assigned as text");
invariant(hostileNodes.get(".card-description").textContent === attack, "description was not assigned as text");
invariant(hostileNodes.get(".result-source-text").textContent === attack, "source was not assigned as text");
invariant(hostileNodes.get(".card-img-top").src === "/static/img/placeholder.png", "unsafe thumbnail survived");
invariant(hostileNodes.get(".save-btn").dataset.itemId === hostileItem.id, "item id was not assigned safely");
invariant(hostileNodes.get(".save-btn").getAttribute("aria-label") === "Save result", "unsaved label is wrong");
invariant(hostileNodes.get(".save-btn").getAttribute("aria-pressed") === "false", "unsaved state is wrong");

let stopped = false;
await hostileNodes.get(".save-btn").dispatch("click", {
  stopPropagation() { stopped = true; },
});
invariant(stopped, "save click did not stop propagation");
invariant(hostileItem.saved === true, "successful save did not mutate item");
invariant(hostileNodes.get(".save-btn").getAttribute("aria-label") === "Saved result", "saved label is wrong");
invariant(hostileNodes.get(".save-btn").getAttribute("aria-pressed") === "true", "saved pressed state is wrong");
invariant(hostileNodes.get(".save-icon-light").className.includes("bi-bookmark-fill"), "saved light glyph is wrong");
invariant(hostileNodes.get(".save-icon-dark").className.includes("bi-bookmark-check"), "saved dark glyph is wrong");

await hostileNodes.get(".save-btn").dispatch("click");
invariant(hostileItem.saved === true, "repeat save changed saved state");
invariant(hostileNodes.get(".save-btn").getAttribute("aria-label") === "Saved result", "repeat save changed label");
invariant(hostileNodes.get(".save-btn").getAttribute("aria-pressed") === "true", "repeat save changed pressed state");

const initiallySaved = {
  id: 18,
  title: "Saved",
  description: "Saved description",
  thumb_url: "https://images.test/saved.png",
  source_name: "PubMed",
  source_url: "https://example.test/saved",
  saved: true,
};
const savedCard = createCard(initiallySaved);
const savedBefore = {
  image: savedCard.nodes.get(".card-img-top").src,
  label: savedCard.nodes.get(".save-btn").getAttribute("aria-label"),
  pressed: savedCard.nodes.get(".save-btn").getAttribute("aria-pressed"),
  lightIcon: savedCard.nodes.get(".save-icon-light").className,
  darkIcon: savedCard.nodes.get(".save-icon-dark").className,
};
await savedCard.nodes.get(".save-btn").dispatch("click");
invariant(initiallySaved.saved === true, "initially saved item changed state");

const failedItem = {
  id: 19,
  title: "Failure",
  description: "No mutation",
  thumb_url: "",
  source_name: "Wikipedia",
  source_url: "https://example.test/failure",
  saved: false,
};
const failedCard = createCard(failedItem);
await failedCard.nodes.get(".save-btn").dispatch("click");
invariant(failedItem.saved === false, "failed save mutated item");
invariant(failedCard.nodes.get(".save-btn").getAttribute("aria-label") === "Save result", "failed save mutated DOM");
invariant(failedCard.nodes.get(".save-icon-light").className === "bi bi-bookmark save-icon-light", "failed save mutated icon");
const saveToasts = toastCalls.slice();

await hostileNodes.get(".view-btn").dispatch("click");
invariant(globalThis.viewedItem === hostileItem, "View lost original item");
await hostileNodes.get(".add-btn").dispatch("click");

const actionCalls = fetchCalls.filter((call) => call.url !== "/static/whitelist.json");
invariant(
  actionCalls.map((call) => call.url).join(",") ===
    "/api/item/save,/api/item/save,/api/item/save,/api/item/save,/api/workspace/add",
  "save/add endpoint sequence is wrong: " + actionCalls.map((call) => call.url).join(","),
);
invariant(JSON.parse(actionCalls[0].options.body).item_id === hostileItem.id, "save payload changed");
const addBody = JSON.parse(actionCalls[4].options.body);
invariant(addBody.item_id === hostileItem.id && addBody.workspace_id === 42, "workspace add payload changed");
invariant(hydrateCalls.length === 3, "workspace hydration count changed");

process.stdout.write(JSON.stringify({
  template: hostileCard.innerHTML,
  className: hostileCard.className,
  hostile: {
    title: hostileNodes.get(".card-title").textContent,
    description: hostileNodes.get(".card-description").textContent,
    source: hostileNodes.get(".result-source-text").textContent,
    image: hostileNodes.get(".card-img-top").src,
    itemId: hostileNodes.get(".save-btn").dataset.itemId,
    label: hostileNodes.get(".save-btn").getAttribute("aria-label"),
    pressed: hostileNodes.get(".save-btn").getAttribute("aria-pressed"),
    lightIcon: hostileNodes.get(".save-icon-light").className,
    darkIcon: hostileNodes.get(".save-icon-dark").className,
  },
  savedBefore,
  saveToasts,
  endpoints: actionCalls.map((call) => call.url),
}));
"""


BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const controls = new Map();
function control(selector, value = "") {
  const element = new FakeElement(selector);
  element.value = value;
  controls.set(selector, element);
  return element;
}
const search = control("#searchInput", "archive");
const go = control("#goBtn");
const filters = control("#filtersDropdown");
const menu = control(".browse-dropdown-menu");
const sorting = control("#filterSorting");
control("#filterYearFrom");
control("#filterYearTo");
control("#filterContentType");
control("#sidebarContainer");
control("#resultsContainer");
control("#whitelistCheckboxes");
const wikipedia = new FakeElement("wikipedia");
wikipedia.value = "wikipedia";
wikipedia.checked = true;
menu.querySelectorAll = () => [wikipedia];

const root = new FakeElement("root");
root.querySelector = (selector) => controls.get(selector) || null;
root.querySelectorAll = () => [wikipedia];
const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  getElementById(id) {
    return id === "google-cse-script" ? {} : null;
  },
  body: { appendChild() {} },
  createElement() {
    return new FakeElement("created");
  },
};
globalThis.window = {};
globalThis.localStorage = {
  getItem() { return null; },
  setItem() {},
};
const fetchCalls = [];
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  return { json() { return new Promise(() => {}); } };
};
globalThis.toastCalls = [];

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");

const searchCalls = fetchCalls.filter((call) => call.url === "/api/browse/search-all");
invariant(searchCalls.length === 1, "Go did not issue exactly one search");
invariant(searchCalls[0].options.method === "POST", "search method changed");
const body = JSON.parse(searchCalls[0].options.body);
invariant(body.query === "archive", "search query changed");
invariant(body.sources.length === 1 && body.sources[0] === "wikipedia", "search sources changed");
invariant(body.num_results === 10, "search result count changed");

process.stdout.write(JSON.stringify({ html: root.innerHTML, body }));
"""


CARD_IMPORT_REPLACEMENTS = (
    (
        "import { showToast } from './toast.js';",
        "const showToast = (...args) => globalThis.toastCalls.push(args);",
    ),
    (
        "import { hydrateWorkspaceSelect, getSelectedWorkspaceId, clearWorkspaceCache } "
        "from './workspace-selector.js';",
        "const hydrateWorkspaceSelect = (...args) => globalThis.hydrateCalls.push(args);\n"
        "const getSelectedWorkspaceId = () => 42;\n"
        "const clearWorkspaceCache = () => {};",
    ),
)
BROWSE_IMPORT_REPLACEMENTS = (
    (
        "import { showToast } from '../toast.js';",
        "const showToast = (...args) => globalThis.toastCalls.push(args);",
    ),
    (
        "import { createCard } from '../card.js';",
        "const createCard = () => ({});",
    ),
)
TASK6_DARK_ONLY_CLASSES = (
    "archive-page-browse",
    "browse-search-shell",
    "browse-results-layout",
    "browse-sidebar",
    "browse-results-pane",
    "ai-overview-panel",
    "source-summary-panel",
    "result-card",
    "result-card-actions",
    "result-source",
    "save-icon-light",
    "save-icon-dark",
)


def card_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/card.js"),
        CARD_IMPORT_REPLACEMENTS,
        CARD_RUNTIME_HARNESS,
        "card",
    )


def browse_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_RUNTIME_HARNESS,
        "browse",
    )


def render_server_result_card(item: dict) -> str:
    environment = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=True,
    )
    template = environment.from_string(
        '{% from "macros.html" import card %}{{ card(item) }}'
    )
    return template.render(item=item)


def composed_background_images(css: str, markup: str, target: str) -> list[str]:
    soup = BeautifulSoup(
        '<html data-bs-theme="dark"><body>' + markup + "</body></html>",
        "html.parser",
    )
    element = soup.select_one(target)
    assert element is not None
    values = []
    for header, body in css_rule_blocks(css):
        if header.startswith("@"):
            continue
        declarations = parse_relevant_css_declarations(body, header)
        if "background-image" not in declarations:
            continue
        for selector in selector_group(header):
            try:
                matches = soupsieve.match(selector, element)
            except soupsieve.SelectorSyntaxError:
                matches = False
            if matches:
                values.append(declarations["background-image"])
    return values


def assert_browse_css_contract(css: str) -> None:
    assert_task_selectors_are_dark_scoped(
        css,
        TASK6_DARK_ONLY_CLASSES,
        frozenset(),
        "Task 6",
        "a dark-only browse/result rule",
    )

    dropdown = css_rule_group_declarations(
        css, ('[data-bs-theme="dark"] .browse-dropdown-menu',)
    )
    assert dropdown["background"] == "var(--surface-600)"
    assert dropdown["border-radius"] == "var(--radius-panel)"
    assert "transition" not in dropdown

    assert css_rule_group_declarations(
        css,
        (
            '[data-bs-theme="dark"] .result-card:hover',
            '[data-bs-theme="dark"] .result-card:focus-within',
        ),
    ) == {
        "border-color": "hsl(35 50% 55% / 0.35)",
        "box-shadow": "var(--shadow-warm-glow) !important",
        "transform": "translateY(-2px)",
    }
    assert css_rule_group_declarations(
        css,
        (
            '[data-bs-theme="dark"] .dropdown-menu',
            '[data-bs-theme="dark"] .browse-dropdown-menu',
        ),
    )["transition"] == "opacity 180ms ease-in, visibility 0s linear 180ms"
    assert css_rule_group_declarations(
        css,
        (
            '[data-bs-theme="dark"] .dropdown-menu.show',
            '[data-bs-theme="dark"] .browse-dropdown-menu.show',
        ),
    )["transition"] == "opacity 180ms ease-out, visibility 0s linear 0s"
    assert css_rule_group_declarations(
        css, ('[data-bs-theme="dark"] .result-card .save-icon-light',)
    ) == {"display": "none !important"}
    assert css_rule_group_declarations(
        css, ('[data-bs-theme="dark"] .result-card .save-icon-dark',)
    ) == {"display": "inline-block !important"}

    mobile = css_block_body(css, "@media (max-width: 767.98px)")
    assert css_rule_group_declarations(
        mobile, ('[data-bs-theme="dark"] .archive-page-browse',)
    ) == {"overflow": "visible"}
    assert css_rule_group_declarations(
        mobile, ('[data-bs-theme="dark"] .browse-results-layout',)
    ) == {"flex-direction": "column", "height": "auto !important"}
    assert css_rule_group_declarations(
        mobile, ('[data-bs-theme="dark"] #sidebarContainer.browse-sidebar',)
    ) == {
        "border-right": "0 !important",
        "border-bottom": "1px solid hsl(35 40% 45% / 0.18)",
        "max-width": "none",
        "min-width": "0",
        "overflow-y": "visible !important",
        "width": "100% !important",
    }
    assert css_rule_group_declarations(
        mobile, ('[data-bs-theme="dark"] .browse-results-pane',)
    ) == {"overflow-y": "visible !important", "width": "100%"}
    assert css_rule_group_declarations(
        mobile,
        (
            '[data-bs-theme="dark"] .browse-results-row .col',
            '[data-bs-theme="dark"] .browse-results-row .result-card',
        ),
    ) == {"min-width": "0", "width": "100%"}


def test_task6_card_runtime_preserves_save_only_state_and_failed_requests():
    assert "/api/item/unsave" not in read_text("static/js/card.js")
    rendered = card_runtime()
    assert rendered["endpoints"] == [
        "/api/item/save",
        "/api/item/save",
        "/api/item/save",
        "/api/item/save",
        "/api/workspace/add",
    ]
    assert rendered["savedBefore"] == {
        "image": "https://images.test/saved.png",
        "label": "Saved result",
        "pressed": "true",
        "lightIcon": "bi bi-bookmark-fill text-danger save-icon-light",
        "darkIcon": "bi bi-bookmark-check save-icon-dark d-none",
    }
    assert rendered["saveToasts"] == [
        ["Saved", "success"],
        ["Already saved", "info"],
        ["Saved", "success"],
        ["Already saved", "info"],
    ]


def test_task6_client_and_jinja_render_hostile_fields_as_inert_text_with_light_parity():
    client = card_runtime()
    attack = '"><img src=x onerror=alert(1)>'
    hostile = {
        "id": '17" autofocus onfocus="alert(1)',
        "title": attack,
        "description": attack,
        "thumb_url": "javascript:alert(1)",
        "source_name": attack,
        "source_url": "https://example.test/source",
        "saved": False,
    }
    server = BeautifulSoup(render_server_result_card(hostile), "html.parser")

    assert attack not in client["template"]
    assert "onerror=" not in client["template"]
    assert client["hostile"] == {
        "title": attack,
        "description": attack,
        "source": attack,
        "image": "/static/img/placeholder.png",
        "itemId": hostile["id"],
        "label": "Saved result",
        "pressed": "true",
        "lightIcon": "bi bi-bookmark-fill text-danger save-icon-light",
        "darkIcon": "bi bi-bookmark-check save-icon-dark d-none",
    }
    assert server.select_one(".card-title").get_text(strip=True) == attack
    assert server.select_one(".card-description").get_text(strip=True) == attack
    assert server.select_one(".result-source-text").get_text(strip=True) == attack
    assert server.select_one("img.card-img-top").get("src") == "/static/img/placeholder.png"
    assert server.select_one(".save-btn").get("data-item-id") == hostile["id"]
    assert not [
        name
        for tag in server.find_all(True)
        for name in tag.attrs
        if name.lower().startswith("on")
    ]

    saved_server = BeautifulSoup(
        render_server_result_card({**hostile, "saved": True}),
        "html.parser",
    )
    save = saved_server.select_one(".save-btn")
    assert save.get("aria-pressed") == client["savedBefore"]["pressed"]
    assert " ".join(save.select_one(".save-icon-light").get("class")) == client[
        "savedBefore"
    ]["lightIcon"]
    assert " ".join(save.select_one(".save-icon-dark").get("class")) == client[
        "savedBefore"
    ]["darkIcon"]


def test_task6_card_templates_keep_shared_structure_and_equal_wood_cascade():
    client = card_runtime()
    client_markup = '<div class="' + client["className"] + '">' + client["template"] + "</div>"
    item = {
        "id": 1,
        "title": "Result",
        "description": "Description",
        "thumb_url": "",
        "source_name": "Wikipedia",
        "source_url": "https://example.test",
        "saved": True,
    }
    server_markup = render_server_result_card(item)
    css = read_text("static/css/custom.css")
    wood = (
        "linear-gradient(var(--surface-700), var(--surface-700)), "
        'url("/static/img/textures/wood-texture.png")'
    )

    for markup in (client_markup, server_markup):
        soup = BeautifulSoup(markup, "html.parser")
        assert set(soup.select_one(".result-card").get("class")) == {
            "card",
            "card-fixed",
            "shadow-sm",
            "surface-leather",
            "result-card",
            "rounded-3",
            "h-100",
        }
        assert soup.select_one(".result-source i").get("aria-hidden") == "true"
        assert soup.select_one(".save-btn").get("type") == "button"
        assert soup.select_one(".view-btn").get("type") == "button"
        assert soup.select_one(".add-btn").get("type") == "button"
        assert {"btn-outline-secondary", "btn-secondary-wood"}.issubset(
            soup.select_one(".view-btn").get("class")
        )
        assert {"btn-primary", "btn-secondary-wood"}.issubset(
            soup.select_one(".add-btn").get("class")
        )
        if markup == client_markup:
            workspace = soup.select_one(".workspace-select")
            assert {"form-select", "form-select-sm", "archive-dropdown"}.issubset(
                workspace.get("class")
            )
            assert workspace.get("aria-label") == "Choose workspace"
        for target in (".view-btn", ".add-btn"):
            applied = composed_background_images(css, markup, target)
            assert applied
            assert applied[-1] == wood


def test_task6_browse_runtime_keeps_go_search_listener_and_payload():
    rendered = browse_runtime()
    assert rendered["body"] == {
        "query": "archive",
        "sources": ["wikipedia"],
        "num_results": 10,
        "filters": {},
    }


def test_task6_runtime_guards_catch_go_listener_and_unsaved_label_mutations():
    browse = read_text("static/js/pages/browse.js")
    listener = "    goBtn.addEventListener('click', performSearch);\n"
    assert browse.count(listener) == 1
    with pytest.raises(AssertionError, match="browse runtime harness failed"):
        browse_runtime(browse.replace(listener, "", 1))

    card = read_text("static/js/card.js")
    label = "'Save result'"
    assert card.count(label) >= 1
    with pytest.raises(AssertionError, match="card runtime harness failed"):
        card_runtime(card.replace(label, "'Corrupt unsaved label'", 1))


def test_task6_browse_structure_preserves_light_output_and_supports_mobile_stack():
    browse = read_text("static/js/pages/browse.js")
    soup = BeautifulSoup(assigned_template_markup(browse, "pageRoot"), "html.parser")
    page = soup.select_one("div.archive-page.archive-page-browse")
    assert page is not None
    assert "container-fluid" not in page.get("class", ())
    direct_children = page.find_all(recursive=False)
    assert [child.name for child in direct_children] == ["span", "span", "div"]
    assert all(
        decoration.get("aria-hidden") == "true"
        for decoration in direct_children[:2]
    )

    search_shell = page.select_one(".browse-search-shell")
    assert {"bg-body-tertiary", "border-bottom", "p-3", "mb-3"}.issubset(
        search_shell.get("class", ())
    )
    assert search_shell.select_one(".container-fluid") is not None
    assert search_shell.select_one("#goBtn").get("type") == "button"
    filters = search_shell.select_one("#filtersDropdown")
    assert (filters.get("type"), filters.get("aria-expanded"), filters.get("aria-controls")) == (
        "button",
        "false",
        "browseFiltersMenu",
    )

    layout = page.select_one(".browse-results-layout.d-flex")
    sidebar = layout.select_one("#sidebarContainer.browse-sidebar")
    pane = layout.select_one(".browse-results-pane")
    assert layout.get("style") == "height: calc(100vh - 200px);"
    assert sidebar.get("style") == "width: 320px; min-width: 320px; overflow-y: auto;"
    assert {"border-end", "p-3", "flex-shrink-0"}.issubset(sidebar.get("class", ()))
    assert {"flex-grow-1", "p-3", "overflow-y-auto"}.issubset(pane.get("class", ()))
    assert pane.select_one("#resultsContainer") is not None
    assert pane.select_one("#googleCseContainer") is not None

    expected_ids = {
        "searchInput",
        "goBtn",
        "filtersDropdown",
        "browseFiltersMenu",
        "filterWikipedia",
        "filterGBooks",
        "filterPubMed",
        "filterScholar",
        "filterYearFrom",
        "filterYearTo",
        "filterContentType",
        "filterSorting",
        "sidebarContainer",
        "resultsContainer",
        "googleCseContainer",
    }
    assert expected_ids.issubset({tag.get("id") for tag in soup.select("[id]")})

    assert browse.count("fetch('/api/browse/search-all'") == 2
    assert "num_results: 20" in browse
    assert "localStorage.setItem(BROWSE_STORAGE_KEY" in browse
    assert "localStorage.getItem(BROWSE_STORAGE_KEY" in browse
    assert "loadMoreBtn.addEventListener('click', loadMoreResults)" in browse


def test_task6_dynamic_panels_pagination_and_dark_contract_remain_intact():
    browse = read_text("static/js/pages/browse.js")
    overview = BeautifulSoup(assigned_template_markup(browse, "sidebar"), "html.parser")
    assert {"card", "mb-3", "surface-leather", "ai-overview-panel"}.issubset(
        overview.select_one(".ai-overview-panel").get("class", ())
    )
    pagination = BeautifulSoup(
        assigned_template_markup(browse, "buttonContainer"), "html.parser"
    )
    load_more = pagination.select_one("#loadMoreBtn")
    assert {"btn", "btn-outline-primary", "btn-secondary-wood"}.issubset(
        load_more.get("class", ())
    )
    assert load_more.get("type") == "button"

    css = read_text("static/css/custom.css")
    assert css_rule_group_declarations(css, (".card-description",))[
        "-webkit-line-clamp"
    ] == "3"
    assert css_rule_group_declarations(css, (".browse-search-group",)) == {
        "display": "flex",
        "width": "100%",
    }
    assert_browse_css_contract(css)


def test_task6_dark_contract_rejects_unscoped_visual_rule():
    css = read_text("static/css/custom.css")
    assert_browse_css_contract(css)
    with pytest.raises(AssertionError, match="outside dark scope"):
        assert_browse_css_contract(css + "\n.result-card { color: red; }\n")


def test_upload_view_uses_leather_file_components_and_safe_decorations():
    upload = read_text("static/js/pages/upload.js")
    css = read_text("static/css/custom.css")
    soup = BeautifulSoup(assigned_template_markup(upload, "pageRoot"), "html.parser")
    page = soup.select_one(".archive-page.archive-page-upload")
    assert page is not None
    decorations = page.find_all("span", recursive=False)
    assert [item.get("class")[-1] for item in decorations] == [
        "illustration-compass", "illustration-sextant", "illustration-flourish"
    ]
    assert all(item.get("aria-hidden") == "true" for item in decorations)
    content = page.select_one(".container.py-4.archive-content.upload-content")
    assert content.get("style") == "max-width: 700px;"
    zone = content.select_one("#uploadZone.surface-leather.upload-zone")
    assert {"card-body", "text-center", "p-5"}.issubset(zone.get("class", ()))
    assert zone.select_one("#fileInput").get("style") == "display: none;"
    upload_button = content.select_one("#uploadBtn")
    assert {"btn", "btn-primary", "btn-brass", "w-100"}.issubset(upload_button.get("class", ()))
    file_panel = content.select_one(".card.surface-leather.file-list-panel")
    assert {"badge", "bg-primary", "archive-count-badge"}.issubset(file_panel.select_one("#fileCountBadge").get("class", ()))
    for marker in (
        "file-icon file-icon-${file.file_type} text-muted",
        "btn btn-outline-danger btn-sm icon-button icon-button-danger delete-btn",
        "progressBar.style.display = 'block'", "progressBar.style.display = 'none'",
        "fetch('/api/files/upload'", "fetch('/api/files/list')",
    ):
        assert marker in upload
    assert "result.files.length === 0" not in upload
    assert "illustration-open-book" not in upload
    empty_book = css_rule_group_declarations(css, ('[data-bs-theme="dark"] #filesList:empty::before',))
    assert empty_book["mask-image"] == 'url("/static/img/illustrations/open-book.svg")'
    assert css_rule_group_declarations(css, ('[data-bs-theme="dark"] #filesList:empty::after',))["content"] == '"No files uploaded yet."'
    mobile = css_block_body(css, "@media (max-width: 575.98px)")
    assert css_rule_group_declarations(mobile, ('[data-bs-theme="dark"] .archive-page-upload > .illustration-compass',)) == {"height": "120px", "left": "-2rem", "width": "120px"}
    assert css.index("@media (max-width: 575.98px)") > css.index('[data-bs-theme="dark"] .archive-page-upload .illustration-compass')
    assert_task_selectors_are_dark_scoped(css, ("archive-page-upload", "upload-content", "upload-panel", "upload-actions", "file-list-panel", "file-icon", "file-size"), frozenset(), "Task 7", "a dark-only upload rule")


def test_workspace_has_archive_panels_tabs_sources_notes_and_chat():
    workspace = read_text("static/js/pages/workspace.js")
    css = read_text("static/css/custom.css")
    for marker in (
        "archive-page archive-page-workspace", "surface-leather workspace-main-panel",
        "surface-leather workspace-right-panel", "workspace-source-item", "chat-messages",
        '<i class="bi bi-file-earmark-text note-icon-dark d-none me-2" aria-hidden="true"></i><span class="note-icon-light">📝 </span>',
    ):
        assert marker in workspace
    for preserved in (
        "workspace-tabs nav nav-pills", "noteBtn.dataset.id = note.id",
        "noteBtn.title = note.title", "editNote(note.id)", "escapeHtml(note.title)",
        "message.role === 'agent'", "escapeHtml(message.text)", "studyHelperAI.chat(value)",
    ):
        assert preserved in workspace
    exact_rules = (
        ((('[data-bs-theme="dark"] .archive-page-workspace .workspace-main-panel', '[data-bs-theme="dark"] .archive-page-workspace .workspace-right-panel')), {"min-height": "680px"}),
        ((('[data-bs-theme="dark"] .quick-note-input:focus',)), {"background": "transparent", "border-color": "var(--gold-500)", "box-shadow": "var(--shadow-warm-glow)"}),
        ((('[data-bs-theme="dark"] .workspace-tabs .nav-link.active',)), {"background": "hsl(35 70% 55% / 0.14)", "color": "var(--gold-100)"}),
        ((('[data-bs-theme="dark"] .workspace-source-item.active',)), {"background": "hsl(35 70% 55% / 0.1)", "border-left": "3px solid var(--gold-300)", "box-shadow": "var(--shadow-warm-glow)", "color": "var(--text-primary)"}),
        ((('[data-bs-theme="dark"] .workspace-source-item h6',)), {"color": "var(--text-primary)"}),
        ((('[data-bs-theme="dark"] .note-item',)), {"background-color": "var(--surface-700)", "background-image": "none", "color": "var(--text-primary)"}),
        ((('[data-bs-theme="dark"] .note-icon-light',)), {"display": "none"}),
        ((('[data-bs-theme="dark"] .note-icon-dark',)), {"color": "var(--gold-300)", "display": "inline-block !important"}),
        ((('[data-bs-theme="dark"] .chat-message-agent',)), {"background": "var(--surface-600) !important", "border-radius": "18px 22px 16px 6px !important"}),
        ((('[data-bs-theme="dark"] .chat-message-user',)), {"background": "linear-gradient(rgb(138 102 53 / 0.42), rgb(138 102 53 / 0.42)), var(--surface-700) !important", "border-radius": "22px 18px 6px 16px !important", "color": "var(--text-primary) !important"}),
        ((('[data-bs-theme="dark"] .chat-avatar::before',)), {"align-items": "center", "background": "var(--surface-700)", "border": "1px solid var(--gold-500)", "border-radius": "50%", "bottom": "0", "color": "var(--gold-300)", "content": r'"\2699"', "display": "flex", "height": "2.25rem", "justify-content": "center", "left": "-2.9rem", "line-height": "1", "position": "absolute", "width": "2.25rem"}),
        ((('[data-bs-theme="dark"] .chat-message-agent::after',)), {"border-color": "transparent var(--surface-600) transparent transparent", "border-width": "0.45rem 0.55rem 0.45rem 0", "left": "-0.5rem"}),
    )
    for selectors, expected in exact_rules:
        assert css_rule_group_declarations(css, selectors) == expected

    assert_task_selectors_are_dark_scoped(css, (
        "archive-page-workspace", "workspace-main-panel", "workspace-right-panel", "quick-note-input",
        "source-preview-shell", "source-preview-content", "workspace-tabs", "workspace-source-item",
        "workspace-source-name", "note-item", "note-icon-light", "note-icon-dark", "chat-messages",
        "chat-row-agent", "chat-row-user",
    ), frozenset({(".workspace-tabs .nav-link",)}), "Task 8", "the existing neutral tab-radius rule")

    desktop_header, mobile_header = "@media (max-width: 991.98px)", "@media (max-width: 575.98px)"
    assert (css.count(desktop_header), css.count(mobile_header)) == (1, 1)
    desktop, mobile = css_block_body(css, desktop_header), css_block_body(css, mobile_header)
    panel_group = ('[data-bs-theme="dark"] .archive-page-workspace .workspace-main-panel', '[data-bs-theme="dark"] .archive-page-workspace .workspace-right-panel')
    assert css_rule_group_declarations(desktop, panel_group) == {"min-height": "auto"}
    assert css_rule_group_declarations(desktop, ('[data-bs-theme="dark"] .archive-page-workspace .resizable-panel',)) == {"max-width": "none", "min-width": "0", "resize": "none", "width": "100%"}
    assert css_rule_group_declarations(mobile, ('[data-bs-theme="dark"] .chat-message',)) == {"max-width": "88%"}
    assert css.index(desktop_header) > css.index(panel_group[0]) and css.index(mobile_header) > css.index('[data-bs-theme="dark"] .chat-message {')

    tokens = css_rule_declarations(css, DARK_ROOT_SELECTOR)
    user_rule = css_rule_group_declarations(css, ('[data-bs-theme="dark"] .chat-message-user',))
    overlay = re.search(r"rgb\((\d+) (\d+) (\d+) / ([0-9.]+)\)", user_rule["background"])
    assert overlay is not None
    foreground, alpha = tuple(map(int, overlay.groups()[:3])), float(overlay.group(4))
    surface = tuple(int(tokens["--surface-700"][index:index + 2], 16) for index in (1, 3, 5))
    composite = "#" + "".join(f"{round(top * alpha + base * (1 - alpha)):02X}" for top, base in zip(foreground, surface))
    user_tail = css_rule_group_declarations(css, ('[data-bs-theme="dark"] .chat-message-user::after',))
    assert user_tail == {"border-color": f"transparent transparent transparent {composite}", "border-width": "0.45rem 0 0.45rem 0.55rem", "right": "-0.5rem"}
    assert contrast_ratio(tokens["--text-primary"], composite) >= 4.5


def test_candle_cursor_contract_is_dark_scoped_and_guarded():
    layout = read_text("templates/layout.html")
    theme = read_text("static/js/theme.js")
    css = read_text("static/css/custom.css")
    layer = '<div class="candle-glow" aria-hidden="true"></div>'
    assert layout.count(layer) == 1
    assert re.search(r"<body>\s*" + re.escape(layer), layout)
    for marker in (
        'matchMedia("(hover: hover) and (pointer: fine)")',
        "function startCandle()",
        "if (!candleLayer || isTracking || !finePointer.matches) return;",
        'addEventListener("pointermove", trackPointer',
        "function stopCandle()",
        "if (!isTracking) return;",
        'removeEventListener("pointermove", trackPointer)',
        "requestAnimationFrame(animateCandle)",
        "cancelAnimationFrame(animationFrame)",
        "currentX += (targetX - currentX) * 0.15",
        "currentY += (targetY - currentY) * 0.15",
        "function syncCandle()",
        'finePointer.addEventListener("change", syncCandle)',
    ):
        assert marker in theme
    assert theme.count('themeBtn.addEventListener("click", toggleTheme)') == 1
    assert css_rule_group_declarations(css, ('[data-bs-theme="dark"] .candle-glow',)) == {
        "animation": "candle-flicker 4.2s ease-in-out infinite",
        "background": (
            "radial-gradient(circle var(--candle-radius) at var(--candle-x) "
            "var(--candle-y), hsl(35 80% 68% / 0.16), "
            "hsl(35 80% 68% / 0.05) 45%, transparent 75%)"
        ),
        "inset": "0",
        "mix-blend-mode": "soft-light",
        "pointer-events": "none",
        "position": "fixed",
        "z-index": "var(--z-candle-glow)",
    }
    assert_task_selectors_are_dark_scoped(
        css, ("candle-glow",), frozenset(), "Task 9", "an approved neutral rule"
    )
    reduced = css_block_body(css, "@media (prefers-reduced-motion: reduce)")
    coarse = css_block_body(css, "@media (hover: none), (pointer: coarse)")
    assert css_rule_declarations(reduced, '[data-bs-theme="dark"] .candle-glow') == {
        "animation": "none"
    }
    assert css_rule_declarations(coarse, '[data-bs-theme="dark"] .candle-glow') == {
        "display": "none"
    }
    assert css.count("@media (prefers-reduced-motion: reduce)") == 1
    assert css.count("@media (hover: none), (pointer: coarse)") == 1
    keyframes = css_block_body(css, "@keyframes candle-flicker")
    frames = list(css_rules(keyframes))
    assert [rule[1]["opacity"] for rule in frames] == [
        "1", "0.94", "1", "0.9", "0.98", "0.93", "1", "0.95"
    ]
    assert all(set(declarations) == {"opacity"} for _, declarations in frames)
