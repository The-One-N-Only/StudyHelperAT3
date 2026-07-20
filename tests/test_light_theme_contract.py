from colorsys import hls_to_rgb
from hashlib import sha256
from pathlib import Path
import re
import struct
import zlib

import pytest


ROOT = Path(__file__).resolve().parents[1]
LIGHT_SPEC_SHA256 = "4dda210b8ea4e43c7ecb17750cd81b1c8dc9468f8324243367d0789ad13980d8"
LIGHT_TEXTURE_NAMES = (
    "leather-texture-light.png",
    "wood-texture-light.png",
)
LIGHT_TEXTURE_CONTRACTS = {
    "leather-texture-light.png": {
        "dimensions": (760, 760),
        "max_bytes": 1_400_000,
    },
    "wood-texture-light.png": {
        "dimensions": (576, 360),
        "max_bytes": 550_000,
    },
}
LIGHT_TEXTURE_TOTAL_MAX_BYTES = 1_900_000
DARK_TEXTURE_NAMES = (
    "leather-texture.png",
    "wood-texture.png",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DARK_CSS_MARKER = "/* Candlelit Archive: dark theme foundation */"
DARK_CSS_SHA256 = "37388ea3aeb7532b74946b67480cec788ee6117b1a65bc5f4486017b4b45ce79"
LIGHT_GUARD = ':root:not([data-bs-theme="dark"])'
CSS_TOKEN_PATTERN = re.compile(
    r'/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r"\\(?:[0-9a-fA-F]{1,6}[ \t\r\n\f]?|[^\r\n\f])|[{};,()\[\]]",
    flags=re.DOTALL,
)
EXPECTED_LIGHT_ROOT_DECLARATIONS = {
    "--paper-50": "#EEE6DD",
    "--paper-100": "#E2D5C6",
    "--paper-200": "#D4C2AB",
    "--paper-300": "#C6AE90",
    "--paper-400": "#B79871",
    "--paper-500": "#A98456",
    "--ink-900": "#36261B",
    "--ink-700": "#654834",
    "--ink-500": "#9C6E4F",
    "--gilt-900": "#925D07",
    "--gilt-700": "#BA7508",
    "--gilt-500": "#E18E0A",
    "--gilt-300": "#F5A423",
    "--gilt-100": "#F8BB59",
    "--rubric-700": "#782C21",
    "--rubric-500": "#98372A",
    "--rubric-50": "#F4DBD7",
    "--folio-blue": "#4A7FA5",
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
    "--shadow-parchment-raised": (
        "0 2px 10px 0 hsl(28 35% 50% / 0.18), "
        "0 0 0 1px hsl(33 30% 60% / 0.12)"
    ),
    "--shadow-gilt-glow": (
        "0 0 0 2px var(--gilt-900), "
        "0 0 12px 1px hsl(37 85% 55% / 0.18)"
    ),
    "--z-bg-base": "0",
    "--z-bg-illustration": "1",
    "--z-content": "10",
    "--z-overlay": "50",
    "--bs-body-bg": "var(--paper-50)",
    "--bs-body-color": "var(--ink-900)",
    "--bs-secondary-color": "var(--ink-700)",
    "--bs-border-color": "hsl(33 30% 72% / 0.55)",
    "--bs-tertiary-bg": "var(--paper-100)",
    "--bs-card-bg": "var(--paper-200)",
    "--bs-offcanvas-bg": "var(--paper-100)",
    "--bs-primary": "var(--rubric-500)",
    "--bs-primary-rgb": "152, 55, 42",
    "--bs-secondary": "var(--paper-400)",
    "--bs-secondary-rgb": "183, 152, 113",
    "--bs-danger": "var(--rubric-700)",
    "--bs-link-color": "var(--ink-700)",
    "--bs-link-hover-color": "var(--rubric-700)",
    "--bs-body-font-family": "var(--font-body)",
}
EXPECTED_LIGHT_MATERIALS = {
    (".surface-wood",): {
        "background-color": "var(--paper-100)",
        "background-image": (
            "linear-gradient(var(--paper-100), var(--paper-100)), "
            'url("/static/img/textures/wood-texture-light.png")'
        ),
        "background-blend-mode": "multiply",
        "background-repeat": "repeat",
        "background-size": "auto, 180px",
        "border": "1px solid hsl(33 30% 65% / 0.45)",
        "border-radius": "var(--radius-panel)",
        "box-shadow": "var(--shadow-parchment-raised)",
    },
    (".btn-secondary-leather",): {
        "background-color": "var(--paper-200)",
        "background-image": (
            "linear-gradient(rgb(226 213 198 / 0.72), "
            "rgb(226 213 198 / 0.72)), "
            'url("/static/img/textures/leather-texture-light.png")'
        ),
        "background-blend-mode": "normal",
        "background-repeat": "repeat, repeat",
        "background-size": "auto, 380px",
        "border": "1px solid hsl(33 30% 60% / 0.50)",
        "border-radius": "var(--radius-button)",
        "color": "var(--ink-900)",
    },
}
EXPECTED_LIGHT_ILLUSTRATIONS = {
    ".illustration-compass": (
        'url("/static/img/illustrations/compass-rose.svg")',
        "0.10",
    ),
    ".illustration-sextant": (
        'url("/static/img/illustrations/sextant.svg")',
        "0.09",
    ),
    ".illustration-books": (
        'url("/static/img/illustrations/stacked-books.svg")',
        "0.13",
    ),
    ".illustration-open-book": (
        'url("/static/img/illustrations/open-book.svg")',
        "0.12",
    ),
    ".illustration-flourish": (
        'url("/static/img/illustrations/scrollwork-flourish.svg")',
        "0.10",
    ),
}
EXPECTED_LIGHT_PRIMARY_BUTTON_STATES = {
    "--bs-btn-active-bg": "var(--rubric-700)",
    "--bs-btn-active-border-color": "transparent",
    "--bs-btn-active-color": "var(--paper-50)",
    "--bs-btn-active-shadow": "none",
    "--bs-btn-bg": "var(--rubric-500)",
    "--bs-btn-border-color": "transparent",
    "--bs-btn-color": "var(--paper-50)",
    "--bs-btn-disabled-bg": "var(--rubric-500)",
    "--bs-btn-disabled-border-color": "transparent",
    "--bs-btn-disabled-color": "var(--paper-50)",
    "--bs-btn-disabled-opacity": "0.65",
    "--bs-btn-focus-shadow-rgb": "146, 93, 7",
    "--bs-btn-hover-bg": "var(--rubric-700)",
    "--bs-btn-hover-border-color": "transparent",
    "--bs-btn-hover-color": "var(--paper-50)",
    "background-image": "linear-gradient(hsl(0 0% 100% / 0.12), transparent 40%)",
    "border-radius": "var(--radius-button)",
}
EXPECTED_LIGHT_WOOD_BUTTON_STATES = {
    "--bs-btn-active-bg": "var(--paper-300)",
    "--bs-btn-active-border-color": "var(--gilt-900)",
    "--bs-btn-active-color": "var(--ink-900)",
    "--bs-btn-active-shadow": "none",
    "--bs-btn-bg": "var(--paper-200)",
    "--bs-btn-border-color": "hsl(33 30% 60% / 0.50)",
    "--bs-btn-color": "var(--ink-900)",
    "--bs-btn-disabled-bg": "var(--paper-200)",
    "--bs-btn-disabled-border-color": "hsl(33 30% 60% / 0.50)",
    "--bs-btn-disabled-color": "var(--ink-700)",
    "--bs-btn-disabled-opacity": "0.65",
    "--bs-btn-focus-shadow-rgb": "146, 93, 7",
    "--bs-btn-hover-bg": "var(--paper-200)",
    "--bs-btn-hover-border-color": "var(--gilt-900)",
    "--bs-btn-hover-color": "var(--ink-900)",
}
EXPECTED_LIGHT_SECONDARY_BUTTON_STATES = {
    "--bs-btn-active-bg": "var(--paper-400)",
    "--bs-btn-active-border-color": "var(--gilt-900)",
    "--bs-btn-active-color": "var(--ink-900)",
    "--bs-btn-active-shadow": "none",
    "--bs-btn-bg": "var(--paper-400)",
    "--bs-btn-border-color": "hsl(33 30% 55% / 0.60)",
    "--bs-btn-color": "var(--ink-900)",
    "--bs-btn-disabled-bg": "var(--paper-200)",
    "--bs-btn-disabled-border-color": "hsl(33 30% 60% / 0.50)",
    "--bs-btn-disabled-color": "var(--ink-700)",
    "--bs-btn-disabled-opacity": "0.65",
    "--bs-btn-focus-shadow-rgb": "146, 93, 7",
    "--bs-btn-hover-bg": "var(--paper-300)",
    "--bs-btn-hover-border-color": "var(--gilt-900)",
    "--bs-btn-hover-color": "var(--ink-900)",
    "border-radius": "var(--radius-button)",
}
EXPECTED_LIGHT_ILLUSTRATION_PLACEMENTS = {
    (
        f"{LIGHT_GUARD} .archive-page-home .illustration-books",
        f"{LIGHT_GUARD} .archive-page-browse .illustration-books",
        f"{LIGHT_GUARD} .archive-page-workspace .illustration-books",
    ): {
        "bottom": "0",
        "height": "160px",
        "left": "0",
        "width": "240px",
    },
    (
        f"{LIGHT_GUARD} .archive-page-home .illustration-flourish",
        f"{LIGHT_GUARD} .archive-page-browse .illustration-flourish",
        f"{LIGHT_GUARD} .archive-page-workspace .illustration-flourish",
    ): {
        "bottom": "0",
        "height": "180px",
        "right": "0",
        "transform": "scaleX(-1)",
        "width": "180px",
    },
    (f"{LIGHT_GUARD} .archive-page-upload .illustration-compass",): {
        "height": "180px",
        "left": "1rem",
        "top": "1rem",
        "width": "180px",
    },
    (f"{LIGHT_GUARD} .archive-page-upload .illustration-sextant",): {
        "height": "200px",
        "right": "1rem",
        "top": "24%",
        "width": "200px",
    },
    (f"{LIGHT_GUARD} .archive-page-upload > .illustration-flourish",): {
        "bottom": "0",
        "height": "180px",
        "right": "0",
        "transform": "scaleX(-1)",
        "width": "180px",
    },
}


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def light_css_from(css: str) -> str:
    assert css.count(DARK_CSS_MARKER) == 1
    return css[: css.index(DARK_CSS_MARKER)]


def light_css() -> str:
    return light_css_from(read_text("static/css/custom.css"))


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
    return tuple(
        " ".join(selector.split())
        for selector in split_css_components(header, ",")
    )


def parse_css_declarations(rule_body: str, context: str) -> dict[str, str]:
    declarations = {}
    for raw_declaration in split_css_components(strip_css_comments(rule_body), ";"):
        assert ":" in raw_declaration, f"invalid declaration in {context}: {raw_declaration!r}"
        property_name, value = raw_declaration.split(":", 1)
        property_name = property_name.strip()
        assert property_name not in declarations, f"duplicate {property_name!r} in {context}"
        declarations[property_name] = " ".join(value.split())
    return declarations


def css_rule_group_declarations(css: str, selectors: tuple[str, ...]) -> dict[str, str]:
    expected = frozenset(selectors)
    matches = []
    for header, body in css_rule_blocks(css):
        if header.startswith("@"):
            continue
        actual = selector_group(header)
        if len(actual) == len(selectors) and frozenset(actual) == expected:
            matches.append(parse_css_declarations(body, repr(actual)))
    assert len(matches) == 1, f"expected one {selectors!r} rule group, found {len(matches)}"
    return matches[0]


def css_block_bodies(css: str, header: str) -> tuple[str, ...]:
    expected = " ".join(header.split())
    return tuple(
        body
        for actual, body in css_rule_blocks(css)
        if " ".join(actual.split()) == expected
    )


def iter_flat_declarations(css: str):
    for header, body in css_rule_blocks(css):
        if header.startswith("@"):
            yield from iter_flat_declarations(body)
            continue
        yield selector_group(header), parse_css_declarations(body, header)


def assert_light_illustration_geometry_contract(css: str) -> None:
    light = light_css_from(css)
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .archive-page",),
    ) == {
        "min-height": "calc(100vh - 58px)",
        "overflow": "hidden",
        "position": "relative",
    }
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .archive-content",),
    ) == {"position": "relative", "z-index": "var(--z-content)"}
    for selectors, expected in EXPECTED_LIGHT_ILLUSTRATION_PLACEMENTS.items():
        assert css_rule_group_declarations(light, selectors) == expected

    desktop = css_block_bodies(
        light,
        "@media screen and (max-width: 991.98px)",
    )
    tablet = css_block_bodies(
        light,
        "@media screen and (max-width: 767.98px)",
    )
    mobile = css_block_bodies(
        light,
        "@media screen and (max-width: 575.98px)",
    )
    assert len(desktop) == len(tablet) == len(mobile) == 1
    assert css_rule_group_declarations(
        desktop[0],
        (f"{LIGHT_GUARD} .archive-page-upload > .illustration-sextant",),
    ) == {"display": "none"}
    assert css_rule_group_declarations(
        tablet[0],
        (f"{LIGHT_GUARD} .archive-page-browse",),
    ) == {"overflow": "visible"}
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .archive-page-upload > .illustration-compass",),
    ) == {"height": "120px", "left": "-2rem", "width": "120px"}


