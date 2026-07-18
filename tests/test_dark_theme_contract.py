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

import src.search as search_api


ROOT = Path(__file__).resolve().parents[1]
SERVER_IDENTITY_METADATA_VECTORS = (
    {
        "name": "ligature-casefold",
        "records": (
            {"source_name": "Archive", "title": "ﬀ"},
            {"source_name": "archive", "title": "FF"},
        ),
        "identity": '["display","archive","ff"]',
        "canonical_url": "",
    },
    {
        "name": "numeric-exponent",
        "records": (
            {"source_name": "Archive", "source_id": 1e-7, "title": "Exponent numeric"},
            {"source_name": "archive", "source_id": "1e-07", "title": "Exponent string"},
        ),
        "identity": '["source_id","archive","1e-07"]',
        "canonical_url": "",
    },
    {
        "name": "leading-zero-port",
        "records": (
            {"source_url": "https://EXAMPLE.test:080/path#intro", "title": "Port 080"},
            {"source_url": "https://example.test:80/path", "title": "Port 80"},
        ),
        "identity": '["url","https://example.test:80/path"]',
        "canonical_url": "https://example.test:80/path",
    },
)
SVG_NAMES = (
    "compass-rose.svg",
    "sextant.svg",
    "stacked-books.svg",
    "open-book.svg",
    "scrollwork-flourish.svg",
)
DARK_ROOT_SELECTOR = '[data-bs-theme="dark"]'
DARK_BODY_SELECTOR = '[data-bs-theme="dark"] body'
LIGHT_GUARD = ':root:not([data-bs-theme="dark"])'
FORCED_COLORS_LIGHT_FOCUS_SELECTORS = (
    f"{LIGHT_GUARD} .archive-wordmark:focus-visible",
    f"{LIGHT_GUARD} .icon-button:focus-visible",
    f"{LIGHT_GUARD} .btn:focus-visible",
    f"{LIGHT_GUARD} .btn-close:focus-visible",
    f"{LIGHT_GUARD} .form-check-input:focus",
    f"{LIGHT_GUARD} .form-check-input:focus-visible",
    f"{LIGHT_GUARD} .form-control:focus",
    f"{LIGHT_GUARD} .form-select:focus",
    f"{LIGHT_GUARD} .archive-dropdown:focus-visible",
    f"{LIGHT_GUARD} .navbar-brand:focus-visible",
    f"{LIGHT_GUARD} .workspace-tabs .nav-link:focus-visible",
    f"{LIGHT_GUARD} .workspace-source-item:focus-visible",
    f"{LIGHT_GUARD} .nav-sidebar .list-group-item:focus-visible",
    f"{LIGHT_GUARD} input:focus-visible",
    f"{LIGHT_GUARD} select:focus-visible",
    f"{LIGHT_GUARD} textarea:focus-visible",
    f"{LIGHT_GUARD} a:focus-visible",
)
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
TASK3_ALLOWED_LIGHT_SELECTOR_GROUPS = frozenset(
    {
        (".surface-leather",),
        (".btn-secondary-wood",),
        (f"{LIGHT_GUARD} .btn-secondary-wood",),
        (
            f"{LIGHT_GUARD} .btn-secondary-wood:hover",
            f"{LIGHT_GUARD} .btn-secondary-wood:active",
        ),
        (
            f"{LIGHT_GUARD} button",
            f"{LIGHT_GUARD} .btn",
            f"{LIGHT_GUARD} input",
            f"{LIGHT_GUARD} select",
            f"{LIGHT_GUARD} textarea",
            f"{LIGHT_GUARD} .btn-secondary-wood",
            f"{LIGHT_GUARD} .btn-brass",
            f"{LIGHT_GUARD} .btn-ghost",
            f"{LIGHT_GUARD} .icon-button",
            f"{LIGHT_GUARD} .archive-dropdown",
            f"{LIGHT_GUARD} .form-control",
            f"{LIGHT_GUARD} .form-select",
            f"{LIGHT_GUARD} .navbar-brand",
        ),
        (
            f"{LIGHT_GUARD} .btn-brass",
            f"{LIGHT_GUARD} .btn-primary:not(.btn-secondary-wood)",
        ),
        (f"{LIGHT_GUARD} .btn-ghost",),
        (f"{LIGHT_GUARD} .btn-ghost:hover",),
        (f"{LIGHT_GUARD} .icon-button",),
        (f"{LIGHT_GUARD} .icon-button:hover",),
        (f"{LIGHT_GUARD} .icon-button-danger:hover",),
        (f'{LIGHT_GUARD} .icon-button[aria-pressed="true"]',),
        (f"{LIGHT_GUARD} .icon-button:focus-visible",),
        (
            f"{LIGHT_GUARD} .icon-button .bi",
            f"{LIGHT_GUARD} .icon-button .text-muted",
        ),
        (
            f"{LIGHT_GUARD} .archive-dropdown",
            f"{LIGHT_GUARD} .form-select",
        ),
        (
            f"{LIGHT_GUARD} .btn:focus-visible",
            f"{LIGHT_GUARD} .icon-button:focus-visible",
            f"{LIGHT_GUARD} .archive-dropdown:focus-visible",
            f"{LIGHT_GUARD} .navbar-brand:focus-visible",
        ),
        (f"{LIGHT_GUARD} .archive-count-badge",),
        (f"{LIGHT_GUARD} .archive-category-badge",),
        (f"{LIGHT_GUARD} .archive-illustration",),
        (f"{LIGHT_GUARD} .illustration-compass",),
        (f"{LIGHT_GUARD} .illustration-sextant",),
        (f"{LIGHT_GUARD} .illustration-books",),
        (f"{LIGHT_GUARD} .illustration-open-book",),
        (f"{LIGHT_GUARD} .illustration-flourish",),
        (
            f"{LIGHT_GUARD} .archive-page-home .illustration-books",
            f"{LIGHT_GUARD} .archive-page-browse .illustration-books",
            f"{LIGHT_GUARD} .archive-page-workspace .illustration-books",
        ),
        (
            f"{LIGHT_GUARD} .archive-page-home .illustration-flourish",
            f"{LIGHT_GUARD} .archive-page-browse .illustration-flourish",
            f"{LIGHT_GUARD} .archive-page-workspace .illustration-flourish",
        ),
        (f"{LIGHT_GUARD} .archive-page-upload .illustration-compass",),
        (f"{LIGHT_GUARD} .archive-page-upload .illustration-sextant",),
        (f"{LIGHT_GUARD} .archive-page-upload > .illustration-flourish",),
        (f"{LIGHT_GUARD} .archive-page-upload > .illustration-sextant",),
        (f"{LIGHT_GUARD} .archive-page-upload > .illustration-compass",),
        FORCED_COLORS_LIGHT_FOCUS_SELECTORS,
    }
)
TASK4_NAVIGATION_CLASSES = (
    "archive-navbar",
    "archive-menu-button",
    "archive-menu-icon",
    "archive-menu-book",
    "archive-menu-bars",
    "archive-wordmark",
    "nav-sidebar-open",
    "nav-sidebar-overlay",
    "nav-sidebar",
)
TASK4_ALLOWED_THEME_NEUTRAL_SELECTOR_GROUPS = frozenset(
    {
        (".archive-menu-button",),
        (".archive-menu-icon",),
        (".archive-menu-book", ".archive-menu-bars"),
        (".archive-menu-book",),
        (".archive-menu-bars",),
        (".archive-menu-bars > span",),
        (
            '.archive-menu-button[aria-expanded="true"] .archive-menu-book',
        ),
        (
            '.archive-menu-button[aria-expanded="true"] .archive-menu-bars',
        ),
        ("body.nav-sidebar-open",),
        (".nav-sidebar-overlay",),
        (".nav-sidebar-overlay.d-none",),
        (".nav-sidebar",),
        (".nav-sidebar .list-group-item",),
        (f"{LIGHT_GUARD} .archive-navbar",),
        (f"{LIGHT_GUARD} .archive-wordmark",),
        (f"{LIGHT_GUARD} .archive-wordmark:hover",),
        (f"{LIGHT_GUARD} .archive-wordmark:focus-visible",),
        (f"{LIGHT_GUARD} .archive-navbar .navbar-text",),
        (f"{LIGHT_GUARD} .nav-sidebar-overlay",),
        (f"{LIGHT_GUARD} .nav-sidebar",),
        (f"{LIGHT_GUARD} .nav-sidebar .list-group-item",),
        (
            f"{LIGHT_GUARD} .nav-sidebar .list-group-item:hover",
            f"{LIGHT_GUARD} .nav-sidebar .list-group-item:focus-visible",
        ),
        FORCED_COLORS_LIGHT_FOCUS_SELECTORS,
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
        (f"{LIGHT_GUARD} .archive-page-title",),
        (f"{LIGHT_GUARD} .home-search-group",),
        (f"{LIGHT_GUARD} .workspace-card",),
        (
            f"{LIGHT_GUARD} .workspace-card:not(.workspace-card-add):hover",
            f"{LIGHT_GUARD} .workspace-card:not(.workspace-card-add):focus-within",
        ),
        (f"{LIGHT_GUARD} .workspace-card-add",),
        (f"{LIGHT_GUARD} .workspace-card-add h5",),
        (
            f"{LIGHT_GUARD} .workspace-card-add:hover",
            f"{LIGHT_GUARD} .workspace-card-add:focus-within",
        ),
        (f"{LIGHT_GUARD} .archive-page.archive-page-browse",),
        (f"{LIGHT_GUARD} .archive-page",),
        (f"{LIGHT_GUARD} .archive-content",),
        (
            f"{LIGHT_GUARD} .archive-page-home .illustration-books",
            f"{LIGHT_GUARD} .archive-page-browse .illustration-books",
            f"{LIGHT_GUARD} .archive-page-workspace .illustration-books",
        ),
        (
            f"{LIGHT_GUARD} .archive-page-home .illustration-flourish",
            f"{LIGHT_GUARD} .archive-page-browse .illustration-flourish",
            f"{LIGHT_GUARD} .archive-page-workspace .illustration-flourish",
        ),
        (f"{LIGHT_GUARD} .archive-page .archive-page-title",),
        (f"{LIGHT_GUARD} .archive-page-home .workspace-card",),
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
LIGHT_REDUCED_MOTION_SELECTORS = (
    f"{LIGHT_GUARD} *",
    f"{LIGHT_GUARD} *::before",
    f"{LIGHT_GUARD} *::after",
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
    this.navigationLinks = [];
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

  querySelectorAll(selector) {
    if (selector === "a[href]") return this.navigationLinks;
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
  {
    "aria-expanded": "false",
    "aria-label": "Open navigation menu",
  },
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
navOverlay.navigationLinks = [homeLink, browseLink, uploadLink];
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
  invariant(brandMenuButton.getAttribute("aria-label") === "Navigation menu open.", `${context}: label`);
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
  invariant(brandMenuButton.getAttribute("aria-label") === "Open navigation menu", `${context}: label`);
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

for (const navigationLink of [homeLink, browseLink, uploadLink]) {
  brandMenuButton.dispatch("click");
  navigationLink.dispatch("click");
  assertClosed(`${navigationLink.id} click`);
}

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
    if (selector === "#homeSearchBtn") return searchButton;
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
const searchButton = new FakeElement("homeSearchBtn");
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
invariant(searchInput.listeners.get("keydown")?.length === 1, "search Enter listener missing");
invariant(searchButton.listeners.get("click")?.length === 1, "search button listener missing");
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

searchInput.value = "   ";
await searchInput.dispatch("keydown", { key: "Enter" });
invariant(window.location.href === "", "blank academic search navigated");
searchInput.value = "quantum mechanics";
await searchInput.dispatch("keydown", { key: "Enter" });
invariant(window.location.href === "/browse?q=quantum%20mechanics", "Enter search did not open Browse");
window.location.href = "";
searchInput.value = "archives";
await searchButton.dispatch("click");
invariant(window.location.href === "/browse?q=archives", "search button did not open Browse");

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
                "linear-gradient(hsl(30 43% 12% / 0.52), "
                "hsl(30 43% 12% / 0.52)), "
                'url("/static/img/textures/leather-texture.png")'
            ),
            "background-blend-mode": "normal",
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
                "linear-gradient(hsl(31 51% 12% / 0.38), "
                "hsl(31 51% 12% / 0.38)), "
                'url("/static/img/textures/wood-texture.png")'
            ),
            "background-blend-mode": "normal",
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
            "opacity": "0.14",
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
EXPECTED_COARSE_POINTER_DECLARATIONS = {"opacity": "0.10"}
EXPECTED_NAVIGATION_NEUTRAL_RULES = (
    (
        (".archive-menu-button",),
        {
            "-webkit-appearance": "none",
            "appearance": "none",
            "background": "transparent",
            "block-size": "2.5rem",
            "border": "0",
            "cursor": "pointer",
            "flex": "0 0 2.5rem",
            "inline-size": "2.5rem",
            "min-block-size": "2.5rem",
            "min-inline-size": "2.5rem",
            "padding-inline": "0",
        },
    ),
    (
        (".archive-menu-icon",),
        {
            "display": "block",
            "height": "1.5rem",
            "position": "relative",
            "width": "1.75rem",
        },
    ),
    (
        (".archive-menu-book", ".archive-menu-bars"),
        {
            "inset": "0",
            "position": "absolute",
            "transition": "opacity 160ms ease, transform 160ms ease",
        },
    ),
    (
        (".archive-menu-book",),
        {
            "-webkit-mask": (
                'url("/static/img/illustrations/open-book.svg") center / contain '
                "no-repeat"
            ),
            "background-color": "currentColor",
            "mask": (
                'url("/static/img/illustrations/open-book.svg") center / contain '
                "no-repeat"
            ),
            "opacity": "1",
            "transform": "scale(1)",
        },
    ),
    (
        (".archive-menu-bars",),
        {
            "display": "flex",
            "flex-direction": "column",
            "gap": "0.25rem",
            "justify-content": "center",
            "opacity": "0",
            "transform": "scale(0.72)",
        },
    ),
    (
        (".archive-menu-bars > span",),
        {
            "background-color": "currentColor",
            "border-radius": "999px",
            "display": "block",
            "height": "2px",
            "width": "100%",
        },
    ),
    (
        ('.archive-menu-button[aria-expanded="true"] .archive-menu-book',),
        {"opacity": "0", "transform": "scale(0.72)"},
    ),
    (
        ('.archive-menu-button[aria-expanded="true"] .archive-menu-bars',),
        {"opacity": "1", "transform": "scale(1)"},
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


def css_block_body_containing_selector(css: str, header: str, selector: str) -> str:
    expected_header = " ".join(header.split())
    matches = []
    for actual_header, body in css_rule_blocks(css):
        if " ".join(actual_header.split()) != expected_header:
            continue
        if any(
            selector in selector_group(nested_header)
            for nested_header, _ in css_rule_blocks(body)
            if not nested_header.startswith("@")
        ):
            matches.append(body)
    assert len(matches) == 1, (
        f"expected one {header!r} block containing {selector!r}, found {len(matches)}"
    )
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
    assert_task_selectors_are_dark_scoped(
        css,
        TASK3_DARK_ONLY_CLASSES,
        TASK3_ALLOWED_LIGHT_SELECTOR_GROUPS,
        "Task 3",
        "an exact Old Book light-theme rule",
    )


def assert_task_selectors_are_dark_scoped(
    css: str,
    class_names: tuple[str, ...],
    allowed_theme_neutral_groups: frozenset[tuple[str, ...]],
    task_label: str,
    neutral_rule_description: str,
) -> None:
    seen_allowed_groups: dict[tuple[str, ...], int] = {}
    for selectors in qualified_css_selector_groups(css):
        relevant_selectors = tuple(
            selector
            for selector in selectors
            if any(name in css_unescape(selector) for name in class_names)
        )
        if not relevant_selectors:
            continue

        normalized_group = tuple(" ".join(selector.split()) for selector in selectors)
        approved_groups = tuple(
            approved_group
            for approved_group in allowed_theme_neutral_groups
            if len(approved_group) == len(normalized_group)
            and frozenset(approved_group) == frozenset(normalized_group)
        )
        assert len(approved_groups) <= 1, (
            f"ambiguous approved {task_label} selector group: {normalized_group!r}"
        )
        if approved_groups:
            approved_group = approved_groups[0]
            seen_allowed_groups[approved_group] = (
                seen_allowed_groups.get(approved_group, 0) + 1
            )
            assert seen_allowed_groups[approved_group] == 1, (
                f"duplicate approved {task_label} selector group outside dark scope: "
                f"{normalized_group!r}"
            )
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


def assert_navigation_markup_contract(layout: str) -> None:
    soup = BeautifulSoup(layout, "html.parser")

    menu_button = soup.select_one("button#brandMenuButton")
    assert menu_button is not None
    assert menu_button.get("type") == "button"
    assert menu_button.get("aria-label") == "Open navigation menu"
    assert menu_button.get("aria-controls") == "navSidebarOverlay"
    assert menu_button.get("aria-expanded") == "false"
    assert set(menu_button.get("class", ())) == {
        "archive-menu-button",
        "icon-button",
    }
    assert menu_button.get_text(strip=True) == ""

    icon_children = menu_button.find_all("span", recursive=False)
    assert len(icon_children) == 1
    icon = icon_children[0]
    assert set(icon.get("class", ())) == {"archive-menu-icon"}
    assert icon.get("aria-hidden") == "true"

    layers = icon.find_all("span", recursive=False)
    assert len(layers) == 2
    book, bars = layers
    assert set(book.get("class", ())) == {"archive-menu-book"}
    assert book.find() is None
    assert set(bars.get("class", ())) == {"archive-menu-bars"}
    bar_children = bars.find_all("span", recursive=False)
    assert len(bar_children) == 3
    assert all(not bar.attrs and bar.get_text(strip=True) == "" for bar in bar_children)

    wordmark = soup.select_one("a.navbar-brand.archive-wordmark")
    assert wordmark is not None
    assert wordmark.get("href") == "/"
    assert wordmark.get("aria-label") == "StudyLib home"
    assert wordmark.get_text(strip=True) == "StudyLib"
    assert set(wordmark.get("class", ())) == {
        "navbar-brand",
        "archive-wordmark",
        "mb-0",
    }
    assert menu_button.find_next_sibling() is wordmark
    assert soup.select_one("button.archive-wordmark") is None
    assert soup.select_one("#navMenuButton") is None


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

    menu_button = css_rule_group_declarations(css, (".archive-menu-button",))
    assert {
        menu_button["inline-size"],
        menu_button["block-size"],
        menu_button["min-inline-size"],
        menu_button["min-block-size"],
    } == {"2.5rem"}
    assert menu_button["flex"] == "0 0 2.5rem"
    # Theme-specific 2rem physical minima arrive later; fixed basis prevents flex shrink.
    for selector in (
        f"{LIGHT_GUARD} .icon-button",
        '[data-bs-theme="dark"] .icon-button',
    ):
        themed_icon = css_rule_group_declarations(css, (selector,))
        assert themed_icon["min-width"] == themed_icon["min-height"] == "2rem"
        assert themed_icon["padding"] == "0.25rem"

    state_selectors = {
        selector
        for selectors, declarations in css_rules(css)
        if {"opacity", "transform"} & declarations.keys()
        for selector in selectors
        if ".archive-menu-button" in selector
        and any(
            layer in selector for layer in (".archive-menu-book", ".archive-menu-bars")
        )
    }
    assert state_selectors == {
        '.archive-menu-button[aria-expanded="true"] .archive-menu-book',
        '.archive-menu-button[aria-expanded="true"] .archive-menu-bars',
    }

    for selectors in (LIGHT_REDUCED_MOTION_SELECTORS, REDUCED_MOTION_SELECTORS):
        reduced_motion = css_block_body_containing_selector(
            css,
            "@media (prefers-reduced-motion: reduce)",
            selectors[0],
        )
        assert (
            css_rule_group_declarations(reduced_motion, selectors)
            == EXPECTED_REDUCED_MOTION_DECLARATIONS
        )


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

    reduced_motion = css_block_body_containing_selector(
        css,
        "@media (prefers-reduced-motion: reduce)",
        REDUCED_MOTION_SELECTORS[0],
    )
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


def mutate_css_rule(
    css: str,
    selector: str,
    old: str,
    new: str,
    *,
    occurrence: int = 0,
) -> str:
    rule_starts = [
        match.end()
        for match in re.finditer(rf"{re.escape(selector)}\s*\{{", css)
    ]
    assert len(rule_starts) > occurrence, f"missing {selector!r} occurrence {occurrence}"
    body_start = rule_starts[occurrence]
    body_end = css.index("}", body_start)
    body = css[body_start:body_end]
    assert old in body, f"missing {old!r} in {selector!r} occurrence {occurrence}"
    return css[:body_start] + body.replace(old, new, 1) + css[body_end:]


def assert_dark_material_visibility_contract(css: str) -> None:
    materials = (
        (
            '[data-bs-theme="dark"] .surface-leather',
            'url("/static/img/textures/leather-texture.png")',
        ),
        (
            '[data-bs-theme="dark"] .btn-secondary-wood',
            'url("/static/img/textures/wood-texture.png")',
        ),
    )
    for selector, texture_url in materials:
        declarations = css_rule_declarations(css, selector)
        background_image = declarations["background-image"]
        alphas = tuple(
            float(value)
            for value in re.findall(
                r"hsl\([^()]*/\s*([0-9]+(?:\.[0-9]+)?)\)",
                background_image,
            )
        )
        assert len(alphas) == 2, f"{selector} must use two alpha-bearing HSL tints"
        assert alphas[0] == alphas[1], f"{selector} tint endpoints must match"
        assert all(0 < alpha < 1 for alpha in alphas), (
            f"{selector} tint alpha must remain translucent"
        )
        assert declarations["background-blend-mode"] == "normal"
        assert background_image.count(texture_url) == 1

    dark_css = css[css.index("/* Candlelit Archive: dark theme foundation */") :]
    assert "linear-gradient(var(--surface-800), var(--surface-800))" not in dark_css
    assert "linear-gradient(var(--surface-700), var(--surface-700))" not in dark_css

    illustration = css_rule_group_declarations(
        css,
        ('[data-bs-theme="dark"] .archive-illustration',),
    )
    assert illustration["opacity"] == "0.14"
    assert illustration["pointer-events"] == "none"
    assert illustration["position"] == "absolute"
    assert illustration["z-index"] == "var(--z-bg-illustration)"

    coarse = css_block_body(css, "@media (hover: none), (pointer: coarse)")
    assert css_rule_declarations(
        coarse,
        '[data-bs-theme="dark"] .archive-illustration',
    ) == {"opacity": "0.10"}


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


def test_dark_material_tints_and_illustrations_are_clearly_visible():
    assert_dark_material_visibility_contract(read_text("static/css/custom.css"))


@pytest.mark.parametrize(
    ("selector", "old", "new"),
    (
        (
            '[data-bs-theme="dark"] .surface-leather',
            "hsl(30 43% 12% / 0.52)",
            "hsl(30 43% 12% / 1)",
        ),
        (
            '[data-bs-theme="dark"] .btn-secondary-wood',
            "background-blend-mode: normal",
            "background-blend-mode: multiply",
        ),
        (
            '[data-bs-theme="dark"] .surface-leather',
            'url("/static/img/textures/leather-texture.png")',
            "none",
        ),
        (
            '[data-bs-theme="dark"] .btn-secondary-wood',
            'url("/static/img/textures/wood-texture.png")',
            "none",
        ),
    ),
    ids=("opaque-alpha", "multiply-blend", "leather-url", "wood-url"),
)
def test_dark_material_contract_rejects_alpha_blend_or_texture_mutation(
    selector,
    old,
    new,
):
    css = mutate_css_rule(read_text("static/css/custom.css"), selector, old, new)
    with pytest.raises(AssertionError):
        assert_dark_material_visibility_contract(css)


@pytest.mark.parametrize(
    ("old", "new", "occurrence"),
    (
        ("opacity: 0.14", "opacity: 0.09", 0),
        ("pointer-events: none", "pointer-events: auto", 0),
        ("z-index: var(--z-bg-illustration)", "z-index: var(--z-content)", 0),
        ("opacity: 0.10", "opacity: 0.06", 1),
    ),
    ids=("desktop-opacity", "pointer-guard", "z-index-guard", "coarse-opacity"),
)
def test_dark_illustration_contract_rejects_opacity_or_guard_mutation(
    old,
    new,
    occurrence,
):
    css = mutate_css_rule(
        read_text("static/css/custom.css"),
        '[data-bs-theme="dark"] .archive-illustration',
        old,
        new,
        occurrence=occurrence,
    )
    with pytest.raises(AssertionError):
        assert_dark_material_visibility_contract(css)


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
    media = css_block_body_containing_selector(
        css,
        "@media (prefers-reduced-motion: reduce)",
        REDUCED_MOTION_SELECTORS[0],
    )
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
    css = mutate_css_rule(
        read_text("static/css/custom.css"),
        '[data-bs-theme="dark"] .surface-leather',
        "background-blend-mode: normal",
        "background-blend-mode: screen",
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


def test_shared_contract_boundary_accepts_reordered_approved_light_selector_group():
    css = read_text("static/css/custom.css")
    selectors = (
        f"{LIGHT_GUARD} .btn-brass",
        f"{LIGHT_GUARD} .btn-primary:not(.btn-secondary-wood)",
    )
    original_group = ",\n".join(selectors)
    reordered_group = ",\n".join(reversed(selectors))
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


def test_navigation_splits_menu_trigger_from_home_wordmark():
    layout = read_text("templates/layout.html")
    main = read_text("static/js/main.js")
    theme = read_text("static/js/theme.js")
    auth = read_text("static/js/auth.js")

    assert_navigation_markup_contract(layout)

    assert "getElementById('brandMenuButton')" in main
    assert "event.key === 'Escape'" in main
    assert 'setAttribute("aria-expanded", "true")' in main
    assert 'setAttribute("aria-expanded", "false")' in main
    assert 'setAttribute("aria-hidden", "false")' in main
    assert 'setAttribute("aria-hidden", "true")' in main
    assert "brandMenuButton.focus()" in main
    assert main.count("const closeSidebar =") == 1
    assert "querySelectorAll('a[href]')" in main

    for script in (theme, auth):
        assert "? '<i class=\"bi bi-sun\" aria-hidden=\"true\"></i>'" in script
        assert ": '<i class=\"bi bi-moon-stars-fill\" aria-hidden=\"true\"></i>'" in script
        assert 'setAttribute("aria-label"' in script


def test_navigation_markup_has_accessible_dialog_relationships():
    layout = read_text("templates/layout.html")
    assert_navigation_markup_contract(layout)
    soup = BeautifulSoup(layout, "html.parser")

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


def test_navigation_markup_contract_rejects_wrong_bar_count():
    layout = read_text("templates/layout.html")
    assert_navigation_markup_contract(layout)
    bars = "<span></span><span></span><span></span>"
    assert layout.count(bars) == 1

    with pytest.raises(AssertionError):
        assert_navigation_markup_contract(layout.replace(bars, "<span></span><span></span>", 1))


def test_navigation_runtime_keeps_visibility_aria_body_and_focus_in_sync():
    assert_navigation_runtime_contract(read_text("static/js/main.js"))


def test_navigation_runtime_contract_rejects_missing_link_close_listener():
    main = read_text("static/js/main.js")
    assert_navigation_runtime_contract(main)
    listener = "navigationLink.addEventListener('click', closeSidebar);"
    assert main.count(listener) == 1

    with pytest.raises(AssertionError):
        assert_navigation_runtime_contract(main.replace(listener, "", 1))


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


@pytest.mark.parametrize(
    ("original", "mutation"),
    (
        (
            'url("/static/img/illustrations/open-book.svg")',
            'url("/static/img/illustrations/closed-book.svg")',
        ),
        (
            '.archive-menu-button[aria-expanded="true"] .archive-menu-book',
            '.archive-menu-button[data-open="true"] .archive-menu-book',
        ),
        (
            f"    {LIGHT_REDUCED_MOTION_SELECTORS[0]},\n",
            f"    {LIGHT_GUARD} body,\n",
        ),
        (
            "    inline-size: 2.5rem;\n",
            "    inline-size: 2.75rem;\n",
        ),
    ),
    ids=(
        "mask-url",
        "expanded-selector",
        "reduced-motion-descendants",
        "unequal-button-axis",
    ),
)
def test_navigation_morph_contract_rejects_asset_state_and_motion_mutations(
    original: str,
    mutation: str,
):
    css = read_text("static/css/custom.css")
    assert_navigation_css_contract(css)
    assert original in css

    with pytest.raises(AssertionError):
        assert_navigation_css_contract(css.replace(original, mutation, 1))


def test_navigation_button_contract_rejects_shrinkable_flex_basis():
    css = read_text("static/css/custom.css")
    assert_navigation_css_contract(css)
    basis = "    flex: 0 0 2.5rem;\n"
    assert css.count(basis) == 1

    with pytest.raises(AssertionError):
        assert_navigation_css_contract(
            css.replace(basis, "    flex: 1 1 auto;\n", 1)
        )


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
    assert search.get("placeholder") == "Search academic sources..."
    button = search_group.select_one("button#homeSearchBtn")
    assert button is not None
    assert button.get("type") == "button"
    assert button.get_text(strip=True) == "Search"

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


def test_dashboard_runtime_preserves_academic_search_create_and_open_flow():
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
    this.listenerOptions = new Map();
    this.attributes = new Map();
    this.dataset = {};
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.children = [];
    this.style = {};
    this.src = "";
    this.alt = "";
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  addEventListener(type, callback, options) {
    const callbacks = this.listeners.get(type) || [];
    callbacks.push(callback);
    this.listeners.set(type, callbacks);
    this.listenerOptions.set(type, options || {});
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
  appendChild(child) {
    this.children.push(child);
    return child;
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
invariant(hostileNodes.get(".card-img-top").src === "/static/img/illustrations/compass-rose.svg", "unsafe thumbnail did not use compass fallback");
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

const fallbackItems = [
  {
    title: "Book",
    source_name: "Google Books",
    source_url: "https://books.google.com/books?id=book-1",
    expected: "/static/img/illustrations/open-book.svg",
  },
  {
    title: "Encyclopedia",
    source_name: "Reference",
    source_url: "https://en.wikipedia.org/wiki/Archive",
    expected: "/static/img/illustrations/scrollwork-flourish.svg",
  },
  {
    title: "Paper",
    source_name: "Google Scholar",
    source_url: "https://scholar.google.com/scholar?q=archive",
    expected: "/static/img/illustrations/stacked-books.svg",
  },
  {
    title: "Medical paper",
    source_name: "PubMed",
    source_url: "https://pubmed.ncbi.nlm.nih.gov/1/",
    expected: "/static/img/illustrations/stacked-books.svg",
  },
];
const fallbackContracts = fallbackItems.map((item, index) => {
  const card = createCard({ id: 30 + index, thumb_url: "http://images.test/unsafe.jpg", ...item });
  const cardImage = card.nodes.get(".card-img-top");
  return {
    sourceName: item.source_name,
    src: cardImage.src,
    fallback: cardImage.getAttribute("data-fallback-src"),
    kind: cardImage.getAttribute("data-image-kind"),
  };
});
const remoteCard = createCard({
  id: 40,
  title: "Remote cover",
  source_name: "Google Books",
  source_url: "https://books.google.com/books?id=remote",
  thumb_url: "https://books.google.com/books/content?id=remote",
});
const remoteImage = remoteCard.nodes.get(".card-img-top");
const remoteBeforeError = remoteImage.src;
await remoteImage.dispatch("error");
const remoteAfterError = remoteImage.src;

process.stdout.write(JSON.stringify({
  template: hostileCard.innerHTML,
  className: hostileCard.className,
  hostile: {
    title: hostileNodes.get(".card-title").textContent,
    description: hostileNodes.get(".card-description").textContent,
    source: hostileNodes.get(".result-source-text").textContent,
    image: hostileNodes.get(".card-img-top").src,
    imageAttrs: {
      loading: hostileNodes.get(".card-img-top").getAttribute("loading"),
      decoding: hostileNodes.get(".card-img-top").getAttribute("decoding"),
      referrerpolicy: hostileNodes.get(".card-img-top").getAttribute("referrerpolicy"),
      alt: hostileNodes.get(".card-img-top").alt,
      fallback: hostileNodes.get(".card-img-top").getAttribute("data-fallback-src"),
      kind: hostileNodes.get(".card-img-top").getAttribute("data-image-kind"),
    },
    itemId: hostileNodes.get(".save-btn").dataset.itemId,
    label: hostileNodes.get(".save-btn").getAttribute("aria-label"),
    pressed: hostileNodes.get(".save-btn").getAttribute("aria-pressed"),
    lightIcon: hostileNodes.get(".save-icon-light").className,
    darkIcon: hostileNodes.get(".save-icon-dark").className,
  },
  savedBefore,
  saveToasts,
  endpoints: actionCalls.map((call) => call.url),
  fallbackContracts,
  remote: {
    beforeError: remoteBeforeError,
    afterError: remoteAfterError,
    fallback: remoteImage.getAttribute("data-fallback-src"),
    kind: remoteImage.getAttribute("data-image-kind"),
    errorOnce: remoteImage.listenerOptions.get("error")?.once === true,
  },
}));
"""


BROWSE_DOM_RUNTIME = r"""
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
const master = control("#filterAllSources");
const sorting = control("#filterSorting");
control("#filterYearFrom");
control("#filterYearTo");
control("#filterContentType");
control("#sidebarContainer");
const resultsContainer = control("#resultsContainer");
control("#whitelistCheckboxes");
const wikipedia = new FakeElement("wikipedia");
wikipedia.value = "wikipedia";
wikipedia.checked = true;
const whitelistWikipedia = new FakeElement("whitelist wikipedia");
whitelistWikipedia.value = "whitelist_en.wikipedia.org";
whitelistWikipedia.checked = false;
const whitelistBooks = new FakeElement("whitelist books");
whitelistBooks.value = "whitelist_books.google.com";
whitelistBooks.checked = false;
const sourceCheckboxes = [wikipedia, whitelistWikipedia, whitelistBooks];
function matchingCheckboxes(selector) {
  return selector.includes(":checked")
    ? sourceCheckboxes.filter((checkbox) => checkbox.checked)
    : sourceCheckboxes;
}
menu.querySelectorAll = matchingCheckboxes;

Object.defineProperty(resultsContainer, "innerHTML", {
  configurable: true,
  get() { return this._innerHTML || ""; },
  set(value) {
    this._innerHTML = String(value);
    this.children = [];
    globalThis.renderedItems.length = 0;
    controls.delete("#loadMoreBtn");
    controls.delete("#loadMoreText");
    controls.delete("#loadMoreSpinner");
  },
});

const root = new FakeElement("root");
root.querySelector = (selector) => controls.get(selector) || null;
root.querySelectorAll = matchingCheckboxes;
const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  getElementById() { return null; },
  body: { appendChild() {} },
  createElement(tag) {
    const element = new FakeElement("created " + tag);
    Object.defineProperty(element, "innerHTML", {
      configurable: true,
      get() { return this._innerHTML || ""; },
      set(value) {
        const markup = String(value);
        this._innerHTML = markup;
        if (!markup.includes('id="loadMoreBtn"')) return;

        const button = new FakeElement("#loadMoreBtn");
        const text = new FakeElement("#loadMoreText");
        const spinner = new FakeElement("#loadMoreSpinner");
        button.disabled = /<button[^>]*\sdisabled(?:\s|>)/.test(markup);
        const textMatch = markup.match(/id="loadMoreText">([^<]*)</);
        text.textContent = textMatch ? textMatch[1] : "";
        spinner.style.display = "none";
        controls.set("#loadMoreBtn", button);
        controls.set("#loadMoreText", text);
        controls.set("#loadMoreSpinner", spinner);
      },
    });
    return element;
  },
};
globalThis.window = {
  location: { pathname: "/browse", search: "" },
  history: { replaceState() {} },
};
const nativeSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = (callback, delay, ...args) => {
  const timer = nativeSetTimeout(callback, delay, ...args);
  if (delay === 30000 && typeof timer?.unref === "function") timer.unref();
  return timer;
};
const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));
"""


BROWSE_FILTER_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const controls = new Map();
function control(selector, value = "") {
  const element = new FakeElement(selector);
  element.value = value;
  controls.set(selector, element);
  return element;
}

const search = control("#searchInput");
const go = control("#goBtn");
const filters = control("#filtersDropdown");
const menu = control(".browse-dropdown-menu");
controls.set("#browseFiltersMenu", menu);
const master = control("#filterAllSources");
control("#filterYearFrom");
control("#filterYearTo");
control("#filterContentType");
control("#filterSorting");
control("#sidebarContainer");
control("#resultsContainer");
control("#whitelistCheckboxes");

function source(name, value, checked) {
  const element = new FakeElement(name, "form-check-input browse-source-checkbox");
  element.value = value;
  element.checked = checked;
  return element;
}

const sources = [
  source("Wikipedia", "wikipedia", true),
  source("Google Books", "gbooks", true),
  source("PubMed", "pubmed", false),
  source("Google Scholar", "scholar", true),
  source("JSTOR", "whitelist_jstor.org", false),
  source("Education sites", "whitelist_*.edu", false),
];

function matchingSources(selector) {
  if (!selector.includes("browse-source-checkbox")) return [];
  return selector.includes(":checked")
    ? sources.filter((checkbox) => checkbox.checked)
    : sources;
}

menu.querySelectorAll = matchingSources;
const root = new FakeElement("root");
root.querySelector = (selector) => controls.get(selector) || null;
root.querySelectorAll = matchingSources;

const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  createElement() { return new FakeElement("created"); },
};
globalThis.window = {
  location: { pathname: "/browse", search: "" },
  history: { replaceState() {} },
};
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.fetch = async (url) => {
  if (url === "/static/whitelist.json") {
    return {
      ok: true,
      async json() { return { domains: ["jstor.org"], domain_patterns: ["*.edu"] }; },
    };
  }
  throw new Error("unexpected fetch: " + url);
};

const { initBrowse, getBrowseState, applySelectedSources } = await import(process.argv[1]);
initBrowse(root);
await new Promise((resolve) => setTimeout(resolve, 0));

const initial = { checked: master.checked, indeterminate: master.indeterminate };

master.checked = true;
await master.dispatch("change");
const selectedAll = sources.map((checkbox) => checkbox.checked);
const selectedAllMaster = { checked: master.checked, indeterminate: master.indeterminate };
const savedAll = getBrowseState().sources;

applySelectedSources(["gbooks", "whitelist_jstor.org"]);
const restored = sources.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
const restoredMaster = { checked: master.checked, indeterminate: master.indeterminate };

sources[1].checked = false;
await menu.dispatch("change", { target: sources[1] });
const oneSelectedMaster = { checked: master.checked, indeterminate: master.indeterminate };

master.checked = false;
await master.dispatch("change");
const cleared = sources.map((checkbox) => checkbox.checked);
const clearedMaster = { checked: master.checked, indeterminate: master.indeterminate };

process.stdout.write(JSON.stringify({
  initial,
  selectedAll,
  selectedAllMaster,
  savedAll,
  restored,
  restoredMaster,
  oneSelectedMaster,
  cleared,
  clearedMaster,
}));
"""


BROWSE_FILTER_RACE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const controls = new Map();
function control(selector, value = "") {
  const element = new FakeElement(selector);
  element.value = value;
  controls.set(selector, element);
  return element;
}

const search = control("#searchInput");
const go = control("#goBtn");
const filters = control("#filtersDropdown");
const menu = control(".browse-dropdown-menu");
controls.set("#browseFiltersMenu", menu);
const master = control("#filterAllSources");
control("#filterYearFrom");
control("#filterYearTo");
control("#filterContentType");
control("#filterSorting");
control("#sidebarContainer");
control("#resultsContainer");
const whitelistContainer = control("#whitelistCheckboxes");

function source(name, value, checked, className = "form-check-input browse-source-checkbox") {
  const element = new FakeElement(name, className);
  element.value = value;
  element.checked = checked;
  return element;
}

const sources = [
  source("Wikipedia", "wikipedia", true),
  source("Google Books", "gbooks", true),
  source("PubMed", "pubmed", false),
  source("Google Scholar", "scholar", true),
];
let whitelistMarkup = "";

Object.defineProperty(whitelistContainer, "innerHTML", {
  configurable: true,
  get() { return this._innerHTML || ""; },
  set(value) {
    whitelistMarkup = String(value);
    this._innerHTML = whitelistMarkup;
    const inputPattern = /<input\s+class="([^"]*)"[^>]*\svalue="([^"]+)"[^>]*>/gu;
    for (const match of whitelistMarkup.matchAll(inputPattern)) {
      sources.push(source(match[2], match[2], false, match[1]));
    }
  },
});

function realSources() {
  return sources.filter((checkbox) => checkbox.classList.contains("browse-source-checkbox"));
}
function matchingSources(selector) {
  if (!selector.includes("browse-source-checkbox")) return [];
  const matches = realSources();
  return selector.includes(":checked")
    ? matches.filter((checkbox) => checkbox.checked)
    : matches;
}

menu.querySelectorAll = matchingSources;
const root = new FakeElement("root");
root.querySelector = (selector) => controls.get(selector) || null;
root.querySelectorAll = matchingSources;

const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  createElement() { return new FakeElement("created"); },
};
globalThis.window = {
  location: { pathname: "/browse", search: "" },
  history: { replaceState() {} },
};
globalThis.renderedItems = [];
globalThis.toastCalls = [];

const restoredState = {
  version: 2,
  query: "archive",
  sources: ["gbooks", "whitelist_jstor.org"],
  filters: { min_date: "", max_date: "", content_type: "", sorting: "" },
  results: [],
  groupedResults: {},
  sourceCounts: {},
  groupPage: 1,
};
const storageWrites = [];
globalThis.localStorage = {
  getItem() { return JSON.stringify(restoredState); },
  setItem(key, value) { storageWrites.push({ key, value: JSON.parse(value) }); },
};

function deferredResponse() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

const whitelistResponse = deferredResponse();
const apiBodies = [];
globalThis.fetch = async (url, options = {}) => {
  if (url === "/static/whitelist.json") return whitelistResponse.promise;
  if (url === "/api/browse/search-all") {
    apiBodies.push(JSON.parse(options.body));
    return {
      ok: true,
      async json() {
        return {
          status: true,
          results: [],
          grouped_results: {},
          source_counts: {},
        };
      },
    };
  }
  throw new Error("unexpected fetch: " + url);
};

const { initBrowse, getBrowseState } = await import(process.argv[1]);
initBrowse(root);
await new Promise((resolve) => setTimeout(resolve, 0));

const dynamicBeforeResolution = sources.filter(
  (checkbox) => checkbox.value.startsWith("whitelist_")
).length;
__PENDING_SOURCE_ACTION__
const beforeResolution = {
  selected: realSources().filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value),
  master: { checked: master.checked, indeterminate: master.indeterminate },
};

whitelistResponse.resolve({
  ok: true,
  async json() { return { domains: ["jstor.org"], domain_patterns: ["*.edu"] }; },
});
await new Promise((resolve) => setTimeout(resolve, 0));

const dynamicSources = sources.filter((checkbox) => checkbox.value.startsWith("whitelist_"));
const afterSources = realSources()
  .filter((checkbox) => checkbox.checked)
  .map((checkbox) => checkbox.value);
const persistedSources = getBrowseState().sources;
const afterMaster = { checked: master.checked, indeterminate: master.indeterminate };

await go.dispatch("click");
await new Promise((resolve) => setTimeout(resolve, 0));

process.stdout.write(JSON.stringify({
  dynamicBeforeResolution,
  dynamicAfterResolution: dynamicSources.length,
  dynamicClasses: dynamicSources.map((checkbox) => checkbox.className),
  whitelistMarkup,
  beforeResolution,
  afterSources,
  persistedSources,
  apiSources: apiBodies.length > 0 ? apiBodies.at(-1).sources : null,
  afterMaster,
  toastCalls: globalThis.toastCalls,
  storageWrites,
}));
"""


BROWSE_SOURCE_READINESS_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const controls = new Map();
function control(selector, value = "") {
  const element = new FakeElement(selector);
  element.value = value;
  controls.set(selector, element);
  return element;
}

const search = control("#searchInput");
const go = control("#goBtn");
const filters = control("#filtersDropdown");
const menu = control(".browse-dropdown-menu");
controls.set("#browseFiltersMenu", menu);
const master = control("#filterAllSources");
control("#filterYearFrom");
control("#filterYearTo");
control("#filterContentType");
control("#filterSorting");
control("#sidebarContainer");
control("#resultsContainer");
const whitelistContainer = control("#whitelistCheckboxes");

function source(name, value, checked, className = "form-check-input browse-source-checkbox") {
  const element = new FakeElement(name, className);
  element.value = value;
  element.checked = checked;
  return element;
}

const sources = [
  source("Wikipedia", "wikipedia", true),
  source("Google Books", "gbooks", true),
  source("PubMed", "pubmed", false),
  source("Google Scholar", "scholar", true),
];
let whitelistMarkup = "";
const throwOnWhitelistRender = __THROW_ON_WHITELIST_RENDER__;
Object.defineProperty(whitelistContainer, "innerHTML", {
  configurable: true,
  get() { return this._innerHTML || ""; },
  set(value) {
    if (throwOnWhitelistRender) throw new Error("whitelist render failed");
    whitelistMarkup = String(value);
    this._innerHTML = whitelistMarkup;
    sources.splice(4);
    const inputPattern = /<input\s+class="([^"]*)"[^>]*\svalue="([^"]+)"[^>]*>/gu;
    for (const match of whitelistMarkup.matchAll(inputPattern)) {
      sources.push(source(match[2], match[2], false, match[1]));
    }
  },
});

function realSources() {
  return sources.filter((checkbox) => checkbox.classList.contains("browse-source-checkbox"));
}
function matchingSources(selector) {
  if (!selector.includes("browse-source-checkbox")) return [];
  const matches = realSources();
  return selector.includes(":checked")
    ? matches.filter((checkbox) => checkbox.checked)
    : matches;
}
menu.querySelectorAll = matchingSources;

const root = new FakeElement("root");
root.querySelector = (selector) => controls.get(selector) || null;
root.querySelectorAll = matchingSources;
const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  createElement() { return new FakeElement("created"); },
};
const historyUrls = [];
globalThis.window = {
  location: { pathname: "/browse", search: "" },
  history: { replaceState(state, title, url) { historyUrls.push(url); } },
};
globalThis.renderedItems = [];
globalThis.toastCalls = [];

const restoredState = __RESTORED_STATE__;
globalThis.localStorage = {
  getItem() { return restoredState ? JSON.stringify(restoredState) : null; },
  setItem() {},
};

const nativeSetTimeout = globalThis.setTimeout;
const nativeClearTimeout = globalThis.clearTimeout;
const readinessTimers = [];
const clearedReadinessTimers = [];
globalThis.setTimeout = (callback, delay, ...args) => {
  if (delay === 5000) {
    const timer = { callback, delay, id: readinessTimers.length + 1 };
    readinessTimers.push(timer);
    return timer;
  }
  return nativeSetTimeout(callback, delay, ...args);
};
globalThis.clearTimeout = (timer) => {
  if (readinessTimers.includes(timer)) {
    clearedReadinessTimers.push(timer.id);
    return;
  }
  nativeClearTimeout(timer);
};
const unhandledRejections = [];
process.on("unhandledRejection", (error) => {
  unhandledRejections.push(error.message);
});

function deferredResponse() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const whitelistResponse = deferredResponse();
const apiBodies = [];
let whitelistSignal = null;
globalThis.fetch = async (url, options = {}) => {
  if (url === "/static/whitelist.json") {
    whitelistSignal = options.signal || null;
    whitelistSignal?.addEventListener("abort", () => {
      const error = new Error("whitelist timeout");
      error.name = "AbortError";
      whitelistResponse.reject(error);
    }, { once: true });
    return whitelistResponse.promise;
  }
  if (url === "/api/browse/search-all") {
    apiBodies.push(JSON.parse(options.body));
    return {
      ok: true,
      async json() {
        return {
          status: true,
          results: [],
          grouped_results: {},
          source_counts: {},
        };
      },
    };
  }
  throw new Error("unexpected fetch: " + url);
};

const { initBrowse, getBrowseState } = await import(process.argv[1]);
initBrowse(root);
await new Promise((resolve) => setTimeout(resolve, 0));

const dynamicBeforeResolution = sources.filter(
  (checkbox) => checkbox.value.startsWith("whitelist_")
).length;
__PRE_READINESS_ACTIONS__
await new Promise((resolve) => setTimeout(resolve, 0));
const apiCountBeforeResolution = apiBodies.length;

__WHITELIST_SETTLEMENT__
for (let index = 0; index < 3; index += 1) {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

const dynamicSources = sources.filter((checkbox) => checkbox.value.startsWith("whitelist_"));
process.stdout.write(JSON.stringify({
  dynamicBeforeResolution,
  dynamicAfterResolution: dynamicSources.length,
  whitelistMarkup,
  apiCountBeforeResolution,
  apiBodies,
  historyUrls,
  selectedSources: getBrowseState().sources,
  masterValue: master.value,
  master: { checked: master.checked, indeterminate: master.indeterminate },
  toastCalls: globalThis.toastCalls,
  readinessTimerDelays: readinessTimers.map((timer) => timer.delay),
  clearedReadinessTimers,
  whitelistAborted: whitelistSignal?.aborted || false,
  unhandledRejections,
}));
"""


BROWSE_REINIT_READINESS_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
function source(name, value, checked, className = "form-check-input browse-source-checkbox") {
  const element = new FakeElement(name, className);
  element.value = value;
  element.checked = checked;
  return element;
}

function makePage(name) {
  const controls = new Map();
  function control(selector, value = "") {
    const element = new FakeElement(name + " " + selector);
    element.value = value;
    controls.set(selector, element);
    return element;
  }

  control("#searchInput");
  control("#goBtn");
  control("#filtersDropdown");
  const menu = control(".browse-dropdown-menu");
  controls.set("#browseFiltersMenu", menu);
  control("#filterAllSources");
  control("#filterYearFrom");
  control("#filterYearTo");
  control("#filterContentType");
  control("#filterSorting");
  control("#sidebarContainer");
  control("#resultsContainer");
  const whitelistContainer = control("#whitelistCheckboxes");
  const sources = [
    source(name + " Wikipedia", "wikipedia", true),
    source(name + " Google Books", "gbooks", true),
    source(name + " PubMed", "pubmed", false),
    source(name + " Google Scholar", "scholar", true),
  ];
  let whitelistMarkup = "";
  Object.defineProperty(whitelistContainer, "innerHTML", {
    configurable: true,
    get() { return this._innerHTML || ""; },
    set(value) {
      whitelistMarkup = String(value);
      this._innerHTML = whitelistMarkup;
      sources.splice(4);
      const inputPattern = /<input\s+class="([^"]*)"[^>]*\svalue="([^"]+)"[^>]*>/gu;
      for (const match of whitelistMarkup.matchAll(inputPattern)) {
        sources.push(source(match[2], match[2], false, match[1]));
      }
    },
  });
  function matchingSources(selector) {
    if (!selector.includes("browse-source-checkbox")) return [];
    const matches = sources.filter(
      (checkbox) => checkbox.classList.contains("browse-source-checkbox")
    );
    return selector.includes(":checked")
      ? matches.filter((checkbox) => checkbox.checked)
      : matches;
  }
  menu.querySelectorAll = matchingSources;
  const root = new FakeElement(name + " root");
  root.querySelector = (selector) => controls.get(selector) || null;
  root.querySelectorAll = matchingSources;
  return {
    controls,
    root,
    sources,
    get whitelistMarkup() { return whitelistMarkup; },
  };
}

const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  createElement() { return new FakeElement("created"); },
};
globalThis.window = {
  location: { pathname: "/browse", search: "" },
  history: { replaceState() {} },
};
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.renderedItems = [];
globalThis.toastCalls = [];

function deferredResponse() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}
const oldWhitelist = deferredResponse();
const newWhitelist = deferredResponse();
const replacementWhitelist = deferredResponse();
let whitelistCall = 0;
const apiBodies = [];
globalThis.fetch = async (url, options = {}) => {
  if (url === "/static/whitelist.json") {
    const response = [
      oldWhitelist.promise,
      newWhitelist.promise,
      replacementWhitelist.promise,
    ][whitelistCall];
    whitelistCall += 1;
    return response;
  }
  if (url === "/api/browse/search-all") {
    apiBodies.push(JSON.parse(options.body));
    return {
      ok: true,
      async json() {
        return {
          status: true,
          results: [],
          grouped_results: {},
          source_counts: {},
        };
      },
    };
  }
  throw new Error("unexpected fetch: " + url);
};

