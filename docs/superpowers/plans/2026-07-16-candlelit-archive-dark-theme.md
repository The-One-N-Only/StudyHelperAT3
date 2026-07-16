# Candlelit Archive Dark Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the supplied Candlelit Archive design across StudyLib's dark theme while preserving the existing light theme and all application behavior.

**Architecture:** Keep Bootstrap's existing `data-bs-theme` mechanism and layer a dark-only token system over it in `static/css/custom.css`. Add semantic class hooks to the current Jinja and vanilla JavaScript-rendered markup, keep the supplied textures and illustrations as static assets, and isolate the candle cursor inside `static/js/theme.js` so it attaches only when dark mode and a fine pointer are both active.

**Tech Stack:** Python 3.12, Flask, Jinja2, Bootstrap 5.3.3, vanilla JavaScript ES modules, CSS custom properties, pytest, ffmpeg for one-time texture conversion, agent-browser for visual QA.

## Global Constraints

- Treat `docs/design/dark-mode-ui-spec.md` as the source of truth. If this plan conflicts with it, the source specification wins.
- Edit dark mode only. Every new visual selector and token must be scoped beneath `[data-bs-theme="dark"]`.
- Keep the existing `data-bs-theme` and `localStorage` theme mechanism. Do not add a `.dark` class or a second theme system.
- Preserve light-mode rendering, backend behavior, API contracts, and data flow.
- Use the exact palette: `#0A0A0A`, `#14100B`, `#22170B`, `#2E1F0F`, `#3D2914`, `#4D3319`, `#EDD9B5`, `#C9A876`, `#A9824F`, `#8A6635`, `#5C4423`, `#E7E1DA`, `#A69A8C`, `#6E6459`, `#9C6242`, `#6E87A6`, and `#6E9B7C`.
- Use Cinzel for display text and Crimson Pro for body/UI text only in dark mode.
- Convert the supplied JPEG textures into real PNG files. Tile leather at `420px` and wood at `200px` with `background-blend-mode: multiply`. Never stretch either texture with `cover`.
- Use the five supplied SVGs unchanged at their final filenames beneath `static/img/illustrations/`.
- Use leather only for panels/cards/dropzones and wood only for secondary buttons.
- Map Bootstrap primary/secondary variables before component overrides so the blue active pill and standard buttons inherit the gold/brown system.
- Keep body and placeholder text at WCAG AA contrast of at least 4.5:1.
- Keep visible focus states, keyboard order, `prefers-reduced-motion` handling, and the `(hover: hover) and (pointer: fine)` candle guard.
- The StudyLib wordmark becomes the sidebar trigger; add Home to the sidebar.
- Do not add the reference mockups' bottom-right sparkle artifact.
- Do not refactor unrelated code.

## File Structure

**Create**

- `.github/instructions/dark-theme.instructions.md`: path-scoped source-of-truth pointer for CSS, JS, and Jinja edits.
- `tests/test_dark_theme_contract.py`: standard-library-only contract tests for assets, selectors, markup hooks, accessibility guards, and contrast.
- `static/img/textures/leather-texture.png`: converted supplied leather swatch.
- `static/img/textures/wood-texture.png`: converted supplied wood swatch.
- `static/img/illustrations/compass-rose.svg`
- `static/img/illustrations/sextant.svg`
- `static/img/illustrations/stacked-books.svg`
- `static/img/illustrations/open-book.svg`
- `static/img/illustrations/scrollwork-flourish.svg`

**Modify**

- `templates/layout.html:5-89`: fonts, brand/menu button, Home link, candle layer.
- `templates/macros.html:1-18`: result-card dark-theme class hooks.
- `static/css/custom.css:1-186`: append the complete dark-only token, material, component, illustration, and responsive system.
- `static/js/theme.js:1-33`: replace with theme toggle plus attachable candle controller.
- `static/js/auth.js:15-21`: keep the legacy theme-button renderer on the same line-icon vocabulary.
- `static/js/toast.js:5-12`: replace filled status glyphs with line glyphs.
- `static/js/main.js:6-32`: move sidebar activation from the removed hamburger to the brand button.
- `static/js/card.js:6-28`: result-card materials and control classes.
- `static/js/pages/home.js:8-101`: dashboard page shell, cards, badges, and illustration hooks.
- `static/js/pages/browse.js:30-120,227-272,498-534`: search shell, overview/source panels, load-more control, and illustration hooks.
- `static/js/pages/upload.js:8-44,134-167`: leather dropzone/file panel, empty state, file icons, and illustration hooks.
- `static/js/pages/workspace.js:26-121,175-233,294-313,472-483`: workspace panels, tabs, source rows, notes, and chat bubbles.

## Known Baseline

- The approved design source is commit `7cceff0` on `andy/repository-setup`; implementation starts after this plan's documentation commit.
- `pytest --collect-only -q` currently stops on missing local dependencies: `flask_session`, `bs4`, and `fitz`.
- The focused contract file in this plan imports only the Python standard library and pytest, so each red-green cycle remains runnable even before the full environment is repaired.
- Install `requirements.txt` in the project virtual environment before final full-suite verification.

---

### Task 1: Wire the Source Specification and Install the Supplied Assets

**Files:**
- Create: `.github/instructions/dark-theme.instructions.md`
- Create: `tests/test_dark_theme_contract.py`
- Create: `static/img/textures/leather-texture.png`
- Create: `static/img/textures/wood-texture.png`
- Create: `static/img/illustrations/compass-rose.svg`
- Create: `static/img/illustrations/sextant.svg`
- Create: `static/img/illustrations/stacked-books.svg`
- Create: `static/img/illustrations/open-book.svg`
- Create: `static/img/illustrations/scrollwork-flourish.svg`

**Interfaces:**
- Consumes: `C:\Users\andyh\Downloads\dark-mode-ui-spec.md`, the two supplied JPEGs, and `C:\Users\andyh\Downloads\RE_ the thing i need.zip`.
- Produces: the final asset paths referenced by all later CSS and markup tasks; `read_text(relative_path) -> str` for later contract tests.

- [ ] **Step 1: Create the local environment and repair the known dependency gap**

~~~powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
~~~

Expected: all requirements install successfully. Do not add `.venv` to Git; it is already ignored.

- [ ] **Step 2: Capture the pre-change light-mode baseline**

Start the app in a long-running terminal:

~~~powershell
.\.venv\Scripts\python app.py
~~~

In another terminal, idempotently seed a disposable local QA account and workspace, log in, force light mode, and capture the four core pages:

~~~powershell
.\.venv\Scripts\python -c "import src.db as db; from werkzeug.security import generate_password_hash; u=db.get_user_by_username('candle_qa'); uid=u.id if u else db.create_local_user('candle_qa@example.test','candle_qa',generate_password_hash('CandleQA!2026'),name='Candle QA')['id']; ws=next((w for w in db.get_user_workspaces(uid) if w['name']=='Candlelit QA'),None); print(ws['id'] if ws else db.create_workspace(uid,'Candlelit QA')['id'])"
$baseline = Join-Path $env:TEMP 'studylib-ui-baseline'
New-Item -ItemType Directory -Force -Path $baseline | Out-Null
$env:AGENT_BROWSER_SESSION = 'studylib-candle'
agent-browser open http://127.0.0.1:8010/login
agent-browser find label "Username" fill "candle_qa"
agent-browser find label "Password" fill "CandleQA!2026"
agent-browser find role button click --name "Login"
agent-browser wait --url "http://127.0.0.1:8010/"
agent-browser eval "localStorage.setItem('theme','light'); location.reload()"
agent-browser wait --load networkidle
agent-browser open http://127.0.0.1:8010/
agent-browser set viewport 1440 1000
agent-browser screenshot "$baseline\light-home-1440.png" --full
agent-browser open http://127.0.0.1:8010/browse
agent-browser screenshot "$baseline\light-browse-1440.png" --full
agent-browser open http://127.0.0.1:8010/upload
agent-browser screenshot "$baseline\light-upload-1440.png" --full
agent-browser open http://127.0.0.1:8010/
agent-browser find text "Candlelit QA" click
agent-browser wait --url "http://127.0.0.1:8010/workspace/*"
agent-browser screenshot "$baseline\light-workspace-1440.png" --full
~~~

Expected: four PNGs exist beneath `%TEMP%\studylib-ui-baseline` and contain no dark-theme styling.

- [ ] **Step 3: Write the failing asset and instruction contract**

Create `tests/test_dark_theme_contract.py`:

~~~python
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
~~~

- [ ] **Step 4: Run the focused test and verify the expected red state**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py -v
~~~

Expected: FAIL because `.github/instructions/dark-theme.instructions.md` and the asset directories do not exist.

- [ ] **Step 5: Add the path-scoped instruction file**

Create `.github/instructions/dark-theme.instructions.md`:

~~~markdown
---
applyTo: "static/css/**/*.css,static/js/**/*.js,templates/**/*.html"
---

When editing dark-theme UI, treat `docs/design/dark-mode-ui-spec.md` as the source of truth. Do not touch light-mode styles. Keep all visual overrides scoped beneath `[data-bs-theme="dark"]`.
~~~

- [ ] **Step 6: Convert the texture JPEGs to true PNG files**

~~~powershell
New-Item -ItemType Directory -Force -Path 'static\img\textures' | Out-Null
ffmpeg -hide_banner -loglevel error -y -i 'C:\Users\andyh\Downloads\28ffd7ad-91ef-4bc1-8719-231624a54c50.jpg' -frames:v 1 'static\img\textures\leather-texture.png'
ffmpeg -hide_banner -loglevel error -y -i 'C:\Users\andyh\Downloads\d1028e8b-6d3e-40ef-b9a7-7e6221fa6a2c.jpg' -frames:v 1 'static\img\textures\wood-texture.png'
~~~

Expected: both files start with the PNG signature and retain their source dimensions.

- [ ] **Step 7: Safely extract the five supplied SVGs into their final directory**

~~~powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = 'C:\Users\andyh\Downloads\RE_ the thing i need.zip'
$target = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) 'static\img\illustrations'))
[System.IO.Directory]::CreateDirectory($target) | Out-Null
$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    foreach ($entry in $archive.Entries) {
        $destination = [System.IO.Path]::GetFullPath((Join-Path $target $entry.FullName))
        if (-not $destination.StartsWith(($target + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Unsafe archive entry: $($entry.FullName)"
        }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $true)
    }
}
finally {
    $archive.Dispose()
}
~~~

Expected: exactly the five names in `SVG_NAMES` exist. Do not add the ZIP itself to Git.

- [ ] **Step 8: Run the focused test and verify green**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py -v
~~~

Expected: all asset and instruction tests PASS.

- [ ] **Step 9: Commit the asset intake**

~~~powershell
git add .github/instructions/dark-theme.instructions.md tests/test_dark_theme_contract.py static/img/textures static/img/illustrations
git commit -m "chore: add Candlelit Archive assets"
~~~

---