def assert_light_button_state_contract(css: str) -> None:
    light = light_css_from(css)
    assert css_rule_group_declarations(
        light,
        (
            f"{LIGHT_GUARD} .btn-brass",
            f"{LIGHT_GUARD} .btn-primary:not(.btn-secondary-leather)",
        ),
    ) == EXPECTED_LIGHT_PRIMARY_BUTTON_STATES
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .btn-secondary-leather",),
    ) == EXPECTED_LIGHT_WOOD_BUTTON_STATES


def assert_light_dropdown_open_state_contract(css: str) -> None:
    assert css_rule_group_declarations(
        light_css_from(css),
        (
            f"{LIGHT_GUARD} .dropdown-menu.show",
            f"{LIGHT_GUARD} .browse-dropdown-menu.show",
        ),
    ) == {
        "opacity": "1",
        "pointer-events": "auto",
        "transition": "opacity 180ms ease-out, visibility 0s linear 0s",
        "visibility": "visible",
    }


def contrast_ratio(foreground: str, background: str) -> float:
    return contrast_ratio_from_channels(
        hex_color_channels(foreground),
        hex_color_channels(background),
    )


def hex_color_channels(hex_color: str) -> tuple[float, float, float]:
    return tuple(
        int(hex_color[index : index + 2], 16) / 255
        for index in (1, 3, 5)
    )


def contrast_ratio_from_channels(
    foreground: tuple[float, float, float],
    background: tuple[float, float, float],
) -> float:
    def relative_luminance(channels: tuple[float, float, float]) -> float:
        linear = [
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def css_color_contrast_ratio(
    foreground: str,
    background: str,
    tokens: dict[str, str],
) -> float:
    background_channels = hex_color_channels(tokens.get(background, background))
    if foreground.startswith("var("):
        foreground_channels = hex_color_channels(tokens[foreground[4:-1]])
        alpha = 1.0
    else:
        match = re.fullmatch(
            r"hsl\(\s*([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)%\s*/\s*([0-9.]+)\s*\)",
            foreground,
        )
        assert match is not None, f"unsupported test color: {foreground}"
        hue, saturation, lightness, alpha = map(float, match.groups())
        foreground_channels = hls_to_rgb(
            hue / 360,
            lightness / 100,
            saturation / 100,
        )

    composite = tuple(
        foreground_channel * alpha + background_channel * (1 - alpha)
        for foreground_channel, background_channel in zip(
            foreground_channels,
            background_channels,
        )
    )
    return contrast_ratio_from_channels(composite, background_channels)


def assert_light_unchecked_form_check_contrast(css: str) -> None:
    border = css_rule_group_declarations(
        light_css_from(css),
        (f"{LIGHT_GUARD} .form-check-input",),
    )["border-color"]
    ratio = css_color_contrast_ratio(
        border,
        EXPECTED_LIGHT_ROOT_DECLARATIONS["--paper-100"],
        EXPECTED_LIGHT_ROOT_DECLARATIONS,
    )
    assert ratio >= 3, f"unchecked form-check boundary contrast is {ratio:.2f}:1"


def assert_light_bootstrap_owned_state_contract(css: str) -> None:
    light = light_css_from(css)
    assert css_rule_group_declarations(light, (LIGHT_GUARD,)) == {
        "--bs-danger-rgb": "120, 44, 33",
        "--bs-link-color-rgb": "101, 72, 52",
        "--bs-link-hover-color-rgb": "120, 44, 33",
    }
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .form-check-input",),
    ) == {
        "background-color": "var(--paper-100)",
        "border-color": "var(--ink-500)",
    }
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .form-check-input:checked",),
    ) == {
        "background-color": "var(--rubric-500)",
        "border-color": "var(--rubric-500)",
    }
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .form-check-input:focus",),
    ) == {
        "border-color": "var(--gilt-900)",
        "box-shadow": "var(--shadow-gilt-glow)",
        "outline": "0",
    }
    for input_type in ("checkbox", "radio"):
        declarations = css_rule_group_declarations(
            light,
            (
                f'{LIGHT_GUARD} .form-check-input[type="{input_type}"]:checked',
            ),
        )
        assert declarations.keys() == {"background-image"}
        assert "%23EEE6DD" in declarations["background-image"]
        assert "%23fff" not in declarations["background-image"].lower()

    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .btn-secondary",),
    ) == EXPECTED_LIGHT_SECONDARY_BUTTON_STATES

    close = css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .btn-close",),
    )
    close_background = close.pop("--bs-btn-close-bg")
    assert close == {
        "--bs-btn-close-color": "var(--ink-900)",
        "--bs-btn-close-focus-opacity": "1",
        "--bs-btn-close-focus-shadow": "var(--shadow-gilt-glow)",
        "--bs-btn-close-hover-opacity": "1",
        "--bs-btn-close-opacity": "0.75",
        "filter": "none",
    }
    assert "%2336261B" in close_background
    assert "%23000" not in close_background

    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .modal-content",),
    ) == {
        "--bs-modal-bg": "var(--paper-100)",
        "--bs-modal-border-color": "hsl(33 30% 60% / 0.45)",
        "--bs-modal-color": "var(--ink-900)",
    }
    assert css_rule_group_declarations(
        light,
        (
            f"{LIGHT_GUARD} .modal-header",
            f"{LIGHT_GUARD} .modal-footer",
        ),
    ) == {"border-color": "hsl(33 30% 60% / 0.45)"}
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .alert",),
    ) == {
        "--bs-alert-bg": "var(--paper-100)",
        "--bs-alert-border-color": "hsl(33 30% 60% / 0.45)",
        "--bs-alert-color": "var(--ink-900)",
        "--bs-alert-link-color": "var(--ink-900)",
    }
    assert css_rule_group_declarations(
        light,
        (f"{LIGHT_GUARD} .alert-danger",),
    ) == {
        "--bs-alert-bg": "var(--rubric-50)",
        "--bs-alert-border-color": "var(--rubric-500)",
        "--bs-alert-color": "var(--rubric-700)",
        "--bs-alert-link-color": "var(--rubric-700)",
    }