const oldPage = makePage("old");
const newPage = makePage("new");
const replacementPage = makePage("replacement");
const {
  initBrowse,
  setBrowseLoadingStateForTest,
  getBrowseLoadingStateForTest,
} = await import(process.argv[1]);

window.location.search = "?q=old";
initBrowse(oldPage.root);
window.location.search = "?q=new";
initBrowse(newPage.root);
await new Promise((resolve) => setTimeout(resolve, 0));

oldWhitelist.resolve({
  ok: true,
  async json() { return { domains: ["old.example"] }; },
});
for (let index = 0; index < 3; index += 1) {
  await new Promise((resolve) => setTimeout(resolve, 0));
}
const afterOldResolution = {
  apiQueries: apiBodies.map((body) => body.query),
  oldMarkup: oldPage.whitelistMarkup,
  newMarkup: newPage.whitelistMarkup,
  newQuery: newPage.controls.get("#searchInput").value,
};

newWhitelist.resolve({
  ok: true,
  async json() { return { domains: ["new.example"] }; },
});
for (let index = 0; index < 3; index += 1) {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

setBrowseLoadingStateForTest(true, true);
replacementPage.controls.get("#filterSorting").disabled = true;
window.location.search = "";
initBrowse(replacementPage.root);
const resetAfterReinit = {
  loadingState: getBrowseLoadingStateForTest(),
  sortingDisabled: replacementPage.controls.get("#filterSorting").disabled,
};
replacementWhitelist.resolve({
  ok: true,
  async json() { return { domains: [] }; },
});
for (let index = 0; index < 3; index += 1) {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

process.stdout.write(JSON.stringify({
  afterOldResolution,
  finalApiQueries: apiBodies.map((body) => body.query),
  finalApiSources: apiBodies.map((body) => body.sources),
  oldMarkup: oldPage.whitelistMarkup,
  newMarkup: newPage.whitelistMarkup,
  newQuery: newPage.controls.get("#searchInput").value,
  resetAfterReinit,
  replacementMarkup: replacementPage.whitelistMarkup,
}));
"""


BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
const fetchCalls = [];
const first = {
  source_name: "Wikipedia",
  source_id: "wiki-1",
  source_url: "https://EXAMPLE.test/first#intro",
  title: "First",
};
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/static/whitelist.json") {
    return {
      ok: true,
      async json() {
        return { domains: ["en.wikipedia.org"], domain_patterns: ["*.edu"] };
      },
    };
  }
  invariant(url === "/api/browse/search-all", "unexpected Browse endpoint");
  return {
    ok: true,
    async json() {
      return {
        status: true,
        results: [first],
        grouped_results: { wikipedia: [first] },
        source_counts: { wikipedia: 1 },
      };
    },
  };
};
globalThis.toastCalls = [];

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();

const searchCalls = fetchCalls.filter((call) => call.url === "/api/browse/search-all");
invariant(searchCalls.length === 1, "Browse issued an extra search request");
invariant(searchCalls[0].options.method === "POST", "search method changed");
const body = JSON.parse(searchCalls[0].options.body);
invariant(body.query === "archive", "search query changed");
invariant(body.sources.length === 1 && body.sources[0] === "wikipedia", "search sources changed");
invariant(body.num_results === 10, "search result count changed");

process.stdout.write(JSON.stringify({
  html: root.innerHTML,
  whitelistMarkup: controls.get("#whitelistCheckboxes").innerHTML,
  body,
  requestSizes: searchCalls.map((call) => JSON.parse(call.options.body).num_results),
  renderedTitles: globalThis.renderedItems.map((item) => item.title),
  loadMoreDisabled: controls.get("#loadMoreBtn").disabled,
  loadMoreText: controls.get("#loadMoreText").textContent,
}));
"""


URL_QUERY_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.toastCalls = [];
search.value = "";
const historyCalls = [];
window.location = { pathname: "/browse", search: "?q=quantum%20mechanics" };
window.history = {
  replaceState(state, title, url) { historyCalls.push({ state, title, url }); },
};
const fetchCalls = [];
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  invariant(url === "/api/browse/search-all", "unexpected URL query endpoint: " + url);
  const body = JSON.parse(options.body);
  return {
    ok: true,
    async json() {
      return {
        status: true,
        results: [{
          source_name: "Wikipedia",
          source_id: body.query,
          source_url: "https://en.wikipedia.org/wiki/" + encodeURIComponent(body.query),
          title: body.query,
        }],
        source_counts: { wikipedia: 1 },
      };
    },
  };
};

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await flushPromises();
await flushPromises();

const initialSearchCalls = fetchCalls.filter((call) => call.url === "/api/browse/search-all");
invariant(initialSearchCalls.length === 1, "URL query did not trigger one native Browse search");
invariant(search.value === "quantum mechanics", "URL query did not populate Browse input");
invariant(JSON.parse(initialSearchCalls[0].options.body).query === "quantum mechanics",
  "URL query changed before native Browse request");
invariant(historyCalls.length === 0, "initial URL query rewrote browser history");

search.value = "archives";
await go.dispatch("click");
await flushPromises();
const searchCalls = fetchCalls.filter((call) => call.url === "/api/browse/search-all");
invariant(searchCalls.length === 2, "manual Browse search did not use native endpoint");
invariant(historyCalls.length === 1, "manual Browse search did not update URL");
invariant(historyCalls[0].url === "/browse?q=archives", "manual Browse URL is wrong");

process.stdout.write(JSON.stringify({
  query: search.value,
  requestQueries: searchCalls.map((call) => JSON.parse(call.options.body).query),
  historyUrls: historyCalls.map((call) => call.url),
}));
"""


BROWSE_ERROR_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.toastCalls = [];
globalThis.fetch = async (url) => {
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  return {
    ok: false,
    async json() {
      return {
        status: false,
        error: "Browse search is not configured. Add SERP_API_KEY and restart StudyLib.",
      };
    },
  };
};

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();

invariant(globalThis.toastCalls.length === 1, "Browse failure did not show one toast");
invariant(
  globalThis.toastCalls[0][0] ===
    "Browse search is not configured. Add SERP_API_KEY and restart StudyLib.",
  "Browse hid the server's safe configuration error",
);
invariant(globalThis.toastCalls[0][1] === "danger", "Browse error toast variant changed");
invariant(sorting.disabled === false, "Browse failure left sorting disabled");

process.stdout.write(JSON.stringify({ toast: globalThis.toastCalls[0] }));
"""


BROWSE_ACTIVE_INVALID_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.toastCalls = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };

