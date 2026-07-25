from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "static" / "css"
TEXTURE_DIR = ROOT / "static" / "img" / "textures"

CSS_FILES = sorted(CSS_DIR.glob("*.css"))


def _all_css() -> str:
    """Concatenate all CSS files for contract testing."""
    parts = []
    for f in CSS_FILES:
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


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
        assert all(f.exists() for f in CSS_FILES)

    def test_contains_selector(self, theme_name, selector, colour_tokens, texture_files):
        assert selector in _all_css()

    def test_contains_colour_tokens(self, theme_name, selector, colour_tokens, texture_files):
        css = _all_css()
        for token in colour_tokens:
            assert token in css

    def test_contains_font_tokens(self, theme_name, selector, colour_tokens, texture_files):
        css = _all_css()
        assert "--font-display" in css
        assert "--font-body" in css

    def test_texture_images_exist(self, theme_name, selector, colour_tokens, texture_files):
        for tex in texture_files:
            assert (TEXTURE_DIR / tex).exists()