def assert_light_outline_resets_have_forced_colors_fallback(css: str) -> None:
    light = light_css_from(css)
    forced_blocks = css_block_bodies(light, "@media (forced-colors: active)")
    assert len(forced_blocks) == 1

    reset_selectors = {
        selector
        for selectors, declarations in iter_flat_declarations(light)
        if declarations.get("outline") in {"0", "none", "0px"}
        for selector in selectors
        if ":focus" in selector
    }
    forced_selectors = set()
    for selectors, declarations in iter_flat_declarations(forced_blocks[0]):
        if declarations.get("outline") == "2px solid Highlight":
            assert declarations.get("outline-offset") == "2px"
            forced_selectors.update(selectors)

    assert reset_selectors <= forced_selectors
    assert {
        f"{LIGHT_GUARD} .archive-wordmark:focus-visible",
        f"{LIGHT_GUARD} .icon-button:focus-visible",
        f"{LIGHT_GUARD} .btn:focus-visible",
        f"{LIGHT_GUARD} .btn-close:focus-visible",
        f"{LIGHT_GUARD} .form-check-input:focus-visible",
        f"{LIGHT_GUARD} .form-control:focus",
        f"{LIGHT_GUARD} .form-select:focus",
        f"{LIGHT_GUARD} .archive-dropdown:focus-visible",
        f"{LIGHT_GUARD} .workspace-tabs .nav-link:focus-visible",
        f"{LIGHT_GUARD} .workspace-source-item:focus-visible",
        f"{LIGHT_GUARD} .nav-sidebar .list-group-item:focus-visible",
        f"{LIGHT_GUARD} a:focus-visible",
    } <= forced_selectors


def png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    assert data.startswith(PNG_SIGNATURE)
    chunks = []
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        chunks.append((chunk_type, payload))
        offset += 12 + length
    return chunks


def write_mutated_png(
    source: Path,
    target: Path,
    *,
    header: bytes | None = None,
    palette: bytes | None = None,
    scanlines: bytes | None = None,
) -> None:
    chunks = png_chunks(source.read_bytes())
    encoded = bytearray(PNG_SIGNATURE)
    wrote_image_data = False
    for chunk_type, original_payload in chunks:
        payload = original_payload
        if chunk_type == b"IHDR" and header is not None:
            payload = header
        elif chunk_type == b"PLTE" and palette is not None:
            payload = palette
        elif chunk_type == b"IDAT" and scanlines is not None:
            if wrote_image_data:
                continue
            payload = zlib.compress(scanlines, level=9)
            wrote_image_data = True

        encoded.extend(struct.pack(">I", len(payload)))
        encoded.extend(chunk_type)
        encoded.extend(payload)
        encoded.extend(struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF))
    target.write_bytes(encoded)


def png_header_and_scanlines(path: Path) -> tuple[bytes, bytes]:
    chunks = png_chunks(path.read_bytes())
    header = next(payload for chunk_type, payload in chunks if chunk_type == b"IHDR")
    image_data = b"".join(
        payload for chunk_type, payload in chunks if chunk_type == b"IDAT"
    )
    return header, zlib.decompress(image_data)


def paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def unfilter_indexed_png_scanlines(
    scanlines: bytes,
    width: int,
    height: int,
) -> bytes:
    row_length = width + 1
    previous = bytearray(width)
    decoded = bytearray()
    for row_index in range(height):
        row_start = row_index * row_length
        filter_type = scanlines[row_start]
        filtered = scanlines[row_start + 1 : row_start + row_length]
        if filter_type == 0:
            current = bytearray(filtered)
        else:
            current = bytearray(width)
            for column, value in enumerate(filtered):
                left = current[column - 1] if column else 0
                above = previous[column]
                upper_left = previous[column - 1] if column else 0
                if filter_type == 1:
                    predictor = left
                elif filter_type == 2:
                    predictor = above
                elif filter_type == 3:
                    predictor = (left + above) // 2
                else:
                    predictor = paeth_predictor(left, above, upper_left)
                current[column] = (value + predictor) & 0xFF
        decoded.extend(current)
        previous = current
    return bytes(decoded)


def read_png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(PNG_SIGNATURE), f"{path.name} is not a PNG"

    offset = len(PNG_SIGNATURE)
    header = None
    palette = None
    image_data = bytearray()
    saw_end = False

    while offset < len(data):
        assert offset + 12 <= len(data), f"{path.name} has a truncated PNG chunk"
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        assert chunk_end <= len(data), f"{path.name} has a truncated PNG chunk"

        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        assert actual_crc == expected_crc, f"{path.name} has a corrupt PNG chunk"

        if chunk_type == b"IHDR":
            assert header is None and length == 13, f"{path.name} has an invalid IHDR"
            header = struct.unpack(">IIBBBBB", payload)
        elif chunk_type == b"PLTE":
            assert palette is None, f"{path.name} has duplicate palette data"
            palette = payload
        elif chunk_type == b"IDAT":
            image_data.extend(payload)
        elif chunk_type == b"IEND":
            assert length == 0, f"{path.name} has an invalid IEND"
            saw_end = True
            offset = chunk_end
            break

        offset = chunk_end

    assert header is not None, f"{path.name} is missing IHDR"
    assert image_data, f"{path.name} is missing image data"
    assert saw_end and offset == len(data), f"{path.name} is not a complete PNG"
    width, height, bit_depth, color_type, compression, filter_method, interlace = header
    assert width > 0 and height > 0, f"{path.name} has invalid dimensions"
    assert compression == 0 and filter_method == 0
    assert (bit_depth, color_type, interlace) == (8, 3, 0), (
        f"{path.name} must use the supported 8-bit indexed non-interlaced format"
    )
    assert palette is not None and len(palette) % 3 == 0 and 3 <= len(palette) <= 768, (
        f"{path.name} has invalid indexed palette data"
    )

    decompressor = zlib.decompressobj()
    try:
        scanlines = decompressor.decompress(image_data) + decompressor.flush()
    except zlib.error as error:
        raise AssertionError(f"{path.name} has unreadable image data") from error
    assert decompressor.eof and not decompressor.unused_data, (
        f"{path.name} has incomplete or trailing compressed image data"
    )

    scanline_length = width + 1
    assert len(scanlines) == scanline_length * height, (
        f"{path.name} has an invalid decompressed scanline length"
    )
    filter_bytes = scanlines[::scanline_length]
    assert all(filter_byte <= 4 for filter_byte in filter_bytes), (
        f"{path.name} has an out-of-range PNG filter byte"
    )
    decoded_indices = unfilter_indexed_png_scanlines(scanlines, width, height)
    palette_entries = len(palette) // 3
    assert all(index < palette_entries for index in decoded_indices), (
        f"{path.name} has a decoded palette index outside PLTE"
    )
    return width, height


def test_light_theme_source_spec_is_installed_unchanged():
    path = ROOT / "docs" / "design" / "light-mode-ui-spec.md"
    assert sha256(path.read_bytes()).hexdigest() == LIGHT_SPEC_SHA256

    spec = path.read_text(encoding="utf-8")
    assert '# StudyLib — "Old Book" Light Theme — Codex Task Spec' in spec
    assert "## 16. Default decisions" in spec