function deferredResponse() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

const activeSearch = deferredResponse();
const apiBodies = [];
const activeResult = {
  source_name: "Wikipedia",
  source_id: "active-a",
  source_url: "https://example.test/active-a",
  title: "Active A",
};
globalThis.fetch = async (url, options = {}) => {
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  if (url === "/api/browse/search-all") {
    apiBodies.push(JSON.parse(options.body));
    return activeSearch.promise;
  }
  throw new Error("unexpected fetch: " + url);
};

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await flushPromises();

search.value = "search a";
await go.dispatch("click");
await flushPromises();
const duringActive = {
  sortingDisabled: sorting.disabled,
  loading: resultsContainer.innerHTML.includes("Searching..."),
  apiQueries: apiBodies.map((body) => body.query),
};

master.checked = false;
await master.dispatch("change");
search.value = "search b";
await go.dispatch("click");
await flushPromises();
const afterInvalid = {
  sortingDisabled: sorting.disabled,
  loading: resultsContainer.innerHTML.includes("Searching..."),
  apiQueries: apiBodies.map((body) => body.query),
  toastCalls: globalThis.toastCalls,
};

activeSearch.resolve({
  ok: true,
  async json() {
    return {
      status: true,
      results: [activeResult],
      grouped_results: { wikipedia: [activeResult] },
      source_counts: { wikipedia: 1 },
    };
  },
});
await flushPromises();
await flushPromises();

