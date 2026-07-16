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


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


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


def test_dark_theme_foundation_contains_exact_tokens_and_bootstrap_mapping():
    css = read_text("static/css/custom.css")
    required = (
        "--bg-950: #0A0A0A",
        "--bg-900: #14100B",
        "--surface-800: #22170B",
        "--surface-700: #2E1F0F",
        "--surface-600: #3D2914",
        "--surface-500: #4D3319",
        "--gold-100: #EDD9B5",
        "--gold-300: #C9A876",
        "--gold-500: #A9824F",
        "--gold-700: #8A6635",
        "--gold-900: #5C4423",
        "--text-primary: #E7E1DA",
        "--text-secondary: #A69A8C",
        "--text-disabled: #6E6459",
        "--danger-rust: #9C6242",
        "--info-slate: #6E87A6",
        "--success-verdigris: #6E9B7C",
        "--bs-primary: var(--gold-300)",
        "--bs-primary-rgb: 201, 168, 118",
        "--bs-secondary-rgb: 61, 41, 20",
        "--font-display: \"Cinzel\"",
        "--font-body: \"Crimson Pro\"",
    )
    for declaration in required:
        assert declaration in css
    assert '[data-bs-theme="dark"] body' in css
    assert "radial-gradient(ellipse 60% 40% at 50% 0%" in css


def test_layout_loads_only_the_approved_dark_theme_fonts():
    layout = read_text("templates/layout.html")
    assert "family=Cinzel:wght@600" in layout
    assert "family=Crimson+Pro:wght@400;600" in layout


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