def test_light_theme_instruction_routes_and_protects_theme_boundaries():
    instruction = read_text(".github/instructions/light-theme.instructions.md")
    assert 'applyTo: "static/css/**/*.css,static/js/**/*.js,templates/**/*.html"' in instruction
    assert "docs/design/light-mode-ui-spec.md" in instruction
    assert "Light mode is the unscoped default" in instruction
    assert 'Never edit any `[data-bs-theme="dark"]` rule' in instruction
    assert 'Never add `[data-bs-theme="light"]` selectors' in instruction
    assert "Apply section 16 defaults without stopping to ask" in instruction


def test_light_texture_manifest_uses_exact_names_separate_from_dark_assets():
    texture_dir = ROOT / "static" / "img" / "textures"
    light_names = {path.name for path in texture_dir.glob("*-texture-light.png")}

    assert light_names == set(LIGHT_TEXTURE_NAMES)
    assert set(LIGHT_TEXTURE_NAMES).isdisjoint(DARK_TEXTURE_NAMES)
    assert all((texture_dir / name).is_file() for name in DARK_TEXTURE_NAMES)

    for light_name, dark_name in zip(LIGHT_TEXTURE_NAMES, DARK_TEXTURE_NAMES):
        assert (texture_dir / light_name).read_bytes() != (texture_dir / dark_name).read_bytes()


@pytest.mark.parametrize("name", LIGHT_TEXTURE_NAMES)
def test_light_texture_asset_is_nonempty_readable_png_with_dimensions(name):
    path = ROOT / "static" / "img" / "textures" / name
    contract = LIGHT_TEXTURE_CONTRACTS[name]

    assert path.stat().st_size > len(PNG_SIGNATURE)
    assert path.stat().st_size <= contract["max_bytes"]
    width, height = read_png_dimensions(path)
    assert (width, height) == contract["dimensions"]


def test_light_texture_assets_stay_within_combined_transfer_budget():
    texture_dir = ROOT / "static" / "img" / "textures"
    total_bytes = sum((texture_dir / name).stat().st_size for name in LIGHT_TEXTURE_NAMES)
    assert total_bytes <= LIGHT_TEXTURE_TOTAL_MAX_BYTES


def test_light_texture_assets_use_optimized_indexed_png_format():
    texture_dir = ROOT / "static" / "img" / "textures"
    for name in LIGHT_TEXTURE_NAMES:
        header, _ = png_header_and_scanlines(texture_dir / name)
        _, _, bit_depth, color_type, _, _, interlace = struct.unpack(
            ">IIBBBBB", header
        )
        assert (bit_depth, color_type, interlace) == (8, 3, 0)


def test_png_validator_rejects_unsupported_committed_asset_format(tmp_path):
    source = ROOT / "static" / "img" / "textures" / LIGHT_TEXTURE_NAMES[0]
    header, _ = png_header_and_scanlines(source)
    unsupported_header = bytearray(header)
    unsupported_header[8] = 16
    mutated = tmp_path / "unsupported.png"
    write_mutated_png(source, mutated, header=bytes(unsupported_header))

    with pytest.raises(AssertionError, match="supported 8-bit indexed"):
        read_png_dimensions(mutated)


def test_png_validator_rejects_incomplete_scanlines(tmp_path):
    source = ROOT / "static" / "img" / "textures" / LIGHT_TEXTURE_NAMES[0]
    _, scanlines = png_header_and_scanlines(source)
    mutated = tmp_path / "short-scanline.png"
    write_mutated_png(source, mutated, scanlines=scanlines[:-1])

    with pytest.raises(AssertionError, match="scanline length"):
        read_png_dimensions(mutated)


def test_png_validator_rejects_out_of_range_filter_bytes(tmp_path):
    source = ROOT / "static" / "img" / "textures" / LIGHT_TEXTURE_NAMES[0]
    _, scanlines = png_header_and_scanlines(source)
    invalid_filter = bytearray(scanlines)
    invalid_filter[0] = 5
    mutated = tmp_path / "bad-filter.png"
    write_mutated_png(source, mutated, scanlines=bytes(invalid_filter))

    with pytest.raises(AssertionError, match="filter byte"):
        read_png_dimensions(mutated)


def test_png_validator_rejects_decoded_index_outside_palette(tmp_path):
    source = ROOT / "static" / "img" / "textures" / LIGHT_TEXTURE_NAMES[0]
    chunks = png_chunks(source.read_bytes())
    header = next(payload for chunk_type, payload in chunks if chunk_type == b"IHDR")
    palette = next(payload for chunk_type, payload in chunks if chunk_type == b"PLTE")
    width, height = struct.unpack(">II", header[:8])
    scanlines = bytearray((width + 1) * height)
    scanlines[0] = 1
    scanlines[1] = 1
    scanlines[2] = 1
    mutated = tmp_path / "palette-index.png"
    write_mutated_png(
        source,
        mutated,
        palette=palette[:6],
        scanlines=bytes(scanlines),
    )

    with pytest.raises(AssertionError, match="palette index"):
        read_png_dimensions(mutated)


def test_light_foundation_has_exact_tokens_and_bootstrap_mappings():
    assert (
        css_rule_group_declarations(light_css(), (":root",))
        == EXPECTED_LIGHT_ROOT_DECLARATIONS
    )
    assert css_rule_group_declarations(light_css(), (LIGHT_GUARD,)) == {
        "--bs-danger-rgb": "120, 44, 33",
        "--bs-link-color-rgb": "101, 72, 52",
        "--bs-link-hover-color-rgb": "120, 44, 33",
    }


def test_light_foundation_precedes_and_preserves_the_entire_dark_css_block():
    css = read_text("static/css/custom.css")
    dark_css = css[css.index(DARK_CSS_MARKER) :]

    assert sha256(dark_css.encode("utf-8")).hexdigest() == DARK_CSS_SHA256
    assert css.index(":root {") < css.index(DARK_CSS_MARKER)


def test_light_body_is_flat_parchment_with_shared_typography():
    css = light_css()
    assert css_rule_group_declarations(css, ("body",)) == {
        "background-color": "var(--paper-50)",
        "color": "var(--ink-900)",
        "font-family": "var(--font-body)",
        "min-height": "100vh",
    }
    heading_rule = css_rule_group_declarations(
        css,
        ("h1", "h2", "h3", "h4", "h5", "h6", ".navbar-brand"),
    )
    assert heading_rule == {
        "color": "var(--ink-900)",
        "font-family": "var(--font-display)",
        "font-weight": "600",
        "letter-spacing": "0.02em",
        "text-wrap": "balance",
    }
    assert not any(
        "gradient(" in value.lower()
        for property_name, value in css_rule_group_declarations(css, ("body",)).items()
        if property_name.startswith("background")
    )


def test_light_materials_use_exact_assets_tints_and_tile_sizes():
    css = light_css()
    for selectors, expected in EXPECTED_LIGHT_MATERIALS.items():
        assert css_rule_group_declarations(css, selectors) == expected


def test_light_candle_guard_is_explicit_and_cannot_hide_dark_behavior():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .candle-glow",),
    ) == {"display": "none"}
    assert not any(
        selectors == (".candle-glow",)
        for selectors, _ in iter_flat_declarations(css)
    )


def test_light_illustrations_use_gilt_masks_and_visible_spec_opacities():
    css = light_css()
    base = css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .archive-illustration",),
    )
    assert base == {
        "--illustration-image": "none",
        "background-color": "var(--gilt-700)",
        "color": "var(--gilt-700)",
        "display": "block",
        "mask-image": "var(--illustration-image)",
        "mask-position": "center",
        "mask-repeat": "no-repeat",
        "mask-size": "contain",
        "opacity": "0.10",
        "pointer-events": "none",
        "position": "absolute",
        "z-index": "var(--z-bg-illustration)",
    }
    for selector, (image, opacity) in EXPECTED_LIGHT_ILLUSTRATIONS.items():
        assert css_rule_group_declarations(
            css,
            (f"{LIGHT_GUARD} {selector}",),
        ) == {"--illustration-image": image, "opacity": opacity}


def test_light_illustrations_have_layered_page_geometry_and_responsive_placements():
    assert_light_illustration_geometry_contract(read_text("static/css/custom.css"))


def test_light_illustration_geometry_contract_rejects_dimension_mutation():
    css = read_text("static/css/custom.css")
    assert_light_illustration_geometry_contract(css)
    assert "width: 240px;" in light_css_from(css)
    with pytest.raises(AssertionError):
        assert_light_illustration_geometry_contract(
            css.replace("width: 240px;", "width: 241px;", 1)
        )


def test_light_navbar_and_sidebar_use_paper_and_ink_without_dark_leakage():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .archive-navbar",),
    ) == {
        "background": "var(--paper-100) !important",
        "border-bottom-color": "hsl(33 30% 60% / 0.30) !important",
        "box-shadow": "none !important",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .archive-wordmark",),
    ) == {
        "color": "var(--ink-900)",
        "font-family": "var(--font-display)",
        "font-size": "1.25rem",
        "font-weight": "600",
        "letter-spacing": "0.06em",
        "padding": "0.35rem 0.5rem",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .nav-sidebar",),
    ) == {
        "background": "var(--paper-100)",
        "border-radius": "0 var(--radius-panel) var(--radius-panel) 0",
        "box-shadow": "var(--shadow-parchment-raised)",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .nav-sidebar .list-group-item",),
    ) == {
        "background": "transparent",
        "border-color": "hsl(33 30% 60% / 0.30)",
        "color": "var(--ink-900)",
    }