process.stdout.write(JSON.stringify({
  duringActive,
  afterInvalid,
  finalSortingDisabled: sorting.disabled,
  finalLoading: resultsContainer.innerHTML.includes("Searching..."),
  renderedTitles: globalThis.renderedItems.map((item) => item.title),
  apiQueries: apiBodies.map((body) => body.query),
}));
"""


BROWSE_TIMEOUT_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.toastCalls = [];
const nativeClearTimeout = globalThis.clearTimeout;
const requestTimers = [];
const clearedTimers = [];
globalThis.setTimeout = (callback, delay, ...args) => {
  if (delay === 30000) {
    const timer = { id: 100 + requestTimers.length, callback, delay };
    requestTimers.push(timer);
    return timer.id;
  }
  return nativeSetTimeout(callback, delay, ...args);
};
globalThis.clearTimeout = (timerId) => {
  clearedTimers.push(timerId);
  nativeClearTimeout(timerId);
};
let searchSignal = null;
globalThis.fetch = async (url, options) => {
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  searchSignal = options.signal;
  return new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => {
      const error = new Error("private timeout detail");
      error.name = "AbortError";
      reject(error);
    }, { once: true });
  });
};

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();
invariant(requestTimers.length === 1, "Browse request timeout was not scheduled");
invariant(requestTimers[0].delay === 30000, "Browse timeout duration changed");
invariant(searchSignal && searchSignal.aborted === false, "Browse request lacked an active abort signal");
requestTimers[0].callback();
await flushPromises();
await flushPromises();

invariant(searchSignal.aborted === true, "Browse timeout did not abort request");
invariant(globalThis.toastCalls.length === 1, "Browse timeout did not show one error");
invariant(globalThis.toastCalls[0][0] === "Browse search timed out. Try again.",
  "Browse timeout message changed");
invariant(!globalThis.toastCalls[0][0].includes("private"), "private timeout detail leaked");
invariant(sorting.disabled === false, "Browse timeout left sorting disabled");
invariant(resultsContainer.innerHTML.includes("No results found"),
  "Browse timeout left the loading spinner visible");
invariant(clearedTimers.includes(requestTimers[0].id), "Browse timeout timer was not cleared");

process.stdout.write(JSON.stringify({
  toast: globalThis.toastCalls[0],
  timeoutDelay: requestTimers[0].delay,
  sortingDisabled: sorting.disabled,
}));
"""


BROWSE_PARTIAL_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.toastCalls = [];
globalThis.fetch = async (url) => {
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  return {
    ok: true,
    async json() {
      return {
        status: true,
        results: [{
          source_name: "Wikipedia",
          source_id: "wiki-1",
          source_url: "https://en.wikipedia.org/wiki/Archive",
          title: "Available result",
        }],
        source_counts: { wikipedia: 1, pubmed: 0 },
        source_errors: { pubmed: "SerpAPI search failed" },
      };
    },
  };
};

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();
await flushPromises();

invariant(globalThis.renderedItems.length === 1, "partial Browse result was not rendered");
invariant(globalThis.renderedItems[0].title === "Available result", "partial result changed");
invariant(globalThis.toastCalls.length === 1, "partial Browse failure did not show one warning");
invariant(globalThis.toastCalls[0][1] === "warning", "partial Browse warning variant changed");
invariant(globalThis.toastCalls[0][0].includes("1 selected source"),
  "partial Browse warning count missing");
invariant(!globalThis.toastCalls[0][0].includes("SerpAPI search failed"),
  "per-source provider detail leaked to warning");

process.stdout.write(JSON.stringify({
  title: globalThis.renderedItems[0].title,
  toast: globalThis.toastCalls[0],
}));
"""


GROUPED_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
const gbooks = new FakeElement("gbooks");
gbooks.value = "gbooks";
gbooks.checked = true;
sourceCheckboxes.splice(1, 0, gbooks);
whitelistWikipedia.value = "whitelist_www.jstor.org";
whitelistWikipedia.checked = true;

const makeItems = (prefix, sourceName, baseUrl) => Array.from(
  { length: 10 },
  (_, index) => ({
    source_name: sourceName,
    source_id: `${prefix}-${index + 1}`,
    source_url: `${baseUrl}/${index + 1}`,
    title: `${prefix}-${index + 1}`,
  }),
);
const wikiItems = makeItems("wiki", "Wikipedia", "https://en.wikipedia.org/wiki/archive");
const bookItems = makeItems("book", "Google Books", "https://books.google.com/books");
const jstorItems = makeItems("jstor", "JSTOR", "https://www.jstor.org/stable");
const payload = {
  status: true,
  results: [...wikiItems, ...bookItems, ...jstorItems],
  grouped_results: {
    wikipedia: wikiItems,
    gbooks: bookItems,
    "whitelist_www.jstor.org": jstorItems,
  },
  source_counts: {
    wikipedia: 10,
    gbooks: 10,
    "whitelist_www.jstor.org": 10,
  },
};
const fetchCalls = [];
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: ["www.jstor.org"] }; } };
  }
  invariant(url === "/api/browse/search-all", "unexpected grouped search endpoint");
  return { ok: true, async json() { return payload; } };
};
globalThis.toastCalls = [];

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();
const initialTitles = globalThis.renderedItems.map((item) => item.title);

await controls.get("#loadMoreBtn").dispatch("click");
await flushPromises();
const afterFirstLoadTitles = globalThis.renderedItems.map((item) => item.title);

for (let rank = 3; rank <= 10; rank += 1) {
  await controls.get("#loadMoreBtn").dispatch("click");
  await flushPromises();
}
const afterNinthLoadCounts = globalThis.renderedItems.reduce((counts, item) => {
  const source = item.source_id.startsWith("wiki-")
    ? "wikipedia"
    : item.source_id.startsWith("book-")
      ? "gbooks"
      : "whitelist_www.jstor.org";
  counts[source] = (counts[source] || 0) + 1;
  return counts;
}, {});
const searchCalls = fetchCalls.filter((call) => call.url === "/api/browse/search-all");

process.stdout.write(JSON.stringify({
  initialTitles,
  afterFirstLoadTitles,
  afterNinthLoadCounts,
  requestSizes: searchCalls.map((call) => JSON.parse(call.options.body).num_results),
  loadMoreDisabled: controls.get("#loadMoreBtn").disabled,
  loadMoreText: controls.get("#loadMoreText").textContent,
}));
"""


UNEVEN_GROUPED_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
const gbooks = new FakeElement("gbooks");
gbooks.value = "gbooks";
gbooks.checked = true;
sourceCheckboxes.splice(1, 0, gbooks);
const wikiItems = Array.from({ length: 3 }, (_, index) => ({
  source_name: "Wikipedia",
  source_id: `wiki-${index + 1}`,
  source_url: `https://en.wikipedia.org/wiki/archive-${index + 1}`,
  title: `wiki-${index + 1}`,
}));
const bookItems = [{
  source_name: "Google Books",
  source_id: "book-1",
  source_url: "https://books.google.com/books/1",
  title: "book-1",
}];
globalThis.fetch = async (url) => {
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  invariant(url === "/api/browse/search-all", "unexpected uneven search endpoint");
  return {
    ok: true,
    async json() {
      return {
        status: true,
        results: [...wikiItems, ...bookItems],
        grouped_results: { wikipedia: wikiItems, gbooks: bookItems },
        source_counts: { wikipedia: 3, gbooks: 1 },
      };
    },
  };
};
globalThis.toastCalls = [];

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();
await controls.get("#loadMoreBtn").dispatch("click");
await flushPromises();
await controls.get("#loadMoreBtn").dispatch("click");
await flushPromises();

process.stdout.write(JSON.stringify({
  unevenAfterSecondLoadTitles: globalThis.renderedItems.map((item) => item.title),
}));
"""


RESTORED_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
const restoredState = {
  version: 1,
  query: "restored archive",
  sources: ["wikipedia", "whitelist_en.wikipedia.org"],
  filters: {
    min_date: "1990",
    max_date: "2020",
    content_type: "review",
    sorting: "recent",
  },
  results: [
    {
      source_name: "Wikipedia",
      source_id: "wiki-1",
      source_url: "https://example.test/first",
      title: "Restored first",
      thumb_url: "https://serpapi.com/restored.jpg",
    },
    {
      source_name: " wikipedia ",
      source_id: "wiki-1",
      source_url: "https://example.test/duplicate",
      title: "Restored duplicate",
    },
    {
      source_name: "Open Archive",
      source_id: "archive-2",
      source_url: "https://example.test/second",
      title: "Restored second",
    },
    ...__SERVER_METADATA_RECORDS__,
  ],
};
const restoredStorageWrites = [];
globalThis.localStorage = {
  getItem(key) {
    invariant(key === "studyhelper_browse_state", "wrong restore key");
    return JSON.stringify(restoredState);
  },
  setItem(key, value) { restoredStorageWrites.push({ key, value }); },
};
const fetchCalls = [];
globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/static/whitelist.json") {
    return {
      ok: true,
      async json() { return { domains: ["en.wikipedia.org", "books.google.com"] }; },
    };
  }
  return { json() { return new Promise(() => {}); } };
};
globalThis.toastCalls = [];

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await flushPromises();
const initialButtonDisabled = controls.get("#loadMoreBtn").disabled;
const initialTitles = globalThis.renderedItems.map((item) => item.title);
await controls.get("#loadMoreBtn").dispatch("click");
await flushPromises();

const searchCalls = fetchCalls.filter((call) => call.url === "/api/browse/search-all");
const upgradedState = restoredStorageWrites.length > 0
  ? JSON.parse(restoredStorageWrites[restoredStorageWrites.length - 1].value)
  : null;
process.stdout.write(JSON.stringify({
  query: search.value,
  filters: {
    min_date: controls.get("#filterYearFrom").value,
    max_date: controls.get("#filterYearTo").value,
    content_type: controls.get("#filterContentType").value,
    sorting: sorting.value,
  },
  checkedSources: sourceCheckboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value),
  initialTitles,
  renderedTitles: globalThis.renderedItems.map((item) => item.title),
  renderedThumbnails: globalThis.renderedItems.map((item) => item.thumb_url || ""),
  storageWrites: restoredStorageWrites.length,
  upgradedVersion: upgradedState?.version ?? null,
  storedThumbnails: Object.values(upgradedState?.groupedResults || {})
    .flat()
    .map((item) => item.thumb_url || ""),
  storedTitles: Object.values(upgradedState?.groupedResults || {})
    .flat()
    .map((item) => item.title),
  storedSourceIds: Object.values(upgradedState?.groupedResults || {})
    .flat()
    .map((item) => item.source_id),
  initialButtonDisabled,
  searchRequestCount: searchCalls.length,
}));
"""


MAX_RANK_RESTORED_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
const cachedItems = Array.from({ length: 20 }, (_, index) => ({
  source_name: "Wikipedia",
  source_id: `wiki-${index + 1}`,
  source_url: `https://en.wikipedia.org/wiki/archive-${index + 1}`,
  title: `wiki-${index + 1}`,
}));
const restoredState = {
  version: 2,
  query: "legacy cumulative cache",
  sources: ["wikipedia"],
  filters: { min_date: "", max_date: "", content_type: "", sorting: "" },
  results: cachedItems,
  groupedResults: { wikipedia: cachedItems },
  sourceCounts: { wikipedia: 20 },
  groupPage: 11,
  resultWindow: 20,
  searchExhausted: false,
};
globalThis.localStorage = {
  getItem(key) {
    invariant(key === "studyhelper_browse_state", "wrong max-rank restore key");
    return JSON.stringify(restoredState);
  },
  setItem() {},
};
const fetchCalls = [];
globalThis.fetch = async (url) => {
  fetchCalls.push(url);
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }
  return {
    ok: true,
    async json() {
      return {
        status: true,
        results: cachedItems,
        grouped_results: { wikipedia: cachedItems },
        source_counts: { wikipedia: 20 },
      };
    },
  };
};
globalThis.toastCalls = [];

const { initBrowse, getBrowseState } = await import(process.argv[1]);
initBrowse(root);
await flushPromises();
const initialTitles = globalThis.renderedItems.map((item) => item.title);
await controls.get("#loadMoreBtn").dispatch("click");
await flushPromises();

process.stdout.write(JSON.stringify({
  initialTitles,
  afterLoadTitles: globalThis.renderedItems.map((item) => item.title),
  loadMoreDisabled: controls.get("#loadMoreBtn").disabled,
  loadMoreText: controls.get("#loadMoreText").textContent,
  searchRequestCount: fetchCalls.filter((url) => url === "/api/browse/search-all").length,
  restoredGroupPage: getBrowseState().groupPage,
}));
"""


LEGACY_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
const gbooks = new FakeElement("gbooks");
gbooks.value = "gbooks";
gbooks.checked = true;
const pubmed = new FakeElement("pubmed");
pubmed.value = "pubmed";
pubmed.checked = true;
sourceCheckboxes.push(gbooks, pubmed);
const legacyWhitelistDomains = [
  "en.wikipedia.org",
  "web.md",
  "scholar.google.com",
  "pubmed.ncbi.nlm.nih.gov",
  "www.jstor.org",
  "eric.ed.gov",
  "www.sciencedirect.com",
  "link.springer.com",
  "www.researchgate.net",
  "www.academia.edu",
  "books.google.com",
  "www.britannica.com",
  "www.bbc.co.uk",
  "www.nationalgeographic.com",
];
const legacyState = {
  query: "legacy archive",
  sources: [
    "wikipedia",
    "gbooks",
    "pubmed",
    ...legacyWhitelistDomains.map((domain) => `whitelist_${domain}`),
  ],
  filters: {
    min_date: "1985",
    max_date: "2015",
    content_type: "article",
    sorting: "title",
  },
  results: [
    {
      source_name: "Wikipedia",
      source_id: "legacy-1",
      source_url: "https://en.wikipedia.org/wiki/Archive",
      title: "Legacy result",
    },
  ],
  resultWindow: 20,
  searchExhausted: false,
};
const storageWrites = [];
globalThis.localStorage = {
  getItem(key) {
    invariant(key === "studyhelper_browse_state", "wrong legacy restore key");
    return JSON.stringify(legacyState);
  },
  setItem(key, value) {
    storageWrites.push({ key, value });
  },
};
globalThis.fetch = async (url) => {
  invariant(url === "/static/whitelist.json", "legacy upgrade made a search request");
  return {
    ok: true,
    async json() { return { domains: legacyWhitelistDomains }; },
  };
};
globalThis.toastCalls = [];

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await flushPromises();
await flushPromises();

const upgradedState = storageWrites.length > 0
  ? JSON.parse(storageWrites[storageWrites.length - 1].value)
  : null;
process.stdout.write(JSON.stringify({
  checkedSources: sourceCheckboxes
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => checkbox.value),
  renderedTitles: globalThis.renderedItems.map((item) => item.title),
  whitelistMarkup: controls.get("#whitelistCheckboxes").innerHTML,
  storageWrites: storageWrites.length,
  upgradedState,
}));
"""


DEFERRED_BROWSE_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME + r"""
globalThis.renderedItems = [];
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.toastCalls = [];
const fetchCalls = [];

function deferredResponse() {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}
function response(results) {
  return {
    ok: true,
    async json() { return { status: true, results, source_counts: { wikipedia: results.length } }; },
  };
}

const oldInitial = deferredResponse();
const newestInitial = deferredResponse();
const fresh = {
  source_name: "Wikipedia",
  source_id: "fresh-1",
  source_url: "https://example.test/fresh",
  title: "Fresh",
};
const newest = {
  source_name: "Wikipedia",
  source_id: "newest-1",
  source_url: "https://example.test/newest",
  title: "Newest",
};

globalThis.fetch = async (url, options) => {
  fetchCalls.push({ url, options });
  if (url === "/static/whitelist.json") {
    return { ok: true, async json() { return { domains: [] }; } };
  }

  const body = JSON.parse(options.body);
  if (body.query === "archive" && body.num_results === 10) return oldInitial.promise;
  if (body.query === "fresh" && body.num_results === 10) return response([fresh]);
  if (body.query === "newest" && body.num_results === 10) return newestInitial.promise;
  throw new Error("unexpected search request: " + JSON.stringify(body));
};

const { initBrowse } = await import(process.argv[1]);
initBrowse(root);
await go.dispatch("click");
await flushPromises();

search.value = "fresh";
await go.dispatch("click");
await flushPromises();
search.value = "newest";
await go.dispatch("click");
await flushPromises();
sorting.value = "recent";
await sorting.dispatch("change");

oldInitial.resolve(response([{
  source_name: "Wikipedia",
  source_id: "old-initial",
  source_url: "https://example.test/old-initial",
  title: "Old initial",
}]));
await flushPromises();
const pendingSearchBodies = fetchCalls
  .filter((call) => call.url === "/api/browse/search-all")
  .map((call) => JSON.parse(call.options.body));
const duringNewestInitial = {
  titles: globalThis.renderedItems.map((item) => item.title),
  sortingDisabled: sorting.disabled,
  loadMorePresent: controls.has("#loadMoreBtn"),
  sidebarReset: controls.get("#sidebarContainer").innerHTML.includes('archive-count-badge">0</span>'),
  requestQueries: pendingSearchBodies.map((body) => body.query),
  requestSizes: pendingSearchBodies.map((body) => body.num_results),
};

newestInitial.resolve(response([newest]));
await flushPromises();
const afterInitialRace = globalThis.renderedItems.map((item) => item.title);
const initialSortingReleased = sorting.disabled;
const searchBodies = fetchCalls
  .filter((call) => call.url === "/api/browse/search-all")
  .map((call) => JSON.parse(call.options.body));
process.stdout.write(JSON.stringify({
  afterInitialRace,
  duringNewestInitial,
  initialSortingReleased,
  requestQueries: searchBodies.map((body) => body.query),
  requestSizes: searchBodies.map((body) => body.num_results),
}));
"""