### Task 2: Add the Dark Theme Foundation and Typography

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `templates/layout.html:5-13`
- Modify: `static/css/custom.css:187` (append foundation block)

**Interfaces:**
- Consumes: Bootstrap 5.3.3 variables already loaded by `templates/layout.html`.
- Produces: the exact color, type, radius, shadow, and z-index tokens used by every later task.

- [ ] **Step 1: Add failing token, font, vignette, and contrast tests**

Append to `tests/test_dark_theme_contract.py`:

~~~python
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
~~~

- [ ] **Step 2: Run the foundation tests and verify red**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py -k "foundation or fonts or wcag" -v
~~~

Expected: token and font tests FAIL because the foundation is absent; contrast-only parameter cases PASS.

- [ ] **Step 3: Load Cinzel and Crimson Pro without changing the light-mode font**

Insert before `custom.css` in `templates/layout.html`:

~~~html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&family=Crimson+Pro:wght@400;600&display=swap" rel="stylesheet">
~~~

- [ ] **Step 4: Append the exact token and global-shell foundation**

Append to `static/css/custom.css`:

~~~css
/* Candlelit Archive: dark theme foundation */
[data-bs-theme="dark"] {
    color-scheme: dark;

    --bg-950: #0A0A0A;
    --bg-900: #14100B;
    --surface-800: #22170B;
    --surface-700: #2E1F0F;
    --surface-600: #3D2914;
    --surface-500: #4D3319;

    --gold-100: #EDD9B5;
    --gold-300: #C9A876;
    --gold-500: #A9824F;
    --gold-700: #8A6635;
    --gold-900: #5C4423;

    --text-primary: #E7E1DA;
    --text-secondary: #A69A8C;
    --text-disabled: #6E6459;

    --danger-rust: #9C6242;
    --info-slate: #6E87A6;
    --success-verdigris: #6E9B7C;

    --font-display: "Cinzel", "Times New Roman", serif;
    --font-body: "Crimson Pro", "EB Garamond", Georgia, serif;

    --text-display-lg: 32px;
    --text-display-sm: 22px;
    --text-body-lg: 16px;
    --text-body: 14px;
    --text-caption: 12px;

    --radius-panel: 12px;
    --radius-button: 8px;
    --radius-pill: 999px;
    --radius-input: 8px;

    --shadow-warm-raised: 0 2px 10px 0 hsl(28 60% 4% / 0.55), 0 0 0 1px hsl(35 40% 40% / 0.06);
    --shadow-warm-glow: 0 0 0 1px var(--gold-500), 0 0 18px 2px hsl(35 70% 55% / 0.25);

    --z-bg-base: 0;
    --z-bg-illustration: 1;
    --z-content: 10;
    --z-candle-glow: 40;
    --z-overlay: 50;

    --bs-body-bg: var(--bg-950);
    --bs-body-color: var(--text-primary);
    --bs-body-font-family: var(--font-body);
    --bs-secondary-color: var(--text-secondary);
    --bs-border-color: hsl(35 40% 45% / 0.18);
    --bs-tertiary-bg: var(--surface-800);
    --bs-card-bg: var(--surface-800);
    --bs-offcanvas-bg: var(--surface-700);
    --bs-primary: var(--gold-300);
    --bs-primary-rgb: 201, 168, 118;
    --bs-secondary: var(--surface-600);
    --bs-secondary-rgb: 61, 41, 20;
    --bs-danger: var(--danger-rust);
    --bs-link-color: var(--gold-300);
    --bs-link-hover-color: var(--gold-100);
}

[data-bs-theme="dark"] body {
    min-height: 100vh;
    color: var(--text-primary);
    background:
        radial-gradient(ellipse 60% 40% at 50% 0%, hsl(32 45% 18% / 0.5), transparent 60%),
        var(--bg-950);
    background-attachment: fixed;
    font-family: var(--font-body);
    font-size: var(--text-body);
}

[data-bs-theme="dark"] h1,
[data-bs-theme="dark"] h2,
[data-bs-theme="dark"] h3,
[data-bs-theme="dark"] h4,
[data-bs-theme="dark"] h5,
[data-bs-theme="dark"] h6,
[data-bs-theme="dark"] .navbar-brand {
    color: var(--gold-100);
    font-family: var(--font-display);
    font-weight: 600;
    letter-spacing: 0.02em;
    text-wrap: balance;
}

[data-bs-theme="dark"] p {
    text-wrap: pretty;
}
~~~

- [ ] **Step 5: Run the foundation tests and the existing focused integration test**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py -k "foundation or fonts or wcag" -v
.\.venv\Scripts\python -m pytest tests/test_integration.py -v
~~~

Expected: all selected tests PASS.

- [ ] **Step 6: Commit the foundation**

~~~powershell
git add templates/layout.html static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: add Candlelit Archive theme foundation"
~~~

---

### Task 3: Build the Shared Material, Control, Icon, Illustration, and Motion System

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `static/css/custom.css` after the foundation block
- Modify: `static/js/toast.js:5-12`

**Interfaces:**
- Consumes: Task 1 asset paths and Task 2 token names.
- Produces: `surface-leather`, `btn-secondary-wood`, `btn-brass`, `btn-ghost`, `icon-button`, `archive-dropdown`, badge classes, focus behavior, scrollbar behavior, and all five illustration mask classes.

- [ ] **Step 1: Add the failing shared-system contract**

Append to `tests/test_dark_theme_contract.py`:

~~~python
def test_shared_dark_theme_materials_and_controls_are_scoped():
    css = read_text("static/css/custom.css")
    required_selectors = (
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
    for selector in required_selectors:
        assert selector in css

    assert 'url("/static/img/textures/leather-texture.png")' in css
    assert 'url("/static/img/textures/wood-texture.png")' in css
    assert "background-blend-mode: multiply" in css
    assert "background-size: auto, 420px" in css
    assert "background-size: auto, 200px" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (hover: none), (pointer: coarse)" in css

    for name in SVG_NAMES:
        assert f'url("/static/img/illustrations/{name}")' in css

    toast = read_text("static/js/toast.js")
    assert "-fill" not in toast
    for icon in ("bi-check-circle", "bi-x-circle", "bi-exclamation-triangle", "bi-info-circle"):
        assert icon in toast
~~~

- [ ] **Step 2: Run the shared-system test and verify red**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_shared_dark_theme_materials_and_controls_are_scoped -v
~~~

Expected: FAIL on the first missing semantic selector and on the still-filled toast glyphs.

- [ ] **Step 3: Append the complete shared material and control system**

Append to `static/css/custom.css`:

~~~css
/* Candlelit Archive: shared materials and controls */
[data-bs-theme="dark"] .surface-leather {
    background-color: var(--surface-800);
    background-image:
        linear-gradient(var(--surface-800), var(--surface-800)),
        url("/static/img/textures/leather-texture.png");
    background-blend-mode: multiply;
    background-position: 0 0;
    background-repeat: repeat, repeat;
    background-size: auto, 420px;
    border: 1px solid hsl(35 40% 45% / 0.18);
    border-radius: var(--radius-panel);
    box-shadow: var(--shadow-warm-raised);
}

[data-bs-theme="dark"] .btn-secondary-wood {
    background-color: var(--surface-700);
    background-image:
        linear-gradient(var(--surface-700), var(--surface-700)),
        url("/static/img/textures/wood-texture.png");
    background-blend-mode: multiply;
    background-position: 0 0;
    background-repeat: repeat, repeat;
    background-size: auto, 200px;
    border: 1px solid hsl(35 40% 45% / 0.22);
    border-radius: var(--radius-button);
    color: var(--gold-300);
}

[data-bs-theme="dark"] .btn-secondary-wood:hover,
[data-bs-theme="dark"] .btn-secondary-wood:active {
    border-color: var(--gold-500);
    color: var(--gold-100);
}

[data-bs-theme="dark"] .btn-brass,
[data-bs-theme="dark"] .btn-primary {
    --bs-btn-color: var(--bg-950);
    --bs-btn-bg: var(--gold-300);
    --bs-btn-border-color: transparent;
    --bs-btn-hover-color: var(--bg-950);
    --bs-btn-hover-bg: var(--gold-100);
    --bs-btn-hover-border-color: transparent;
    --bs-btn-active-color: var(--bg-950);
    --bs-btn-active-bg: var(--gold-500);
    --bs-btn-active-border-color: transparent;
    background-image: linear-gradient(hsl(35 80% 75% / 0.25), transparent 40%);
    border-radius: var(--radius-button);
}

[data-bs-theme="dark"] .btn-ghost {
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-button);
    color: var(--gold-300);
}

[data-bs-theme="dark"] .btn-ghost:hover {
    border-color: var(--gold-700);
    color: var(--gold-100);
}

[data-bs-theme="dark"] .icon-button {
    align-items: center;
    background: transparent;
    border: 0;
    border-radius: var(--radius-button);
    color: var(--gold-300);
    display: inline-flex;
    justify-content: center;
    min-height: 2rem;
    min-width: 2rem;
    padding: 0.25rem;
}

[data-bs-theme="dark"] .icon-button:hover {
    background: hsl(35 70% 55% / 0.08);
    color: var(--gold-100);
}

[data-bs-theme="dark"] .icon-button-danger:hover {
    color: var(--danger-rust);
}