def test_light_navbar_menu_morph_uses_neutral_current_color_layers():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (".archive-menu-book", ".archive-menu-bars"),
    ) == {
        "inset": "0",
        "position": "absolute",
        "transition": "opacity 160ms ease, transform 160ms ease",
    }
    assert css_rule_group_declarations(css, (".archive-menu-book",)) == {
        "-webkit-mask": (
            'url("/static/img/illustrations/open-book.svg") center / contain no-repeat'
        ),
        "background-color": "currentColor",
        "mask": 'url("/static/img/illustrations/open-book.svg") center / contain no-repeat',
        "opacity": "1",
        "transform": "scale(1)",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .icon-button",),
    )["color"] == "var(--ink-700) !important"


def test_light_navbar_menu_button_stays_square_through_icon_button_cascade():
    css = light_css()
    menu_button = css_rule_group_declarations(css, (".archive-menu-button",))
    assert {
        menu_button["inline-size"],
        menu_button["block-size"],
        menu_button["min-inline-size"],
        menu_button["min-block-size"],
    } == {"2.5rem"}
    assert menu_button["flex"] == "0 0 2.5rem"

    themed_icon = css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .icon-button",),
    )
    assert themed_icon["min-width"] == themed_icon["min-height"] == "2rem"
    assert themed_icon["padding"] == "0.25rem"


def test_light_button_hierarchy_uses_rubric_wood_and_ink():
    css = light_css()
    primary = css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .btn-brass",
            f"{LIGHT_GUARD} .btn-primary:not(.btn-secondary-leather)",
        ),
    )
    assert primary == EXPECTED_LIGHT_PRIMARY_BUTTON_STATES
    assert_light_button_state_contract(read_text("static/css/custom.css"))
    browse = read_text("static/js/pages/browse.js")
    upload = read_text("static/js/pages/upload.js")
    assert 'btn btn-outline-primary btn-secondary-wood" id="loadMoreBtn"' in browse
    assert "loadMoreBtn.disabled = true" in browse
    assert 'btn btn-primary btn-brass w-100" id="uploadBtn" disabled' in upload
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .btn-ghost",),
    ) == {
        "background": "transparent",
        "border": "1px solid transparent",
        "border-radius": "var(--radius-button)",
        "color": "var(--ink-700)",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .icon-button",),
    )["color"] == "var(--ink-700) !important"
    assert css_rule_group_declarations(
        css,
        (f'{LIGHT_GUARD} .icon-button[aria-pressed="true"]',),
    ) == {"color": "var(--gilt-900) !important"}
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .icon-button:focus-visible",),
    ) == {"color": "var(--ink-900) !important"}


@pytest.mark.parametrize(
    ("declaration", "mutation"),
    (
        (
            "--bs-btn-disabled-bg: var(--rubric-500);",
            "--bs-btn-disabled-bg: #0d6efd;",
        ),
        (
            "--bs-btn-disabled-bg: var(--paper-200);",
            "--bs-btn-disabled-bg: #0d6efd;",
        ),
    ),
    ids=("rubric-upload", "wood-load-more"),
)
def test_light_button_state_contract_rejects_disabled_blue_fallback(
    declaration,
    mutation,
):
    css = read_text("static/css/custom.css")
    assert_light_button_state_contract(css)
    assert light_css_from(css).count(declaration) >= 1
    with pytest.raises(AssertionError):
        assert_light_button_state_contract(css.replace(declaration, mutation, 1))


def test_light_bootstrap_owned_runtime_states_use_old_book_palette():
    css = read_text("static/css/custom.css")
    assert_light_bootstrap_owned_state_contract(css)

    browse = read_text("static/js/pages/browse.js")
    workspace = read_text("static/js/pages/workspace.js")
    layout = read_text("templates/layout.html")
    assert 'class="form-check-input" type="checkbox"' in browse
    assert 'class="btn btn-secondary" id="cancelNoteBtn"' in workspace
    assert 'class="btn-close" id="closeModalBtn"' in workspace
    assert 'class="btn-close" data-bs-dismiss="alert"' in layout


def test_light_unchecked_form_check_boundary_meets_non_text_contrast():
    translucent_border = "hsl(33 30% 55% / 0.60)"
    paper = EXPECTED_LIGHT_ROOT_DECLARATIONS["--paper-100"]
    old_ratio = css_color_contrast_ratio(
        translucent_border,
        paper,
        EXPECTED_LIGHT_ROOT_DECLARATIONS,
    )
    assert old_ratio == pytest.approx(1.52, abs=0.02)

    css = read_text("static/css/custom.css")
    assert_light_unchecked_form_check_contrast(css)
    assert light_css_from(css).count("border-color: var(--ink-500);") == 1
    with pytest.raises(AssertionError, match="boundary contrast"):
        assert_light_unchecked_form_check_contrast(
            css.replace(
                "border-color: var(--ink-500);",
                f"border-color: {translucent_border};",
                1,
            )
        )


@pytest.mark.parametrize(
    ("declaration", "mutation"),
    (
        (
            "--bs-link-color-rgb: 101, 72, 52;",
            "--bs-link-color-rgb: 13, 110, 253;",
        ),
        (
            "background-color: var(--rubric-500);",
            "background-color: #0d6efd;",
        ),
        (
            "--bs-btn-bg: var(--paper-400);",
            "--bs-btn-bg: #6c757d;",
        ),
    ),
    ids=("link-blue", "checked-blue", "secondary-gray"),
)
def test_light_bootstrap_owned_state_contract_rejects_vendor_mutations(
    declaration,
    mutation,
):
    css = read_text("static/css/custom.css")
    assert_light_bootstrap_owned_state_contract(css)
    assert light_css_from(css).count(declaration) == 1
    with pytest.raises(AssertionError):
        assert_light_bootstrap_owned_state_contract(
            css.replace(declaration, mutation, 1)
        )


def test_light_inputs_dropdowns_badges_offcanvas_and_focus_match_contract():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .archive-dropdown",
            f"{LIGHT_GUARD} .form-select",
        ),
    ) == {
        "background-color": "var(--paper-200)",
        "border": "1px solid hsl(33 30% 60% / 0.50)",
        "border-radius": "var(--radius-button)",
        "color": "var(--ink-900)",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .form-select",),
    ) == {
        "background-image": (
            'url("data:image/svg+xml,%3csvg xmlns=\'http://www.w3.org/2000/svg\' '
            "viewBox=\'0 0 16 16\'%3e%3cpath fill=\'none\' stroke=\'%23654834\' "
            "stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'2\' "
            "d=\'m2 5 6 6 6-6\'/%3e%3c/svg%3e\")"
        )
    }
    assert css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .dropdown-menu",
            f"{LIGHT_GUARD} .browse-dropdown-menu",
        ),
    ) == {
        "background": "var(--paper-100)",
        "border-color": "hsl(33 30% 60% / 0.50)",
        "border-radius": "var(--radius-button)",
        "box-shadow": "var(--shadow-parchment-raised)",
        "color": "var(--ink-900)",
        "display": "block",
        "opacity": "0",
        "pointer-events": "none",
        "transition": "opacity 180ms ease-in, visibility 0s linear 180ms",
        "visibility": "hidden",
    }
    assert_light_dropdown_open_state_contract(read_text("static/css/custom.css"))
    assert css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .form-control",
            f"{LIGHT_GUARD} .input-group-text",
        ),
    ) == {
        "background": "var(--paper-100)",
        "border": "1px solid hsl(33 30% 60% / 0.50)",
        "border-radius": "var(--radius-input)",
        "color": "var(--ink-900)",
    }
    assert css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .form-control:focus",
            f"{LIGHT_GUARD} .form-select:focus",
        ),
    ) == {
        "background-color": "var(--paper-200)",
        "border-color": "var(--gilt-900)",
        "box-shadow": "var(--shadow-gilt-glow)",
        "color": "var(--ink-900)",
        "outline": "0",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .archive-count-badge",),
    ) == {
        "background": "var(--paper-400) !important",
        "border-radius": "var(--radius-pill)",
        "color": "var(--ink-900)",
        "font-size": "var(--text-caption)",
        "font-variant-numeric": "tabular-nums",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .archive-category-badge",),
    ) == {
        "background": "hsl(33 30% 72% / 0.50) !important",
        "border-radius": "var(--radius-pill)",
        "color": "var(--ink-900) !important",
        "font-size": "var(--text-caption)",
        "letter-spacing": "0.04em",
        "text-transform": "uppercase",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .offcanvas",),
    ) == {
        "--bs-offcanvas-bg": "var(--paper-100)",
        "--bs-offcanvas-color": "var(--ink-900)",
    }
    focus = css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .btn:focus-visible",
            f"{LIGHT_GUARD} .icon-button:focus-visible",
            f"{LIGHT_GUARD} .archive-dropdown:focus-visible",
            f"{LIGHT_GUARD} .navbar-brand:focus-visible",
        ),
    )
    assert focus == {
        "border-color": "var(--gilt-900)",
        "box-shadow": "var(--shadow-gilt-glow)",
        "outline": "0",
    }