BROWSE_IDENTITY_RUNTIME_HARNESS = r"""
const vectors = __SERVER_IDENTITY_METADATA_VECTORS__;
const {
  canonicalSourceUrl,
  resultIdentity,
  deduplicateResults,
  mergeUniqueResults,
} = await import(process.argv[1]);
const inheritedMetadataRecord = Object.assign(
  Object.create({
    _dedupe_identity: '["display","wrong","identity"]',
    _canonical_source_url: "https://wrong.test/identity",
  }),
  { source_name: " Open  Archive ", title: "Entry" },
);
const identitylessLegacy = { description: "Opaque provider record" };
const identitylessNewFormat = {
  ...identitylessLegacy,
  _dedupe_identity: "",
  _canonical_source_url: "",
};
const identitylessMerge = mergeUniqueResults(
  [identitylessLegacy],
  [identitylessNewFormat],
);
const aliasChain = [
  {
    title: "First",
    _dedupe_identity: '["source_id","archive","shared-id"]',
    _canonical_source_url: "https://example.test/first",
  },
  {
    title: "Repeated ID",
    _dedupe_identity: '["source_id","archive","shared-id"]',
    _canonical_source_url: "https://example.test/alias",
  },
  {
    title: "Repeated alias URL",
    _dedupe_identity: '["source_id","archive","other-id"]',
    _canonical_source_url: "https://example.test/alias",
  },
];
const lateAliasBridge = [aliasChain[0], aliasChain[2], aliasChain[1]];

process.stdout.write(JSON.stringify({
  vectors: vectors.map((vector) => {
    const records = vector.records.map((record) => ({
      ...record,
      _dedupe_identity: vector.identity,
      _canonical_source_url: vector.canonical_url,
    }));
    const merged = mergeUniqueResults([records[0]], records);
    return {
      name: vector.name,
      identities: records.map((record) => resultIdentity(record)),
      deduplicatedTitles: deduplicateResults(records).map((record) => record.title),
      mergedTitles: merged.results.map((record) => record.title),
      addedCount: merged.addedCount,
    };
  }),
  legacyIdentity: resultIdentity({ source_name: " Open  Archive ", title: "Entry" }),
  inheritedMetadataIdentity: resultIdentity(inheritedMetadataRecord),
  identitylessMetadataMerge: {
    resultCount: identitylessMerge.results.length,
    addedCount: identitylessMerge.addedCount,
  },
  aliasChainTitles: deduplicateResults(aliasChain).map((record) => record.title),
  lateAliasBridgeTitles: deduplicateResults(lateAliasBridge).map((record) => record.title),
  malformedBackslashUrl: canonicalSourceUrl("https://example.com\\archive"),
}));
"""


WORKSPACE_IMPORT_REPLACEMENTS = (
    (
        "import { showToast } from '../toast.js';",
        "const showToast = (...args) => globalThis.toastCalls.push(args);",
    ),
    (
        "import { studyHelperAI } from '../ai-prompt.js';",
        "const studyHelperAI = {};",
    ),
    (
        "let pageRoot = null;",
        "let pageRoot = globalThis.__workspaceRoot;",
    ),
)
WORKSPACE_PREVIEW_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const preview = new FakeElement("preview");
const createdIframes = [];
const fetchCalls = [];
const fetchResults = [];
globalThis.__workspaceRoot = {
  querySelector(selector) {
    invariant(selector === "#selectedSourcePreview", "unexpected workspace selector: " + selector);
    return preview;
  },
};
globalThis.toastCalls = [];
globalThis.escapeHtml = (value) => String(value);
globalThis.window = { location: { origin: "https://study.test" } };
globalThis.document = {
  createElement(tag) {
    if (tag === "div") {
      const div = new FakeElement("escape div");
      let escaped = "";
      Object.defineProperty(div, "textContent", {
        get() { return escaped; },
        set(value) {
          escaped = String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
          div.innerHTML = escaped;
        },
      });
      return div;
    }
    invariant(tag === "iframe", "unexpected preview element: " + tag);
    const iframe = new FakeElement("iframe");
    iframe.events = [];
    const baseSetAttribute = iframe.setAttribute.bind(iframe);
    iframe.setAttribute = (name, value) => {
      iframe.events.push(`attr:${name}`);
      baseSetAttribute(name, value);
    };
    let assignedSrc = "";
    let assignedSrcdoc = "";
    Object.defineProperty(iframe, "src", {
      get() { return assignedSrc; },
      set(value) { iframe.events.push("src"); assignedSrc = String(value); },
    });
    Object.defineProperty(iframe, "srcdoc", {
      get() { return assignedSrcdoc; },
      set(value) { iframe.events.push("srcdoc"); assignedSrcdoc = String(value); },
    });
    createdIframes.push(iframe);
    return iframe;
  },
};
globalThis.fetch = async (url) => {
  fetchCalls.push(url);
  const result = fetchResults.shift();
  invariant(result, "unexpected workspace proxy request");
  return { async json() { return result; } };
};
const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 0));

const { renderSelectedSourcePreview } = await import(process.argv[1]);

fetchResults.push({ status: true, html: "<article>Remote HTML</article>" });
renderSelectedSourcePreview({ source_url: "https://en.wikipedia.org/archive.html" });
await flushPromises();
const remoteHtmlFrame = createdIframes[0];

preview.children = [];
fetchResults.push({ status: true, html: "<article>Remote HTM</article>" });
renderSelectedSourcePreview({ source_url: "https://en.wikipedia.org/archive.htm" });
await flushPromises();
const remoteHtmFrame = createdIframes[1];

preview.children = [];
renderSelectedSourcePreview({ source_url: "https://en.wikipedia.org/archive.pdf" });
const directPdfFrame = createdIframes[2];

preview.children = [];
fetchResults.push({ status: false, fallback_url: "javascript:alert(1)" });
renderSelectedSourcePreview({ source_url: "https://en.wikipedia.org/no-preview" });
await flushPromises();
const fallbackHtml = preview.innerHTML;

preview.children = [];
renderSelectedSourcePreview({ source_url: "javascript:alert(1).html" });

process.stdout.write(JSON.stringify({
  fetchCalls,
  remoteHtml: {
    src: remoteHtmlFrame?.src,
    srcdoc: remoteHtmlFrame?.srcdoc,
    sandbox: remoteHtmlFrame?.getAttribute("sandbox"),
    events: remoteHtmlFrame?.events,
  },
  remoteHtm: {
    src: remoteHtmFrame?.src,
    srcdoc: remoteHtmFrame?.srcdoc,
    sandbox: remoteHtmFrame?.getAttribute("sandbox"),
    events: remoteHtmFrame?.events,
  },
  directPdf: {
    src: directPdfFrame?.src,
    sandbox: directPdfFrame?.getAttribute("sandbox"),
    events: directPdfFrame?.events,
  },
  fallbackHtml,
  invalidHtml: preview.innerHTML,
}));
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
        "const createCard = (item) => { globalThis.renderedItems.push(item); return item; };",
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
TASK6_ALLOWED_LIGHT_SELECTOR_GROUPS = frozenset(
    {
        (f"{LIGHT_GUARD} .archive-page.archive-page-browse",),
        (f"{LIGHT_GUARD} .browse-search-shell",),
        (
            f"{LIGHT_GUARD} .ai-overview-panel",
            f"{LIGHT_GUARD} .source-summary-panel",
        ),
        (
            f"{LIGHT_GUARD} .ai-overview-panel .card-title",
            f"{LIGHT_GUARD} .source-summary-panel .card-title",
        ),
        (f"{LIGHT_GUARD} .ai-overview-panel .card-body",),
        (f"{LIGHT_GUARD} .source-summary-panel .list-group-item",),
        (f"{LIGHT_GUARD} .result-card",),
        (
            f"{LIGHT_GUARD} .result-card:hover",
            f"{LIGHT_GUARD} .result-card:focus-within",
        ),
        (f"{LIGHT_GUARD} .result-card img",),
        (f'{LIGHT_GUARD} .result-card .result-card-image',),
        (
            f'{LIGHT_GUARD} .result-card '
            '.result-card-image[data-image-kind="fallback"]',
        ),
        (f"{LIGHT_GUARD} .result-card .card-title",),
        (f"{LIGHT_GUARD} .result-source",),
        (f"{LIGHT_GUARD} .result-card .card-text",),
        (f"{LIGHT_GUARD} .result-card-actions",),
        (f"{LIGHT_GUARD} .result-card .save-btn",),
        (f"{LIGHT_GUARD} .result-card .save-btn:hover",),
        (
            f"{LIGHT_GUARD} .archive-page-home .illustration-books",
            f"{LIGHT_GUARD} .archive-page-browse .illustration-books",
            f"{LIGHT_GUARD} .archive-page-workspace .illustration-books",
        ),
        (
            f"{LIGHT_GUARD} .archive-page-home .illustration-flourish",
            f"{LIGHT_GUARD} .archive-page-browse .illustration-flourish",
            f"{LIGHT_GUARD} .archive-page-workspace .illustration-flourish",
        ),
        (f"{LIGHT_GUARD} .archive-page-browse",),
        (f"{LIGHT_GUARD} .browse-results-layout",),
        (f"{LIGHT_GUARD} #sidebarContainer.browse-sidebar",),
        (f"{LIGHT_GUARD} .browse-results-pane",),
        (
            f"{LIGHT_GUARD} .browse-results-row .col",
            f"{LIGHT_GUARD} .browse-results-row .result-card",
        ),
    }
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


def browse_filter_runtime(source: str | None = None) -> dict:
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += "\nexport { getBrowseState, applySelectedSources };\n"
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_FILTER_RUNTIME_HARNESS,
        "browse filters",
    )


def browse_filter_race_runtime(action: str, source: str | None = None) -> dict:
    actions = {
        "select_all": """
master.checked = true;
await master.dispatch("change");
""",
        "clear_all": """
master.checked = false;
await master.dispatch("change");
""",
        "select_individual": """
sources[0].checked = true;
await menu.dispatch("change", { target: sources[0] });
""",
        "select_all_then_clear_gbooks": """
master.checked = true;
await master.dispatch("change");
sources[1].checked = false;
await menu.dispatch("change", { target: sources[1] });
""",
    }
    assert action in actions
    harness = BROWSE_FILTER_RACE_RUNTIME_HARNESS.replace(
        "__PENDING_SOURCE_ACTION__",
        actions[action],
    )
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += "\nexport { getBrowseState };\n"
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        harness,
        f"browse filter {action} race",
    )


def browse_source_readiness_runtime(
    action: str,
    outcome: str,
    *,
    restored: bool = False,
    render_failure: bool = False,
    source: str | None = None,
) -> dict:
    actions = {
        "master_latest": """
master.checked = true;
await master.dispatch("change");
search.value = "older";
await go.dispatch("click");
search.value = "latest";
await go.dispatch("click");
""",
        "restored": """
search.value = "restored";
await go.dispatch("click");
""",
        "dedicated": """
search.value = "dedicated";
await go.dispatch("click");
""",
    }
    settlements = {
        "success": """
whitelistResponse.resolve({
  ok: true,
  async json() { return { domains: ["jstor.org"], domain_patterns: ["*.edu"] }; },
});
""",
        "empty": """
whitelistResponse.resolve({
  ok: true,
  async json() { return { domains: [], domain_patterns: [] }; },
});
""",
        "non_ok": """
whitelistResponse.resolve({ ok: false });
""",
        "failure": """
whitelistResponse.reject(new Error("whitelist unavailable"));
""",
        "timeout": """
if (readinessTimers.length === 1) readinessTimers[0].callback();
""",
    }
    assert action in actions
    assert outcome in settlements
    restored_state = None
    if restored:
        restored_state = {
            "version": 2,
            "query": "restored",
            "sources": ["gbooks", "whitelist_jstor.org"],
            "filters": {
                "min_date": "",
                "max_date": "",
                "content_type": "",
                "sorting": "",
            },
            "results": [],
            "groupedResults": {},
            "sourceCounts": {},
            "groupPage": 1,
        }
    harness = BROWSE_SOURCE_READINESS_RUNTIME_HARNESS
    harness = harness.replace("__RESTORED_STATE__", json.dumps(restored_state))
    harness = harness.replace(
        "__THROW_ON_WHITELIST_RENDER__",
        "true" if render_failure else "false",
    )
    harness = harness.replace("__PRE_READINESS_ACTIONS__", actions[action])
    harness = harness.replace("__WHITELIST_SETTLEMENT__", settlements[outcome])
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += "\nexport { getBrowseState };\n"
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        harness,
        f"browse source readiness {action} {outcome}",
    )


def browse_reinit_readiness_runtime(source: str | None = None) -> dict:
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += """
export function setBrowseLoadingStateForTest(initialPending, loadingMore) {
    isInitialSearchPending = initialPending;
    isLoadingMore = loadingMore;
}
export function getBrowseLoadingStateForTest() {
    return { isInitialSearchPending, isLoadingMore };
}
"""
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_REINIT_READINESS_RUNTIME_HARNESS,
        "browse reinit readiness",
    )


def url_query_browse_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        URL_QUERY_BROWSE_RUNTIME_HARNESS,
        "URL query browse",
    )


def browse_error_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_ERROR_RUNTIME_HARNESS,
        "Browse error",
    )


def browse_active_invalid_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_ACTIVE_INVALID_RUNTIME_HARNESS,
        "Browse active invalid action",
    )


def browse_timeout_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_TIMEOUT_RUNTIME_HARNESS,
        "Browse timeout",
    )


def browse_partial_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_PARTIAL_RUNTIME_HARNESS,
        "partial Browse",
    )


def grouped_browse_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        GROUPED_BROWSE_RUNTIME_HARNESS,
        "grouped browse",
    )


def uneven_grouped_browse_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        UNEVEN_GROUPED_BROWSE_RUNTIME_HARNESS,
        "uneven grouped browse",
    )


def restored_browse_runtime(source: str | None = None) -> dict:
    harness = RESTORED_BROWSE_RUNTIME_HARNESS.replace(
        "__SERVER_METADATA_RECORDS__",
        json.dumps(server_metadata_records(), ensure_ascii=False),
    )
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        harness,
        "restored browse",
    )


def max_rank_restored_browse_runtime(source: str | None = None) -> dict:
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += "\nexport { getBrowseState };\n"
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        MAX_RANK_RESTORED_BROWSE_RUNTIME_HARNESS,
        "max-rank restored browse",
    )


def legacy_browse_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        LEGACY_BROWSE_RUNTIME_HARNESS,
        "legacy browse",
    )


def deferred_browse_runtime(source: str | None = None) -> dict:
    return run_task6_module_harness(
        source or read_text("static/js/pages/browse.js"),
        BROWSE_IMPORT_REPLACEMENTS,
        DEFERRED_BROWSE_RUNTIME_HARNESS,
        "deferred browse",
    )


def browse_identity_runtime(source: str | None = None) -> dict:
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += (
        "\nexport { canonicalSourceUrl, resultIdentity, deduplicateResults, mergeUniqueResults };\n"
    )
    harness = BROWSE_IDENTITY_RUNTIME_HARNESS.replace(
        "__SERVER_IDENTITY_METADATA_VECTORS__",
        json.dumps(SERVER_IDENTITY_METADATA_VECTORS, ensure_ascii=False),
    )
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        harness,
        "browse identity",
    )


def workspace_preview_runtime(source: str | None = None) -> dict:
    workspace_source = source or read_text("static/js/pages/workspace.js")
    workspace_source += "\nexport { renderSelectedSourcePreview };\n"
    return run_task6_module_harness(
        workspace_source,
        WORKSPACE_IMPORT_REPLACEMENTS,
        WORKSPACE_PREVIEW_RUNTIME_HARNESS,
        "workspace preview",
    )


def server_metadata_records() -> list[dict]:
    return [
        {
            **record,
            "_dedupe_identity": vector["identity"],
            "_canonical_source_url": vector["canonical_url"],
        }
        for vector in SERVER_IDENTITY_METADATA_VECTORS
        for record in vector["records"]
    ]


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
        TASK6_ALLOWED_LIGHT_SELECTOR_GROUPS,
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
        "image": "/static/img/illustrations/compass-rose.svg",
        "imageAttrs": {
            "loading": "lazy",
            "decoding": "async",
            "referrerpolicy": "no-referrer",
            "alt": "",
            "fallback": "/static/img/illustrations/compass-rose.svg",
            "kind": "fallback",
        },
        "itemId": hostile["id"],
        "label": "Saved result",
        "pressed": "true",
        "lightIcon": "bi bi-bookmark-fill text-danger save-icon-light",
        "darkIcon": "bi bi-bookmark-check save-icon-dark d-none",
    }
    assert server.select_one(".card-title").get_text(strip=True) == attack
    assert server.select_one(".card-description").get_text(strip=True) == attack
    assert server.select_one(".result-source-text").get_text(strip=True) == attack
    assert server.select_one("img.card-img-top").get("src") == (
        "/static/img/illustrations/compass-rose.svg"
    )
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


