from html.parser import HTMLParser
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest


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


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            self.links.append(dict(attrs))


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


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

    declarations = {}
    for raw_declaration in rule_body.split(";"):
        raw_declaration = raw_declaration.strip()
        if not raw_declaration:
            continue
        property_name, value = raw_declaration.split(":", 1)
        property_name = property_name.strip()
        assert property_name not in declarations, f"duplicate {property_name!r} in {selector!r}"
        declarations[property_name] = " ".join(value.split())
    return declarations


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
    assert css_rule_declarations(css, DARK_ROOT_SELECTOR) == EXPECTED_DARK_ROOT_DECLARATIONS


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
    body = css_rule_declarations(read_text("static/css/custom.css"), DARK_BODY_SELECTOR)
    assert "font-size" not in body


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