def test_light_accessibility_corrections_meet_wcag_aa():
    tokens = EXPECTED_LIGHT_ROOT_DECLARATIONS
    assert contrast_ratio(tokens["--paper-50"], tokens["--paper-500"]) < 4.5
    assert contrast_ratio(tokens["--ink-700"], tokens["--paper-300"]) < 4.5

    assert contrast_ratio(tokens["--ink-900"], tokens["--paper-400"]) >= 4.5
    assert contrast_ratio(tokens["--ink-700"], tokens["--paper-200"]) >= 4.5
    assert contrast_ratio(tokens["--ink-700"], tokens["--paper-50"]) >= 4.5
    assert contrast_ratio(tokens["--rubric-700"], tokens["--paper-50"]) >= 4.5


def test_light_count_badge_uses_accessible_in_family_pair():
    declarations = css_rule_group_declarations(
        light_css(),
        (f"{LIGHT_GUARD} .archive-count-badge",),
    )
    assert declarations["background"] == "var(--paper-400) !important"
    assert declarations["color"] == "var(--ink-900)"


def test_light_dropdown_open_state_contract_rejects_pointer_event_mutation():
    css = read_text("static/css/custom.css")
    assert_light_dropdown_open_state_contract(css)
    assert light_css_from(css).count("pointer-events: auto;") == 1
    with pytest.raises(AssertionError):
        assert_light_dropdown_open_state_contract(
            css.replace("pointer-events: auto;", "pointer-events: none;", 1)
        )


def test_light_scrollbars_motion_and_reduced_motion_match_contract():
    css = light_css()
    assert css_rule_group_declarations(css, ("::-webkit-scrollbar",)) == {
        "height": "10px",
        "width": "10px",
    }
    assert css_rule_group_declarations(css, ("::-webkit-scrollbar-track",)) == {
        "background": "transparent"
    }
    assert css_rule_group_declarations(css, ("::-webkit-scrollbar-thumb",)) == {
        "background": "var(--paper-400)",
        "border": "2px solid var(--paper-50)",
        "border-radius": "999px",
    }
    assert css_rule_group_declarations(css, ("*",)) == {
        "scrollbar-color": "var(--paper-400) transparent",
        "scrollbar-width": "thin",
    }

    control_motion = css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} button",
            f"{LIGHT_GUARD} .btn",
            f"{LIGHT_GUARD} input",
            f"{LIGHT_GUARD} select",
            f"{LIGHT_GUARD} textarea",
            f"{LIGHT_GUARD} .btn-secondary-leather",
            f"{LIGHT_GUARD} .btn-brass",
            f"{LIGHT_GUARD} .btn-ghost",
            f"{LIGHT_GUARD} .icon-button",
            f"{LIGHT_GUARD} .archive-dropdown",
            f"{LIGHT_GUARD} .form-control",
            f"{LIGHT_GUARD} .form-select",
            f"{LIGHT_GUARD} .navbar-brand",
        ),
    )
    assert control_motion == {
        "transition": (
            "background-color 150ms ease, border-color 150ms ease, color 150ms ease"
        )
    }

    reduced_blocks = css_block_bodies(css, "@media (prefers-reduced-motion: reduce)")
    assert len(reduced_blocks) == 1
    assert css_rule_group_declarations(
        reduced_blocks[0],
        (
            f"{LIGHT_GUARD} *",
            f"{LIGHT_GUARD} *::before",
            f"{LIGHT_GUARD} *::after",
        ),
    ) == {
        "animation-duration": "0.01ms !important",
        "animation-iteration-count": "1 !important",
        "scroll-behavior": "auto !important",
        "transition-delay": "0s !important",
        "transition-duration": "0.01ms !important",
    }


def test_light_outline_resets_have_forced_colors_focus_fallbacks():
    assert_light_outline_resets_have_forced_colors_fallback(
        read_text("static/css/custom.css")
    )


def test_light_forced_colors_contract_rejects_missing_button_fallback():
    css = read_text("static/css/custom.css")
    assert_light_outline_resets_have_forced_colors_fallback(css)
    selector = f"    {LIGHT_GUARD} .btn-close:focus-visible,\n"
    assert light_css_from(css).count(selector) == 1
    with pytest.raises(AssertionError):
        assert_light_outline_resets_have_forced_colors_fallback(
            css.replace(selector, "", 1)
        )


def test_light_css_forbids_light_attribute_selectors_and_pure_hex_colors():
    css = light_css()
    pure_hex = re.compile(r"(?i)(?<![0-9a-f])#(?:fff(?:fff)?|000(?:000)?)(?![0-9a-f])")

    for selectors, declarations in iter_flat_declarations(css):
        assert not any('[data-bs-theme="light"]' in selector for selector in selectors)
        for selector in selectors:
            if "data-bs-theme" in selector:
                assert selector == LIGHT_GUARD or selector.startswith(f"{LIGHT_GUARD} ")
        for property_name, value in declarations.items():
            assert not pure_hex.search(value), (
                f"{selectors!r} {property_name} uses forbidden pure color {value!r}"
            )


def test_light_small_controls_and_icons_use_ink_not_gilt():
    css = light_css()
    relevant_markers = (
        ".btn",
        ".icon-button",
        ".archive-dropdown",
        ".form-control",
        ".form-select",
        ".bi",
    )
    for selectors, declarations in iter_flat_declarations(css):
        if not any(marker in selector for selector in selectors for marker in relevant_markers):
            continue
        for property_name in ("color", "--bs-btn-color", "--bs-btn-hover-color"):
            value = declarations.get(property_name, "")
            if "var(--gilt-" in value:
                assert selectors == (
                    f'{LIGHT_GUARD} .icon-button[aria-pressed="true"]',
                ), (
                    f"{selectors!r} uses gilt for small control/icon text: "
                    f"{property_name}: {value}"
                )


def test_light_dashboard_and_page_header_use_old_book_hierarchy():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .archive-page-title",),
    ) == {
        "color": "var(--ink-900)",
        "font-family": "var(--font-display)",
        "font-size": "var(--text-display-lg)",
        "font-weight": "600",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .home-search-group",),
    ) == {"max-width": "560px", "width": "100%"}
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .workspace-card",),
    ) == {
        "min-height": "220px",
        "transition": (
            "border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease"
        ),
    }
    assert css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .workspace-card:not(.workspace-card-add):hover",
            f"{LIGHT_GUARD} .workspace-card:not(.workspace-card-add):focus-within",
        ),
    ) == {
        "border-color": "var(--gilt-900)",
        "box-shadow": "var(--shadow-gilt-glow)",
        "transform": "translateY(-2px)",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .workspace-card-add",),
    ) == {
        "background": "var(--paper-50)",
        "border": "2px dashed hsl(33 30% 55% / 0.45)",
        "border-radius": "var(--radius-panel)",
        "color": "var(--ink-700) !important",
        "cursor": "pointer",
    }
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .workspace-card-add h5",),
    ) == {"color": "var(--ink-700)"}
    assert css_rule_group_declarations(
        css,
        (
            f"{LIGHT_GUARD} .workspace-card-add:hover",
            f"{LIGHT_GUARD} .workspace-card-add:focus-within",
        ),
    ) == {
        "background": "var(--paper-100)",
        "border-color": "var(--gilt-900)",
        "box-shadow": "var(--shadow-gilt-glow)",
    }


