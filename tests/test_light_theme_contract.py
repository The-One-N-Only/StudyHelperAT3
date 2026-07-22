import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_light_theme_css_exists():
    assert (ROOT / "static" / "css" / "custom.css").exists()


def test_light_theme_contains_guard_selector():
    css = (ROOT / "static" / "css" / "custom.css").read_text(encoding="utf-8")
    assert ':root:not([data-bs-theme="dark"])' in css


def test_light_theme_contains_colour_tokens():
    css = (ROOT / "static" / "css" / "custom.css").read_text(encoding="utf-8")
    assert "--paper-50" in css
    assert "--ink-900" in css
    assert "--rubric-500" in css
    assert "--gilt-500" in css


def test_light_theme_contains_font_tokens():
    css = (ROOT / "static" / "css" / "custom.css").read_text(encoding="utf-8")
    assert "--font-display" in css
    assert "--font-body" in css


def test_light_theme_texture_images_exist():
    texture_dir = ROOT / "static" / "img" / "textures"
    assert (texture_dir / "leather-texture-light.png").exists()
    assert (texture_dir / "wood-texture-light.png").exists()
