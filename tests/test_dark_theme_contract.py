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
