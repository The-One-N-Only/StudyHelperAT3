# StudyLib — "Candlelit Archive" Dark Theme Specification

**Audience:** GitHub Copilot (Chat, Agent Mode, Code Review) and any human engineer implementing alongside it.
**Scope:** Dark theme only. Light theme is explicitly out of scope — see §1.
**Source material:** 6 reference mockups (search, upload, workspace × 3 tabs, dashboard) + 2 texture swatches, supplied alongside this file. Palette values below were sampled programmatically from those mockups, not eyeballed, so treat the hex values as ground truth over any conflicting assumption.

---

## 0. How to use this document

This file is written to be handed to an AI coding assistant, not just read by a human. Two ways to wire it in:

1. **Repo-wide, always-on:** Keep this file at `docs/design/dark-mode-ui-spec.md` (a design reference doc doesn't belong inside `.github/copilot-instructions.md` itself — that file should stay short, since it's injected into every single Copilot request). In `.github/copilot-instructions.md`, add one line pointing to it:
   ```markdown
   When editing dark-theme styles, treat docs/design/dark-mode-ui-spec.md as the source of truth. Do not touch light-mode styles. Confirm scope before editing (see its §1).
   ```
2. **Path-scoped (recommended if your theme files are separated):** Create `.github/instructions/dark-theme.instructions.md` with frontmatter so it only auto-applies to relevant files:
   ```markdown
   ---
   applyTo: "**/*.css,**/*.scss,**/theme/**,**/styles/**"
   ---
   Full instructions inherited from docs/design/dark-mode-ui-spec.md — read that file before editing anything matched by this glob.
   ```
3. **Ad hoc in Copilot Chat:** Attach this file plus the SVGs/textures to a chat message and open with the kickoff prompt in §16.

Adjust the `applyTo` glob to your actual folder structure once you know it.

---

## 1. Non-negotiable scope constraint

**You are editing dark mode only.** Before touching any file:

- The theming mechanism is already confirmed: `templates/layout.html` sets `data-bs-theme="light"` on `<html>`, and `static/js/theme.js` flips it to `data-bs-theme="dark"` (persisted in `localStorage`) via the `#themeToggle` button. This is Bootstrap 5's own theming attribute, not a custom one — every selector below must be scoped under `[data-bs-theme="dark"]`. Do not introduce a second, competing theming mechanism (no new `.dark` class, no `prefers-color-scheme` media query).
- Every new selector, token, or override you add must be scoped under that dark-mode selector. If a value currently lives in a selector shared by both themes (e.g. a bare `.card` rule with no theme scoping), split it rather than overwriting it — the light-mode value must render identically after your change.
- Do not delete, rename, or restructure any light-mode token, class, or component prop as part of this pass. If a shared component needs a new prop to support a dark-only visual (e.g. a texture layer), default that prop to a no-op in light mode.
- This is a **visual/styling pass**, not a refactor. Don't change component logic, data flow, or markup structure beyond what's strictly required to add the illustration layer and the cursor-glow overlay (both described below, both additive).
- Work component by component (see §8) and get each one rendering correctly before moving to the next, rather than one sweeping rewrite across the whole codebase.

---

## 2. Theme concept

**Candlelit Archive**: a 19th-century naturalist's study crossed with a ship's chart room after dark — leather-bound source material, brass and gold fittings, carved wood furniture, faint nautical instruments on the walls, and a single warm light source that seems to move with the reader. The interface should feel like it's lit from one lamp, not evenly floodlit: contrast and warmth concentrate near where attention is, and recede at the edges.

The signature element (see §7) is the cursor behaving like a carried candle — it doesn't just move a spotlight, it warms the surface it passes over, with the same soft irregularity a real flame has.

---

## 3. Reconciling reference inconsistencies

The six reference mockups appear to be independently generated concept renders rather than screenshots of one running app, so they don't agree with each other on every detail. This spec resolves those disagreements as follows — don't replicate the inconsistencies:

- **Top nav / hamburger icon — removed by design decision, not left inconsistent.** The current markup (`templates/layout.html`) has a separate `<button id="navMenuButton">` (hamburger icon) sitting next to the `.navbar-brand` logo link. **That separate hamburger button is being removed.** The logo itself becomes the sidebar trigger — see §8.2 for the exact change.
- **Dashboard card badge** reads "WORRSPACE" in one mockup. That's a typo in the reference — implement "WORKSPACE".
- **Bottom-right sparkle/diamond accent** from the reference mockups is an artifact of the Gemini image generation, not an intended UI element. **Do not implement it, decoratively or functionally.** It's omitted entirely from this spec — nothing in §6, §7, or §8 should produce anything resembling it.
- **File-type icon colors:** a rust/red PDF icon was sampled directly from the reference (§4.1). No clean blue sample was recoverable for the `.docx` icon (likely too small/anti-aliased in the source render) — the blue token below is a conventional choice, not an extracted one. Flagged in §17.
- **Framework — confirmed from the codebase, not assumed.** This is a Flask + Jinja2 app using Bootstrap 5.3.3 (CDN) and vanilla JS ES modules (`static/js/*.js`, loaded via `page-loader.js`) — there is no React/Tailwind anywhere in it. Everything below is written as plain CSS custom properties + vanilla JS, which is what this stack needs directly (no framework mapping note required). See the new §4.4 for how these tokens plug into Bootstrap 5's own CSS variables.
- **The "blue" active tab you flagged is a real, explainable bug, not a rendering artifact.** `static/js/pages/workspace.js` builds the Sources/Notes/Alexander switcher with Bootstrap's `nav nav-pills` component (`<button class="nav-link active" ...>`), and `static/css/custom.css` only adds `border-radius: 999rem` to `.workspace-tabs .nav-link` — it never overrides the color. Bootstrap 5's default `.nav-pills .nav-link.active` background is `var(--bs-primary)`, which is Bootstrap's stock blue. That's why it renders blue: nothing in the codebase has told it to be gold yet. Fixed in §4.4 and §8.11.