def test_light_browse_search_overview_and_results_match_component_contract():
    css = light_css()
    browse = read_text("static/js/pages/browse.js")
    assert 'class="card surface-leather source-summary-panel mb-3"' in browse
    assert 'class="list-group-item"' in browse
    assert f"{LIGHT_GUARD} .source-summary-panel .card-body" not in css
    expected_rules = (
        (
            (f"{LIGHT_GUARD} .archive-page.archive-page-browse",),
            {"padding": "0 0 2rem"},
        ),
        (
            (f"{LIGHT_GUARD} .browse-search-shell",),
            {
                "background-color": "var(--paper-100)",
                "background-image": 'linear-gradient(hsl(33 28% 82% / 0.65), hsl(33 28% 82% / 0.65)), url("/static/img/textures/wood-texture-light.png")',
                "background-blend-mode": "normal",
                "background-repeat": "repeat",
                "background-size": "auto, 180px",
                "border-bottom": "1px solid hsl(33 30% 60% / 0.30) !important",
                "position": "relative",
                "z-index": "calc(var(--z-content) + 1)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .browse-search-group",),
            {"margin-inline": "auto", "max-width": "960px"},
        ),
        (
            (f"{LIGHT_GUARD} .browse-search-input",),
            {
                "background": "var(--paper-100)",
                "border-color": "hsl(33 30% 60% / 0.50)",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .browse-search-input:focus",),
            {
                "background": "var(--paper-100)",
                "border-color": "var(--gilt-900)",
                "box-shadow": "var(--shadow-gilt-glow)",
            },
        ),
        (
            (
                f"{LIGHT_GUARD} .ai-overview-panel",
                f"{LIGHT_GUARD} .source-summary-panel",
            ),
            {"margin-bottom": "1rem", "padding": "1.25rem"},
        ),
        (
            (
                f"{LIGHT_GUARD} .ai-overview-panel .card-title",
                f"{LIGHT_GUARD} .source-summary-panel .card-title",
            ),
            {
                "color": "var(--ink-900)",
                "font-family": "var(--font-display)",
                "font-size": "var(--text-display-sm)",
                "letter-spacing": "0.02em",
            },
        ),
        (
            (f"{LIGHT_GUARD} .ai-overview-panel .card-body",),
            {"color": "var(--ink-700)"},
        ),
        (
            (f"{LIGHT_GUARD} .source-summary-panel .list-group-item",),
            {
                "background": "transparent",
                "border-color": "hsl(33 30% 60% / 0.30)",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .result-card",),
            {
                "border-radius": "var(--radius-panel) !important",
                "box-shadow": "var(--shadow-parchment-raised) !important",
                "overflow": "hidden",
                "transition": (
                    "border-color 150ms ease, box-shadow 150ms ease, "
                    "transform 150ms ease"
                ),
            },
        ),
        (
            (
                f"{LIGHT_GUARD} .result-card:hover",
                f"{LIGHT_GUARD} .result-card:focus-within",
            ),
            {
                "border-color": "var(--gilt-900)",
                "box-shadow": "var(--shadow-gilt-glow) !important",
                "transform": "translateY(-2px)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .result-card img",),
            {"filter": "none"},
        ),
        (
            (f"{LIGHT_GUARD} .result-card .card-title",),
            {"color": "var(--ink-900)"},
        ),
        (
            (f"{LIGHT_GUARD} .result-card .card-text",),
            {
                "-webkit-box-orient": "vertical",
                "-webkit-line-clamp": "2",
                "color": "var(--ink-700)",
                "display": "-webkit-box",
                "overflow": "hidden",
            },
        ),
        (
            (f"{LIGHT_GUARD} .result-card-actions",),
            {"display": "flex", "gap": "0.5rem"},
        ),
        (
            (f"{LIGHT_GUARD} .result-card .save-btn",),
            {"padding": "0.25rem !important"},
        ),
        (
            (f"{LIGHT_GUARD} .result-card .save-btn:hover",),
            {"color": "var(--rubric-500) !important"},
        ),
    )
    for selectors, expected in expected_rules:
        assert css_rule_group_declarations(css, selectors) == expected


def test_light_result_card_image_region_and_fallback_match_parchment_contract():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .result-card .result-card-image",),
    ) == {
        "background": "transparent",
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
        "filter": "brightness(0.25) sepia(0.6)",
        "mix-blend-mode": "multiply",
        "opacity": "0.72",
        "padding": "1.25rem",
    }


def test_light_browse_overview_spinner_inherits_theme_and_reduces_motion():
    css = light_css()
    assert css_rule_group_declarations(css, (".ai-overview-spinner",)) == {
        "animation-duration": "0.9s",
        "border-width": "0.12em",
        "color": "currentColor",
        "flex": "0 0 auto",
        "height": "1rem",
        "width": "1rem",
    }
    reduced_motion_matches = [
        body
        for body in css_block_bodies(css, "@media (prefers-reduced-motion: reduce)")
        if any(
            selector_group(header) == (".ai-overview-spinner",)
            for header, _body in css_rule_blocks(body)
            if not header.startswith("@")
        )
    ]
    assert len(reduced_motion_matches) == 1
    assert css_rule_group_declarations(
        reduced_motion_matches[0],
        (".ai-overview-spinner",),
    ) == {"animation": "none"}
    assert f"{LIGHT_GUARD} .ai-overview-spinner" not in css


def test_light_browse_empty_and_loading_art_uses_parchment_surface_and_dark_engraving():
    css = light_css()
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .browse-empty-engraving",),
    ) == {"background-color": "var(--ink-500)", "opacity": "0.62"}
    assert contrast_ratio(
        EXPECTED_LIGHT_ROOT_DECLARATIONS["--ink-500"],
        EXPECTED_LIGHT_ROOT_DECLARATIONS["--paper-100"],
    ) > 2.5
    assert css_rule_group_declarations(
        css,
        (f"{LIGHT_GUARD} .loader-container",),
    )["background-color"] == "var(--paper-100)"
    assert read_png_dimensions(
        ROOT / "static" / "img" / "loaders" / "bible-page-turn-still.png"
    ) == (480, 480)


def test_light_source_tags_use_accessible_ink_at_caption_size():
    css = light_css()
    for selector in (".result-source", ".workspace-source-name"):
        assert css_rule_group_declarations(
            css,
            (f"{LIGHT_GUARD} {selector}",),
        ) == {
            "color": "var(--ink-700) !important",
            "font-size": "var(--text-caption)",
        }