def test_task1_card_image_fallback_parity_and_remote_failure_contract():
    client = card_runtime()
    expected_fallbacks = {
        "Google Books": "/static/img/illustrations/open-book.svg",
        "Reference": "/static/img/illustrations/scrollwork-flourish.svg",
        "Google Scholar": "/static/img/illustrations/stacked-books.svg",
        "PubMed": "/static/img/illustrations/stacked-books.svg",
    }

    assert {
        contract["sourceName"]: contract["src"]
        for contract in client["fallbackContracts"]
    } == expected_fallbacks
    assert all(
        contract["src"] == contract["fallback"]
        and contract["kind"] == "fallback"
        for contract in client["fallbackContracts"]
    )
    assert client["remote"] == {
        "beforeError": "https://books.google.com/books/content?id=remote",
        "afterError": "/static/img/illustrations/open-book.svg",
        "fallback": "/static/img/illustrations/open-book.svg",
        "kind": "fallback",
        "errorOnce": True,
    }

    server_items = (
        {
            "source_name": "Google Books",
            "source_url": "https://books.google.com/books?id=1",
        },
        {
            "source_name": "Reference",
            "source_url": "https://en.wikipedia.org/wiki/Archive",
        },
        {
            "source_name": "Google Scholar",
            "source_url": "https://scholar.google.com/scholar?q=archive",
        },
        {
            "source_name": "PubMed",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/1/",
        },
    )
    for index, partial_item in enumerate(server_items, start=1):
        item = {
            "id": index,
            "title": "Result",
            "description": "Description",
            "thumb_url": "http://images.test/unsafe.jpg",
            "saved": False,
            **partial_item,
        }
        image = BeautifulSoup(
            render_server_result_card(item), "html.parser"
        ).select_one("img.card-img-top")
        fallback = expected_fallbacks[item["source_name"]]
        assert image.get("src") == fallback
        assert image.get("data-fallback-src") == fallback
        assert image.get("data-image-kind") == "fallback"
        assert image.get("loading") == "lazy"
        assert image.get("decoding") == "async"
        assert image.get("referrerpolicy") == "no-referrer"
        assert image.get("alt") == ""
        assert not [name for name in image.attrs if name.lower().startswith("on")]

    remote = {
        "id": 5,
        "title": "Remote",
        "description": "Description",
        "thumb_url": "https://upload.wikimedia.org/remote.jpg",
        "source_name": "Wikipedia",
        "source_url": "https://en.wikipedia.org/wiki/Remote",
        "saved": False,
    }
    remote_image = BeautifulSoup(
        render_server_result_card(remote), "html.parser"
    ).select_one("img.card-img-top")
    assert remote_image.get("src") == remote["thumb_url"]
    assert remote_image.get("data-image-kind") == "remote"
    assert remote_image.get("data-fallback-src") == (
        "/static/img/illustrations/scrollwork-flourish.svg"
    )

    for unsafe_thumbnail in (
        "https://user:password@serpapi.com/image.jpg",
        "https://serpapi.com:444/image.jpg",
        "https://serpapi.com/image name.jpg",
    ):
        unsafe_image = BeautifulSoup(
            render_server_result_card({
                **remote,
                "thumb_url": unsafe_thumbnail,
                "source_name": "Other",
                "source_url": "https://example.test/result",
            }),
            "html.parser",
        ).select_one("img.card-img-top")
        assert unsafe_image.get("src") == (
            "/static/img/illustrations/compass-rose.svg"
        )
        assert unsafe_image.get("data-image-kind") == "fallback"

    assert "/static/img/placeholder.png" not in read_text("static/js/card.js")
    assert "/static/img/placeholder.png" not in read_text("templates/macros.html")


def test_task1_result_card_image_css_is_stable_and_theme_aware():
    css = read_text("static/css/custom.css")
    base_selectors = (
        f"{LIGHT_GUARD} .result-card .result-card-image",
    )
    assert css_rule_group_declarations(css, base_selectors) == {
        "background": "var(--paper-100)",
        "height": "130px",
        "object-fit": "contain",
        "width": "100%",
    }
    assert css_rule_group_declarations(
        css,
        (
            f'{LIGHT_GUARD} .result-card '
            '.result-card-image[data-image-kind="fallback"]',
        ),
    ) == {
        "filter": "sepia(0.75) saturate(0.8) contrast(1.15)",
        "padding": "1.25rem",
    }
    assert css_rule_group_declarations(
        css,
        ('[data-bs-theme="dark"] .result-card .result-card-image',),
    ) == {
        "background": "var(--surface-700)",
        "height": "130px",
        "object-fit": "contain",
        "width": "100%",
    }
    assert css_rule_group_declarations(
        css,
        (
            '[data-bs-theme="dark"] .result-card '
            '.result-card-image[data-image-kind="fallback"]',
        ),
    ) == {
        "filter": (
            "brightness(0) saturate(100%) invert(76%) sepia(20%) "
            "saturate(667%) hue-rotate(357deg) brightness(88%) contrast(86%)"
        ),
        "padding": "1.25rem",
    }


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
        "linear-gradient(hsl(31 51% 12% / 0.38), "
        "hsl(31 51% 12% / 0.38)), "
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


def test_task6_browse_runtime_starts_search_without_legacy_globals():
    rendered = browse_runtime()
    assert rendered["body"] == {
        "query": "archive",
        "sources": ["wikipedia"],
        "num_results": 10,
        "filters": {},
    }


def test_home_query_runs_native_browse_search_and_manual_search_updates_url():
    assert url_query_browse_runtime() == {
        "query": "archives",
        "requestQueries": ["quantum mechanics", "archives"],
        "historyUrls": ["/browse?q=archives"],
    }


def test_browse_surfaces_safe_server_error_and_bounds_requests():
    rendered = browse_error_runtime()
    browse = read_text("static/js/pages/browse.js")

    assert rendered["toast"] == [
        "Browse search is not configured. Add SERP_API_KEY and restart StudyLib.",
        "danger",
    ]
    assert "const BROWSE_REQUEST_TIMEOUT_MS = 30000;" in browse
    assert "new AbortController()" in browse
    assert "signal: controller.signal" in browse


def test_browse_timeout_aborts_request_and_clears_loading_state():
    assert browse_timeout_runtime() == {
        "toast": ["Browse search timed out. Try again.", "danger"],
        "timeoutDelay": 30000,
        "sortingDisabled": False,
    }


def test_browse_invalid_source_action_does_not_orphan_active_search_loading_state():
    assert browse_active_invalid_runtime() == {
        "duringActive": {
            "sortingDisabled": True,
            "loading": True,
            "apiQueries": ["search a"],
        },
        "afterInvalid": {
            "sortingDisabled": True,
            "loading": True,
            "apiQueries": ["search a"],
            "toastCalls": [["Please select at least one source", "warning"]],
        },
        "finalSortingDisabled": False,
        "finalLoading": False,
        "renderedTitles": ["Active A"],
        "apiQueries": ["search a"],
    }


def test_browse_partial_failure_renders_results_with_one_safe_warning():
    rendered = browse_partial_runtime()

    assert rendered["title"] == "Available result"
    assert rendered["toast"] == [
        "1 selected source could not be searched. Showing available results.",
        "warning",
    ]


def test_browse_defaults_only_dedicated_sources_and_leaves_dynamic_whitelist_opt_in():
    browse = read_text("static/js/pages/browse.js")
    app_source = read_text("app.py")
    rendered = browse_runtime()

    assert "const DEFAULT_SOURCES = ['wikipedia', 'gbooks', 'scholar'];" in browse
    assert "data.get('sources', ['wikipedia', 'gbooks', 'scholar'])" in app_source
    assert 'value="wikipedia" checked' in browse
    assert 'value="gbooks" checked' in browse
    assert 'value="scholar" checked' in browse
    assert 'value="pubmed" checked' not in browse
    assert 'value="whitelist_en.wikipedia.org"' in rendered["whitelistMarkup"]
    assert 'value="whitelist_*.edu"' in rendered["whitelistMarkup"]
    assert " checked" not in rendered["whitelistMarkup"]
    dynamic_sources = BeautifulSoup(rendered["whitelistMarkup"], "html.parser").select(
        'input[value^="whitelist_"]'
    )
    assert len(dynamic_sources) == 2
    assert all(
        "browse-source-checkbox" in checkbox.get("class", ())
        for checkbox in dynamic_sources
    )


def test_browse_filters_menu_is_viewport_bounded_and_scrollable():
    declarations = css_rule_group_declarations(
        read_text("static/css/custom.css"),
        (".browse-dropdown-menu",),
    )

    assert declarations["max-height"] == "min(32rem, calc(100vh - 8rem))"
    assert declarations["overflow-y"] == "auto"


def test_browse_master_source_checkbox_controls_all_sources_and_restores_state():
    rendered = browse_filter_runtime()

    assert rendered["initial"] == {"checked": False, "indeterminate": True}
    assert rendered["selectedAll"] == [True, True, True, True, True, True]
    assert rendered["selectedAllMaster"] == {"checked": True, "indeterminate": False}
    assert rendered["savedAll"] == [
        "wikipedia",
        "gbooks",
        "pubmed",
        "scholar",
        "whitelist_jstor.org",
        "whitelist_*.edu",
    ]
    assert rendered["restored"] == ["gbooks", "whitelist_jstor.org"]
    assert rendered["restoredMaster"] == {"checked": False, "indeterminate": True}
    assert rendered["oneSelectedMaster"] == {"checked": False, "indeterminate": True}
    assert rendered["cleared"] == [False, False, False, False, False, False]
    assert rendered["clearedMaster"] == {"checked": False, "indeterminate": False}


def test_browse_pending_source_intent_wins_deferred_whitelist_restore_race():
    selected = browse_filter_race_runtime("select_all")
    cleared = browse_filter_race_runtime("clear_all")
    individual = browse_filter_race_runtime("select_individual")
    master_then_individual = browse_filter_race_runtime("select_all_then_clear_gbooks")
    all_sources = [
        "wikipedia",
        "gbooks",
        "pubmed",
        "scholar",
        "whitelist_jstor.org",
        "whitelist_*.edu",
    ]

    for rendered in (selected, cleared, individual, master_then_individual):
        assert rendered["dynamicBeforeResolution"] == 0
        assert rendered["dynamicAfterResolution"] == 2
        assert all(
            "browse-source-checkbox" in class_name
            for class_name in rendered["dynamicClasses"]
        )
        assert rendered["whitelistMarkup"].count("browse-source-checkbox") == 2

    assert selected["beforeResolution"] == {
        "selected": ["wikipedia", "gbooks", "pubmed", "scholar"],
        "master": {"checked": True, "indeterminate": False},
    }
    assert selected["afterSources"] == all_sources
    assert selected["persistedSources"] == all_sources
    assert selected["apiSources"] == all_sources
    assert selected["afterMaster"] == {"checked": True, "indeterminate": False}

    assert cleared["beforeResolution"] == {
        "selected": [],
        "master": {"checked": False, "indeterminate": False},
    }
    assert cleared["afterSources"] == []
    assert cleared["persistedSources"] == []
    assert cleared["apiSources"] is None
    assert cleared["afterMaster"] == {"checked": False, "indeterminate": False}
    assert cleared["toastCalls"] == [["Please select at least one source", "warning"]]

    assert individual["beforeResolution"] == {
        "selected": ["wikipedia", "gbooks"],
        "master": {"checked": False, "indeterminate": True},
    }
    assert individual["afterSources"] == [
        "wikipedia",
        "gbooks",
        "whitelist_jstor.org",
    ]
    assert individual["persistedSources"] == individual["afterSources"]
    assert individual["apiSources"] == individual["afterSources"]
    assert individual["afterMaster"] == {"checked": False, "indeterminate": True}

    assert master_then_individual["beforeResolution"] == {
        "selected": ["wikipedia", "pubmed", "scholar"],
        "master": {"checked": False, "indeterminate": True},
    }
    assert master_then_individual["afterSources"] == [
        "wikipedia",
        "pubmed",
        "scholar",
        "whitelist_jstor.org",
        "whitelist_*.edu",
    ]
    assert master_then_individual["persistedSources"] == master_then_individual["afterSources"]
    assert master_then_individual["apiSources"] == master_then_individual["afterSources"]
    assert master_then_individual["afterMaster"] == {
        "checked": False,
        "indeterminate": True,
    }


def test_browse_search_waits_for_current_whitelist_source_readiness():
    browse = read_text("static/js/pages/browse.js")
    selected = browse_source_readiness_runtime("master_latest", "success")
    restored = browse_source_readiness_runtime(
        "restored",
        "success",
        restored=True,
    )
    settled_without_dynamic = {
        outcome: browse_source_readiness_runtime("dedicated", outcome)
        for outcome in ("empty", "non_ok", "failure")
    }
    timed_out = browse_source_readiness_runtime("dedicated", "timeout")
    render_failed = browse_source_readiness_runtime(
        "dedicated",
        "success",
        render_failure=True,
    )
    all_sources = [
        "wikipedia",
        "gbooks",
        "pubmed",
        "scholar",
        "whitelist_jstor.org",
        "whitelist_*.edu",
    ]
    dedicated_sources = ["wikipedia", "gbooks", "scholar"]

    assert "const BROWSE_WHITELIST_TIMEOUT_MS = 5000;" in browse
    assert selected["dynamicBeforeResolution"] == 0
    assert selected["apiCountBeforeResolution"] == 0
    assert len(selected["apiBodies"]) == 1
    assert selected["apiBodies"][0]["query"] == "latest"
    assert selected["apiBodies"][0]["sources"] == all_sources
    assert selected["selectedSources"] == all_sources
    assert selected["historyUrls"] == ["/browse?q=latest"]
    assert selected["dynamicAfterResolution"] == 2
    assert selected["masterValue"] == ""
    assert selected["master"] == {"checked": True, "indeterminate": False}

    assert restored["dynamicBeforeResolution"] == 0
    assert restored["apiCountBeforeResolution"] == 0
    assert len(restored["apiBodies"]) == 1
    assert restored["apiBodies"][0]["query"] == "restored"
    assert restored["apiBodies"][0]["sources"] == [
        "gbooks",
        "whitelist_jstor.org",
    ]
    assert restored["selectedSources"] == restored["apiBodies"][0]["sources"]
    assert restored["dynamicAfterResolution"] == 2

    for outcome, rendered in settled_without_dynamic.items():
        assert rendered["dynamicBeforeResolution"] == 0, outcome
        assert rendered["apiCountBeforeResolution"] == 0, outcome
        assert len(rendered["apiBodies"]) == 1, outcome
        assert rendered["apiBodies"][0]["query"] == "dedicated", outcome
        assert rendered["apiBodies"][0]["sources"] == dedicated_sources, outcome
        assert rendered["selectedSources"] == dedicated_sources, outcome
        assert rendered["dynamicAfterResolution"] == 0, outcome

    for rendered in (selected, restored, *settled_without_dynamic.values()):
        assert rendered["readinessTimerDelays"] == [5000]
        assert rendered["clearedReadinessTimers"] == [1]
        assert rendered["unhandledRejections"] == []

    for outcome, rendered in (("timeout", timed_out), ("render failure", render_failed)):
        assert rendered["apiCountBeforeResolution"] == 0, outcome
        assert len(rendered["apiBodies"]) == 1, outcome
        assert rendered["apiBodies"][0]["query"] == "dedicated", outcome
        assert rendered["apiBodies"][0]["sources"] == dedicated_sources, outcome
        assert rendered["selectedSources"] == dedicated_sources, outcome
        assert rendered["dynamicAfterResolution"] == 0, outcome
        assert rendered["readinessTimerDelays"] == [5000], outcome
        assert rendered["clearedReadinessTimers"] == [1], outcome
        assert rendered["unhandledRejections"] == [], outcome

    assert timed_out["whitelistAborted"] is True
    assert render_failed["whitelistAborted"] is False


def test_browse_reinit_ignores_older_whitelist_readiness_and_search_continuation():
    rendered = browse_reinit_readiness_runtime()

    assert rendered["afterOldResolution"] == {
        "apiQueries": [],
        "oldMarkup": "",
        "newMarkup": "",
        "newQuery": "new",
    }
    assert rendered["finalApiQueries"] == ["new"]
    assert rendered["finalApiSources"] == [["wikipedia", "gbooks", "scholar"]]
    assert rendered["oldMarkup"] == ""
    assert 'value="whitelist_new.example"' in rendered["newMarkup"]
    assert "whitelist_old.example" not in rendered["newMarkup"]
    assert rendered["newQuery"] == "new"
    assert rendered["resetAfterReinit"] == {
        "loadingState": {
            "isInitialSearchPending": False,
            "isLoadingMore": False,
        },
        "sortingDisabled": False,
    }
    assert rendered["replacementMarkup"] == ""


def test_browse_grouped_paging_reveals_each_cached_rank_without_refetching():
    rendered = grouped_browse_runtime()

    assert rendered["initialTitles"] == ["wiki-1", "book-1", "jstor-1"]
    assert rendered["afterFirstLoadTitles"] == [
        "wiki-1",
        "wiki-2",
        "book-1",
        "book-2",
        "jstor-1",
        "jstor-2",
    ]
    assert rendered["requestSizes"] == [10]


def test_browse_grouped_paging_disables_after_all_cached_ranks_are_visible():
    rendered = grouped_browse_runtime()

    assert rendered["afterNinthLoadCounts"] == {
        "wikipedia": 10,
        "gbooks": 10,
        "whitelist_www.jstor.org": 10,
    }
    assert rendered["requestSizes"] == [10]
    assert rendered["loadMoreDisabled"] is True
    assert rendered["loadMoreText"] == "No more results."


def test_browse_grouped_paging_keeps_revealing_longer_groups():
    rendered = uneven_grouped_browse_runtime()

    assert rendered["unevenAfterSecondLoadTitles"] == [
        "wiki-1",
        "wiki-2",
        "wiki-3",
        "book-1",
    ]


def test_task2_browse_runtime_ignores_stale_initial_responses():
    rendered = deferred_browse_runtime()

    assert rendered["afterInitialRace"] == ["Newest"]
    assert rendered["duringNewestInitial"] == {
        "titles": [],
        "sortingDisabled": True,
        "loadMorePresent": False,
        "sidebarReset": True,
        "requestQueries": ["archive", "fresh", "newest"],
        "requestSizes": [10, 10, 10],
    }
    assert rendered["initialSortingReleased"] is False
    assert rendered["requestQueries"] == ["archive", "fresh", "newest"]
    assert rendered["requestSizes"] == [10, 10, 10]


def test_task2_browse_runtime_uses_server_identity_metadata_across_batches():
    rendered = browse_identity_runtime()
    expected = []
    for vector in SERVER_IDENTITY_METADATA_VECTORS:
        for record in vector["records"]:
            original = dict(record)
            decorated = search_api.with_response_dedupe_metadata(record)
            assert decorated["_dedupe_identity"] == vector["identity"]
            assert decorated["_canonical_source_url"] == vector["canonical_url"]
            assert record == original

        first_title = vector["records"][0]["title"]
        expected.append(
            {
                "name": vector["name"],
                "identities": [vector["identity"], vector["identity"]],
                "deduplicatedTitles": [first_title],
                "mergedTitles": [first_title],
                "addedCount": 0,
            }
        )

    assert rendered["vectors"] == expected
    assert rendered["legacyIdentity"] == ["display", "open archive", "entry"]
    assert rendered["inheritedMetadataIdentity"] == [
        "display",
        "open archive",
        "entry",
    ]
    assert rendered["identitylessMetadataMerge"] == {
        "resultCount": 1,
        "addedCount": 0,
    }
    assert rendered["aliasChainTitles"] == ["First"]
    assert rendered["lateAliasBridgeTitles"] == ["First"]
    assert rendered["malformedBackslashUrl"] == ""


def test_task2_restored_browse_deduplicates_legacy_and_server_metadata_state():
    rendered = restored_browse_runtime()

    assert rendered["query"] == "restored archive"
    assert rendered["filters"] == {
        "min_date": "1990",
        "max_date": "2020",
        "content_type": "review",
        "sorting": "recent",
    }
    assert rendered["checkedSources"] == [
        "wikipedia",
        "whitelist_en.wikipedia.org",
    ]
    assert rendered["storedTitles"] == [
        "Restored first",
        "Restored second",
        "ﬀ",
        "Exponent numeric",
        "Port 080",
    ]
    assert rendered["initialTitles"] == ["Restored first"]
    assert rendered["renderedTitles"] == ["Restored first", "Restored second"]
    assert rendered["renderedThumbnails"] == [
        "https://serpapi.com/restored.jpg",
        "",
    ]
    assert rendered["storedThumbnails"] == [
        "https://serpapi.com/restored.jpg",
        "",
        "",
        "",
        "",
    ]
    assert rendered["storedSourceIds"][:2] == ["wiki-1", "archive-2"]
    assert rendered["storageWrites"] == 2
    assert rendered["upgradedVersion"] == 2
    assert rendered["initialButtonDisabled"] is False
    assert rendered["searchRequestCount"] == 0


