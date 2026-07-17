from hashlib import sha256
from pathlib import Path
import struct
import zlib

import pytest


ROOT = Path(__file__).resolve().parents[1]
LIGHT_SPEC_SHA256 = "38cfddd7d60b33930f6e76e3be90e3387ce6d5b53a55976438da1bed9605eb92"
LIGHT_TEXTURE_NAMES = (
    "leather-texture-light.png",
    "wood-texture-light.png",
)
DARK_TEXTURE_NAMES = (
    "leather-texture.png",
    "wood-texture.png",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def read_png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(PNG_SIGNATURE), f"{path.name} is not a PNG"

    offset = len(PNG_SIGNATURE)
    header = None
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
    assert zlib.decompress(image_data), f"{path.name} has unreadable image data"

    width, height, _, _, compression, filter_method, interlace = header
    assert compression == 0 and filter_method == 0
    assert interlace in (0, 1)
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

    assert path.stat().st_size > len(PNG_SIGNATURE)
    width, height = read_png_dimensions(path)
    assert width > 0
    assert height > 0