---

## 4. Design tokens

### 4.1 Color tokens

All hex values are sampled means from the reference mockups (background/surface/gold/text) or from the two provided texture swatches, then rounded into a clean scale. Do not substitute your own guesses for these — implement exactly.

**Base / Surface (warm brown-black — the "room")**

| Token | Hex | Sampled from | Usage |
|---|---|---|---|
| `--bg-950` | `#0A0A0A` | Largest single cluster across all 6 mockups | `<body>` base fill, outside any panel |
| `--bg-900` | `#14100B` | Interpolated step | Base with the faintest warmth; used under the static vignette (§5.3) |
| `--surface-800` | `#22170B` | Card/panel cluster (search cards, upload panel) | Resting state of cards, panels, list rows |
| `--surface-700` | `#2E1F0F` | Card/panel cluster (notes card, workspace panel) | Hover state of cards/rows; secondary-elevation panels |
| `--surface-600` | `#3D2914` | Highest-luminance panel cluster observed | Active/selected row wash base, popovers, tooltips |
| `--surface-500` | `#4D3319` | Extrapolated top step | Reserved for modal/dialog surfaces (highest elevation) |

**Accent gold/brass**

| Token | Hex | Sampled from | Usage |
|---|---|---|---|
| `--gold-100` | `#EDD9B5` | Bright-gold pixel cluster (logo, active text) | Hover/active text and icon state, brightest highlight edge on "brass" buttons |
| `--gold-300` | `#C9A876` | Aggregate mean of all gold-hued pixels across mockups | **Primary accent** — default link/icon/button-text color, focus rings |
| `--gold-500` | `#A9824F` | Interpolated | Secondary accent — default border strength on inputs/dropdowns |
| `--gold-700` | `#8A6635` | Muted-gold pixel cluster | Low-emphasis dividers, decorative illustration stroke color (used at low opacity, see §6) |
| `--gold-900` | `#5C4423` | Interpolated (shadow step) | Pressed/active button shading, deep inset borders |

**Text**

| Token | Hex | Sampled from | Usage |
|---|---|---|---|
| `--text-primary` | `#E7E1DA` | Cream/off-white pixel cluster across all mockups | Titles, primary body copy, primary button labels on dark surfaces |
| `--text-secondary` | `#A69A8C` | Interpolated between `--text-primary` and `--surface-700` | Descriptions, metadata, timestamps, placeholder text |
| `--text-disabled` | `#6E6459` | Interpolated | Disabled control labels |

**Semantic**

| Token | Hex | Sampled from | Usage |
|---|---|---|---|
| `--danger-rust` | `#9C6242` | PDF file-icon cluster, brightened ~15% for legibility | Destructive actions, PDF file-type icon, delete/trash icon on hover |
| `--info-slate` | `#6E87A6` | **Not sampled** — no clean sample recovered; conventional choice | `.docx`/Word file-type icon only |
| `--success-verdigris` | `#6E9B7C` | Not present in mockups; derived to sit in-family (aged copper/verdigris green, not a bright modern green) | Success toasts/confirmations, if needed |

### 4.2 Typography

The mockups render a real font, but a raster image cannot be reverse-engineered into an exact font file — recommend closest-matching, licensed web fonts rather than guessing a proprietary match:

| Role | Recommendation | Why |
|---|---|---|
| Display / headings / logo wordmark | **Cinzel** (Google Fonts) | High-contrast, classical capital-letter proportions — reads like an engraved brass plate or a ship's registry, matching the logo and page-title letterforms in every mockup |
| Body / UI text | **Crimson Pro** or **EB Garamond** (Google Fonts) | Warm, moderate-contrast old-style serif, comfortable at UI sizes (14–16px), avoids the coldness of a geometric sans against a warm palette |
| Numerals / dense data (file sizes, counts, timestamps) | Same body face, `font-variant-numeric: tabular-nums` | Keeps the aesthetic consistent while numbers still align in lists |

```css
[data-bs-theme="dark"] {
  --font-display: "Cinzel", "Times New Roman", serif;
  --font-body: "Crimson Pro", "EB Garamond", Georgia, serif;
}
```

Neither font is loaded anywhere currently — `templates/layout.html`'s `<head>` only pulls in Bootstrap, Bootstrap Icons, and Quill's stylesheet. Add the two Google Fonts `<link>` tags there (same pattern as the existing CDN links), and apply `--font-body` to `--bs-body-font-family` in the block above so Bootstrap's own typography inherits it too.

Type scale (unchanged between themes — this is a dark-mode color spec, not a resize):

| Token | Size | Weight | Used for |
|---|---|---|---|
| `--text-display-lg` | 32px | 600 | Page titles ("Recent Workspaces", workspace name) |
| `--text-display-sm` | 22px | 600 | Panel headers ("AI Overview", "Workspace Studio") |
| `--text-body-lg` | 16px | 400 | Card titles, chat message text |
| `--text-body` | 14px | 400 | Descriptions, list rows |
| `--text-caption` | 12px | 400 | Metadata, timestamps, source tags |