def test_light_upload_dropzone_and_file_list_match_component_contract():
    css = light_css()
    expected_rules = (
        (
            (f"{LIGHT_GUARD} .upload-content",),
            {"margin-inline": "auto", "max-width": "700px"},
        ),
        (
            (f"{LIGHT_GUARD} .upload-panel",),
            {"background": "transparent", "border": "0"},
        ),
        (
            (f"{LIGHT_GUARD} .upload-zone",),
            {
                "border": "2px dashed hsl(33 30% 55% / 0.50)",
                "border-radius": "var(--radius-panel)",
            },
        ),
        (
            (
                f"{LIGHT_GUARD} .upload-zone:hover",
                f"{LIGHT_GUARD} .upload-zone.dragover",
            ),
            {
                "background-color": "var(--paper-300)",
                "border-color": "var(--gilt-900)",
                "box-shadow": "var(--shadow-gilt-glow)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .archive-upload-icon",),
            {"color": "var(--ink-700) !important", "font-size": "3rem"},
        ),
        (
            (f"{LIGHT_GUARD} .upload-actions",),
            {"color": "var(--ink-900)"},
        ),
        (
            (f"{LIGHT_GUARD} .file-list-panel",),
            {"overflow": "hidden"},
        ),
        (
            (
                f"{LIGHT_GUARD} .file-list-panel .card-header",
                f"{LIGHT_GUARD} .file-list-panel .list-group-item",
            ),
            {
                "background": "transparent",
                "border-color": "hsl(33 30% 60% / 0.30)",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .file-list-panel .flex-grow-1",),
            {"min-width": "0"},
        ),
        (
            (f"{LIGHT_GUARD} .file-icon",),
            {
                "color": "var(--ink-700) !important",
                "flex": "0 0 auto",
                "font-size": "1.35rem",
            },
        ),
        (
            (f"{LIGHT_GUARD} .file-icon-docx",),
            {"color": "var(--folio-blue) !important"},
        ),
        (
            (f"{LIGHT_GUARD} .file-icon-pdf",),
            {"color": "var(--rubric-700) !important"},
        ),
        (
            (
                f"{LIGHT_GUARD} .file-icon-txt",
                f"{LIGHT_GUARD} .file-icon-image",
                f"{LIGHT_GUARD} .file-icon-xls",
                f"{LIGHT_GUARD} .file-icon-xlsx",
            ),
            {"color": "var(--ink-700) !important"},
        ),
        (
            (f"{LIGHT_GUARD} .file-size",),
            {"font-variant-numeric": "tabular-nums"},
        ),
        (
            (f"{LIGHT_GUARD} #filesList:empty",),
            {
                "display": "block",
                "min-height": "190px",
                "padding": "1.25rem",
                "text-align": "center",
            },
        ),
        (
            (f"{LIGHT_GUARD} #filesList:empty::before",),
            {
                "background-color": "var(--gilt-700)",
                "content": '""',
                "display": "block",
                "height": "112px",
                "margin": "0 auto 0.5rem",
                "mask-image": 'url("/static/img/illustrations/open-book.svg")',
                "mask-position": "center",
                "mask-repeat": "no-repeat",
                "mask-size": "contain",
                "opacity": "0.12",
                "pointer-events": "none",
                "width": "160px",
            },
        ),
        (
            (f"{LIGHT_GUARD} #filesList:empty::after",),
            {
                "color": "var(--ink-700)",
                "content": '"No files uploaded yet."',
                "display": "block",
            },
        ),
    )
    for selectors, expected in expected_rules:
        assert css_rule_group_declarations(css, selectors) == expected


def test_light_workspace_panels_tabs_sources_notes_and_preview_match_contract():
    css = light_css()
    expected_rules = (
        (
            (
                f"{LIGHT_GUARD} .workspace-main-panel",
                f"{LIGHT_GUARD} .workspace-right-panel",
            ),
            {"min-height": "680px"},
        ),
        (
            (
                f"{LIGHT_GUARD} .workspace-main-panel .card-header",
                f"{LIGHT_GUARD} .workspace-right-panel .card-header",
            ),
            {
                "background": "transparent",
                "border-color": "hsl(33 30% 60% / 0.30)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .quick-note-input",),
            {
                "background": "transparent",
                "border-color": "transparent",
                "color": "var(--ink-900)",
                "resize": "vertical",
            },
        ),
        (
            (f"{LIGHT_GUARD} .quick-note-input:focus",),
            {
                "background": "transparent",
                "border-color": "var(--gilt-900)",
                "box-shadow": "var(--shadow-gilt-glow)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .source-preview-shell",),
            {
                "background": "var(--paper-100) !important",
                "border-color": "hsl(33 30% 60% / 0.30) !important",
            },
        ),
        (
            (f"{LIGHT_GUARD} .source-preview-content",),
            {
                "background": "var(--paper-100) !important",
                "border-color": "hsl(33 30% 60% / 0.30) !important",
            },
        ),
        (
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link",),
            {
                "background": "transparent",
                "color": "var(--ink-700)",
                "transition": "background 150ms ease, color 150ms ease",
            },
        ),
        (
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link:hover",),
            {
                "background": "hsl(33 30% 72% / 0.35)",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link:focus-visible",),
            {"box-shadow": "var(--shadow-gilt-glow)", "outline": "0"},
        ),
        (
            (f"{LIGHT_GUARD} .workspace-tabs .nav-link.active",),
            {
                "background": "var(--rubric-50)",
                "color": "var(--rubric-700)",
                "font-weight": "600",
            },
        ),
        (
            (f"{LIGHT_GUARD} .workspace-source-item",),
            {
                "background": "transparent",
                "border-color": "hsl(33 30% 60% / 0.30)",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .workspace-source-item h6",),
            {"color": "var(--ink-900)"},
        ),
        (
            (f"{LIGHT_GUARD} .workspace-source-item:hover",),
            {"background": "var(--paper-100)", "color": "var(--ink-900)"},
        ),
        (
            (f"{LIGHT_GUARD} .workspace-source-item:focus-visible",),
            {"box-shadow": "var(--shadow-gilt-glow)", "outline": "0"},
        ),
        (
            (f"{LIGHT_GUARD} .workspace-source-item.active",),
            {
                "background": "hsl(33 30% 72% / 0.30)",
                "border-left": "3px solid var(--gilt-900)",
                "box-shadow": "var(--shadow-gilt-glow)",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .note-item",),
            {
                "background-color": "var(--paper-100)",
                "background-image": "none",
                "color": "var(--ink-900)",
            },
        ),
        (
            (f"{LIGHT_GUARD} .note-icon-light",),
            {"display": "none"},
        ),
        (
            (f"{LIGHT_GUARD} .note-icon-dark",),
            {
                "color": "var(--ink-700) !important",
                "display": "inline-block !important",
            },
        ),
    )
    for selectors, expected in expected_rules:
        assert css_rule_group_declarations(css, selectors) == expected


def test_light_alexander_chat_uses_asymmetric_paper_and_rubric_bubbles():
    css = light_css()
    expected_rules = (
        (
            (f"{LIGHT_GUARD} .chat-messages",),
            {
                "background": "var(--paper-200)",
                "border-color": "hsl(33 30% 60% / 0.30) !important",
            },
        ),
        (
            (f"{LIGHT_GUARD} .chat-message",),
            {
                "color": "var(--ink-900) !important",
                "max-width": "min(82%, 34rem)",
                "padding": "0.8rem 1rem !important",
                "position": "relative",
                "width": "fit-content",
            },
        ),
        (
            (f"{LIGHT_GUARD} .chat-row-agent",),
            {"margin-left": "2.9rem", "margin-right": "auto"},
        ),
        (
            (f"{LIGHT_GUARD} .chat-row-user",),
            {"margin-left": "auto"},
        ),
        (
            (f"{LIGHT_GUARD} .chat-message-agent",),
            {
                "background": "var(--paper-100) !important",
                "border-radius": "18px 22px 16px 6px !important",
            },
        ),
        (
            (f"{LIGHT_GUARD} .chat-message-user",),
            {
                "background": "var(--rubric-50) !important",
                "border-radius": "22px 18px 6px 16px !important",
                "color": "var(--rubric-700) !important",
            },
        ),
        (
            (f"{LIGHT_GUARD} .chat-avatar::before",),
            {
                "align-items": "center",
                "background": "var(--paper-300)",
                "border": "1px solid hsl(33 30% 60% / 0.40)",
                "border-radius": "50%",
                "bottom": "0",
                "color": "var(--ink-700)",
                "content": r'"\2699"',
                "display": "flex",
                "height": "2.25rem",
                "justify-content": "center",
                "left": "-2.9rem",
                "line-height": "1",
                "position": "absolute",
                "width": "2.25rem",
            },
        ),
        (
            (
                f"{LIGHT_GUARD} .chat-message-agent::after",
                f"{LIGHT_GUARD} .chat-message-user::after",
            ),
            {
                "border-style": "solid",
                "bottom": "0.3rem",
                "content": '""',
                "position": "absolute",
            },
        ),
        (
            (f"{LIGHT_GUARD} .chat-message-agent::after",),
            {
                "border-color": "transparent var(--paper-100) transparent transparent",
                "border-width": "0.45rem 0.55rem 0.45rem 0",
                "left": "-0.5rem",
            },
        ),
        (
            (f"{LIGHT_GUARD} .chat-message-user::after",),
            {
                "border-color": "transparent transparent transparent var(--rubric-50)",
                "border-width": "0.45rem 0 0.45rem 0.55rem",
                "right": "-0.5rem",
            },
        ),
    )
    for selectors, expected in expected_rules:
        assert css_rule_group_declarations(css, selectors) == expected


def test_light_component_layouts_stack_cleanly_at_existing_breakpoints():
    css = light_css()
    tablet = css_block_bodies(css, "@media screen and (max-width: 991.98px)")
    narrow = css_block_bodies(css, "@media screen and (max-width: 767.98px)")
    mobile = css_block_bodies(css, "@media screen and (max-width: 575.98px)")
    assert len(tablet) == len(narrow) == len(mobile) == 1

    assert css_rule_group_declarations(
        tablet[0],
        (
            f"{LIGHT_GUARD} .archive-page-workspace .workspace-main-panel",
            f"{LIGHT_GUARD} .archive-page-workspace .workspace-right-panel",
        ),
    ) == {"min-height": "auto"}
    assert css_rule_group_declarations(
        tablet[0],
        (f"{LIGHT_GUARD} .archive-page-workspace .resizable-panel",),
    ) == {
        "max-width": "none",
        "min-width": "0",
        "resize": "none",
        "width": "100%",
    }
    assert css_rule_group_declarations(
        narrow[0],
        (f"{LIGHT_GUARD} .browse-results-layout",),
    ) == {"flex-direction": "column", "height": "auto !important"}
    assert css_rule_group_declarations(
        narrow[0],
        (f"{LIGHT_GUARD} #sidebarContainer.browse-sidebar",),
    ) == {
        "border-bottom": "1px solid hsl(33 30% 60% / 0.30)",
        "border-right": "0 !important",
        "max-width": "none",
        "min-width": "0 !important",
        "overflow-y": "visible !important",
        "width": "100% !important",
    }
    assert css_rule_group_declarations(
        narrow[0],
        (f"{LIGHT_GUARD} .browse-search-group",),
    ) == {
        "align-items": "stretch",
        "display": "grid",
        "grid-template-columns": "1fr auto auto",
    }
    assert css_rule_group_declarations(
        narrow[0],
        (f"{LIGHT_GUARD} .browse-results-pane",),
    ) == {"overflow-y": "visible !important", "width": "100%"}
    assert css_rule_group_declarations(
        narrow[0],
        (
            f"{LIGHT_GUARD} .browse-results-row .col",
            f"{LIGHT_GUARD} .browse-results-row .result-card",
        ),
    ) == {"min-width": "0", "width": "100%"}
    assert css_rule_group_declarations(
        narrow[0],
        (f"{LIGHT_GUARD} .browse-search-group .input-group-text",),
    ) == {"display": "none"}
    assert css_rule_group_declarations(
        narrow[0],
        (f"{LIGHT_GUARD} .browse-search-input",),
    ) == {"min-width": "0", "width": "100%"}
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .browse-dropdown-menu",),
    ) == {
        "left": "0",
        "max-width": "100%",
        "min-width": "0 !important",
        "right": "auto",
        "width": "100%",
    }
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .archive-page .archive-page-title",),
    ) == {"font-size": "1.65rem"}
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .upload-zone",),
    ) == {"padding": "2.5rem 1.25rem !important"}
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .archive-page-home .workspace-card",),
    ) == {"min-height": "190px"}
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .chat-message",),
    ) == {"max-width": "88%"}
    assert css_rule_group_declarations(
        mobile[0],
        (f"{LIGHT_GUARD} .chat-message-agent",),
    ) == {"max-width": "calc(88% - 2.9rem)"}