def test_restored_v2_browse_clamps_cached_visibility_to_ten_ranks():
    rendered = max_rank_restored_browse_runtime()
    expected_titles = [f"wiki-{rank}" for rank in range(1, 11)]

    assert rendered["initialTitles"] == expected_titles
    assert rendered["afterLoadTitles"] == expected_titles
    assert rendered["loadMoreDisabled"] is True
    assert rendered["loadMoreText"] == "No more results."
    assert rendered["searchRequestCount"] == 0
    assert rendered["restoredGroupPage"] == 10


def test_browse_async_whitelist_render_upgrades_versionless_all_domain_state():
    browse = read_text("static/js/pages/browse.js")
    rendered = legacy_browse_runtime()

    assert "const BROWSE_STATE_VERSION = 2;" in browse
    assert rendered["checkedSources"] == ["wikipedia", "gbooks", "pubmed"]
    assert rendered["renderedTitles"] == ["Legacy result"]
    assert rendered["storageWrites"] == 1
    assert rendered["upgradedState"] == {
        "version": 2,
        "query": "legacy archive",
        "sources": ["wikipedia", "gbooks", "pubmed"],
        "filters": {
            "min_date": "1985",
            "max_date": "2015",
            "content_type": "article",
            "sorting": "title",
        },
        "results": [
            {
                "source_name": "Wikipedia",
                "source_id": "legacy-1",
                "source_url": "https://en.wikipedia.org/wiki/Archive",
                "title": "Legacy result",
                "thumb_url": "",
            }
        ],
        "groupedResults": {
            "wikipedia": [
                {
                    "source_name": "Wikipedia",
                    "source_id": "legacy-1",
                    "source_url": "https://en.wikipedia.org/wiki/Archive",
                    "title": "Legacy result",
                    "thumb_url": "",
                }
            ]
        },
        "sourceCounts": {},
        "groupPage": 1,
        "resultWindow": 10,
        "searchExhausted": False,
    }
    assert 'value="whitelist_en.wikipedia.org"' in rendered["whitelistMarkup"]


def test_task6_runtime_guards_catch_go_listener_and_unsaved_label_mutations():
    browse = read_text("static/js/pages/browse.js")
    listener = (
        "    goBtn.addEventListener('click', () => {\n"
        "        performSearch({ initGeneration });\n"
        "    });\n"
    )
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
    filters_menu = search_shell.select_one("#browseFiltersMenu")
    assert filters_menu is not None

    source_master = search_shell.select_one("#filterAllSources")
    assert source_master is not None
    assert source_master.get("type") == "checkbox"
    source_master_label = search_shell.select_one('label[for="filterAllSources"]')
    assert source_master_label is not None
    assert source_master_label.get_text(" ", strip=True) == "All sources"

    dedicated_sources = search_shell.select(
        "#filterWikipedia, #filterGBooks, #filterPubMed, #filterScholar"
    )
    assert len(dedicated_sources) == 4
    assert all("browse-source-checkbox" in node.get("class", ()) for node in dedicated_sources)
    assert "browse-source-checkbox" not in source_master.get("class", ())

    layout = page.select_one(".browse-results-layout.d-flex")
    sidebar = layout.select_one("#sidebarContainer.browse-sidebar")
    pane = layout.select_one(".browse-results-pane")
    assert layout.get("style") == "height: calc(100vh - 200px);"
    assert sidebar.get("style") == "width: 320px; min-width: 320px; overflow-y: auto;"
    assert {"border-end", "p-3", "flex-shrink-0"}.issubset(sidebar.get("class", ()))
    assert {"flex-grow-1", "p-3", "overflow-y-auto"}.issubset(pane.get("class", ()))
    assert pane.select_one("#resultsContainer") is not None

    expected_ids = {
        "searchInput",
        "goBtn",
        "filtersDropdown",
        "browseFiltersMenu",
        "filterAllSources",
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
    }
    assert expected_ids.issubset({tag.get("id") for tag in soup.select("[id]")})

    assert browse.count("fetch('/api/browse/search-all'") == 1
    assert browse.count("await fetchBrowseResults({") == 1
    assert "const nextWindow = resultWindow + 10;" not in browse
    assert "localStorage.setItem(BROWSE_STORAGE_KEY" in browse
    assert "localStorage.getItem(BROWSE_STORAGE_KEY" in browse
    assert "loadMoreBtn.addEventListener('click', () =>" in browse


def test_browse_has_no_google_programmable_search_assets_or_container():
    browse = read_text("static/js/pages/browse.js")
    css = read_text("static/css/custom.css")

    for obsolete in (
        "cse.google.com",
        "google-cse-script",
        "ensureGoogleCustomSearch",
        "googleCseContainer",
    ):
        assert obsolete not in browse

    assert ".gsc-" not in css


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
    assert_task_selectors_are_dark_scoped(
        css,
        ("archive-page-upload", "upload-content", "upload-panel", "upload-actions", "file-list-panel", "file-icon", "file-size"),
        frozenset(
            {
                (f"{LIGHT_GUARD} .upload-content",),
                (f"{LIGHT_GUARD} .upload-panel",),
                (f"{LIGHT_GUARD} .upload-actions",),
                (f"{LIGHT_GUARD} .file-list-panel",),
                (
                    f"{LIGHT_GUARD} .file-list-panel .card-header",
                    f"{LIGHT_GUARD} .file-list-panel .list-group-item",
                ),
                (f"{LIGHT_GUARD} .file-list-panel .flex-grow-1",),
                (f"{LIGHT_GUARD} .file-icon",),
                (f"{LIGHT_GUARD} .file-size",),
                (f"{LIGHT_GUARD} .archive-page-upload .illustration-compass",),
                (f"{LIGHT_GUARD} .archive-page-upload .illustration-sextant",),
                (f"{LIGHT_GUARD} .archive-page-upload > .illustration-flourish",),
                (f"{LIGHT_GUARD} .archive-page-upload > .illustration-sextant",),
                (f"{LIGHT_GUARD} .archive-page-upload > .illustration-compass",),
            }
        ),
        "Task 7",
        "a dark-only upload rule",
    )


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
            "message.role === 'agent'", "escapeHtml(message.text)",
            "studyHelperAI.chat(value, { workspaceId: currentWorkspaceId })",
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

    assert_task_selectors_are_dark_scoped(
        css,
        (
            "archive-page-workspace", "workspace-main-panel", "workspace-right-panel",
            "quick-note-input", "source-preview-shell", "source-preview-content",
            "workspace-tabs", "workspace-source-item", "workspace-source-name",
            "note-item", "note-icon-light", "note-icon-dark", "chat-messages",
            "chat-row-agent", "chat-row-user",
        ),
        frozenset({
            (".workspace-tabs .nav-link",),
            (
                f"{LIGHT_GUARD} .workspace-main-panel",
                f"{LIGHT_GUARD} .workspace-right-panel",
            ),
            (
                f"{LIGHT_GUARD} .workspace-main-panel .card-header",
                f"{LIGHT_GUARD} .workspace-right-panel .card-header",
            ),
            (f"{LIGHT_GUARD} .quick-note-input",),
            (f"{LIGHT_GUARD} .quick-note-input:focus",),
            (f"{LIGHT_GUARD} .source-preview-shell",),
            (f"{LIGHT_GUARD} .source-preview-content",),
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link",),
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link:hover",),
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link:focus-visible",),
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link.active",),
            (f"{LIGHT_GUARD} .workspace-source-item",),
            (f"{LIGHT_GUARD} .workspace-source-item h6",),
            (f"{LIGHT_GUARD} .workspace-source-item:hover",),
            (f"{LIGHT_GUARD} .workspace-source-item:focus-visible",),
            (f"{LIGHT_GUARD} .workspace-source-item.active",),
            (f"{LIGHT_GUARD} .workspace-source-name",),
            (f"{LIGHT_GUARD} .note-item",),
            (f"{LIGHT_GUARD} .note-icon-light",),
            (f"{LIGHT_GUARD} .note-icon-dark",),
            (f"{LIGHT_GUARD} .chat-messages",),
            (f"{LIGHT_GUARD} .chat-row-agent",),
            (f"{LIGHT_GUARD} .chat-row-user",),
            (
                f"{LIGHT_GUARD} .archive-page-home .illustration-books",
                f"{LIGHT_GUARD} .archive-page-browse .illustration-books",
                f"{LIGHT_GUARD} .archive-page-workspace .illustration-books",
            ),
            (
                f"{LIGHT_GUARD} .archive-page-home .illustration-flourish",
                f"{LIGHT_GUARD} .archive-page-browse .illustration-flourish",
                f"{LIGHT_GUARD} .archive-page-workspace .illustration-flourish",
            ),
            (
                f"{LIGHT_GUARD} .archive-page-workspace .workspace-main-panel",
                f"{LIGHT_GUARD} .archive-page-workspace .workspace-right-panel",
            ),
            (f"{LIGHT_GUARD} .archive-page-workspace .resizable-panel",),
            FORCED_COLORS_LIGHT_FOCUS_SELECTORS,
        }),
        "Task 8",
        "the existing neutral tab-radius rule or an exact Old Book light placement",
    )

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
        css,
        ("candle-glow",),
        frozenset({(f"{LIGHT_GUARD} .candle-glow",)}),
        "Task 9",
        "the exact Old Book non-dark display guard",
    )
    reduced = css_block_body_containing_selector(
        css,
        "@media (prefers-reduced-motion: reduce)",
        '[data-bs-theme="dark"] .candle-glow',
    )
    coarse = css_block_body(css, "@media (hover: none), (pointer: coarse)")
    assert css_rule_declarations(reduced, '[data-bs-theme="dark"] .candle-glow') == {
        "animation": "none"
    }
    assert css_rule_declarations(coarse, '[data-bs-theme="dark"] .candle-glow') == {
        "display": "none"
    }
    assert css.count("@media (prefers-reduced-motion: reduce)") == 2
    assert css.count("@media (hover: none), (pointer: coarse)") == 1
    keyframes = css_block_body(css, "@keyframes candle-flicker")
    frames = list(css_rules(keyframes))
    assert [rule[1]["opacity"] for rule in frames] == [
        "1", "0.94", "1", "0.9", "0.98", "0.93", "1", "0.95"
    ]
    assert all(set(declarations) == {"opacity"} for _, declarations in frames)


VIEWER_IMPORT_REPLACEMENTS = (
    (
        "import { showToast } from './toast.js';",
        "const { showToast } = globalThis.__viewerMocks;",
    ),
    (
        "import { createWorkspaceSelectElement, getSelectedWorkspaceId, clearWorkspaceCache } from './workspace-selector.js';",
        (
            "const { createWorkspaceSelectElement, getSelectedWorkspaceId, "
            "clearWorkspaceCache } = globalThis.__viewerMocks;"
        ),
    ),
)