Letter-spacing: add `0.02em` on display text only (Cinzel reads better with a touch of tracking); leave body text at normal tracking for readability.

### 4.3 Spacing, radius, elevation, z-index

| Token | Value | Usage |
|---|---|---|
| `--radius-panel` | 12px | Cards, panels, dropzone |
| `--radius-button` | 8px | Buttons, dropdown controls |
| `--radius-pill` | 999px | Badges, tags, "55 sources" pill |
| `--radius-input` | 8px | Search bar, textareas |
| `--shadow-warm-raised` | `0 2px 10px 0 hsl(28 60% 4% / 0.55), 0 0 0 1px hsl(35 40% 40% / 0.06)` | Default card elevation — a near-black warm shadow, not a cool grey one |
| `--shadow-warm-glow` | `0 0 0 1px var(--gold-500), 0 0 18px 2px hsl(35 70% 55% / 0.25)` | Selected-row / focused-card glow |
| `--z-bg-base` | 0 | Body background + static vignette |
| `--z-bg-illustration` | 1 | Decorative SVGs (§6) |
| `--z-content` | 10 | Normal app content |
| `--z-candle-glow` | 40 | Cursor light overlay (§7) — above content, below overlays |
| `--z-overlay` | 50 | Modals, toasts, dropdown menus |

### 4.4 Bootstrap 5 variable mapping — do this before restyling individual components

This codebase leans on Bootstrap 5 utility classes almost everywhere (`btn btn-primary`, `btn-outline-secondary`, `nav-pills`, `card`, `badge`, `offcanvas`, `list-group`, `.text-muted`, `.bg-body-tertiary`...). Fighting that class-by-class is both more work and easy to miss instances. Override Bootstrap's own CSS custom properties once, scoped to `[data-bs-theme="dark"]`, and most of the app inherits the new palette for free — this is exactly what those variables are designed for in Bootstrap 5.3+.

```css
[data-bs-theme="dark"] {
  --bs-body-bg: var(--bg-950);
  --bs-body-color: var(--text-primary);
  --bs-secondary-color: var(--text-secondary);
  --bs-border-color: hsl(35 40% 45% / 0.18);
  --bs-tertiary-bg: var(--surface-800);      /* navbar background, .bg-body-tertiary */
  --bs-card-bg: var(--surface-800);          /* base .card fill, before .surface-leather is layered on */
  --bs-offcanvas-bg: var(--surface-700);     /* the source-viewer offcanvas */

  --bs-primary: var(--gold-300);
  --bs-primary-rgb: 201, 168, 118;           /* rgb of --gold-300 — Bootstrap needs this alongside --bs-primary for its rgba()-based hover/focus states */
  --bs-secondary: var(--surface-600);
  --bs-secondary-rgb: 61, 41, 20;
  --bs-danger: var(--danger-rust);

  --bs-link-color: var(--gold-300);
  --bs-link-hover-color: var(--gold-100);
}
```

**This is what fixes the blue Sources/Notes/Alexander tab** (§3): `.nav-pills .nav-link.active` reads `--bs-primary` for its background, so once this block is in place it inherits `--gold-300` automatically, no separate override needed. It also fixes every `btn-primary`/`btn-outline-primary`/`btn-outline-secondary` instance scattered across `static/js/pages/*.js` (search "Go", upload "Upload File", workspace "Refresh"/"Add note", etc.) in one pass — which is also *why* §8.14's button variants are described by visual role rather than by which Bootstrap class each button happens to use in the source: after this mapping, role and Bootstrap class mostly line up on their own. Any individual button that still doesn't match its intended weight after this (e.g. a `btn-outline-primary` that should read as secondary/wood) is a small follow-up swap of its class in the relevant file — not something to hunt down exhaustively in this pass.

---

## 5. Texture system

### 5.1 Provided assets

| File | Use for |
|---|---|
| `wood-texture.png` | Secondary ("carved wood") buttons only |
| `leather-texture.png` | Panels, cards, the upload dropzone |
| `compass-rose.svg`, `sextant.svg`, `stacked-books.svg`, `open-book.svg`, `scrollwork-flourish.svg` | Background decoration only (§6) |

Place the two textures at `static/img/textures/` and the five SVGs at `static/img/illustrations/`, matching the existing convention (`static/img/favicon.svg`, `static/img/placeholder.png` are already there). Reference them from CSS as `/static/img/textures/leather-texture.png` etc. (Flask serves the `static/` folder at `/static/`); from Jinja templates, use `{{ url_for('static', filename='img/textures/leather-texture.png') }}` instead of a hardcoded path.

Sampled tone reference (for the tint technique in §5.2):

| Swatch | Mean | Darkest ~12th pct | Lightest ~88th pct |
|---|---|---|---|
| Wood | `#1E1009` | `#0E0704` | `#321B10` |
| Leather | `#2C0F0E` | `#1C0201` | `#492C28` |

Both swatches are already close in darkness to the app's palette — they need tone-matching, not heavy darkening.

### 5.2 Application rule — never use either texture at raw opacity/saturation

Placing `background-image: url(...)` directly on an element will look too saturated/reddish compared to the reference UI, which reads the textures through the same dim, warm light as everything else. Always tint via a same-color layer blended with `background-blend-mode: multiply`, tiled at a natural (not stretched) scale:

```css
/* Leather — panels, cards, dropzone */
.surface-leather {
  background-color: var(--surface-800);
  background-image:
    linear-gradient(var(--surface-800), var(--surface-800)),
    url("/static/img/textures/leather-texture.png");
  background-blend-mode: multiply;
  background-size: auto, 420px;
  background-repeat: repeat, repeat;
  border: 1px solid hsl(35 40% 45% / 0.18);
  border-radius: var(--radius-panel);
  box-shadow: var(--shadow-warm-raised);
}

/* Wood — secondary buttons only */
.btn-secondary-wood {
  background-color: var(--surface-700);
  background-image:
    linear-gradient(var(--surface-700), var(--surface-700)),
    url("/static/img/textures/wood-texture.png");
  background-blend-mode: multiply;
  background-size: auto, 200px;
  background-repeat: repeat;
  color: var(--gold-300);
  border: 1px solid hsl(35 40% 45% / 0.22);
  border-radius: var(--radius-button);
}
```

**Do not** tile at less than ~150px (grain becomes muddy noise) or more than ~500px (grain becomes an obviously repeating tile — visible seams are the tell). Test at both mobile and desktop widths.

The upload dropzone already exists as `.upload-zone` in `static/css/custom.css`, with a dashed border and a `:hover`/`.dragover` state currently keyed to `--bs-primary`/`--bs-primary-bg-subtle` (Bootstrap defaults). Once §4.4's `--bs-primary` override is in place that hover state already goes gold automatically; you still need to add `.surface-leather`'s texture treatment to `.upload-zone` itself, and switch its border from `var(--bs-border-color)` to the explicit dashed-stitch treatment in §8.6.

### 5.3 Base background — neither texture, a static vignette instead

The page background itself is not wood or leather in the reference — it's a flat near-black with a soft warm glow concentrated toward the top of the viewport, like light falling from a room's single lamp, independent of the cursor:

```css
[data-bs-theme="dark"] body {
  background:
    radial-gradient(ellipse 60% 40% at 50% 0%, hsl(32 45% 18% / 0.5), transparent 60%),
    var(--bg-950);
  background-attachment: fixed;
}
```

This sits at `--z-bg-base` and is static — it does not track the cursor. §7 adds the moving light on top of this, not instead of it.

---

## 6. Decorative illustration layer

Five SVGs are provided, all pure line art (`stroke="currentColor"`, `fill="none"` except small accent dots), sized on their own viewBox, meant to be tinted via CSS `color` and used at very low opacity — **decoration, not content**. All must carry `aria-hidden="true"` (already set in the files) and `pointer-events: none`.

| File | Suggested placement | Suggested size | Opacity |
|---|---|---|---|
| `stacked-books.svg` | Bottom-left of search/results and dashboard pages | 240×160px | 0.05–0.07 |
| `open-book.svg` | Optional — an empty-state graphic (e.g. "no files uploaded yet"). **Not the nav logo**: that's your own existing logo asset, see §8.2 | 160×112px | 0.08 |
| `compass-rose.svg` | Top-left corner of upload/onboarding-style pages | 180×180px | 0.06 |
| `sextant.svg` | Right-hand margin of upload/onboarding-style pages | 200×200px | 0.05 |
| `scrollwork-flourish.svg` | Bottom-right corner, mirror with `transform: scaleX(-1)` for other corners as needed | 180×180px | 0.06 |

```css
.illustration {
  position: absolute;
  color: var(--gold-700);
  pointer-events: none;
  z-index: var(--z-bg-illustration);
}
```

**Treat these as starter placeholder line art**, not final illustration assets — they establish correct silhouette, weight, and placement conventions (thin single-color stroke, generous whitespace, low opacity, corner-anchored) so a designer can replace them with higher-fidelity artwork later without changing how they're wired into the layout.

**Do not** raise their opacity above ~0.1 (they read as noise/damage on a screen if they compete with content) and **do not** place them where they'd sit directly behind dense text — reserve them for empty margins.

---

## 7. Signature interaction — the candle cursor

**Behavior:** on desktop/mouse input, a soft warm glow follows the pointer with a slight lag (as if carried, not teleported), gently brightening the surface nearby via a light-blend-mode rather than painting flat color over it. A slow, irregular flicker animation layers on top so it reads as flame-lit rather than as a UI spotlight effect.

