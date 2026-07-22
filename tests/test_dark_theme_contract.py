import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dark_theme_css_exists():
    assert (ROOT / "static" / "css" / "custom.css").exists()


def test_dark_theme_contains_selector():
    css = (ROOT / "static" / "css" / "custom.css").read_text(encoding="utf-8")
    assert '[data-bs-theme="dark"]' in css


def test_dark_theme_contains_colour_tokens():
    css = (ROOT / "static" / "css" / "custom.css").read_text(encoding="utf-8")
    assert "--bg-950" in css
    assert "--gold-300" in css
    assert "--text-primary" in css
    assert "--surface-800" in css


def test_dark_theme_contains_font_tokens():
    css = (ROOT / "static" / "css" / "custom.css").read_text(encoding="utf-8")
    assert "--font-display" in css
    assert "--font-body" in css


def test_dark_theme_texture_images_exist():
    texture_dir = ROOT / "static" / "img" / "textures"
    assert (texture_dir / "leather-texture.png").exists()
    assert (texture_dir / "wood-texture.png").exists()
