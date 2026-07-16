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
            "color": "var(--gold-300)",
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
            "color": "var(--gold-100)",
        },
    ),
    (
        ('[data-bs-theme="dark"] .icon-button-danger:hover',),
        {"color": "var(--danger-rust)"},
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


def qualified_css_selectors(css: str, parent_selectors: tuple[str, ...] = ()):
    for header, body in css_rule_blocks(css):
        if header.startswith("@"):
            yield from qualified_css_selectors(body, parent_selectors)
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

        yield from selectors
        yield from qualified_css_selectors(body, selectors)


def semantic_selector_targets_task3_class(selector) -> bool:
    if any(name in TASK3_DARK_ONLY_CLASSES for name in selector.classes):
        return True

    for attribute in selector.attributes:
        if attribute.attribute != "class" or attribute.pattern is None:
            continue
        if any(attribute.pattern.fullmatch(name) for name in TASK3_DARK_ONLY_CLASSES):
            return True

    for nested_selector_list in selector.selectors:
        if nested_selector_list.is_not:
            continue
        if any(
            semantic_selector_targets_task3_class(nested_selector)
            for nested_selector in nested_selector_list.selectors
        ):
            return True

    return any(
        semantic_selector_targets_task3_class(relation)
        for relation in selector.relation.selectors
    )


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