**Constraints, in order of importance:**
1. Must never drop body text below WCAG AA contrast (4.5:1) — use a brightening blend mode (`soft-light` or `screen`), never a darkening or fully-opaque one, and cap peak opacity.
2. Must respect `prefers-reduced-motion: reduce` — disable the flicker keyframe (keep the positional glow, since it's not what triggers motion sensitivity; only the flicker is decorative motion).
3. Must not activate on touch devices — there's no persistent pointer to light a path with, and a phantom glow stuck at the last-tap position looks broken. Gate with `(hover: hover) and (pointer: fine)`.
4. Must not cause layout thrash — only `background`/custom-property updates inside `requestAnimationFrame`, `pointer-events: none` throughout, `will-change: background` on the overlay only if profiling shows it's needed.

```css
[data-bs-theme="dark"] {
  --candle-x: 50%;
  --candle-y: 30%;
  --candle-radius: 380px;
}

[data-bs-theme="dark"] .candle-glow {
  position: fixed;
  inset: 0;
  z-index: var(--z-candle-glow);
  pointer-events: none;
  background: radial-gradient(
    circle var(--candle-radius) at var(--candle-x) var(--candle-y),
    hsl(35 80% 68% / 0.16),
    hsl(35 80% 68% / 0.05) 45%,
    transparent 75%
  );
  mix-blend-mode: soft-light;
  animation: candle-flicker 4.2s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  [data-bs-theme="dark"] .candle-glow { animation: none; }
}

@media (hover: none), (pointer: coarse) {
  [data-bs-theme="dark"] .candle-glow { display: none; }
}

@keyframes candle-flicker {
  0%, 100% { opacity: 1; }
  8%  { opacity: 0.94; }
  17% { opacity: 1; }
  26% { opacity: 0.9; }
  35% { opacity: 0.98; }
  50% { opacity: 0.93; }
  68% { opacity: 1; }
  82% { opacity: 0.95; }
}
```

Add one element to `templates/layout.html`, right after the opening `<body>` tag (same place `#toastContainer` and `#navSidebarOverlay` already live, near the end of `<body>`, is also fine — position in the DOM doesn't matter since it's `position: fixed`):

```html
<div class="candle-glow" aria-hidden="true"></div>
```

Then add the tracker script below to `static/js/theme.js` (it already owns dark/light state and is loaded as a plain `<script>` in `<head>`, so it's the natural home for anything dark-theme-only) — gate it so it only runs when the resolved theme is dark, and re-check that gate inside `toggleTheme()` so switching themes at runtime attaches/detaches it rather than leaving a stale glow active in light mode:

```js
(function initCandleGlow() {
  const layer = document.querySelector(".candle-glow");
  if (!layer) return;

  let targetX = window.innerWidth / 2;
  let targetY = window.innerHeight * 0.3;
  let currentX = targetX;
  let currentY = targetY;
  let raf = null;

  function update() {
    currentX += (targetX - currentX) * 0.15;
    currentY += (targetY - currentY) * 0.15;
    layer.style.setProperty("--candle-x", `${currentX}px`);
    layer.style.setProperty("--candle-y", `${currentY}px`);
    raf = (Math.abs(targetX - currentX) > 0.5 || Math.abs(targetY - currentY) > 0.5)
      ? requestAnimationFrame(update)
      : null;
  }

  window.addEventListener("mousemove", (e) => {
    targetX = e.clientX;
    targetY = e.clientY;
    if (!raf) raf = requestAnimationFrame(update);
  }, { passive: true });
})();
```

The `0.15` easing factor controls "how heavy the candle feels" — lower is laggier/heavier, higher is snappier. Don't set it above ~0.3 or the lag disappears and it stops reading as carried light.

---

## 8. Component specifications

For every component: what it is, current inconsistency (if any) across the mockups, and the exact dark-mode treatment. States not mentioned should be assumed to not change from light-mode behavior (only color/texture changes).

### 8.1 Global shell
`--bg-950` base, static vignette from §5.3, illustration layer from §6, candle-glow overlay from §7 mounted once at the root. `--font-body` as the default document font.

### 8.2 Primary navigation bar
Full-width, `--surface-800`, no texture (flat color — the nav bar is the one large surface that stays plain so it doesn't compete with the vignette). Bottom border: 1px solid `hsl(35 40% 45% / 0.12)`.

**Logo replaces the hamburger icon — this is a markup change, not just a style change.** Currently in `templates/layout.html`:
```html
<button class="btn btn-link p-1" id="navMenuButton" type="button" aria-label="Open menu">
    <i class="bi bi-list fs-4"></i>
</button>
<a class="navbar-brand mb-0" href="/">StudyLib</a>
```
Remove the `#navMenuButton` button entirely. Move its click behavior (currently wired in `initNavigation()` in `static/js/main.js`, which shows `#navSidebarOverlay` and adds `.nav-sidebar-open` to `<body>`) onto the logo element instead — change `document.getElementById('navMenuButton')` to target the logo element's id, and swap `.navbar-brand` from an `<a href="/">` to a `<button>` (a link that doesn't navigate is a real accessibility problem, so this should be a genuine element-type change, not just a re-purposed anchor). Since the logo can no longer double as a "go home" link, add a "Home" entry to the `.nav-sidebar` list in the same file, next to the existing "Browse" and "Upload" entries — this is flagged in §17 in case a "go home" path is wanted somewhere more direct than the sidebar.

Logo lockup itself: your existing logo asset (not this spec's `open-book.svg`, which is decoration-only per §6) at `--gold-300`/`--gold-100`, next to the "StudyLib" wordmark in `--font-display`, `--gold-100`.

Right side, unchanged in structure: theme toggle icon (`#themeToggle`, already wired in `static/js/theme.js` — render its `bi-moon-stars-fill`/`bi-sun-fill` glyphs in `--gold-300`) → "Hi, {name}" in `--text-secondary` → "LOGOUT" as a tertiary/ghost button, `--gold-300` text, uppercase, letter-spacing `0.05em`.

### 8.3 Search input + Go button + Filters control
Input: `--surface-800`, `--radius-input`, 1px border `--gold-700` at 30% opacity, placeholder text `--text-secondary`, entered text `--text-primary`, leading magnifying-glass icon `--gold-300`. On focus: border brightens to `--gold-300`, add `--shadow-warm-glow`.
"Go" button: **primary/brass variant** (§8.14) — solid `--gold-300` fill, `--bg-950` text (dark-on-gold for max legibility on the one brightest control on the page), `--radius-button`.
"Filters": a **dropdown control** (§8.16), not a button — `--surface-700`, 1px `--gold-700` border, chevron icon, opens a panel using `--surface-600` + `--shadow-warm-raised`.

### 8.4 AI Overview panel
`.surface-leather` (§5.2). Heading in `--font-display`, `--gold-100`. Body copy `--text-secondary`. This is the first leather-panel instance on the page — get its tint-overlay right before doing the ones below, since every other panel reuses the same class.

### 8.5 Result card (search grid)
`.surface-leather`. Thumbnail image: no filter/tint (photographic content stays neutral — texture and warm color only applies to UI chrome, never to user/source imagery). Title `--text-primary`, description `--text-secondary` (2-line clamp + ellipsis, unchanged from existing behavior). Source tag ("🌐 wikipedia"): `--gold-300`, `--text-caption` size. Bookmark icon top-right: ghost icon button, `--gold-300`, subtle warm-highlight background on hover only (`hsl(35 70% 55% / 0.08)`).
"View" and "Add" buttons: both **secondary/wood variant** (§8.14) — same visual weight; nothing in the reference suggests one outranks the other.
Below the card, the "Test (0)" control is a **dropdown control** (§8.16), same treatment as Filters, full width of the card.

### 8.6 Upload dropzone
`.surface-leather`, but with a **dashed stitched border** instead of the standard 1px solid: `border: 2px dashed hsl(35 50% 55% / 0.35); border-radius: var(--radius-panel);` — reads as leather stitching around a bound edge. Upload-cloud icon `--gold-300`. Primary line `--text-primary`, "Maximum 10MB" caption `--text-secondary`.
"Upload File" button: **primary/brass variant** — it's the page's one main action.

### 8.7 File list panel + file list item
Panel: `.surface-leather`. Header "Your Files" with a count badge (§8.17). Each row: file-type icon (`.docx` → `--info-slate`, `.pdf` → `--danger-rust`), filename `--text-primary`, size `--text-secondary` (`font-variant-numeric: tabular-nums`), trash icon as a destructive **icon button** (§8.14) — `--gold-300` at rest, `--danger-rust` on hover, never destructive-colored at rest (avoid a permanently "alarming" list).

### 8.8 Page header (workspace title block)
Title in `--font-display`, `--text-display-lg`, `--gold-100`. Subtitle `--text-secondary`. Action cluster ("…", "Rename", "Refresh"): "…" is an **icon button**; "Rename" and "Refresh" are **secondary/wood** buttons.

### 8.9 Workspace Notes card
`.surface-leather`. Textarea: transparent background (inherits the leather surface beneath it, no separate fill), `--text-primary` typed text, `--text-secondary` placeholder, no visible border at rest, `--gold-500` border on focus. "Save quick note": **secondary/wood** button.

### 8.10 Selected Source Preview card
`.surface-leather`. Tag pills ("Test", "Test", "Test" in the mockup — presumably real tag names in production): **pill/badge** styling (§8.17). "Open": **secondary/wood** button. The embedded source content area needs the **custom scrollbar** (§8.18) since it's independently scrollable from the page.

### 8.11 Workspace Studio panel + tab bar + source list
Panel: `.surface-leather`. Tab bar ("Sources" / "Notes" / "Alexander") is `static/js/pages/workspace.js`'s `.workspace-tabs.nav.nav-pills` — Bootstrap's nav-pills component, `<button class="nav-link active">`. **This is the control that currently renders blue** (§3) because nothing overrides Bootstrap's default `.nav-pills .nav-link.active` background (`var(--bs-primary)`). §4.4's `--bs-primary: var(--gold-300)` override already fixes it structurally; on top of that, add an explicit rule in `static/css/custom.css` next to the existing `.workspace-tabs .nav-link { border-radius: 999rem; }` so the exact tone matches the rest of this spec rather than just inheriting whatever shade `--bs-primary` resolves to elsewhere:
```css
[data-bs-theme="dark"] .workspace-tabs .nav-link {
  color: hsl(35 40% 76% / 0.7); /* --gold-300 at 70% */
  background: transparent;
  transition: background 150ms ease, color 150ms ease;
}
[data-bs-theme="dark"] .workspace-tabs .nav-link.active {
  background: hsl(35 70% 55% / 0.14);
  color: var(--gold-100);
}
```
Source list rows: default `--text-primary` title, `--gold-700` "wikipedia" tag. **Selected row state**: background wash `hsl(35 70% 55% / 0.1)`, 3px solid `--gold-300` left border, `--shadow-warm-glow`.

### 8.12 Notes list + note item
"Add note": **secondary/wood** button. Note item card: `--surface-700` (one step lighter than the panel behind it, so individual notes read as distinct objects sitting on the panel), document icon `--gold-300`, note title `--text-primary`.

### 8.13 Chat interface (Alexander)
Two bubble variants, both built from a rounded rectangle + a CSS triangle tail (classic speech-bubble technique) + slightly irregular per-corner radius to suggest a torn/deckled parchment edge rather than a machine-perfect rectangle:
- **AI (Alexander) bubble** — left-aligned, tail points left toward the avatar. Fill `--surface-600`, text `--text-primary`, `border-radius: 18px 22px 16px 6px`. Avatar: circular, `--surface-700` fill, gear/book icon `--gold-300`, 1px `--gold-500` ring.
- **User bubble** — right-aligned, tail points right. Fill `--gold-700` at reduced opacity over `--surface-700` (a visibly lighter/warmer parchment than the AI bubble, per the reference), text `--bg-950` or `--text-primary` depending on final contrast check, `border-radius: 22px 18px 6px 16px`.
Pagination dots + "…" overflow: small ghost **icon buttons**, `--gold-700` inactive / `--gold-300` active dot.

### 8.14 Button system (summary)

| Variant | Fill | Text | Border | Used for |
|---|---|---|---|---|
| **Primary / Brass** | Solid `--gold-300`, subtle top-edge highlight via `background-image: linear-gradient(hsl(35 80% 75% / 0.25), transparent 40%)` for an embossed-metal look | `--bg-950` | none | The single most important action per view: "Go", "Upload File" |
| **Secondary / Wood** | `.btn-secondary-wood` (§5.2) | `--gold-300` | 1px `hsl(35 40% 45% / 0.22)` | Everything of standard importance: "View", "Add", "Rename", "Refresh", "Save quick note", "Add note", "Open" |
| **Tertiary / Ghost** | transparent | `--gold-300` | 1px `--gold-700` on hover only | Low-emphasis actions, "LOGOUT" |
| **Icon button** | transparent at rest, `hsl(35 70% 55% / 0.08)` on hover | `--gold-300` (or `--danger-rust` for destructive, on hover only) | none | "…" overflow, bookmark, trash, pagination dots |

All buttons: `--radius-button`, `150ms ease` transition on background/border/color, visible focus ring (`--shadow-warm-glow`) — **never remove the focus outline without replacing it**, dark themes make default browser focus rings hard to see so this one actually matters more than usual.

### 8.15 Dropdown / select control
Distinct from buttons (Filters, "Test (0)", "55 sources"): `--surface-700` fill, 1px `--gold-700` border, `--radius-button`, chevron icon `--gold-300`, open-state menu uses `--surface-600` + `--shadow-warm-raised`.

### 8.16 Badges & pills
Count badges (file count, "55 sources"): `--radius-pill`, `--gold-900` fill, `--gold-100` text, `--text-caption` size. Category badges ("WORKSPACE"): same shape, `hsl(35 40% 45% / 0.15)` fill, `--gold-300` text, uppercase, letter-spacing `0.04em`. Remember: the dashboard reference typo is "WORRSPACE" — implement "WORKSPACE".

### 8.17 Custom scrollbar
```css
[data-bs-theme="dark"] ::-webkit-scrollbar { width: 10px; height: 10px; }
[data-bs-theme="dark"] ::-webkit-scrollbar-track { background: transparent; }
[data-bs-theme="dark"] ::-webkit-scrollbar-thumb {
  background: var(--gold-700);
  border-radius: 999px;
  border: 2px solid var(--surface-800);
}
[data-bs-theme="dark"] * { scrollbar-color: var(--gold-700) transparent; scrollbar-width: thin; }
```

### 8.18 Workspace dashboard cards
"Create new workspace" card: dashed border (same stitched-leather treatment as §8.6, but no fill/texture — it represents an empty slot, not a bound object), centered "+" and label. Populated workspace cards: `.surface-leather`, badge pill top-left, "…" icon button top-right, title `--text-primary`, meta line ("3 sources · 0 notes") `--text-secondary`, "Created on…" `--text-secondary` at `--text-caption` size.

---

## 9. Iconography

Line icons only, `stroke-width: 1.5–2`, `stroke-linecap: round`, `stroke-linejoin: round`, no filled/solid icon style anywhere (matches the illustration system in §6, keeps the whole UI on one "engraved line" visual language). Default color `--gold-300`; never render an icon in `--text-primary` (icons are always gold-family, text is always cream-family — keep that distinction consistent so the eye can tell "control" from "content" at a glance).

---

## 10. Motion

| Interaction | Duration | Easing |
|---|---|---|
| Button/control hover, focus | 150ms | ease |
| Tab switch | 150ms | ease |
| Dropdown open/close | 180ms | ease-out (open), ease-in (close) |
| Candle flicker | 4200ms loop | ease-in-out, see §7 keyframes |

Respect `prefers-reduced-motion: reduce` globally: disable the flicker; keep instant (non-animated) state changes for everything else so the app remains fully usable.

---

## 11. Accessibility floor

- Body text (`--text-primary`, `--text-secondary`) against `--surface-800`/`--bg-950` must hold ≥4.5:1 contrast. Verify after implementing — a moody palette is not an excuse to dip below AA.
- Every interactive element keeps a visible focus state (`--shadow-warm-glow`), keyboard-navigable in the same order as light mode.
- The candle-glow overlay must never be the only way information is conveyed, and must never reduce contrast (§7, constraint 1).
- Respect `prefers-reduced-motion` (§7, §10) and `(hover: hover) and (pointer: fine)` (§7) — both are correctness requirements, not nice-to-haves.
- Decorative SVGs and the candle-glow div all carry `aria-hidden="true"` / `pointer-events: none` — confirm this survives however you integrate them (some frameworks strip unrecognized SVG attributes on import; re-add if so).

---

## 12. Do's and don'ts

**Do**
- Scope every change under the existing dark-mode selector.
- Reuse the token names in §4 exactly, so they're greppable and consistent.
- Tint both textures via `background-blend-mode: multiply` before using them (§5.2) — never at raw swatch color.
- Treat wood as a button material and leather as a panel material — don't mix them.
- Keep icons gold, text cream — a strict, consistent split.
- Preserve keyboard focus visibility and reduced-motion behavior.
- Ship component by component and check each before moving on.

**Don't**
- Don't touch anything scoped to light mode, `prefers-color-scheme: light`, or an equivalent `.light` selector.
- Don't apply either texture image at full opacity/saturation directly as a `background-image` with no tint layer.
- Don't stretch a texture to `cover` — it must tile at a natural scale (§5.2).
- Don't use the raw leather swatch's saturation for large areas — always go through the tint.
- Don't let the candle-glow overlay use a normal/`source-over` blend — it must brighten, not paint over.
- Don't ship the candle effect without the `prefers-reduced-motion` and touch-device guards.
- Don't invent a second gold or a second background hue "because it looked closer" — extend the existing ramp in §4 instead.
- Don't replicate the reference's "WORRSPACE" typo, and don't leave the separate `#navMenuButton` hamburger in place — it's removed, not just restyled (§8.2).
- Don't hand-patch individual blue Bootstrap components one at a time — do the `--bs-primary`/`--bs-secondary` override in §4.4 first; it's what actually fixes the nav-pills tab bar and most buttons at once.
- Don't build anything resembling the reference mockups' bottom-right sparkle — it's a generation artifact, not a spec'd element (§3).

---

## 13. Working instructions for the coding agent

Before writing any CSS or component code:
1. The theme mechanism is confirmed (§1): `[data-bs-theme="dark"]`, toggled by `static/js/theme.js`. Don't re-derive it, just scope everything to it.
2. Global styles live in `static/css/custom.css`, loaded from `templates/layout.html`. Add §4's tokens there, inside a `[data-bs-theme="dark"] { ... }` block.
3. Add the two texture images to `static/img/textures/` and the five SVGs to `static/img/illustrations/` (§5.1). The CSS in this spec already uses those real paths.
4. Implement in this order: §4.1–4.3 tokens → **§4.4 Bootstrap variable mapping** (do this before anything else visual — it fixes most of the app's color, including the blue tab bar, before you touch a single component file) → texture mixins/classes (§5) → base shell + vignette (§5.3, §8.1) → nav, including the logo/hamburger markup change (§8.2) → buttons/dropdowns/badges (§8.14–8.17, mostly already correct after §4.4, confirm rather than rebuild) → remaining components (§8.3–8.13, 8.18) → illustration layer (§6) → candle-glow (§7) last, since it's the most novel piece and easiest to debug in isolation once everything else is stable.
5. After each component, visually diff against the relevant reference mockup and against the equivalent light-mode component to confirm light mode is untouched.

---

## 14. Asset manifest

| File | Type | Role |
|---|---|---|
| `wood-texture.png` | raster | Secondary/wood button material (§5) |
| `leather-texture.png` | raster | Leather panel material (§5) |
| `compass-rose.svg` | vector | Background decoration (§6) |
| `sextant.svg` | vector | Background decoration (§6) |
| `stacked-books.svg` | vector | Background decoration (§6) |
| `open-book.svg` | vector | Optional empty-state decoration only (§6) — the nav logo is your own separate asset (§8.2) |
| `scrollwork-flourish.svg` | vector | Corner decoration (§6) |
| `dark-mode-ui-spec.md` | this file | Source of truth |

---

## 15. Implementation checklist

- [ ] Add color tokens (§4.1) inside `[data-bs-theme="dark"]` in `static/css/custom.css`
- [ ] Add font tokens + load Cinzel / Crimson Pro (or EB Garamond) in `templates/layout.html` (§4.2)
- [ ] Add spacing/radius/elevation/z-index tokens (§4.3)
- [ ] **Add the §4.4 Bootstrap variable overrides** — confirm the nav-pills tab bar is no longer blue before moving on
- [ ] Place texture + SVG assets at `static/img/textures/` and `static/img/illustrations/` (§5.1)
- [ ] Implement `.surface-leather` / `.btn-secondary-wood` tint classes (§5.2); apply `.surface-leather` to `.upload-zone`
- [ ] Implement body base + static vignette (§5.3)
- [ ] Remove `#navMenuButton`, move its handler onto the logo, add "Home" to the sidebar list (§8.2)
- [ ] Implement illustration layer, positioned per §6
- [ ] Implement candle-glow overlay in `templates/layout.html` + `static/js/theme.js` (§7), gated by hover/pointer + reduced-motion
- [ ] Restyle remaining components one at a time (§8.3–8.13, 8.18)
- [ ] Contrast-check `--text-primary`/`--text-secondary` against every surface they appear on
- [ ] Confirm light mode renders unchanged
- [ ] Confirm `prefers-reduced-motion` and touch-device behavior

---

## 16. Ready-to-paste Copilot kickoff prompt

> Using `dark-mode-ui-spec.md` (attached) as the single source of truth, implement the dark theme described in it. Do not modify any light-mode styles. Start with §4 (design tokens) and §5 (texture system), confirm they're in place, then proceed through §8 component by component in the order given in §13. Ask me before touching any file outside the theme/styles layer. Flag anything in §3 or §17 that needs my confirmation rather than guessing.

---

## 17. Open questions / assumptions — confirm before final polish

1. **Docx icon color (§4.1):** `--info-slate` is a conventional pick, not sampled — confirm or swap.
2. **User-bubble text color (§8.13):** flagged for a contrast check once the exact `--gold-700`-over-`--surface-700` opacity is finalized in code — pick whichever of `--bg-950` / `--text-primary` clears 4.5:1.
3. **Logo as menu trigger vs. "go home" (§8.2):** the logo no longer navigates to `/` directly since it now opens the sidebar; a "Home" entry was added to the sidebar as the replacement path. Confirm that's an acceptable tradeoff, or say if a direct one-click home path needs to be preserved some other way (e.g. logo click navigates, a separate small icon opens the sidebar).