[data-bs-theme="dark"] .archive-dropdown,
[data-bs-theme="dark"] .form-select {
    background-color: var(--surface-700);
    border-color: var(--gold-700);
    border-radius: var(--radius-button);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .dropdown-menu,
[data-bs-theme="dark"] .browse-dropdown-menu {
    background: var(--surface-600);
    border-color: hsl(35 40% 45% / 0.22);
    border-radius: var(--radius-button);
    box-shadow: var(--shadow-warm-raised);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .form-control,
[data-bs-theme="dark"] .input-group-text {
    background: var(--surface-800);
    border-color: hsl(35 40% 45% / 0.3);
    border-radius: var(--radius-input);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .form-control::placeholder,
[data-bs-theme="dark"] textarea::placeholder {
    color: var(--text-secondary);
    opacity: 1;
}

[data-bs-theme="dark"] .form-control:focus,
[data-bs-theme="dark"] .form-select:focus,
[data-bs-theme="dark"] .btn:focus-visible,
[data-bs-theme="dark"] .icon-button:focus-visible,
[data-bs-theme="dark"] .navbar-brand:focus-visible {
    border-color: var(--gold-300);
    box-shadow: var(--shadow-warm-glow);
    outline: 0;
}

[data-bs-theme="dark"] .text-muted {
    color: var(--text-secondary) !important;
}

[data-bs-theme="dark"] .archive-count-badge {
    background: var(--gold-900);
    border-radius: var(--radius-pill);
    color: var(--gold-100);
    font-size: var(--text-caption);
    font-variant-numeric: tabular-nums;
}

[data-bs-theme="dark"] .archive-category-badge {
    background: hsl(35 40% 45% / 0.15);
    border-radius: var(--radius-pill);
    color: var(--gold-300);
    font-size: var(--text-caption);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

[data-bs-theme="dark"] .card {
    --bs-card-bg: var(--surface-800);
    --bs-card-border-color: hsl(35 40% 45% / 0.18);
}

[data-bs-theme="dark"] .offcanvas {
    --bs-offcanvas-bg: var(--surface-700);
}

[data-bs-theme="dark"] .bi {
    color: var(--gold-300);
}

[data-bs-theme="dark"] ::-webkit-scrollbar {
    height: 10px;
    width: 10px;
}

[data-bs-theme="dark"] ::-webkit-scrollbar-track {
    background: transparent;
}

[data-bs-theme="dark"] ::-webkit-scrollbar-thumb {
    background: var(--gold-700);
    border: 2px solid var(--surface-800);
    border-radius: var(--radius-pill);
}

[data-bs-theme="dark"] * {
    scrollbar-color: var(--gold-700) transparent;
    scrollbar-width: thin;
}

[data-bs-theme="dark"] .archive-illustration {
    --illustration-image: none;
    background-color: var(--gold-700);
    display: block;
    mask-image: var(--illustration-image);
    mask-position: center;
    mask-repeat: no-repeat;
    mask-size: contain;
    opacity: 0.06;
    pointer-events: none;
    position: absolute;
    z-index: var(--z-bg-illustration);
}

[data-bs-theme="dark"] .illustration-compass {
    --illustration-image: url("/static/img/illustrations/compass-rose.svg");
}

[data-bs-theme="dark"] .illustration-sextant {
    --illustration-image: url("/static/img/illustrations/sextant.svg");
}

[data-bs-theme="dark"] .illustration-books {
    --illustration-image: url("/static/img/illustrations/stacked-books.svg");
}

[data-bs-theme="dark"] .illustration-open-book {
    --illustration-image: url("/static/img/illustrations/open-book.svg");
}

[data-bs-theme="dark"] .illustration-flourish {
    --illustration-image: url("/static/img/illustrations/scrollwork-flourish.svg");
}

@media (prefers-reduced-motion: reduce) {
    [data-bs-theme="dark"] *,
    [data-bs-theme="dark"] *::before,
    [data-bs-theme="dark"] *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
    }
}

@media (hover: none), (pointer: coarse) {
    [data-bs-theme="dark"] .archive-illustration {
        opacity: 0.045;
    }
}
~~~

- [ ] **Step 4: Move toast status glyphs onto the same line-icon vocabulary**

In `static/js/toast.js`, replace only the icon map values:

~~~javascript
const iconMap = {
    success: "bi-check-circle text-success",
    danger: "bi-x-circle text-danger",
    warning: "bi-exclamation-triangle text-warning",
    info: "bi-info-circle text-info"
};
~~~

Preserve toast roles, text, timing, and dismissal behavior.

- [ ] **Step 5: Run the focused contract and inspect the diff for accidental bare dark selectors**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_shared_dark_theme_materials_and_controls_are_scoped -v
git diff --check
git diff -- static/css/custom.css static/js/toast.js
~~~

Expected: test PASS, `git diff --check` exits 0, and every new visual selector begins with `[data-bs-theme="dark"]` except `@keyframes` and media-query wrappers.

- [ ] **Step 6: Commit the shared system**

~~~powershell
git add static/css/custom.css static/js/toast.js tests/test_dark_theme_contract.py
git commit -m "feat: add Candlelit Archive materials"
~~~

---

### Task 4: Replace the Hamburger With the Accessible Wordmark Menu Trigger

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `templates/layout.html:15-69`
- Modify: `static/js/main.js:6-34`
- Modify: `static/js/theme.js:15-21`
- Modify: `static/js/auth.js:15-21`
- Modify: `static/css/custom.css`

**Interfaces:**
- `#brandMenuButton` owns `aria-controls="navSidebarOverlay"` and keeps `aria-expanded` synchronized with the sidebar.
- `#navSidebarOverlay` keeps `aria-hidden` synchronized with `d-none`.
- Escape, overlay click, and the close button all use one `closeSidebar()` path and return focus to the wordmark.
- The existing theme toggle behavior remains unchanged; only its accessible label and line-style glyphs change in this task.

- [ ] **Step 1: Add the failing navigation contract**

Append to `tests/test_dark_theme_contract.py`:

~~~python
def test_navigation_uses_wordmark_trigger_and_home_entry():
    layout = read_text("templates/layout.html")
    main = read_text("static/js/main.js")
    theme = read_text("static/js/theme.js")
    auth = read_text("static/js/auth.js")

    assert 'id="brandMenuButton"' in layout
    assert 'aria-controls="navSidebarOverlay"' in layout
    assert 'aria-expanded="false"' in layout
    assert 'id="navMenuButton"' not in layout
    assert '<a class="list-group-item list-group-item-action" href="/">Home</a>' in layout
    assert 'id="navSidebarOverlay"' in layout
    assert 'aria-hidden="true"' in layout

    assert "getElementById('brandMenuButton')" in main
    assert "event.key === 'Escape'" in main
    assert 'setAttribute("aria-expanded", "true")' in main
    assert 'setAttribute("aria-expanded", "false")' in main
    assert 'setAttribute("aria-hidden", "false")' in main
    assert 'setAttribute("aria-hidden", "true")' in main
    assert "brandMenuButton.focus()" in main

    assert "-fill" not in layout + theme + auth
    assert 'setAttribute("aria-label"' in theme
    assert 'setAttribute("aria-label"' in auth
~~~

- [ ] **Step 2: Run the focused test and verify the red state**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_navigation_uses_wordmark_trigger_and_home_entry -v
~~~

Expected: FAIL because the layout still contains `#navMenuButton` and has no Home entry.

- [ ] **Step 3: Update the shared layout without changing route behavior**

In `templates/layout.html`:

1. Add `archive-navbar` to the `<nav>` class list:

~~~diff
-<nav class="navbar bg-body-tertiary border-bottom shadow-sm sticky-top">
+<nav class="navbar archive-navbar bg-body-tertiary border-bottom shadow-sm sticky-top">
~~~

2. Replace the hamburger and anchor with a real button:

~~~html
<button
    class="navbar-brand archive-wordmark mb-0"
    id="brandMenuButton"
    type="button"
    aria-label="Open navigation menu"
    aria-controls="navSidebarOverlay"
    aria-expanded="false"
>
    StudyLib
</button>
~~~

3. Change the theme control to an accessible line icon:

~~~html
<button class="btn icon-button" id="themeToggle" type="button" aria-label="Switch to dark theme">
    <i class="bi bi-moon-stars" aria-hidden="true"></i>
</button>
~~~

4. Replace the Login/Logout link class values without changing their Jinja branches or routes:

~~~html
<a class="btn btn-outline-secondary btn-ghost btn-sm" href="{{ url_for('logout') }}">LOGOUT</a>
<a class="btn btn-outline-secondary btn-ghost btn-sm" href="{{ url_for('login') }}">LOGIN</a>
~~~

5. Change the sidebar opening markup to:

~~~html
<div id="navSidebarOverlay" class="nav-sidebar-overlay d-none" aria-hidden="true">
    <div class="nav-sidebar surface-leather" role="dialog" aria-modal="true" aria-labelledby="navSidebarTitle">
        <div class="d-flex align-items-center justify-content-between mb-4">
            <div>
                <h5 id="navSidebarTitle" class="mb-0">Menu</h5>
                <p class="text-muted small mb-0">Quick navigation</p>
            </div>
            <button class="btn icon-button" id="closeNavSidebarBtn" type="button" aria-label="Close menu">
                <i class="bi bi-x-lg" aria-hidden="true"></i>
            </button>
        </div>
        <div class="list-group">
            <a class="list-group-item list-group-item-action" href="/">Home</a>
            <a class="list-group-item list-group-item-action" href="/browse">Browse</a>
            <a class="list-group-item list-group-item-action" href="/upload">Upload</a>
        </div>
    </div>
</div>
~~~

Do not use `open-book.svg` in the nav; that file remains decoration-only.

- [ ] **Step 4: Move the existing menu behavior onto the wordmark**

Replace `initNavigation()` in `static/js/main.js`:

~~~javascript
function initNavigation() {
    const brandMenuButton = document.getElementById('brandMenuButton');
    const navOverlay = document.getElementById('navSidebarOverlay');
    const closeButton = document.getElementById('closeNavSidebarBtn');

    if (!brandMenuButton || !navOverlay) return;

    const openSidebar = () => {
        navOverlay.classList.remove('d-none');
        navOverlay.setAttribute("aria-hidden", "false");
        brandMenuButton.setAttribute("aria-expanded", "true");
        document.body.classList.add('nav-sidebar-open');
        closeButton?.focus();
    };

    const closeSidebar = () => {
        navOverlay.classList.add('d-none');
        navOverlay.setAttribute("aria-hidden", "true");
        brandMenuButton.setAttribute("aria-expanded", "false");
        document.body.classList.remove('nav-sidebar-open');
        brandMenuButton.focus();
    };

    brandMenuButton.addEventListener('click', openSidebar);
    closeButton?.addEventListener('click', closeSidebar);

    navOverlay.addEventListener('click', (event) => {
        if (event.target === navOverlay) closeSidebar();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !navOverlay.classList.contains('d-none')) {
            closeSidebar();
        }
    });
}
~~~

- [ ] **Step 5: Keep the theme toggle accessible while preserving its behavior**

Replace the complete `updateThemeButton()` function in both `static/js/theme.js` and the legacy `static/js/auth.js` with:

~~~javascript
function updateThemeButton() {
    const themeBtn = document.getElementById("themeToggle");
    if (!themeBtn) return;

    const current = document.documentElement.getAttribute("data-bs-theme");
    const isDark = current === "dark";
    themeBtn.innerHTML = isDark
        ? '<i class="bi bi-sun" aria-hidden="true"></i>'
        : '<i class="bi bi-moon-stars" aria-hidden="true"></i>';
    themeBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
}
~~~

- [ ] **Step 6: Add the dark-only navigation treatment**

Append to `static/css/custom.css`:

~~~css
[data-bs-theme="dark"] .archive-navbar {
    background: var(--surface-800) !important;
    border-bottom-color: hsl(35 40% 45% / 0.12) !important;
    box-shadow: 0 4px 18px hsl(28 60% 4% / 0.35) !important;
}

[data-bs-theme="dark"] .archive-wordmark {
    appearance: none;
    background: transparent;
    border: 0;
    color: var(--gold-100);
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 0.35rem 0.5rem;
}

[data-bs-theme="dark"] .archive-wordmark:hover {
    color: var(--gold-300);
}

[data-bs-theme="dark"] .archive-wordmark:focus-visible {
    border-radius: var(--radius-button);
    box-shadow: var(--shadow-warm-glow);
    outline: 0;
}

[data-bs-theme="dark"] .nav-sidebar-overlay {
    background: hsl(28 60% 4% / 0.72);
}

[data-bs-theme="dark"] .nav-sidebar {
    border-radius: 0 var(--radius-panel) var(--radius-panel) 0;
}

[data-bs-theme="dark"] .nav-sidebar .list-group-item {
    background: transparent;
    border-color: hsl(35 40% 45% / 0.12);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .nav-sidebar .list-group-item:hover,
[data-bs-theme="dark"] .nav-sidebar .list-group-item:focus-visible {
    background: hsl(35 70% 55% / 0.1);
    color: var(--gold-100);
}
~~~

- [ ] **Step 7: Verify keyboard behavior and commit**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_navigation_uses_wordmark_trigger_and_home_entry -v
git diff --check
git add templates/layout.html static/js/main.js static/js/theme.js static/js/auth.js static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: add wordmark navigation trigger"
~~~

Expected: the contract passes; later browser QA must confirm click, Escape, focus return, and the Home route.

---

### Task 5: Build the Candlelit Archive Workspace Dashboard

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `static/js/pages/home.js:8-101`
- Modify: `static/css/custom.css`

**Interfaces:**
- Preserve `loadWorkspaces()`, `renderWorkspaceCards()`, `createWorkspaceDialog()`, and all existing API URLs.
- New classes are semantic hooks only; every visual rule stays under `[data-bs-theme="dark"]`.
- The stacked-books and flourish SVGs remain decorative with `aria-hidden="true"`.

- [ ] **Step 1: Add the failing dashboard contract**

Append:

~~~python
def test_dashboard_has_archive_hooks_without_changing_data_flow():
    home = read_text("static/js/pages/home.js")
    required = (
        "archive-page archive-page-home",
        "archive-content",
        "archive-page-title",
        "archive-illustration illustration-books",
        "archive-illustration illustration-flourish",
        "surface-leather workspace-card",
        "workspace-card-add",
        "archive-category-badge",
        ">WORKSPACE<",
        "loadWorkspaces()",
        "createWorkspaceDialog",
        "fetch('/api/workspaces')",
    )
    for marker in required:
        assert marker in home
    assert "WORRSPACE" not in home
~~~

- [ ] **Step 2: Verify the expected red state**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_dashboard_has_archive_hooks_without_changing_data_flow -v
~~~

Expected: FAIL on the missing archive shell and material hooks.

- [ ] **Step 3: Add the page shell and decorative layer**

Change the opening and closing markup assigned in `initHome()` to this structure while keeping the existing header/search content and IDs inside `.archive-content`:

~~~javascript
root.innerHTML = `
    <div class="container-fluid py-4 archive-page archive-page-home">
        <span class="archive-illustration illustration-books" aria-hidden="true"></span>
        <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
        <div class="archive-content">
            <div class="d-flex flex-column flex-md-row align-items-start align-items-md-center justify-content-between gap-3 mb-4">
                <div>
                    <h1 class="archive-page-title mb-1">Recent Workspaces</h1>
                    <p class="text-muted mb-0">Jump back into your most recent work or search for the right workspace.</p>
                </div>
                <div class="input-group home-search-group">
                    <span class="input-group-text"><i class="bi bi-search" aria-hidden="true"></i></span>
                    <input id="workspaceSearch" type="search" class="form-control" placeholder="Search workspaces..." autocomplete="off">
                </div>
            </div>
            <div id="workspaceCards" class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3"></div>
        </div>
    </div>
`;
~~~

- [ ] **Step 4: Add semantic hooks to both card variants**

Make these exact substitutions in `renderWorkspaceCards()`; no title, metadata, date, `stretched-link`, escaping, or listener line changes:

~~~diff
-<div class="card h-100 border-dashed workspace-card workspace-card-add text-center text-muted">
+<div class="card h-100 workspace-card workspace-card-add text-center text-muted">
~~~

~~~diff
-<div class="card h-100 workspace-card position-relative">
+<div class="card h-100 surface-leather workspace-card position-relative">
~~~

~~~diff
-<div class="badge bg-primary bg-opacity-10 text-primary">Workspace</div>
-<i class="bi bi-three-dots-vertical text-muted"></i>
+<div class="badge archive-category-badge">WORKSPACE</div>
+<span class="icon-button" aria-hidden="true"><i class="bi bi-three-dots-vertical"></i></span>
~~~

- [ ] **Step 5: Add dashboard layout and card states**

Append:

~~~css
[data-bs-theme="dark"] .archive-page {
    min-height: calc(100vh - 58px);
    overflow: hidden;
    position: relative;
}

[data-bs-theme="dark"] .archive-content {
    position: relative;
    z-index: var(--z-content);
}

[data-bs-theme="dark"] .archive-page-title {
    color: var(--gold-100);
    font-family: var(--font-display);
    font-size: var(--text-display-lg);
    font-weight: 600;
}

[data-bs-theme="dark"] .home-search-group {
    max-width: 560px;
    width: 100%;
}

[data-bs-theme="dark"] .workspace-card {
    min-height: 220px;
    transition: border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

[data-bs-theme="dark"] .workspace-card:not(.workspace-card-add):hover {
    border-color: hsl(35 50% 55% / 0.35);
    box-shadow: var(--shadow-warm-glow);
    transform: translateY(-2px);
}

[data-bs-theme="dark"] .workspace-card-add {
    background: transparent;
    border: 2px dashed hsl(35 50% 55% / 0.35);
    border-radius: var(--radius-panel);
    color: var(--gold-300) !important;
    cursor: pointer;
}

[data-bs-theme="dark"] .workspace-card-add:hover,
[data-bs-theme="dark"] .workspace-card-add:focus-within {
    background: hsl(35 70% 55% / 0.05);
    border-color: var(--gold-300);
    box-shadow: var(--shadow-warm-glow);
}

[data-bs-theme="dark"] .archive-page-home .illustration-books {
    bottom: 0;
    left: 0;
    height: 160px;
    width: 240px;
}

[data-bs-theme="dark"] .archive-page-home .illustration-flourish {
    bottom: 0;
    right: 0;
    height: 180px;
    transform: scaleX(-1);
    width: 180px;
}

@media (max-width: 575.98px) {
    [data-bs-theme="dark"] .archive-page-title {
        font-size: 1.65rem;
    }

    [data-bs-theme="dark"] .workspace-card {
        min-height: 190px;
    }
}
~~~

- [ ] **Step 6: Run the contract, existing home tests, and commit**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_dashboard_has_archive_hooks_without_changing_data_flow tests/test_integration.py -v
git diff --check
git add static/js/pages/home.js static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: style Candlelit Archive dashboard"
~~~

Expected: the focused contract and existing integration tests pass; workspace creation/opening code remains unchanged.

---

### Task 6: Style Browse, Search Results, and Shared Result Cards

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `static/js/pages/browse.js:30-120,227-272,498-534`
- Modify: `static/js/card.js:6-28`
- Modify: `templates/macros.html:1-18`
- Modify: `static/css/custom.css`

**Interfaces:**
- Preserve browse state, filters, search endpoints, pagination, viewer behavior, and workspace-add behavior.
- Keep both result-card renderers aligned because `static/js/card.js` renders client results while `templates/macros.html` remains the server-side equivalent.
- The Go action is brass; View/Add/Load more are wood; Filters and workspace selection use the dropdown treatment.

- [ ] **Step 1: Add the failing browse/card contract**

Append:

~~~python
def test_browse_and_result_cards_use_archive_components():
    browse = read_text("static/js/pages/browse.js")
    card = read_text("static/js/card.js")
    macros = read_text("templates/macros.html")

    for marker in (
        "archive-page archive-page-browse",
        "browse-search-shell",
        "btn-brass",
        "archive-dropdown",
        "surface-leather ai-overview-panel",
        "surface-leather source-summary-panel",
        "archive-illustration illustration-books",
        "archive-illustration illustration-flourish",
        "archive-count-badge",
        "btn-secondary-wood",
    ):
        assert marker in browse

    for source in (card, macros):
        assert "surface-leather result-card" in source
        assert "result-source" in source
        assert "icon-button" in source
        assert source.count("btn-secondary-wood") >= 2
        assert "-fill" not in source

    assert "archive-dropdown workspace-select" in card
~~~

- [ ] **Step 2: Verify the red state**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_browse_and_result_cards_use_archive_components -v
~~~

Expected: FAIL because browse and card renderers still use generic Bootstrap surfaces and controls.

- [ ] **Step 3: Add the browse page shell and control roles**

Immediately inside the `initBrowse()` template literal, before the current top-level search-shell element, add:

~~~html
<div class="container-fluid archive-page archive-page-browse">
    <span class="archive-illustration illustration-books" aria-hidden="true"></span>
    <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
    <div class="archive-content">
~~~

Immediately before the template literal's closing backtick, add the two matching closing tags:

~~~html
    </div>
</div>
~~~

Then make these targeted class substitutions without changing IDs or listeners:

~~~diff
-<div class="bg-body-tertiary border-bottom p-3 mb-3">
+<div class="browse-search-shell p-3 mb-3">
~~~

~~~diff
-<button class="btn btn-primary" id="goBtn">Go</button>
+<button class="btn btn-brass" id="goBtn">Go</button>
~~~

~~~diff
-<button class="btn btn-outline-secondary dropdown-toggle" type="button" id="filtersDropdown">Filters</button>
+<button class="btn archive-dropdown dropdown-toggle" type="button" id="filtersDropdown">Filters</button>
~~~

~~~diff
-<div class="browse-dropdown-menu p-3"
+<div class="browse-dropdown-menu archive-dropdown-menu p-3"
~~~

Make the panel, count, and pagination substitutions at their existing render sites:

~~~diff
-<div class="card mb-3">
+<div class="card surface-leather ai-overview-panel mb-3">
~~~

~~~diff
-let html = '<div class="card mb-3">';
+let html = '<div class="card surface-leather source-summary-panel mb-3">';
~~~

~~~diff
-<span class="badge bg-primary rounded-pill">${count}</span>
+<span class="badge archive-count-badge">${count}</span>
~~~

~~~diff
-<button class="btn btn-outline-primary" id="loadMoreBtn">
+<button class="btn btn-secondary-wood" id="loadMoreBtn">
~~~

Preserve all existing element IDs and listeners.

- [ ] **Step 4: Align both result-card renderers**

In `static/js/card.js`, replace `card.className` and the full `card.innerHTML` assignment with:

~~~javascript
card.className = 'card card-fixed surface-leather result-card rounded-3 h-100';
card.innerHTML = `
    <img src="${item.thumb_url || '/static/img/placeholder.png'}" class="card-img-top" style="height: 130px; object-fit: contain; background-color: var(--bs-body-secondary);" alt="">
    <div class="card-body">
        <h6 class="card-title text-truncate mb-1">${item.title}</h6>
        <p class="card-text small text-muted card-description mb-2">${item.description}</p>
        <div class="d-flex align-items-center justify-content-between">
            <small class="result-source"><i class="bi bi-globe2" aria-hidden="true"></i> ${item.source_name}</small>
            <button class="btn icon-button save-btn" data-item-id="${item.id}" type="button" aria-label="${item.saved ? 'Remove saved result' : 'Save result'}" aria-pressed="${item.saved ? 'true' : 'false'}">
                <i class="bi ${item.saved ? 'bi-bookmark-check' : 'bi-bookmark'}" aria-hidden="true"></i>
            </button>
        </div>
    </div>
    <div class="card-footer bg-transparent border-top p-2 d-flex gap-2">
        <button class="btn btn-secondary-wood btn-sm w-50 view-btn" data-item-id="${item.id}">View</button>
        <button class="btn btn-secondary-wood btn-sm w-50 add-btn" data-item-id="${item.id}">Add</button>
    </div>
    <div class="d-flex align-items-center gap-2 mt-2">
        <select class="form-select form-select-sm archive-dropdown workspace-select" aria-label="Choose workspace"></select>
    </div>
`;
~~~

Keep the existing listener code below this assignment unchanged.

In `templates/macros.html`, replace the complete `card(item)` macro with:

~~~html
{% macro card(item) %}
<div class="card card-fixed surface-leather result-card rounded-3 h-100">
    <img src="{{ item.thumb_url or '/static/img/placeholder.png' }}" class="card-img-top" style="height: 130px; object-fit: contain; background-color: var(--bs-body-secondary);" alt="">
    <div class="card-body">
        <h6 class="card-title text-truncate mb-1">{{ item.title }}</h6>
        <p class="card-text small text-muted card-description mb-2">{{ item.description }}</p>
        <div class="d-flex align-items-center justify-content-between">
            <small class="result-source"><i class="bi bi-globe2" aria-hidden="true"></i> {{ item.source_name }}</small>
            <button class="btn icon-button save-btn" data-item-id="{{ item.id }}" type="button" aria-label="{{ 'Remove saved result' if item.saved else 'Save result' }}" aria-pressed="{{ 'true' if item.saved else 'false' }}">
                <i class="bi {{ 'bi-bookmark-check' if item.saved else 'bi-bookmark' }}" aria-hidden="true"></i>
            </button>
        </div>
    </div>
    <div class="card-footer bg-transparent border-top p-2 d-flex gap-2">
        <button class="btn btn-secondary-wood btn-sm w-50 view-btn" data-item-id="{{ item.id }}">View</button>
        <button class="btn btn-secondary-wood btn-sm w-50 add-btn" data-item-id="{{ item.id }}">Add</button>
    </div>
</div>
{% endmacro %}
~~~

Leave the separate `workspace_card(item)` macro unchanged.

- [ ] **Step 5: Add browse/search/card styling**

Append:

~~~css
[data-bs-theme="dark"] .archive-page-browse {
    padding: 0 0 2rem;
}

[data-bs-theme="dark"] .browse-search-shell {
    background: hsl(28 45% 8% / 0.78);
    border-bottom: 1px solid hsl(35 40% 45% / 0.12);
    position: relative;
    z-index: calc(var(--z-content) + 1);
}

[data-bs-theme="dark"] .browse-search-group {
    margin-inline: auto;
    max-width: 960px;
}

[data-bs-theme="dark"] .browse-dropdown-menu {
    background: var(--surface-600);
    border: 1px solid hsl(35 40% 45% / 0.25);
    border-radius: var(--radius-panel);
    box-shadow: var(--shadow-warm-raised);
    transition: opacity 180ms ease-out, transform 180ms ease-out;
}

[data-bs-theme="dark"] .ai-overview-panel,
[data-bs-theme="dark"] .source-summary-panel {
    margin-bottom: 1rem;
    padding: 1.25rem;
}

[data-bs-theme="dark"] .ai-overview-panel h2,
[data-bs-theme="dark"] .source-summary-panel h2 {
    color: var(--gold-100);
    font-family: var(--font-display);
    font-size: var(--text-display-sm);
}

[data-bs-theme="dark"] .result-card {
    overflow: hidden;
    transition: border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

[data-bs-theme="dark"] .result-card:hover {
    border-color: hsl(35 50% 55% / 0.35);
    box-shadow: var(--shadow-warm-glow);
    transform: translateY(-2px);
}

[data-bs-theme="dark"] .result-card img {
    filter: none;
}

[data-bs-theme="dark"] .result-source {
    color: var(--gold-300);
    font-size: var(--text-caption);
}

[data-bs-theme="dark"] .result-card .card-text {
    color: var(--text-secondary);
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}

[data-bs-theme="dark"] .archive-page-browse .illustration-books {
    bottom: 0;
    height: 160px;
    left: 0;
    width: 240px;
}

[data-bs-theme="dark"] .archive-page-browse .illustration-flourish {
    bottom: 0;
    height: 180px;
    right: 0;
    transform: scaleX(-1);
    width: 180px;
}

@media (max-width: 767.98px) {
    [data-bs-theme="dark"] .browse-search-group {
        align-items: stretch;
        display: grid;
        grid-template-columns: 1fr auto auto;
    }

    [data-bs-theme="dark"] .browse-search-group .input-group-text {
        display: none;
    }

    [data-bs-theme="dark"] .browse-search-input {
        min-width: 0;
    }
}
~~~

- [ ] **Step 6: Run focused and existing search tests, then commit**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_browse_and_result_cards_use_archive_components tests/test_search.py -v
git diff --check
git add static/js/pages/browse.js static/js/card.js templates/macros.html static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: style Candlelit Archive search"
~~~

Expected: result-card behavior and search tests pass, and both render paths expose the same visual hooks.

---

### Task 7: Build the Leather Upload and File-Library View

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `static/js/pages/upload.js:8-44,134-167`
- Modify: `static/css/custom.css`

**Interfaces:**
- Preserve `setupUploadZone()`, `handleFile()`, `uploadFile()`, `deleteFile()`, all accepted file types, the 10 MB limit, and all `/api/files/*` endpoints.
- File-type color comes from a semantic `file-icon-${file.file_type}` hook.
- The open-book SVG appears only when the file list is empty.

- [ ] **Step 1: Add the failing upload contract**

Append:

~~~python
def test_upload_view_uses_leather_file_components_and_safe_decorations():
    upload = read_text("static/js/pages/upload.js")
    for marker in (
        "archive-page archive-page-upload",
        "archive-content upload-content",
        "archive-illustration illustration-compass",
        "archive-illustration illustration-sextant",
        "archive-illustration illustration-flourish",
        "surface-leather upload-zone",
        "surface-leather file-list-panel",
        "btn-brass",
        "archive-count-badge",
        "illustration-open-book",
        "file-icon-${file.file_type}",
        "icon-button icon-button-danger delete-btn",
        "setupUploadZone()",
        "loadUploadedFiles()",
        "fetch('/api/files/upload'",
        "fetch('/api/files/list')",
    ):
        assert marker in upload
~~~

- [ ] **Step 2: Run the focused test and verify red**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_upload_view_uses_leather_file_components_and_safe_decorations -v
~~~

Expected: FAIL because the upload page has no archive shell or semantic material hooks.

- [ ] **Step 3: Reshape only the upload markup**

Replace the static markup in `initUpload()` with the same IDs and content inside this shell:

~~~javascript
pageRoot.innerHTML = `
    <div class="container-fluid py-4 archive-page archive-page-upload">
        <span class="archive-illustration illustration-compass" aria-hidden="true"></span>
        <span class="archive-illustration illustration-sextant" aria-hidden="true"></span>
        <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
        <div class="archive-content upload-content">
            <div class="card p-0 mb-4 upload-panel">
                <div class="card-body text-center p-5 surface-leather upload-zone" id="uploadZone">
                    <i class="bi bi-cloud-upload archive-upload-icon" aria-hidden="true"></i>
                    <h6 class="mt-3">Drag files here or click to browse</h6>
                    <p class="small text-muted">Maximum 10MB</p>
                    <input type="file" id="fileInput" accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.gif,.webp,.xlsx,.xls" hidden>
                </div>
                <div class="p-3 upload-actions">
                    <p class="mb-3"><strong>Selected:</strong> <span id="selectedFile">No file selected</span></p>
                    <div class="progress mb-3" hidden id="progressBar">
                        <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                    </div>
                    <button class="btn btn-brass w-100" id="uploadBtn" disabled>Upload File</button>
                </div>
            </div>
            <div class="card surface-leather file-list-panel">
                <div class="card-header d-flex align-items-center">
                    <i class="bi bi-files me-2" aria-hidden="true"></i>
                    <h5 class="mb-0">Your Files</h5>
                    <span class="badge archive-count-badge ms-2" id="fileCountBadge">0</span>
                </div>
                <div class="card-body p-0">
                    <ul class="list-group list-group-flush" id="filesList"></ul>
                </div>
            </div>
        </div>
    </div>
`;
~~~

Keep the progress-bar show/hide logic compatible with the `hidden` attribute by making these exact substitutions in `uploadFile()`:

~~~diff
-progressBar.style.display = 'block';
+progressBar.hidden = false;
~~~

Replace both failure/success hide writes with:

~~~diff
-progressBar.style.display = 'none';
+progressBar.hidden = true;
~~~

- [ ] **Step 4: Add the empty state and file-row hooks**

After clearing the list and setting the badge in `loadUploadedFiles()`, add:

~~~javascript
if (result.files.length === 0) {
    container.innerHTML = `
        <li class="list-group-item upload-empty-state text-center">
            <span class="archive-illustration illustration-open-book" aria-hidden="true"></span>
            <p class="mb-0 text-muted">No files uploaded yet.</p>
        </li>
    `;
    return;
}
~~~

Change each file icon to:

~~~html
<i class="bi bi-${icon} file-icon file-icon-${file.file_type}" aria-hidden="true"></i>
~~~

Change each delete button to:

~~~html
<button class="btn icon-button icon-button-danger delete-btn" data-id="${file.id}" type="button" aria-label="Delete file">
    <i class="bi bi-trash" aria-hidden="true"></i>
</button>
~~~

Keep the existing filename, size calculation, delete confirmation, and event listener intact.

- [ ] **Step 5: Add upload/dropzone/file-list styling**

Append:

~~~css
[data-bs-theme="dark"] .upload-content {
    margin-inline: auto;
    max-width: 700px;
}

[data-bs-theme="dark"] .upload-panel {
    background: transparent;
    border: 0;
}

[data-bs-theme="dark"] .upload-zone {
    border: 2px dashed hsl(35 50% 55% / 0.35);
    border-radius: var(--radius-panel);
}

[data-bs-theme="dark"] .upload-zone:hover,
[data-bs-theme="dark"] .upload-zone.dragover {
    background-color: var(--surface-700);
    border-color: var(--gold-300);
    box-shadow: var(--shadow-warm-glow);
}

[data-bs-theme="dark"] .archive-upload-icon {
    color: var(--gold-300);
    font-size: 3rem;
}

[data-bs-theme="dark"] .upload-actions {
    color: var(--text-primary);
}

[data-bs-theme="dark"] .file-list-panel {
    overflow: hidden;
}

[data-bs-theme="dark"] .file-list-panel .card-header,
[data-bs-theme="dark"] .file-list-panel .list-group-item {
    background: transparent;
    border-color: hsl(35 40% 45% / 0.14);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .file-icon {
    color: var(--gold-300);
    font-size: 1.35rem;
}

[data-bs-theme="dark"] .file-icon-pdf {
    color: var(--danger-rust);
}

[data-bs-theme="dark"] .file-icon-docx {
    color: var(--info-slate);
}

[data-bs-theme="dark"] .upload-empty-state {
    min-height: 190px;
    position: relative;
}

[data-bs-theme="dark"] .upload-empty-state .illustration-open-book {
    display: block;
    height: 112px;
    margin: 0 auto 0.75rem;
    position: relative;
    width: 160px;
}

[data-bs-theme="dark"] .archive-page-upload .illustration-compass {
    height: 180px;
    left: 1rem;
    top: 1rem;
    width: 180px;
}

[data-bs-theme="dark"] .archive-page-upload .illustration-sextant {
    height: 200px;
    right: 1rem;
    top: 24%;
    width: 200px;
}

[data-bs-theme="dark"] .archive-page-upload > .illustration-flourish {
    bottom: 0;
    height: 180px;
    right: 0;
    transform: scaleX(-1);
    width: 180px;
}

@media (max-width: 991.98px) {
    [data-bs-theme="dark"] .archive-page-upload > .illustration-sextant {
        display: none;
    }
}

@media (max-width: 575.98px) {
    [data-bs-theme="dark"] .upload-zone {
        padding: 2.5rem 1.25rem !important;
    }

    [data-bs-theme="dark"] .archive-page-upload > .illustration-compass {
        height: 120px;
        left: -2rem;
        width: 120px;
    }
}
~~~

- [ ] **Step 6: Run focused and existing upload tests, then commit**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_upload_view_uses_leather_file_components_and_safe_decorations tests/test_upload.py -v
git diff --check
git add static/js/pages/upload.js static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: style Candlelit Archive uploads"
~~~

Expected: upload validation, upload/delete APIs, and the new contract pass.

---

### Task 8: Build the Workspace Notes, Source Studio, and Parchment Chat

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `static/js/pages/workspace.js:26-121,175-233,294-313,472-483`
- Modify: `static/css/custom.css`

**Interfaces:**
- Preserve workspace loading, source selection and preview, note CRUD, resize behavior, tab IDs/Bootstrap attributes, and Alexander chat calls.
- `message.role` maps only to `chat-row-agent`/`chat-message-agent` or `chat-row-user`/`chat-message-user`.
- User bubble text uses `--text-primary`, resolving the approved source-spec assumption.

- [ ] **Step 1: Add the failing workspace contract**

Append:

~~~python
def test_workspace_has_archive_panels_tabs_sources_notes_and_chat():
    workspace = read_text("static/js/pages/workspace.js")
    css = read_text("static/css/custom.css")
    required = (
        "archive-page archive-page-workspace",
        "archive-page-title",
        "archive-illustration illustration-books",
        "archive-illustration illustration-flourish",
        "surface-leather workspace-main-panel",
        "surface-leather workspace-right-panel",
        "btn-secondary-wood",
        "archive-count-badge",
        "quick-note-input",
        "source-preview-shell",
        "workspace-source-item",
        "workspace-source-name",
        "note-item",
        "chat-messages",
        "chat-row-agent",
        "chat-row-user",
        "chat-message-agent",
        "chat-message-user",
        "chat-avatar",
        "btn-brass",
    )
    for marker in required:
        assert marker in workspace

    for preserved in (
        "workspace-tabs nav nav-pills",
        "loadWorkspaceDetails()",
        "renderSelectedSource()",
        "loadWorkspaceNotes()",
        "sendAlexanderMessage",
        "studyHelperAI.chat(value)",
    ):
        assert preserved in workspace

    user_bubble_background = "#553D1F"
    assert "rgb(138 102 53 / 0.42)" in css
    assert contrast_ratio("#E7E1DA", user_bubble_background) >= 4.5
~~~

- [ ] **Step 2: Run the focused test and verify red**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_workspace_has_archive_panels_tabs_sources_notes_and_chat -v
~~~

Expected: FAIL because the workspace still uses only generic Bootstrap classes.

- [ ] **Step 3: Add the workspace shell and panel/control hooks**


Replace the opening and closing shell lines exactly:

~~~diff
-<div class="container-fluid py-4">
+<div class="container-fluid py-4 archive-page archive-page-workspace">
+    <span class="archive-illustration illustration-books" aria-hidden="true"></span>
+    <span class="archive-illustration illustration-flourish" aria-hidden="true"></span>
+    <div class="archive-content">
~~~

~~~diff
-    <div id="noteEditorModal"></div>
-</div>
+        <div id="noteEditorModal"></div>
+    </div>
+</div>
~~~

Apply these exact class substitutions inside that template:

~~~diff
-<h3 class="mb-1">${escapeHtml(workspaceName)}</h3>
+<h3 class="archive-page-title mb-1">${escapeHtml(workspaceName)}</h3>
~~~

~~~diff
-<button class="btn btn-outline-secondary btn-sm" id="renameWorkspaceBtn">Rename</button>
-<button class="btn btn-primary btn-sm" id="refreshWorkspaceBtn">Refresh</button>
+<button class="btn btn-secondary-wood btn-sm" id="renameWorkspaceBtn">Rename</button>
+<button class="btn btn-secondary-wood btn-sm" id="refreshWorkspaceBtn">Refresh</button>
~~~

~~~diff
-<div class="card h-100 workspace-main-panel">
+<div class="card h-100 surface-leather workspace-main-panel">
~~~

~~~diff
-<button class="btn btn-sm btn-outline-primary" id="saveQuickNoteBtn">Save quick note</button>
+<button class="btn btn-sm btn-secondary-wood" id="saveQuickNoteBtn">Save quick note</button>
~~~

~~~diff
-<textarea id="quickNoteInput" class="form-control h-100" rows="10" placeholder="Write your thoughts, outline key ideas, or summarise the selected source..."></textarea>
+<textarea id="quickNoteInput" class="form-control quick-note-input h-100" rows="10" placeholder="Write your thoughts, outline key ideas, or summarise the selected source..."></textarea>
~~~

~~~diff
-<span id="sourceBadge" class="badge bg-secondary">${currentWorkspaceItems.length} sources</span>
+<span id="sourceBadge" class="badge archive-count-badge">${currentWorkspaceItems.length} sources</span>
~~~

~~~diff
-<div id="selectedSourceViewer" class="border rounded p-2 bg-body-secondary" style="min-height: 320px;"></div>
+<div id="selectedSourceViewer" class="border rounded p-2 source-preview-shell" style="min-height: 320px;"></div>
~~~

~~~diff
-<div class="card h-100 workspace-right-panel resizable-panel">
+<div class="card h-100 surface-leather workspace-right-panel resizable-panel">
~~~

~~~diff
-<button class="btn btn-sm btn-outline-primary" id="createNoteBtn">Add note</button>
+<button class="btn btn-sm btn-secondary-wood" id="createNoteBtn">Add note</button>
~~~

~~~diff
-<div id="alexanderChatMessages" class="border rounded p-3 mb-3 overflow-auto" style="min-height: 220px;"></div>
+<div id="alexanderChatMessages" class="border rounded p-3 mb-3 overflow-auto chat-messages" style="min-height: 220px;"></div>
~~~

~~~diff
-<input id="alexanderChatInput" type="text" class="form-control" placeholder="Ask Alexander a question...">
-<button class="btn btn-primary" id="alexanderSendBtn" type="button">Send</button>
+<input id="alexanderChatInput" type="text" class="form-control chat-input" placeholder="Ask Alexander a question...">
+<button class="btn btn-brass" id="alexanderSendBtn" type="button">Send</button>
~~~

Keep every existing ID, `data-bs-toggle`, `data-bs-target`, `role`, API call, and listener unchanged.


- [ ] **Step 4: Add source, note, preview, and chat hooks**

Change source buttons and source labels exactly:

~~~javascript
itemButton.className = `list-group-item list-group-item-action workspace-source-item text-start ${item.id === selectedWorkspaceItemId ? 'active' : ''}`;
~~~

~~~diff
-<small class="text-muted align-self-start">${escapeHtml(item.source_name)}</small>
+<small class="workspace-source-name align-self-start">${escapeHtml(item.source_name)}</small>
~~~

Change the selected source Open link and preview root:

~~~diff
-${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-secondary btn-sm">Open</a>` : ''}
+${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary-wood btn-sm">Open</a>` : ''}
~~~

~~~diff
-<div id="selectedSourcePreview" class="rounded overflow-hidden border bg-white" style="min-height: 320px;"></div>
+<div id="selectedSourcePreview" class="rounded overflow-hidden border source-preview-content" style="min-height: 320px;"></div>
~~~

Change note creation to:

~~~javascript
noteBtn.className = 'btn btn-secondary-wood note-item w-100 text-start mb-2 text-truncate';
noteBtn.dataset.id = note.id;
noteBtn.title = note.title;
noteBtn.innerHTML = '<i class="bi bi-file-earmark-text me-2" aria-hidden="true"></i>' + escapeHtml(note.title);
~~~

Replace the body of the `alexanderMessages.forEach` callback in `renderAlexanderMessages()`:

~~~javascript
const messageEl = document.createElement('div');
const isAgent = message.role === 'agent';
messageEl.className = `chat-row ${isAgent ? 'chat-row-agent' : 'chat-row-user'}`;
messageEl.innerHTML = `
    ${isAgent ? '<div class="chat-avatar" aria-hidden="true"><i class="bi bi-gear"></i></div>' : ''}
    <div class="chat-message ${isAgent ? 'chat-message-agent' : 'chat-message-user'}">
        <strong>${isAgent ? 'Alexander' : 'You'}</strong>
        <div class="mt-1">${escapeHtml(message.text)}</div>
    </div>
`;
container.appendChild(messageEl);
~~~

- [ ] **Step 5: Add the workspace studio and parchment-chat styling**

Append:

~~~css
[data-bs-theme="dark"] .archive-page-workspace .workspace-main-panel,
[data-bs-theme="dark"] .archive-page-workspace .workspace-right-panel {
    min-height: 680px;
}

[data-bs-theme="dark"] .workspace-main-panel .card-header,
[data-bs-theme="dark"] .workspace-right-panel .card-header {
    background: transparent;
    border-color: hsl(35 40% 45% / 0.14);
}

[data-bs-theme="dark"] .quick-note-input {
    background: transparent;
    border-color: transparent;
    color: var(--text-primary);
    resize: vertical;
}

[data-bs-theme="dark"] .quick-note-input:focus {
    background: transparent;
    border-color: var(--gold-500);
    box-shadow: var(--shadow-warm-glow);
}

[data-bs-theme="dark"] .source-preview-shell {
    background: hsl(28 50% 5% / 0.35) !important;
    border-color: hsl(35 40% 45% / 0.18) !important;
}

[data-bs-theme="dark"] .source-preview-content {
    background: var(--surface-700);
    border-color: hsl(35 40% 45% / 0.18) !important;
}

[data-bs-theme="dark"] .workspace-tabs .nav-link {
    background: transparent;
    color: hsl(35 40% 76% / 0.7);
    transition: background 150ms ease, color 150ms ease;
}

[data-bs-theme="dark"] .workspace-tabs .nav-link.active {
    background: hsl(35 70% 55% / 0.14);
    color: var(--gold-100);
}

[data-bs-theme="dark"] .workspace-source-item {
    background: transparent;
    border-color: hsl(35 40% 45% / 0.12);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .workspace-source-item:hover {
    background: var(--surface-700);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .workspace-source-item.active {
    background: hsl(35 70% 55% / 0.1);
    border-left: 3px solid var(--gold-300);
    box-shadow: var(--shadow-warm-glow);
    color: var(--text-primary);
}

[data-bs-theme="dark"] .workspace-source-name {
    color: var(--gold-700);
    font-size: var(--text-caption);
}

[data-bs-theme="dark"] .note-item {
    background-color: var(--surface-700);
    background-image: none;
    color: var(--text-primary);
}

[data-bs-theme="dark"] .note-item i {
    color: var(--gold-300);
}

[data-bs-theme="dark"] .chat-messages {
    background: hsl(28 50% 5% / 0.28);
    border-color: hsl(35 40% 45% / 0.18) !important;
}

[data-bs-theme="dark"] .chat-row {
    align-items: flex-end;
    display: flex;
    gap: 0.65rem;
    margin-bottom: 1rem;
}

[data-bs-theme="dark"] .chat-row-user {
    justify-content: flex-end;
}

[data-bs-theme="dark"] .chat-avatar {
    align-items: center;
    background: var(--surface-700);
    border: 1px solid var(--gold-500);
    border-radius: 50%;
    color: var(--gold-300);
    display: flex;
    flex: 0 0 2.25rem;
    height: 2.25rem;
    justify-content: center;
    width: 2.25rem;
}

[data-bs-theme="dark"] .chat-message {
    color: var(--text-primary);
    max-width: min(82%, 34rem);
    padding: 0.8rem 1rem;
    position: relative;
}

[data-bs-theme="dark"] .chat-message-agent {
    background: var(--surface-600);
    border-radius: 18px 22px 16px 6px;
}

[data-bs-theme="dark"] .chat-message-user {
    background: linear-gradient(rgb(138 102 53 / 0.42), rgb(138 102 53 / 0.42)), var(--surface-700);
    border-radius: 22px 18px 6px 16px;
    color: var(--text-primary);
}

[data-bs-theme="dark"] .chat-message-agent::before,
[data-bs-theme="dark"] .chat-message-user::after {
    border-style: solid;
    bottom: 0.3rem;
    content: "";
    position: absolute;
}

[data-bs-theme="dark"] .chat-message-agent::before {
    border-color: transparent var(--surface-600) transparent transparent;
    border-width: 0.45rem 0.55rem 0.45rem 0;
    left: -0.5rem;
}

[data-bs-theme="dark"] .chat-message-user::after {
    border-color: transparent transparent transparent var(--surface-700);
    border-width: 0.45rem 0 0.45rem 0.55rem;
    right: -0.5rem;
}

[data-bs-theme="dark"] .archive-page-workspace .illustration-books {
    bottom: 0;
    height: 160px;
    left: 0;
    width: 240px;
}

[data-bs-theme="dark"] .archive-page-workspace .illustration-flourish {
    bottom: 0;
    height: 180px;
    right: 0;
    transform: scaleX(-1);
    width: 180px;
}

@media (max-width: 991.98px) {
    [data-bs-theme="dark"] .archive-page-workspace .workspace-main-panel,
    [data-bs-theme="dark"] .archive-page-workspace .workspace-right-panel {
        min-height: auto;
    }

    [data-bs-theme="dark"] .archive-page-workspace .resizable-panel {
        max-width: none;
        min-width: 0;
        resize: none;
        width: 100%;
    }
}

@media (max-width: 575.98px) {
    [data-bs-theme="dark"] .chat-message {
        max-width: 88%;
    }
}
~~~

- [ ] **Step 6: Run focused and integration tests, then commit**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py::test_workspace_has_archive_panels_tabs_sources_notes_and_chat tests/test_integration.py -v
git diff --check
git add static/js/pages/workspace.js static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: style Candlelit Archive workspace"
~~~

Expected: existing workspace, note, preview, and chat data flow passes unchanged, while every required component has a dark-only visual hook.

---

### Task 9: Add the Candle Cursor Last, Then Run Full Functional and Visual QA

**Files:**
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `templates/layout.html:14-15`
- Modify: `static/js/theme.js:1-33`
- Modify: `static/css/custom.css`
- Verify: every file listed in this plan

**Interfaces:**
- One `.candle-glow` layer exists globally and is always decorative.
- Tracking runs only when the resolved theme is dark and `matchMedia("(hover: hover) and (pointer: fine)")` matches.
- `startCandle()` and `stopCandle()` are idempotent; toggling themes never accumulates listeners or animation frames.
- Reduced motion removes flicker only; touch or coarse pointer removes the entire glow.
- This task does not close until dark mode, the required shared navigation change, and otherwise unchanged light-mode styling are verified in a real browser.

- [ ] **Step 1: Add failing candle, scoping, and light-rule preservation contracts**

Append:

~~~python
def test_candle_layer_and_controller_have_all_runtime_guards():
    layout = read_text("templates/layout.html")
    theme = read_text("static/js/theme.js")
    css = read_text("static/css/custom.css")

    assert layout.count('<div class="candle-glow" aria-hidden="true"></div>') == 1
    for marker in (
        'matchMedia("(hover: hover) and (pointer: fine)")',
        'addEventListener("pointermove", trackPointer',
        'removeEventListener("pointermove", trackPointer)',
        "requestAnimationFrame(animateCandle)",
        "cancelAnimationFrame(animationFrame)",
        "currentX += (targetX - currentX) * 0.15",
        "function startCandle()",
        "function stopCandle()",
        "function syncCandle()",
    ):
        assert marker in theme

    for marker in (
        '[data-bs-theme="dark"] .candle-glow',
        "mix-blend-mode: soft-light",
        "animation: candle-flicker 4.2s ease-in-out infinite",
        "@keyframes candle-flicker",
        "@media (prefers-reduced-motion: reduce)",
        "@media (hover: none), (pointer: coarse)",
    ):
        assert marker in css


def test_new_visual_hooks_are_dark_scoped_and_light_sentinels_remain():
    css = read_text("static/css/custom.css")

    light_sentinels = (
        ".upload-zone {\n    border: 2px dashed var(--bs-border-color);",
        ".workspace-card-add {\n    border: 1px dashed rgba(13, 110, 253, 0.5);",
        ".workspace-tabs .nav-link {\n    border-radius: 999rem;",
        ".nav-sidebar-overlay {\n    position: fixed;",
    )
    for sentinel in light_sentinels:
        assert sentinel in css

    dark_only_hooks = (
        ".surface-leather",
        ".btn-secondary-wood",
        ".btn-brass",
        ".btn-ghost",
        ".icon-button",
        ".archive-",
        ".result-source",
        ".file-icon",
        ".quick-note-input",
        ".source-preview",
        ".workspace-source",
        ".note-item",
        ".chat-",
        ".candle-glow",
    )
    for line_number, line in enumerate(css.splitlines(), start=1):
        stripped = line.strip()
        is_selector_line = stripped.endswith("{") or stripped.endswith(",")
        if is_selector_line and any(hook in stripped for hook in dark_only_hooks):
            assert stripped.startswith('[data-bs-theme="dark"]'), (
                f"dark-only selector is unscoped on line {line_number}: {stripped}"
            )
~~~

- [ ] **Step 2: Run the focused tests and verify red**

~~~powershell
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py -k "candle or visual_hooks" -v
~~~

Expected: the candle test FAILS because the layer/controller are absent; the light sentinel test may already pass.

- [ ] **Step 3: Mount exactly one inert candle layer**

Immediately after `<body>` in `templates/layout.html`, add:

~~~html
<div class="candle-glow" aria-hidden="true"></div>
~~~

Do not put page content inside this element.

- [ ] **Step 4: Replace the theme script with toggle plus idempotent candle tracking**

Keep the current early theme resolution at the top of the IIFE, then use this controller inside the same IIFE:

~~~javascript
(function () {
    const root = document.documentElement;
    const saved = localStorage.getItem("theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    root.setAttribute("data-bs-theme", saved || preferred);

    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    let candleLayer = null;
    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight * 0.3;
    let currentX = targetX;
    let currentY = targetY;
    let animationFrame = null;
    let isTracking = false;

    function animateCandle() {
        currentX += (targetX - currentX) * 0.15;
        currentY += (targetY - currentY) * 0.15;
        candleLayer.style.setProperty("--candle-x", `${currentX}px`);
        candleLayer.style.setProperty("--candle-y", `${currentY}px`);

        const isMoving = Math.abs(targetX - currentX) > 0.5 || Math.abs(targetY - currentY) > 0.5;
        animationFrame = isMoving ? requestAnimationFrame(animateCandle) : null;
    }

    function trackPointer(event) {
        targetX = event.clientX;
        targetY = event.clientY;
        if (animationFrame === null) {
            animationFrame = requestAnimationFrame(animateCandle);
        }
    }

    function startCandle() {
        if (!candleLayer || isTracking || !finePointer.matches) return;
        isTracking = true;
        window.addEventListener("pointermove", trackPointer, { passive: true });
    }

    function stopCandle() {
        if (!isTracking) return;
        window.removeEventListener("pointermove", trackPointer);
        if (animationFrame !== null) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
        isTracking = false;
    }

    function syncCandle() {
        const shouldTrack = root.getAttribute("data-bs-theme") === "dark" && finePointer.matches;
        if (shouldTrack) startCandle();
        else stopCandle();
    }

    function updateThemeButton() {
        const themeBtn = document.getElementById("themeToggle");
        if (!themeBtn) return;

        const isDark = root.getAttribute("data-bs-theme") === "dark";
        themeBtn.innerHTML = isDark
            ? '<i class="bi bi-sun" aria-hidden="true"></i>'
            : '<i class="bi bi-moon-stars" aria-hidden="true"></i>';
        themeBtn.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    }

    function toggleTheme() {
        const nextTheme = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-bs-theme", nextTheme);
        localStorage.setItem("theme", nextTheme);
        updateThemeButton();
        syncCandle();
    }

    document.addEventListener("DOMContentLoaded", () => {
        candleLayer = document.querySelector(".candle-glow");
        const themeBtn = document.getElementById("themeToggle");
        themeBtn?.addEventListener("click", toggleTheme);
        finePointer.addEventListener("change", syncCandle);
        updateThemeButton();
        syncCandle();
    });
})();
~~~

- [ ] **Step 5: Add the candle rendering and both correctness guards**

Append:

~~~css
[data-bs-theme="dark"] {
    --candle-x: 50%;
    --candle-y: 30%;
    --candle-radius: 380px;
}

[data-bs-theme="dark"] .candle-glow {
    animation: candle-flicker 4.2s ease-in-out infinite;
    background: radial-gradient(
        circle var(--candle-radius) at var(--candle-x) var(--candle-y),
        hsl(35 80% 68% / 0.16),
        hsl(35 80% 68% / 0.05) 45%,
        transparent 75%
    );
    inset: 0;
    mix-blend-mode: soft-light;
    pointer-events: none;
    position: fixed;
    z-index: var(--z-candle-glow);
}

@keyframes candle-flicker {
    0%, 100% { opacity: 1; }
    8% { opacity: 0.94; }
    17% { opacity: 1; }
    26% { opacity: 0.9; }
    35% { opacity: 0.98; }
    50% { opacity: 0.93; }
    68% { opacity: 1; }
    82% { opacity: 0.95; }
}

@media (prefers-reduced-motion: reduce) {
    [data-bs-theme="dark"] .candle-glow {
        animation: none;
    }
}

@media (hover: none), (pointer: coarse) {
    [data-bs-theme="dark"] .candle-glow {
        display: none;
    }
}
~~~

- [ ] **Step 6: Run syntax checks, the complete contract, and the complete Python suite**

~~~powershell
node --check static/js/main.js
node --check static/js/theme.js
node --check static/js/auth.js
node --check static/js/toast.js
node --check static/js/card.js
node --check static/js/pages/home.js
node --check static/js/pages/browse.js
node --check static/js/pages/upload.js
node --check static/js/pages/workspace.js
.\.venv\Scripts\python -m pytest tests/test_dark_theme_contract.py -v
.\.venv\Scripts\python -m pytest -v
git diff --check
~~~

Expected: every command exits 0. Stop and repair any regression before visual QA.

- [ ] **Step 7: Start the app and prepare one authenticated browser session**

Run the server in a dedicated terminal:

~~~powershell
.\.venv\Scripts\python app.py
~~~

In a second terminal:

~~~powershell
$env:AGENT_BROWSER_SESSION = 'studylib-candle'
$visual = Join-Path $env:TEMP 'studylib-ui-final'
New-Item -ItemType Directory -Force -Path $visual | Out-Null
agent-browser open http://127.0.0.1:8010/login
agent-browser find label "Username" fill "candle_qa"
agent-browser find label "Password" fill "CandleQA!2026"
agent-browser find role button click --name "Login"
agent-browser wait --url "http://127.0.0.1:8010/"
agent-browser eval "localStorage.setItem('theme','dark'); location.reload()"
agent-browser wait --load networkidle
agent-browser open http://127.0.0.1:8010/
agent-browser find text "Candlelit QA" click
agent-browser wait --url "http://127.0.0.1:8010/workspace/*"
$workspaceUrl = (agent-browser get url).Trim()
~~~

Expected: `$workspaceUrl` contains the seeded workspace route and the page is visibly dark.

- [ ] **Step 8: Capture all four pages at desktop, tablet, and mobile widths**

~~~powershell
$pages = [ordered]@{
    home = 'http://127.0.0.1:8010/'
    browse = 'http://127.0.0.1:8010/browse'
    upload = 'http://127.0.0.1:8010/upload'
    workspace = $workspaceUrl
}
$viewports = @(
    @{ Width = 1440; Height = 1000 },
    @{ Width = 1024; Height = 900 },
    @{ Width = 390; Height = 844 }
)

foreach ($viewport in $viewports) {
    agent-browser set viewport $viewport.Width $viewport.Height
    foreach ($page in $pages.GetEnumerator()) {
        agent-browser open $page.Value
        agent-browser wait --load networkidle
        agent-browser screenshot "$visual\dark-$($page.Key)-$($viewport.Width).png" --full
    }
}
~~~

Inspect all 12 images with the local image viewer. Confirm:

- textures tile naturally with no stretched grain or obvious seams;
- illustrations stay below 0.1 opacity, out of text, and do not resemble the rejected sparkle artifact;
- page headings, cream text, gold icons, brass/wood hierarchy, dropdowns, badges, and scrollbars match the source specification;
- no horizontal overflow occurs at 390 px;
- the workspace resize affordance remains desktop-only;
- photographic result images remain untinted.

- [ ] **Step 9: Verify navigation, focus, candle lag, reduced motion, touch suppression, and console health**

~~~powershell
agent-browser set viewport 1440 1000
agent-browser open http://127.0.0.1:8010/
agent-browser snapshot -i
agent-browser find role button click --name "Open navigation menu"
agent-browser get attr aria-expanded "#brandMenuButton"
agent-browser get attr aria-hidden "#navSidebarOverlay"
agent-browser press Escape
agent-browser get attr aria-expanded "#brandMenuButton"
agent-browser eval "document.activeElement === document.querySelector('#brandMenuButton')"
agent-browser mouse move 900 500
agent-browser wait 350
agent-browser eval "document.querySelector('.candle-glow').getAttribute('style')"
agent-browser set media dark reduced-motion
agent-browser eval "getComputedStyle(document.querySelector('.candle-glow')).animationName"
agent-browser set device "iPhone 12"
agent-browser eval "getComputedStyle(document.querySelector('.candle-glow')).display"
agent-browser console
agent-browser errors
~~~

Expected:

- open state is `aria-expanded="true"` and `aria-hidden="false"`;
- Escape restores `false` and `true`, then returns focus;
- the candle style contains changing `--candle-x` and `--candle-y` pixel values;
- reduced-motion animation name is `none`;
- the touch-device display value is `none`;
- console and page-error output contain no application errors.

Also keyboard through Home, Browse, Upload, theme, sidebar close, search, upload, and workspace controls with `agent-browser press Tab`; every focused control must show a visible gold focus ring and follow the existing DOM order.

- [ ] **Step 10: Restore light mode and compare against the saved baseline**

Start a fresh desktop session after device emulation:

~~~powershell
agent-browser close
$env:AGENT_BROWSER_SESSION = 'studylib-candle-light-check'
agent-browser open http://127.0.0.1:8010/login
agent-browser find label "Username" fill "candle_qa"
agent-browser find label "Password" fill "CandleQA!2026"
agent-browser find role button click --name "Login"
agent-browser wait --url "http://127.0.0.1:8010/"
agent-browser eval "localStorage.setItem('theme','light'); location.reload()"
agent-browser wait --load networkidle
agent-browser set viewport 1440 1000
$baseline = Join-Path $env:TEMP 'studylib-ui-baseline'
agent-browser open http://127.0.0.1:8010/
agent-browser diff screenshot --baseline "$baseline\light-home-1440.png"
agent-browser open http://127.0.0.1:8010/browse
agent-browser diff screenshot --baseline "$baseline\light-browse-1440.png"
agent-browser open http://127.0.0.1:8010/upload
agent-browser diff screenshot --baseline "$baseline\light-upload-1440.png"
agent-browser open http://127.0.0.1:8010/
agent-browser find text "Candlelit QA" click
agent-browser wait --url "http://127.0.0.1:8010/workspace/*"
agent-browser diff screenshot --baseline "$baseline\light-workspace-1440.png"
~~~

Expected: page content and component styling are unchanged in light mode. The only accepted visual delta is the source-required shared navigation change: the separate hamburger is gone and the wordmark is now the menu trigger. Investigate any other pixel difference.

- [ ] **Step 11: Commit any verification-driven correction, or leave history unchanged if no correction was needed**

If QA required code or test changes:

~~~powershell
.\.venv\Scripts\python -m pytest -v
git diff --check
git add tests/test_dark_theme_contract.py templates/layout.html templates/macros.html static/css/custom.css static/js/main.js static/js/theme.js static/js/auth.js static/js/toast.js static/js/card.js static/js/pages/home.js static/js/pages/browse.js static/js/pages/upload.js static/js/pages/workspace.js
git commit -m "test: verify Candlelit Archive theme"
~~~

Do not create an empty commit when QA needed no correction.

- [ ] **Step 12: Confirm the branch is ready for review**

~~~powershell
git status --short
git log --oneline --decorate -10
~~~

Expected: the worktree is clean; commits are small and ordered from assets/foundation through components and candle QA. Do not push or open a pull request until the user explicitly chooses that next step.

---

## Specification Coverage Review

| Source requirement | Plan coverage | Verification |
|---|---|---|
| §0–1 source-of-truth and dark-only scope | Global Constraints; Tasks 1 and 9 | Instruction contract, selector audit, light screenshot diff |
| §2–3 concept and reconciled mockup inconsistencies | Tasks 2–8 | Exact palette and material roles; gold tabs; no sparkle; correct `WORKSPACE` |
| §4 tokens, typography, Bootstrap mapping, contrast | Task 2 | Exact-token and font tests plus calculated WCAG ratios |
| §5 textures and vignette | Tasks 1–3 | PNG signatures, exact asset URLs, blend and tile assertions, browser seam inspection |
| §6 all five decorative SVGs | Tasks 1, 3, 5–8 | SVG safety contract, CSS references, page placement screenshots |
| §7 candle cursor | Task 9, deliberately last | Runtime contract, mouse movement, reduced-motion and touch checks |
| §8.1–8.2 global shell and nav | Tasks 2 and 4 | Contract plus click, Escape, focus, and Home browser checks |
| §8.3–8.5 browse, overview, result cards | Task 6 | Dual-renderer contract, search tests, responsive screenshots |
| §8.6–8.7 upload and file list | Task 7 | Upload tests, empty state, file colors, responsive screenshots |
| §8.8–8.13 workspace, notes, source studio, chat | Task 8 | Integration tests, preserved IDs and data flow, workspace screenshots |
| §8.14–8.18 controls, dropdowns, badges, scrollbar, dashboard | Tasks 3 and 5–8 | Shared selector contract and per-page browser inspection |
| §9 line iconography | Tasks 3–8 | Theme fill-icon contract and visual inspection |
| §10–11 motion and accessibility | Tasks 3, 4, and 9 | Reduced-motion, touch, contrast, keyboard, focus, and ARIA checks |
| §12–15 do and do-not rules, manifest, checklist | Global Constraints; Tasks 1–9 | Full contract, test suite, syntax, diff, and screenshot gates |
| §17 resolved assumptions | Approved design record; Tasks 4, 7, and 8 | Home sidebar entry, `--info-slate`, user bubble contrast |

## Plan Self-Review

- Every source-spec section that changes code maps to a task and an executable verification step.
- Every created or modified file is named before its steps; no backend or API file is changed.
- Every component task follows red → green → focused regression tests → commit.
- All visual CSS examples are dark-scoped; the final selector test catches accidental bare hooks.
- The only shared light-mode change is the explicitly required hamburger-to-wordmark navigation behavior.
- Asset filenames, token names, selectors, element IDs, route paths, and JavaScript function names are consistent across tasks.
- No implementation placeholder remains: the supplied assets have final destinations, all four pages have concrete hooks, and all three responsive widths have explicit QA.
