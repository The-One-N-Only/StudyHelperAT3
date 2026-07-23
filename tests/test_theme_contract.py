import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "static" / "css" / "custom.css"
TEXTURE_DIR = ROOT / "static" / "img" / "textures"


THEMES = [
    (
        "dark",
        '[data-bs-theme="dark"]',
        ["--bg-950", "--gold-300", "--text-primary", "--surface-800"],
        ["leather-texture.png", "wood-texture.png"],
    ),
    (
        "light",
        ':root:not([data-bs-theme="dark"])',
        ["--paper-50", "--ink-900", "--rubric-500", "--gilt-500"],
        ["leather-texture-light.png", "wood-texture-light.png"],
    ),
]


@pytest.mark.parametrize("theme_name,selector,colour_tokens,texture_files", THEMES)
class TestThemeContract:

    def test_css_exists(self, theme_name, selector, colour_tokens, texture_files):
        assert CSS.exists()

    def test_contains_selector(self, theme_name, selector, colour_tokens, texture_files):
        css = CSS.read_text(encoding="utf-8")
        assert selector in css

    def test_contains_colour_tokens(self, theme_name, selector, colour_tokens, texture_files):
        css = CSS.read_text(encoding="utf-8")
        for token in colour_tokens:
            assert token in css

    def test_contains_font_tokens(self, theme_name, selector, colour_tokens, texture_files):
        css = CSS.read_text(encoding="utf-8")
        assert "--font-display" in css
        assert "--font-body" in css

    def test_texture_images_exist(self, theme_name, selector, colour_tokens, texture_files):
        for tex in texture_files:
            assert (TEXTURE_DIR / tex).exists()