VIEWER_RUNTIME_HARNESS = r"""
function invariant(condition, message) {
  if (!condition) throw new Error(message);
}

const scenario = "__SCENARIO__";
const innerHTMLWrites = [];
const scripts = [];
const resizeObservers = [];
const fetchCalls = [];

class FakeClassList {
  constructor(owner) {
    this.owner = owner;
  }
  values() {
    return new Set((this.owner.className || "").split(/\s+/).filter(Boolean));
  }
  add(...names) {
    const values = this.values();
    names.forEach((name) => values.add(name));
    this.owner.className = [...values].join(" ");
  }
  remove(...names) {
    const values = this.values();
    names.forEach((name) => values.delete(name));
    this.owner.className = [...values].join(" ");
  }
  contains(name) {
    return this.values().has(name);
  }
}

class FakeElement {
  constructor(tagName, id = "") {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.className = "";
    this.classList = new FakeClassList(this);
    this.dataset = {};
    this.style = {};
    this.onclick = null;
    this.disabled = false;
    this.value = "";
    this.href = "";
    this.src = "";
    this.srcdoc = "";
    this.target = "";
    this.rel = "";
    this.alt = "";
    this._innerHTML = "";
    this._textContent = "";
    this.onload = null;
    this.onerror = null;
    this.listeners = new Map();
  }
  set innerHTML(value) {
    this._innerHTML = String(value);
    this.children = [];
    innerHTMLWrites.push(this._innerHTML);
  }
  get innerHTML() {
    return this._innerHTML;
  }
  set textContent(value) {
    this._textContent = String(value ?? "");
    this.children = [];
  }
  get textContent() {
    return this._textContent;
  }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    if (this.tagName === "HEAD" && child.tagName === "SCRIPT") scripts.push(child);
    return child;
  }
  replaceChildren(...children) {
    this.children = [];
    this._innerHTML = "";
    this._textContent = "";
    children.forEach((child) => this.appendChild(child));
  }
  setAttribute(name, value) {
    const normalized = String(value);
    this.attributes.set(name, normalized);
    if (name === "id") this.id = normalized;
    if (name === "href") this.href = normalized;
    if (name === "src") this.src = normalized;
    if (name === "target") this.target = normalized;
    if (name === "rel") this.rel = normalized;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  querySelectorAll(selector) {
    const matches = [];
    const targetTag = selector.toUpperCase();
    const targetClass = selector.startsWith(".") ? selector.slice(1) : null;
    const targetId = selector.startsWith("#") ? selector.slice(1) : null;
    const visit = (node) => {
      for (const child of node.children) {
        if (
          (targetClass && child.classList.contains(targetClass)) ||
          (targetId && child.id === targetId) ||
          (!targetClass && !targetId && child.tagName === targetTag)
        ) {
          matches.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
  querySelector(selector) {
    const match = this.querySelectorAll(selector)[0];
    if (match) return match;
    if (
      selector.startsWith("#") &&
      this._innerHTML.includes(`id="${selector.slice(1)}"`)
    ) {
      const parsed = new FakeElement("select", selector.slice(1));
      this.appendChild(parsed);
      return parsed;
    }
    return null;
  }
  addEventListener(type, callback, options = {}) {
    const listeners = this.listeners.get(type) || [];
    listeners.push({ callback, once: options?.once === true });
    this.listeners.set(type, listeners);
  }
  removeEventListener(type, callback) {
    const listeners = this.listeners.get(type) || [];
    this.listeners.set(type, listeners.filter((listener) => listener.callback !== callback));
  }
  dispatchEvent(event) {
    const listeners = [...(this.listeners.get(event.type) || [])];
    listeners.forEach((listener) => {
      listener.callback.call(this, event);
      if (listener.once) this.removeEventListener(event.type, listener.callback);
    });
  }
}

function contains(root, target) {
  if (root === target) return true;
  return root.children.some((child) => contains(child, target));
}

function collectedText(root) {
  return [root.textContent, ...root.children.map(collectedText)].join(" ");
}

const viewerHeader = new FakeElement("div", "viewerHeader");
const viewerBody = new FakeElement("div", "viewerBody");
const addButton = new FakeElement("button", "addToWorkspaceBtn");
const offcanvas = new FakeElement("div", "viewerOffcanvas");
const byId = new Map([
  ["viewerHeader", viewerHeader],
  ["viewerBody", viewerBody],
  ["addToWorkspaceBtn", addButton],
  ["viewerOffcanvas", offcanvas],
]);

globalThis.document = {
  head: new FakeElement("head"),
  createElement(tagName) {
    return new FakeElement(tagName);
  },
  getElementById(id) {
    return byId.get(id) || null;
  },
};
globalThis.window = globalThis;
globalThis.bootstrap = {
  Offcanvas: class {
    constructor(element) {
      this.element = element;
      this.showCalls = 0;
      this.hideCalls = 0;
    }
    show() { this.showCalls += 1; }
    hide() { this.hideCalls += 1; }
  },
};
globalThis.ResizeObserver = class {
  constructor(callback) {
    this.callback = callback;
    this.disconnected = false;
    this.observed = null;
    resizeObservers.push(this);
  }
  observe(element) { this.observed = element; }
  disconnect() { this.disconnected = true; }
};
globalThis.__viewerMocks = {
  showToast() {},
  createWorkspaceSelectElement() {
    const select = document.createElement("select");
    select.value = "5";
    return select;
  },
  getSelectedWorkspaceId(select) { return Number(select?.value) || null; },
  clearWorkspaceCache() {},
};

async function flush() {
  for (let index = 0; index < 6; index += 1) await Promise.resolve();
}

function showViewerOffcanvas() {
  offcanvas.classList.add("show");
  offcanvas.dispatchEvent({ type: "shown.bs.offcanvas" });
}

function googleBook(id, overrides = {}) {
  return {
    id: 1,
    title: `Title ${id}`,
    description: `Description ${id}`,
    thumb_url: `https://books.google.com/cover-${id}.jpg`,
    source_name: "gbooks",
    source_id: id,
    source_url: `https://books.google.com/books?id=${id}`,
    accessInfo: {
      embeddable: true,
      webReaderLink: `https://books.google.com/books/reader?id=${id}`,
      viewability: "PARTIAL",
      accessViewStatus: "SAMPLE",
    },
    ...overrides,
  };
}

function installGoogleBooks() {
  const viewers = [];
  const loads = [];
  let apiCallback = null;
  let apiLoadCalls = 0;
  class DefaultViewer {
    constructor(container) {
      this.container = container;
      this.resizeCalls = 0;
      viewers.push(this);
    }
    load(identifier, notFound, success) {
      loads.push({ viewer: this, identifier, notFound, success });
    }
    resize() { this.resizeCalls += 1; }
  }
  globalThis.google = {
    books: {
      load() { apiLoadCalls += 1; },
      setOnLoadCallback(callback) { apiCallback = callback; },
      DefaultViewer,
    },
  };
  return {
    viewers,
    loads,
    get apiCallback() { return apiCallback; },
    get apiLoadCalls() { return apiLoadCalls; },
  };
}

const { openViewer } = await import(process.argv[1]);

if (scenario === "google_waits_for_offcanvas") {
  globalThis.fetch = async () => { throw new Error("Google Books must not use proxy fetch"); };
  const opening = openViewer(googleBook("wait-for-sidebar"));
  invariant(scripts.length === 0, "Google Books started before offcanvas shown");
  showViewerOffcanvas();
  await flush();
  invariant(scripts.length === 1, "Google Books did not start after offcanvas shown");
  scripts[0].onerror({ secret: "expected-test-stop" });
  await opening;
  process.stdout.write(JSON.stringify({ scriptCount: scripts.length }));
} else if (scenario === "google_timeout_fallback") {
  const timers = [];
  const clearedTimers = [];
  let openedTabs = 0;
  globalThis.setTimeout = (callback, delay) => {
    const timer = { id: timers.length + 1, callback, delay };
    timers.push(timer);
    return timer.id;
  };
  globalThis.clearTimeout = (timerId) => { clearedTimers.push(timerId); };
  globalThis.open = () => { openedTabs += 1; };
  globalThis.fetch = async () => { throw new Error("Google Books must not use proxy fetch"); };

  const item = googleBook("timeout-volume");
  const opening = openViewer(item);
  showViewerOffcanvas();
  await flush();
  invariant(scripts.length === 1, "timeout path did not start native loader");
  invariant(timers.length === 1, "Google Books timeout was not scheduled");
  invariant(timers[0].delay === 8000, "Google Books timeout was not eight seconds");
  timers[0].callback();
  await opening;

  const text = collectedText(viewerBody);
  const links = viewerBody.querySelectorAll("a");
  invariant(text.includes(item.title), "timeout fallback lost book metadata");
  invariant(text.includes("timed out"), "timeout fallback reason missing");
  invariant(links.length === 1, "timeout fallback link missing");
  invariant(openedTabs === 0, "timeout forcibly opened a new tab");
  process.stdout.write(JSON.stringify({
    delay: timers[0].delay,
    fallback: links[0].href,
    openedTabs,
    clearedTimers,
  }));
} else if (scenario === "google_serp_url_volume_id") {
  globalThis.fetch = async () => { throw new Error("Google Books must not use proxy fetch"); };
  const api = installGoogleBooks();
  const sourceUrl = "https://books.google.com/books?vid=ISBN123&id=serp-volume&dq=archive";
  const opening = openViewer(googleBook("legacy-id", {
    source_id: sourceUrl,
    source_url: sourceUrl,
    accessInfo: undefined,
  }));
  showViewerOffcanvas();
  await flush();
  invariant(api.loads.length === 1, "SerpAPI Google Books result did not open native viewer");
  invariant(api.loads[0].identifier === "serp-volume", "Google Books volume ID was not parsed from URL");
  api.loads[0].success();
  await opening;
  process.stdout.write(JSON.stringify({ identifier: api.loads[0].identifier }));
} else if (scenario === "google_success_race_resize") {
  globalThis.fetch = async () => { throw new Error("Google Books must not use proxy fetch"); };
  const staleBeforeLoad = openViewer(googleBook("stale-before-load"));
  const firstOpen = openViewer(googleBook("volume-one"));
  showViewerOffcanvas();
  await flush();
  invariant(scripts.length === 1, "first opening did not append one loader script");
  invariant(scripts[0].src === "https://www.google.com/books/jsapi.js", "wrong loader URL");

  const api = installGoogleBooks();
  scripts[0].onload();
  invariant(api.apiLoadCalls === 1, "google.books.load was not called once");
  invariant(typeof api.apiCallback === "function", "Google load callback missing");
  api.apiCallback();
  await flush();
  invariant(api.loads.length === 1, "first DefaultViewer.load missing");
  invariant(api.loads[0].identifier === "volume-one", "volume ID did not reach viewer.load");
  api.loads[0].success();
  await firstOpen;
  await staleBeforeLoad;
  invariant(resizeObservers.length === 1, "success did not attach one ResizeObserver");
  resizeObservers[0].callback();
  invariant(api.viewers[0].resizeCalls === 1, "ResizeObserver did not call viewer.resize");

  const slowOpen = openViewer(googleBook("slow-volume"));
  await flush();
  const slowLoad = api.loads.at(-1);
  invariant(slowLoad.identifier === "slow-volume", "slow viewer did not start");
  invariant(resizeObservers[0].disconnected, "prior ResizeObserver was not disconnected");

  const newestOpen = openViewer(googleBook("newest-volume"));
  await flush();
  const newestLoad = api.loads.at(-1);
  invariant(newestLoad.identifier === "newest-volume", "newest viewer did not start");
  newestLoad.success();
  await newestOpen;
  const newestCanvas = newestLoad.viewer.container;
  invariant(contains(viewerBody, newestCanvas), "newest canvas not rendered");

  slowLoad.notFound();
  await slowOpen;
  invariant(contains(viewerBody, newestCanvas), "slow opening replaced newer viewer");
  invariant(scripts.length === 1, "two openings appended more than one script");
  invariant(resizeObservers.filter((observer) => !observer.disconnected).length === 1,
    "more than one ResizeObserver remained active");
  process.stdout.write(JSON.stringify({
    identifiers: api.loads.map((load) => load.identifier),
    scriptCount: scripts.length,
    activeObservers: resizeObservers.filter((observer) => !observer.disconnected).length,
  }));
} else if (scenario === "fallback_metadata_and_unsafe_links") {
  globalThis.fetch = async () => { throw new Error("fallback must not use proxy fetch"); };
  const unavailable = googleBook("blocked-volume", {
    accessInfo: {
      embeddable: false,
      webReaderLink: "https://books.google.com/books/reader?id=blocked-volume",
      viewability: "NO_PAGES",
      accessViewStatus: "NONE",
    },
  });
  const unavailableOpening = openViewer(unavailable);
  showViewerOffcanvas();
  await unavailableOpening;
  const unavailableText = collectedText(viewerBody);
  const unavailableLinks = viewerBody.querySelectorAll("a");
  invariant(unavailableText.includes(unavailable.title), "fallback title missing");
  invariant(unavailableText.includes(unavailable.description), "fallback description missing");
  invariant(unavailableText.includes("NO_PAGES"), "fallback preview status missing");
  invariant(unavailableText.includes("embedded preview"), "non-embeddable reason missing");
  invariant(unavailableLinks.length === 1, "safe fallback link missing");
  invariant(unavailableLinks[0].href === unavailable.accessInfo.webReaderLink,
    "webReaderLink was not preferred");

  const sourceFallback = googleBook("source-fallback", {
    accessInfo: {
      embeddable: false,
      webReaderLink: "javascript:alert(1)",
      viewability: "PARTIAL",
      accessViewStatus: "SAMPLE",
    },
  });
  await openViewer(sourceFallback);
  const sourceFallbackLinks = viewerBody.querySelectorAll("a");
  invariant(sourceFallbackLinks.length === 1, "safe source fallback link missing");
  invariant(sourceFallbackLinks[0].href === sourceFallback.source_url,
    "safe source URL did not replace unsafe webReaderLink");

  const noIdAttack = '<img src=x onerror=globalThis.pwned=true>';
  await openViewer(googleBook("unused", {
    title: noIdAttack,
    description: noIdAttack,
    thumb_url: "javascript:alert(1)",
    source_id: "",
    source_url: "javascript://books.google.com/alert(1)",
    accessInfo: {
      embeddable: true,
      webReaderLink: "data:text/html,unsafe",
      viewability: "PARTIAL",
      accessViewStatus: "SAMPLE",
    },
  }));
  const noIdText = collectedText(viewerBody);
  invariant(noIdText.includes(noIdAttack), "hostile metadata was not assigned as text");
  invariant(noIdText.includes("volume ID"), "missing-ID reason absent");
  invariant(viewerBody.querySelectorAll("a").length === 0, "unsafe fallback link survived");
  invariant(viewerBody.querySelectorAll("img").length === 0, "unsafe cover survived");
  invariant(!innerHTMLWrites.some((value) => value.includes(noIdAttack)),
    "provider metadata reached innerHTML");
  invariant(scripts.length === 0, "fallback-only openings loaded Google script");
  process.stdout.write(JSON.stringify({ unavailableText, noIdText, scriptCount: scripts.length }));
} else if (scenario === "script_error") {
  globalThis.fetch = async () => { throw new Error("Google Books must not proxy"); };
  const item = googleBook("script-error");
  const opening = openViewer(item);
  showViewerOffcanvas();
  await flush();
  invariant(scripts.length === 1, "script-error path did not append loader");
  scripts[0].onerror({ secret: "raw-script-exception" });
  await opening;
  const text = collectedText(viewerBody);
  invariant(text.includes(item.title), "script-error fallback lost title");
  invariant(text.includes("preview service"), "script-error reason not user safe");
  invariant(!text.includes("raw-script-exception"), "raw script exception exposed");
  process.stdout.write(JSON.stringify({ text, scriptCount: scripts.length }));
} else if (scenario === "viewer_load_error") {
  globalThis.fetch = async () => { throw new Error("Google Books must not proxy"); };
  const item = googleBook("load-error");
  const opening = openViewer(item);
  showViewerOffcanvas();
  await flush();
  const api = installGoogleBooks();
  scripts[0].onload();
  api.apiCallback();
  await flush();
  invariant(api.loads.length === 1, "load-error viewer did not call load");
  api.loads[0].notFound({ secret: "raw-load-exception" });
  await opening;
  const text = collectedText(viewerBody);
  invariant(text.includes(item.title), "load-error fallback lost title");
  invariant(text.includes("embedded preview"), "load-error reason not user safe");
  invariant(!text.includes("raw-load-exception"), "raw load exception exposed");
  process.stdout.write(JSON.stringify({ text, identifier: api.loads[0].identifier }));
} else if (scenario === "wikipedia_iframe") {
  const attack = '<img src=x onerror=globalThis.pwned=true>';
  const sourceUrl = `https://en.wikipedia.org/wiki/Test?probe=${attack}`;
  globalThis.fetch = async (url) => {
    fetchCalls.push(url);
    return { json: async () => ({ status: true, mode: "iframe", html: "<article>Wiki</article>" }) };
  };
  await openViewer({
    id: 3,
    title: attack,
    description: "Wikipedia description",
    source_name: `Wikipedia ${attack}`,
    source_id: "wiki-3",
    source_url: sourceUrl,
  });
  await flush();
  const iframe = viewerBody.querySelector("iframe");
  invariant(fetchCalls.length === 1, "Wikipedia did not make one proxy request");
  invariant(fetchCalls[0] === `/api/proxy/source?url=${encodeURIComponent(sourceUrl)}`,
    "Wikipedia proxy URL changed");
  invariant(iframe?.srcdoc === "<article>Wiki</article>", "Wikipedia iframe srcdoc changed");
  const sandbox = iframe?.getAttribute("sandbox") || "";
  invariant(sandbox.includes("allow-popups"), "Wikipedia direct links cannot open");
  invariant(!sandbox.includes("allow-scripts"), "Wikipedia iframe permits scripts");
  invariant(!sandbox.includes("allow-same-origin"), "Wikipedia iframe retains source origin");
  invariant(collectedText(viewerHeader).includes(attack), "provider metadata not assigned as text");
  invariant(!innerHTMLWrites.some((value) => value.includes(attack)),
    "provider metadata reached innerHTML");
  process.stdout.write(JSON.stringify({ fetchCalls, srcdoc: iframe.srcdoc, sandbox }));
} else if (scenario === "reader_iframe") {
  globalThis.fetch = async (url) => {
    fetchCalls.push(url);
    return { json: async () => ({ status: true, mode: "reader", html: "<article>Reader</article>" }) };
  };
  await openViewer({
    id: 5,
    title: "Reader source",
    description: "Reader description",
    source_name: "NHS",
    source_id: "reader-5",
    source_url: "https://www.nhs.uk/conditions/test",
  });
  await flush();
  const iframe = viewerBody.querySelector("iframe");
  const sandbox = iframe?.getAttribute("sandbox") || "";
  invariant(iframe?.srcdoc === "<article>Reader</article>", "reader HTML did not use srcdoc");
  invariant(viewerBody.classList.contains("viewer-mode-reader"), "reader mode class missing");
  invariant(
    viewerBody.querySelectorAll(".viewer-reader").every((node) => node.tagName === "IFRAME"),
    "reader HTML reached a non-iframe container",
  );
  invariant(sandbox.includes("allow-popups"), "reader direct links cannot open");
  invariant(!sandbox.includes("allow-scripts"), "reader iframe permits scripts");
  invariant(!sandbox.includes("allow-same-origin"), "reader iframe retains source origin");
  process.stdout.write(JSON.stringify({ srcdoc: iframe.srcdoc, sandbox }));
} else if (scenario === "proxy_error_safety") {
  const attack = '<img src=x onerror=globalThis.pwned=true>';
  const fallbackUrl = "https://en.wikipedia.org/wiki/Safe_fallback";
  globalThis.fetch = async (url) => {
    fetchCalls.push(url);
    return {
      json: async () => ({ status: false, error: attack, fallback_url: fallbackUrl }),
    };
  };
  await openViewer({
    id: 4,
    title: attack,
    description: "Proxy description",
    source_name: attack,
    source_id: "proxy-4",
    source_url: "https://en.wikipedia.org/wiki/Source",
  });
  await flush();
  const bodyText = collectedText(viewerBody);
  const links = viewerBody.querySelectorAll("a");
  invariant(bodyText.includes(attack), "proxy error was not assigned as text");
  invariant(links.length === 1 && links[0].href === fallbackUrl,
    "safe proxy fallback was not assigned through href");
  invariant(links[0].target === "_blank" && links[0].rel === "noopener noreferrer",
    "external fallback protections missing");
  invariant(!innerHTMLWrites.some((value) => value.includes(attack)),
    "proxy error reached innerHTML");
  process.stdout.write(JSON.stringify({ bodyText, fallback: links[0].href }));
} else {
  throw new Error(`unknown viewer scenario: ${scenario}`);
}
"""


def viewer_runtime(scenario: str, source: str | None = None) -> dict:
    harness = VIEWER_RUNTIME_HARNESS.replace("__SCENARIO__", scenario)
    return run_task6_module_harness(
        source or read_text("static/js/viewer.js"),
        VIEWER_IMPORT_REPLACEMENTS,
        harness,
        f"viewer {scenario}",
    )


def test_google_books_viewer_loads_volume_once_and_rejects_stale_openings():
    rendered = viewer_runtime("google_success_race_resize")

    assert rendered == {
        "identifiers": ["volume-one", "slow-volume", "newest-volume"],
        "scriptCount": 1,
        "activeObservers": 1,
    }


def test_google_books_viewer_parses_serpapi_result_url_without_access_metadata():
    assert viewer_runtime("google_serp_url_volume_id") == {"identifier": "serp-volume"}


def test_google_books_waits_for_visible_offcanvas_before_loading_viewer():
    rendered = viewer_runtime("google_waits_for_offcanvas")

    assert rendered == {"scriptCount": 1}


def test_google_books_timeout_uses_safe_sidebar_fallback_without_forced_popup():
    rendered = viewer_runtime("google_timeout_fallback")

    assert rendered["delay"] == 8000
    assert rendered["fallback"].startswith("https://books.google.com/")
    assert rendered["openedTabs"] == 0


def test_google_books_fallback_renders_metadata_without_unsafe_links():
    rendered = viewer_runtime("fallback_metadata_and_unsafe_links")

    assert "Title blocked-volume" in rendered["unavailableText"]
    assert "NO_PAGES" in rendered["unavailableText"]
    assert "volume ID" in rendered["noIdText"]
    assert rendered["scriptCount"] == 0


@pytest.mark.parametrize("scenario", ("script_error", "viewer_load_error"))
def test_google_books_failures_render_safe_metadata_fallback(scenario):
    rendered = viewer_runtime(scenario)

    assert "Title" in rendered["text"]
    assert "raw-" not in rendered["text"]


def test_viewer_keeps_wikipedia_proxy_iframe_behavior():
    rendered = viewer_runtime("wikipedia_iframe")

    assert rendered["srcdoc"] == "<article>Wiki</article>"
    assert rendered["fetchCalls"][0].startswith("/api/proxy/source?url=")
    assert "allow-popups" in rendered["sandbox"]
    assert "allow-scripts" not in rendered["sandbox"]
    assert "allow-same-origin" not in rendered["sandbox"]
    assert "allow-forms" not in rendered["sandbox"]
    assert "allow-top-navigation" not in rendered["sandbox"]


def test_viewer_renders_reader_proxy_html_in_the_same_restricted_iframe_boundary():
    rendered = viewer_runtime("reader_iframe")

    assert rendered["srcdoc"] == "<article>Reader</article>"
    assert "allow-popups" in rendered["sandbox"]
    assert "allow-scripts" not in rendered["sandbox"]
    assert "allow-same-origin" not in rendered["sandbox"]
    assert "allow-forms" not in rendered["sandbox"]
    assert "allow-top-navigation" not in rendered["sandbox"]


def test_workspace_proxy_srcdoc_iframe_omits_script_and_same_origin_privileges():
    workspace = read_text("static/js/pages/workspace.js")
    iframe_factory = workspace[
        workspace.index("function createPreviewIframe()") : workspace.index(
            "function renderPreviewNotice("
        )
    ]
    proxy_branch = workspace[
        workspace.index("fetch(`/api/proxy/source?") : workspace.index(
            "function loadWorkspaceNotes()"
        )
    ]
    sandbox = "iframe.setAttribute('sandbox', WORKSPACE_IFRAME_SANDBOX);"

    assert (
        "const WORKSPACE_IFRAME_SANDBOX = "
        "'allow-popups allow-popups-to-escape-sandbox';"
    ) in workspace
    assert sandbox in iframe_factory
    assert proxy_branch.index("const iframe = createPreviewIframe()") < proxy_branch.index(
        "iframe.srcdoc = result.html"
    )
    assert "allow-scripts" not in iframe_factory
    assert "allow-same-origin" not in iframe_factory


def test_workspace_runtime_proxies_remote_html_and_sandboxes_every_iframe_before_src():
    workspace = read_text("static/js/pages/workspace.js")
    rendered = workspace_preview_runtime()

    assert rendered["fetchCalls"] == [
        "/api/proxy/source?url=https%3A%2F%2Fen.wikipedia.org%2Farchive.html",
        "/api/proxy/source?url=https%3A%2F%2Fen.wikipedia.org%2Farchive.htm",
        "/api/proxy/source?url=https%3A%2F%2Fen.wikipedia.org%2Fno-preview",
    ]
    assert rendered["remoteHtml"]["src"] == ""
    assert rendered["remoteHtml"]["srcdoc"] == "<article>Remote HTML</article>"
    assert rendered["remoteHtml"]["events"].index("attr:sandbox") < rendered[
        "remoteHtml"
    ]["events"].index("srcdoc")
    assert rendered["remoteHtm"]["src"] == ""
    assert rendered["remoteHtm"]["srcdoc"] == "<article>Remote HTM</article>"
    assert rendered["remoteHtm"]["events"].index("attr:sandbox") < rendered[
        "remoteHtm"
    ]["events"].index("srcdoc")
    assert rendered["directPdf"]["src"] == "https://en.wikipedia.org/archive.pdf"
    assert rendered["directPdf"]["events"].index("attr:sandbox") < rendered[
        "directPdf"
    ]["events"].index("src")
    for preview in (
        rendered["remoteHtml"],
        rendered["remoteHtm"],
        rendered["directPdf"],
    ):
        assert "allow-scripts" not in preview["sandbox"]
        assert "allow-same-origin" not in preview["sandbox"]
        assert "allow-forms" not in preview["sandbox"]
        assert "allow-top-navigation" not in preview["sandbox"]
    assert "javascript:" not in rendered["fallbackHtml"]
    assert 'href="https://en.wikipedia.org/no-preview"' in rendered["fallbackHtml"]
    assert "javascript:" not in rendered["invalidHtml"]
    assert "href=" not in rendered["invalidHtml"]
    assert 'href="${escapeHtml(item.source_url)}"' not in workspace
    assert 'href="${escapeHtml(sourceUrl)}"' in workspace


def test_viewer_assigns_provider_and_proxy_values_without_html_interpolation():
    rendered = viewer_runtime("proxy_error_safety")

    assert "<img src=x" in rendered["bodyText"]
    assert rendered["fallback"] == "https://en.wikipedia.org/wiki/Safe_fallback"


def test_google_books_viewer_css_replaces_obsolete_proxy_panel():
    css = read_text("static/css/custom.css")

    assert ".proxy-google-books" not in css
    viewer = css_rule_group_declarations(css, (".google-books-viewer",))
    canvas = css_rule_group_declarations(css, (".google-books-viewer-canvas",))
    fallback = css_rule_group_declarations(css, (".google-books-fallback",))
    assert viewer["height"] == "100%"
    assert viewer["display"] in {"flex", "grid"}
    assert canvas["width"] == "100%"
    assert canvas["background"] == "var(--bs-body-bg)"
    assert canvas["border"].endswith("var(--bs-border-color)")
    assert fallback["background"] == "var(--bs-tertiary-bg)"
    assert fallback["color"] == "var(--bs-body-color)"
