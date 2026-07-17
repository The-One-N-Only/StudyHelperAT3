# StudyLib — "Old Book" Light Theme — Codex Task Spec

**Audience:** ChatGPT Codex, running autonomously against this repository.
**Scope:** Light theme only. Dark theme is explicitly out of scope for this task — see §1.
**Companion document:** `docs/design/dark-mode-ui-spec.md` — the light theme is designed to complement the dark theme, not replicate it. Read §2 for how they relate.
**Source material:** 2 light-mode texture swatches (supplied, see §14) + the actual StudyLib codebase. All palette values below were sampled programmatically from those swatches and contrast-verified before being committed to this spec — treat them as ground truth.

---

## TASK — paste this block as the Codex task

> Implement the "Old Book" light theme described in the rest of this file, against this repository, light mode only. Do not modify any dark-mode style, selector, or `data-bs-theme="dark"` behavior.
>
> Work through §13's ordering: design tokens → §4.4 Bootstrap variable overrides → texture classes → base shell → nav → buttons/dropdowns/badges → remaining components → illustration layer.
>
> Where this file gives you a default decision instead of asking you to confirm something (§16), apply the default and move on — do not stop the task to ask a question. Run the existing `pytest` suite before finishing as a sanity check that nothing broke. When done, produce a single diff/PR whose description lists every default decision you applied from §16, so a human can review and override any of them afterward.

---

## 0. How to wire this into Codex

Keep this file at `docs/design/light-mode-ui-spec.md`. Submit the TASK block above as the Codex task — Codex has full read access to the repo and will open this file itself. No `AGENTS.md` changes are required for a one-off run.

If you already have the dark theme's pointer in `AGENTS.md`, add a second line alongside it:
```markdown
When touching light-mode styles, follow docs/design/light-mode-ui-spec.md as the source of truth. Never modify dark-mode styles. Apply its §16 default decisions without stopping to ask.
```

The two texture PNGs must already be in the repo before the task starts — Codex can write CSS and SVGs but cannot source photographic texture swatches itself. See §14.

---

## 1. Non-negotiable scope constraint

**You are editing light mode only.** Before touching any file:

- The theming mechanism is already confirmed: `templates/layout.html` sets `data-bs-theme="light"` on `<html>`, and `static/js/theme.js` flips it to `data-bs-theme="dark"`. The light theme is therefore the **default, un-scoped state** — styles that apply without any theme selector are light-mode styles.
- Every new selector, token, or override you add must either be un-scoped (applies in light mode by default) or be explicitly scoped to `:root:not([data-bs-theme="dark"])` if it needs to not leak into dark mode. Do not use `[data-bs-theme="light"]` as a selector — it won't match the default state where the attribute is absent on page load before JS runs.
- Do not delete, rename, or restructure any `[data-bs-theme="dark"]` selector, rule, or token. If you find yourself touching a dark-mode rule to make light mode work, you are solving the wrong problem — split the declaration instead.
- This is a **visual/styling pass**, not a refactor. Don't change component logic, data flow, or markup structure beyond what's strictly required to add texture layers.
- Work through the order in §13 and confirm each layer before moving to the next.

---

## 2. Theme concept and relationship to dark mode

**Old Book**: a well-used reference volume taken off the shelf in daylight — cream and parchment pages, tan leather binding, ink-brown type, gilt-edged chapter headings, and a faint blush of red for emphasis, as though annotated in oxblood ink. The feeling is scholarly and analog, not sterile or digital.

**How it relates to dark mode ("Candlelit Archive"):** they share the same typefaces (Cinzel + Crimson Pro/EB Garamond), the same iconography system (gold-family line icons), the same structural layout, the same component shapes and radius tokens, and the same general gold/brown hue family — so switching between them feels like opening the same book at a desk versus reading it under lamplight at night. They are not inverses of each other (a simple color-invert would look wrong — the dark mode has much richer contrast and warmth from the candle-glow effect). Instead, the light mode is the daylight version of the same room: brighter, cooler-warm, with less atmospheric drama and more clarity.

**What does not carry over from dark mode:**
- The candle-cursor effect. No `candle-glow` overlay in light mode — daylight doesn't have a moving warm spotlight.
- The vignette background — replaced by a flat, slightly warm off-white page.
- The very dark `--bg-950`/`--surface-800` base colors — replaced by the parchment/paper ramp.
- The token names are **different** by design (paper, ink, gilt, rubric — not bg, surface, gold, danger) to make it impossible to accidentally use light tokens in dark context or vice versa. Map them clearly in §4.4's Bootstrap overrides.

---

## 3. Reconciling reference inconsistencies

There are no new UI-layout mockups for the light theme — the component structure is identical to the dark theme, so follow `docs/design/dark-mode-ui-spec.md` §3 for structural decisions (hamburger removal, "WORRSPACE" typo, sparkle omission). The only light-mode-specific resolution:

- **No candle-glow div** — if Codex is implementing both themes in one pass, confirm `<div class="candle-glow">` carries `aria-hidden="true"` and `display: none` in light mode by default, not just via the media queries already in the dark-mode spec. Light mode should not render the div visually even if JS hasn't run yet.

---

## 4. Design tokens

### 4.1 Paper / Surface tokens

Rooted in the sampled leather texture mean (`#B69770`), extended into a parchment scale. All values sampled or derived programmatically — implement exactly.

| Token | Hex | Usage |
|---|---|---|
| `--paper-50` | `#EEE6DD` | Page background, the "white" of this theme — a warm cream, not a cold `#FFFFFF` |
| `--paper-100` | `#E2D5C6` | Navbar background, secondary page surfaces |
| `--paper-200` | `#D4C2AB` | Card surfaces, panel backgrounds (before leather texture is layered on) |
| `--paper-300` | `#C6AE90` | Hover state of rows/cards; input background on focus |
| `--paper-400` | `#B79871` | Dividers, inactive tab fills, input background at rest |
| `--paper-500` | `#A98456` | Strongest surface — pressed button base, deep panel insets |

### 4.2 Ink / Text tokens

Rooted in bistre (`#3D2B1F`) — the brown-black of iron gall ink, not a neutral grey or pure black. Pure black (`#000000`) is explicitly forbidden in this theme; it reads as a printing artifact, not a manuscript.

| Token | Hex | Contrast on `--paper-50` | Usage |
|---|---|---|---|
| `--ink-900` | `#36261B` | 11.72:1 ✓ | Primary body text, card titles, nav labels — the main reading color |
| `--ink-700` | `#654834` | 6.72:1 ✓ | Secondary text, descriptions, timestamps, placeholder text |
| `--ink-500` | `#9C6E4F` | 3.48:1 — use on `--paper-50` for decorative/caption-only text where AA is not required | Disabled control labels, decorative captions |

**Contrast guarantee:** `--ink-900` and `--ink-700` both clear WCAG AA (4.5:1) on `--paper-50`, `--paper-100`, and `--paper-200`. Do not use either on `--paper-300` or darker without re-checking; `--ink-500` does not clear AA anywhere and must only be used for non-essential decoration.

### 4.3 Gilt / Gold accent tokens

Rooted in the light wood texture's hue (`#EFC787`, sampled mean), darkened and saturation-boosted to produce legible, ink-like accent tones. These are the light-mode equivalents of the dark mode's `--gold-*` family — same hue family, different luminance direction.

| Token | Hex | Contrast on `--paper-50` | Usage |
|---|---|---|---|
| `--gilt-900` | `#925D07` | 4.48:1 — borderline AA; use only at 18px+ or bold, or for non-text decoration | Focus rings, active borders, selected-row left-border |
| `--gilt-700` | `#BA7508` | 3.02:1 — below AA for text; use for decorative borders, dividers, illustration strokes | Decorative dividers, icon accents, illustration `currentColor` |
| `--gilt-500` | `#E18E0A` | 1.80:1 — never for text | Button-face highlight shimmer only (top-edge gradient), never standalone text |
| `--gilt-300` | `#F5A423` | 1.45:1 — never for text | Warm hover wash backgrounds |
| `--gilt-100` | `#F8BB59` | 1.26:1 — never for text | Subtle highlight accent |

**Important:** gilt tones in light mode are used primarily as decorative strokes, borders, and button shimmers — not as the primary text/icon color (that's `--ink-900`). This is the biggest single difference from dark mode, where `--gold-300` carries most icons and interactive labels. In light mode, icons are `--ink-900` or `--ink-700` by default; gilt is the accent, not the workhorse.

### 4.4 Rubric / Red accent tokens

"Rubric" is the medieval term for chapter headings and important annotations written in red ink. This gives the theme its one warm-contrast accent that isn't gold.

| Token | Hex | Contrast on `--paper-50` | Usage |
|---|---|---|---|
| `--rubric-700` | `#782C21` | 7.79:1 ✓✓ | Destructive actions, trash icon on hover, PDF file-type icon |
| `--rubric-500` | `#98372A` | 5.83:1 ✓ | Primary action buttons (see §8.14), active/hover states of destructive controls |
| `--rubric-50` | `#F4DBD7` | Used as a background: `--rubric-700` on `--rubric-50` gives 7.79:1 | Error state fills, destructive confirmation surfaces |

**Why rubric instead of the dark mode's `--danger-rust`:** the dark mode's rust tone is calibrated to glow warmly against a near-black surface. The same hue in light mode would read as muddy on parchment. Rubric is shifted slightly cooler and more saturated — it's recognisably the same "red danger" family while working correctly on a warm-cream page.

### 4.5 Docx / Info accent

| Token | Hex | Usage |
|---|---|---|
| `--folio-blue` | `#4A7FA5` | `.docx`/Word file-type icon only — same conventionality as dark mode's `--info-slate`, shifted lighter for legibility on parchment |

### 4.6 Typography

**Identical to dark mode** — share the same font imports and `--font-display`/`--font-body` tokens. If the dark mode spec has already added Cinzel and Crimson Pro (or EB Garamond) to `templates/layout.html`, those `<link>` tags are already present and must not be duplicated. If this task runs before the dark mode is implemented, add them here (same instruction as dark-mode-ui-spec.md §4.2).

The un-scoped (light-mode default) font assignment:
```css
:root {
  --font-display: "Cinzel", "Times New Roman", serif;
  --font-body: "Crimson Pro", "EB Garamond", Georgia, serif;
}
```

### 4.7 Spacing, radius, elevation, z-index

**Identical to dark mode** — share the same token names and values. Define them once in `:root` (un-scoped) so both themes inherit them without duplication:

| Token | Value | Usage |
|---|---|---|
| `--radius-panel` | 12px | Cards, panels, dropzone |
| `--radius-button` | 8px | Buttons, dropdown controls |
| `--radius-pill` | 999px | Badges, tags, "55 sources" pill |
| `--radius-input` | 8px | Search bar, textareas |
| `--shadow-parchment-raised` | `0 2px 10px 0 hsl(28 35% 50% / 0.18), 0 0 0 1px hsl(33 30% 60% / 0.12)` | Default card elevation — a warm tan shadow, not a neutral grey one |
| `--shadow-gilt-glow` | `0 0 0 2px var(--gilt-900), 0 0 12px 1px hsl(37 85% 55% / 0.18)` | Selected-row / focused-card glow; focus ring |
| `--z-bg-base` | 0 | Body background |
| `--z-bg-illustration` | 1 | Decorative SVGs (§6) |
| `--z-content` | 10 | Normal app content |
| `--z-overlay` | 50 | Modals, toasts, dropdown menus |

Note: `--z-candle-glow` (40) exists in dark mode but has no light-mode equivalent — do not define it in `:root`.

### 4.8 Bootstrap 5 variable mapping — do this before restyling individual components

Same principle as dark mode's §4.4: override Bootstrap's own CSS custom properties once, un-scoped (so they apply in the default / light state), and most of the app inherits the new palette for free.

```css
:root {
  /* Page and surface */
  --bs-body-bg: var(--paper-50);
  --bs-body-color: var(--ink-900);
  --bs-secondary-color: var(--ink-700);
  --bs-border-color: hsl(33 30% 72% / 0.55);
  --bs-tertiary-bg: var(--paper-100);      /* navbar, .bg-body-tertiary */
  --bs-card-bg: var(--paper-200);          /* base .card fill before texture layered on */
  --bs-offcanvas-bg: var(--paper-100);     /* source-viewer offcanvas */

  /* Primary action — rubric red, not gold */
  /* In light mode the primary action color is rubric (see §8.14), not gilt.
     Gilt is too light to be legible as a fill in daylight at standard sizes. */
  --bs-primary: var(--rubric-500);
  --bs-primary-rgb: 152, 55, 42;

  /* Secondary */
  --bs-secondary: var(--paper-400);
  --bs-secondary-rgb: 183, 152, 113;

  /* Danger */
  --bs-danger: var(--rubric-700);
  --bs-danger-rgb: 120, 44, 33;

  /* Links */
  --bs-link-color: var(--gilt-900);
  --bs-link-hover-color: var(--rubric-700);

  /* Font */
  --bs-body-font-family: var(--font-body);
}
```

**Why rubric as `--bs-primary` instead of gilt:** gilt tones are below 4.5:1 contrast on parchment at actionable sizes (see §4.3 contrast column). Bootstrap uses `--bs-primary` as button backgrounds, active nav-pill fills, and focus indicators — all of which must clear AA. Rubric-500 clears 5.83:1 on `--paper-50`. Gilt remains the decorative/border accent system (§4.3), exactly as it was in dark mode — just from the other direction.

**Consequence for the nav-pills tab bar:** unlike dark mode where §4.4 alone fixed the blue active tab, in light mode `.nav-pills .nav-link.active` will now fill with rubric-500. That is correct — see §8.11 for the explicit override that fine-tunes the exact tone.

---

## 5. Texture system

### 5.1 Provided assets

| File | Sampled mean | Dark ~p12 | Light ~p88 | Use for |
|---|---|---|---|---|
| `wood-texture-light.png` | `#EFC787` | `#DEAF69` | `#F9DBA7` | Secondary ("carved wood") buttons |
| `leather-texture-light.png` | `#B69770` | `#AF8F68` | `#BDA17C` | Panels, cards, the upload dropzone |

Place both at `static/img/textures/` alongside the dark-mode textures already there (`wood-texture.png`, `leather-texture.png`). The light and dark variants are separate files — do not overwrite the dark ones.

### 5.2 Application rule — tint with a paper-colored layer before use

Both light textures are significantly lighter and warmer than the dark equivalents. Placed raw on a parchment background they will be too vivid and read as a deliberate contrast element rather than a material surface. Apply the same `background-blend-mode: multiply` tint technique as dark mode, but with a light-colored tint layer:

```css
/* Light leather — panels, cards, dropzone */
.surface-leather {
  background-color: var(--paper-200);
  background-image:
    linear-gradient(var(--paper-200), var(--paper-200)),
    url("/static/img/textures/leather-texture-light.png");
  background-blend-mode: multiply;
  background-size: auto, 380px;
  background-repeat: repeat, repeat;
  border: 1px solid hsl(33 30% 65% / 0.45);
  border-radius: var(--radius-panel);
  box-shadow: var(--shadow-parchment-raised);
}

/* Light wood — secondary buttons only */
.btn-secondary-wood {
  background-color: var(--paper-100);
  background-image:
    linear-gradient(var(--paper-100), var(--paper-100)),
    url("/static/img/textures/wood-texture-light.png");
  background-blend-mode: multiply;
  background-size: auto, 180px;
  background-repeat: repeat;
  color: var(--ink-900);
  border: 1px solid hsl(33 30% 60% / 0.50);
  border-radius: var(--radius-button);
}
```

**Important:** `.surface-leather` and `.btn-secondary-wood` are class names shared with dark mode in the markup, but their CSS declarations must be un-scoped (defaulting to light) and then overridden under `[data-bs-theme="dark"]` (already done in the dark-mode spec). Make sure the un-scoped declarations here don't collide with the dark-mode scoped ones — they shouldn't, because the dark-mode rules have explicit `[data-bs-theme="dark"]` prefixes, but verify the cascade order once both specs are implemented.

**Tile sizes:** 150–500px range. The light leather has finer grain than the dark and looks good at ~380px; the light wood has broad grain and looks good at ~180px. Don't stretch to `cover`.

The upload dropzone already exists as `.upload-zone` in `static/css/custom.css`. The same note as dark mode applies: add `.surface-leather`'s texture to `.upload-zone` and switch its border to the dashed-stitch treatment in §8.6.

### 5.3 Base background — warm parchment, no vignette

Unlike dark mode, there is no static radial vignette in light mode — daylight is even, not pooled. The base is simply:

```css
body {
  background-color: var(--paper-50);
}
```

The subtle warmth comes from the parchment tone itself, not from a gradient. Do not add any gradient to the body background in light mode.

---

## 6. Decorative illustration layer

The same five SVGs from the dark mode are reused — but in light mode they are tinted with `--gilt-700` (a warm tan-gold) rather than the same token's darker equivalent. The opacity range is slightly higher in light mode because there's no dark background to add depth — the illustrations need to be just barely readable to add visual richness without competing with content.

| File | Suggested placement | Suggested size | Opacity | Color |
|---|---|---|---|---|
| `stacked-books.svg` | Bottom-left of search/results and dashboard pages | 240×160px | 0.10–0.13 | `--gilt-700` |
| `open-book.svg` | Optional empty-state graphic | 160×112px | 0.12 | `--gilt-700` |
| `compass-rose.svg` | Top-left corner of upload/onboarding-style pages | 180×180px | 0.10 | `--gilt-700` |
| `sextant.svg` | Right-hand margin of upload/onboarding-style pages | 200×200px | 0.09 | `--gilt-700` |
| `scrollwork-flourish.svg` | Bottom-right corner | 180×180px | 0.10 | `--gilt-700` |

```css
.illustration {
  position: absolute;
  color: var(--gilt-700);
  pointer-events: none;
  z-index: var(--z-bg-illustration);
}
```

The same `aria-hidden="true"` requirement applies. This is the only CSS property change from the dark-mode `.illustration` rule — `color` is the only override needed; everything else is the same. Structure the CSS so the un-scoped `.illustration` rule uses `--gilt-700` (light mode default) and the dark-mode spec's override uses `[data-bs-theme="dark"] .illustration { color: var(--gold-700); }`.

---

## 7. No candle cursor in light mode

The `<div class="candle-glow">` added by the dark-mode spec must be hidden in light mode. The dark-mode spec already gates it with `@media (hover: none)` and touch guards, but a display guard for the non-dark state is also needed so it doesn't activate if theme.js hasn't run yet on first paint:

```css
/* Un-scoped: hidden by default (light mode) */
.candle-glow {
  display: none;
}

/* Dark mode only re-enables it */
[data-bs-theme="dark"] .candle-glow {
  display: block;
}
```

This one rule handles it — add it to the un-scoped section of `static/css/custom.css` alongside the other light-mode base styles.

---

## 8. Component specifications

All structural and layout decisions follow the dark-mode spec. What follows describes only the **color/texture changes** specific to light mode. For any component not listed here, apply the new token set from §4 and treat it as visually resolved.

### 8.1 Global shell
`--paper-50` base, no vignette (§5.3), illustration layer from §6 using `--gilt-700`. `--font-body` as the default document font, `--ink-900` as default text.

### 8.2 Primary navigation bar
`--paper-100` background. Bottom border: 1px solid `hsl(33 30% 60% / 0.30)` — a soft tan line, reads as a page edge. Logo wordmark in `--font-display`, `--ink-900`. Theme toggle and action icons: `--ink-700`. "Hi, {name}" in `--ink-700`. "LOGOUT" tertiary button: `--ink-700` text, 1px `hsl(33 30% 60% / 0.45)` border on hover only.

### 8.3 Search input + Go button + Filters control
Input: `--paper-100` fill, 1px border `hsl(33 30% 60% / 0.50)` at rest, `--ink-700` placeholder, `--ink-900` typed text, leading magnifying-glass icon `--ink-700`. On focus: border `--gilt-900`, add `--shadow-gilt-glow`.
"Go" button: **primary/rubric variant** (§8.14) — `--rubric-500` fill, `--paper-50` text, `--radius-button`.
"Filters": **dropdown control** (§8.15) — `--paper-200` fill, 1px `hsl(33 30% 60% / 0.50)` border, `--ink-900` text, chevron icon `--ink-700`.

### 8.4 AI Overview panel
`.surface-leather`. Heading in `--font-display`, `--ink-900`. Body copy `--ink-700`. Panel header text should feel like a printed chapter heading — set at `--text-display-sm` size with letter-spacing `0.02em`.

### 8.5 Result card (search grid)
`.surface-leather`. Thumbnail: no filter/tint. Title `--ink-900`, description `--ink-700` (2-line clamp, unchanged). Source tag ("🌐 wikipedia"): `--gilt-900` at `--text-caption` size. Bookmark icon: `--ink-700` at rest, `--rubric-500` on hover.
"View" and "Add" buttons: both **secondary/wood variant** (§8.14).
Workspace dropdown below card: **dropdown control** (§8.15), full card width.

### 8.6 Upload dropzone
`.surface-leather` + dashed stitched border: `border: 2px dashed hsl(33 30% 55% / 0.50); border-radius: var(--radius-panel);` — reads as twine binding on a leather cover. Upload icon `--ink-700`. Primary line `--ink-900`, "Maximum 10MB" caption `--ink-700`.
"Upload File" button: **primary/rubric variant** — the page's one main action.

### 8.7 File list panel + file list item
Panel: `.surface-leather`. Header "Your Files" with count badge (§8.16). Each row: `.docx` icon `--folio-blue`, `.pdf` icon `--rubric-700`, filename `--ink-900`, size `--ink-700` (`font-variant-numeric: tabular-nums`), trash icon `--ink-700` at rest → `--rubric-700` on hover.

### 8.8 Page header (workspace title block)
Title in `--font-display`, `--text-display-lg`, `--ink-900`. Subtitle `--ink-700`. "Rename" and "Refresh": **secondary/wood** buttons. "…" icon button: `--ink-700`.

### 8.9 Workspace Notes card
`.surface-leather`. Textarea: transparent background, `--ink-900` typed text, `--ink-700` placeholder, no border at rest, 1px `--gilt-900` on focus. "Save quick note": **secondary/wood** button.

### 8.10 Selected Source Preview card
`.surface-leather`. Tag pills (§8.16). "Open": **secondary/wood** button. Custom scrollbar (§8.17) on the embedded content area.

### 8.11 Workspace Studio panel + tab bar + source list
Panel: `.surface-leather`.

Tab bar (``.workspace-tabs.nav.nav-pills``): §4.8 sets `--bs-primary` to rubric, so `.nav-link.active` defaults to rubric-fill — which is correct in principle but needs fine-tuning to sit in-family with the surrounding parchment. Add this explicit rule in `static/css/custom.css` next to the existing `.workspace-tabs .nav-link { border-radius: 999rem; }`:

```css
/* Light mode — un-scoped (default) */
.workspace-tabs .nav-link {
  color: var(--ink-700);
  background: transparent;
  transition: background 150ms ease, color 150ms ease;
}
.workspace-tabs .nav-link:hover {
  background: hsl(33 30% 72% / 0.35);
  color: var(--ink-900);
}
.workspace-tabs .nav-link.active {
  background: var(--rubric-50);
  color: var(--rubric-700);
  font-weight: 600;
}
```

This gives the active tab a blush-parchment fill with deep rubric text — it reads as a thumb-tab on a physical reference book. The dark-mode override (already in the dark-mode spec, under `[data-bs-theme="dark"]`) is untouched.

Source list rows: title `--ink-900`, source tag `--gilt-900`. **Selected row**: background `hsl(33 30% 72% / 0.30)`, 3px solid `--gilt-900` left border, `--shadow-gilt-glow`.

### 8.12 Notes list + note item
"Add note": **secondary/wood** button. Note item: `--paper-100` fill (one shade lighter than the panel behind it, so notes read as discrete pages resting on a leather desk), document icon `--ink-700`, title `--ink-900`.

### 8.13 Chat interface (Alexander)
Same bubble shapes and border-radius values as dark mode — the "torn parchment" corner rhythm stays:
- **AI (Alexander) bubble** — `--paper-100` fill, `--ink-900` text, `border-radius: 18px 22px 16px 6px`. Avatar: `--paper-300` fill, icon `--ink-700`, 1px `hsl(33 30% 60% / 0.40)` ring.
- **User bubble** — `--rubric-50` fill, `--rubric-700` text (contrast 7.79:1 on `--rubric-50` ✓), `border-radius: 22px 18px 6px 16px`. This gives the user's voice a distinct warm-red tint — like an annotation in red ink in the margin of a manuscript, immediately distinguishable from the neutral AI response.
Pagination dots: `--ink-500` inactive, `--gilt-900` active.

### 8.14 Button system (summary)

| Variant | Fill | Text | Border | Used for |
|---|---|---|---|---|
| **Primary / Rubric** | `--rubric-500`, subtle top-edge highlight `background-image: linear-gradient(hsl(0 0% 100% / 0.12), transparent 40%)` | `--paper-50` | none | The single most important action per view: "Go", "Upload File" |
| **Secondary / Wood** | `.btn-secondary-wood` (§5.2) | `--ink-900` | 1px `hsl(33 30% 60% / 0.50)` | Everything of standard importance: "View", "Add", "Rename", "Refresh", "Save quick note", "Add note", "Open" |
| **Tertiary / Ghost** | transparent | `--ink-700` | 1px `hsl(33 30% 60% / 0.45)` on hover only | Low-emphasis actions, "LOGOUT" |
| **Icon button** | transparent at rest, `hsl(33 30% 72% / 0.35)` on hover | `--ink-700` (or `--rubric-700` for destructive, on hover only) | none | "…" overflow, bookmark, trash, pagination dots |

All buttons: `--radius-button`, `150ms ease` transition on background/border/color, visible focus ring (`--shadow-gilt-glow`) — confirm it's visible on parchment; the gilt-900 ring color at 2px clears this.

**Note on consistency with dark mode:** primary is rubric in light / brass-gold in dark; secondary is wood in both / same class name, different texture file and text color; tertiary is ghost in both / same structure, different color tokens. The button *hierarchy* is identical — only the colors differ.

### 8.15 Dropdown / select control
`--paper-200` fill, 1px `hsl(33 30% 60% / 0.50)` border, `--radius-button`, chevron icon `--ink-700`, `--ink-900` selected text. Open-state menu: `--paper-100` fill + `--shadow-parchment-raised`.

### 8.16 Badges & pills
Count badges ("55 sources", file count): `--radius-pill`, `--paper-500` fill, `--paper-50` text, `--text-caption` size. Category badges ("WORKSPACE"): `hsl(33 30% 72% / 0.50)` fill, `--ink-900` text, uppercase, letter-spacing `0.04em`.

### 8.17 Custom scrollbar
```css
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--paper-400);
  border-radius: 999px;
  border: 2px solid var(--paper-50);
}
* { scrollbar-color: var(--paper-400) transparent; scrollbar-width: thin; }
```
These are un-scoped (light mode default). The dark-mode spec already has `[data-bs-theme="dark"]` scoped overrides for the same properties — confirm they take precedence in dark mode (they will, given selector specificity).

### 8.18 Workspace dashboard cards
"Create new workspace" card: dashed border `2px dashed hsl(33 30% 55% / 0.45)`, `--paper-50` fill (no texture — empty slot), `--ink-700` "+" and label.
Populated workspace cards: `.surface-leather`, "WORKSPACE" badge (§8.16) top-left, "…" icon button top-right (`--ink-700`), title `--ink-900`, meta line `--ink-700`, "Created on…" `--ink-700` at `--text-caption` size.

---

## 9. Iconography

Line icons, `stroke-width: 1.5–2`, `stroke-linecap: round`, `stroke-linejoin: round` — same visual language as dark mode. Default icon color in light mode: `--ink-700` (not `--gilt-900`; gilt is below AA for icon labeling). Actively hovered or focused interactive icons: `--ink-900`. Accent/highlight icons (bookmark saved, starred item): `--gilt-900`. Destructive icons on hover: `--rubric-700`.

This is the most significant behavioral difference from dark mode's icon system, where all icons were `--gold-300`. In light mode, icons are ink-family by default and gilt only on specific accent use. The reason: gilt tones are below AA contrast on parchment at small sizes (§4.3), while ink tones clear AA comfortably.

---

## 10. Motion

Identical to dark mode. All timing and easing values carry over:

| Interaction | Duration | Easing |
|---|---|---|
| Button/control hover, focus | 150ms | ease |
| Tab switch | 150ms | ease |
| Dropdown open/close | 180ms | ease-out (open), ease-in (close) |

No candle-flicker animation in light mode. `prefers-reduced-motion: reduce` still applies to any animation that does exist.

---

## 11. Accessibility floor

- `--ink-900` and `--ink-700` on `--paper-50` clear WCAG AA (11.72:1 and 6.72:1 respectively) — verified at token derivation time. Do not swap these color combinations without re-checking.
- `--rubric-500` on `--paper-50` clears AA (5.83:1) — verified. Use confidently for button fills and active-state fills.
- `--gilt-900` on `--paper-50` is 4.48:1 — just under AA for small/normal text. Only use for large text (18px+), bold text (14px+ bold), or non-text decorative borders. Do not use as a body-text color.
- `--gilt-700` and lighter gilt tones must never appear as body text or interactive labels — decoration only (§4.3).
- Focus rings use `--shadow-gilt-glow` (a 2px `--gilt-900` ring) — visible on parchment, consistent with dark mode's focus system.
- Every interactive element keeps a visible focus state, keyboard-navigable in the same order as dark mode.
- The `<div class="candle-glow">` must be `display: none` in light mode (§7) — confirm after implementation.
- `--ink-500` must never be used for body text, button labels, or interactive labels (§4.2).

---

## 12. Do's and don'ts

**Do**
- Keep light-mode styles un-scoped (or explicitly `:root:not([data-bs-theme="dark"])`) — never `[data-bs-theme="light"]`.
- Use `--ink-900`/`--ink-700` for icons, not gilt (§9) — different rule from dark mode.
- Use rubric for the primary action, not gilt (§4.8, §8.14) — different from dark mode's brass.
- Use the same `.surface-leather` and `.btn-secondary-wood` class names as dark mode — but confirm their un-scoped CSS here and dark-mode CSS under `[data-bs-theme="dark"]` are correctly separated.
- Keep the user chat bubble in `--rubric-50`/`--rubric-700` — it reads as a red-ink annotation, the light-mode equivalent of dark mode's warm-parchment bubble.
- Reuse the exact same SVG illustration files from dark mode — only `color` changes (§6).
- Confirm `display: none` on `.candle-glow` in un-scoped CSS (§7).
- Apply §16's default decisions and keep going — surface them in the final PR description.

**Don't**
- Don't use `#FFFFFF` or `#000000` anywhere. They are forbidden in this theme — pure white reads as digital, pure black reads as printer's ink, neither fits a manuscript.
- Don't touch any `[data-bs-theme="dark"]` rule.
- Don't use gilt tones as body text or icon fill — they fail contrast below 18px.
- Don't add a vignette or gradient to the body background (§5.3) — the warmth is in the parchment tone, not a lighting effect.
- Don't render the candle-glow div visibly in light mode.
- Don't re-implement the sparkle from the reference mockups (§3, inherited from dark-mode spec).
- Don't tile textures at less than ~150px or more than ~500px.
- Don't use `[data-bs-theme="light"]` as a selector — it won't match the default un-attributed state.
- Don't stop mid-task to ask which default to use from §16 — apply the stated default and note it in the PR description.

---

## 13. Working instructions for Codex

1. The theming mechanism is confirmed (§1): light mode is the un-scoped default, dark mode is `[data-bs-theme="dark"]`. All light-mode CSS goes un-scoped.
2. Global styles live in `static/css/custom.css`. Light-mode tokens go in `:root { ... }`. If the dark-mode spec has already been implemented, a `:root` block may already exist for shared tokens — extend it, don't create a duplicate.
3. Confirm the two light-mode texture PNGs already exist at `static/img/textures/` (§14) before writing any CSS that references them.
4. Confirm the five SVG illustrations already exist at `static/img/illustrations/` (from the dark-mode spec or your own generation per dark-mode-ui-spec.md §6) — they are reused, not duplicated.
5. Implement in this order: `:root` tokens (§4.1–4.7) → **§4.8 Bootstrap variable overrides** (do this before anything else visual) → `.candle-glow { display: none }` guard (§7) → texture classes / `.surface-leather` un-scoped override (§5.2) → base shell (§5.3, §8.1) → nav (§8.2) → buttons/dropdowns/badges (§8.14–8.17) → tab bar explicit override (§8.11) → remaining components (§8.3–8.10, 8.12, 8.13, 8.18) → illustration layer color override (§6).
6. After each component, confirm: (a) it matches the old-book palette, (b) the dark-mode version of the same component is visually unchanged.
7. Run `pytest`. Write the PR description per §13 step 8.
8. The PR description must list: every component touched, every default decision applied from §16, any deviation from this spec and why, and a note that visual review of the dark/light theme switch is a manual step for the human reviewer.

---

## 14. Asset manifest

| File | Type | Role | Must exist before task starts? |
|---|---|---|---|
| `wood-texture-light.png` | raster | Light-mode wood button material (§5) | **Yes** — add to `static/img/textures/` before starting |
| `leather-texture-light.png` | raster | Light-mode leather panel material (§5) | **Yes** — same |
| `compass-rose.svg` | vector | Background decoration (§6) — reused from dark mode | No — generate per dark-mode-ui-spec.md §6 if missing |
| `sextant.svg` | vector | Background decoration (§6) — reused | No — same |
| `stacked-books.svg` | vector | Background decoration (§6) — reused | No — same |
| `open-book.svg` | vector | Optional empty-state decoration (§6) — reused | No — same |
| `scrollwork-flourish.svg` | vector | Corner decoration (§6) — reused | No — same |
| `dark-mode-ui-spec.md` | reference | Companion document — structural decisions inherited from here | — |
| `light-mode-ui-spec.md` | this file | Source of truth for light mode | — |

---

## 15. Implementation checklist

- [ ] Add `:root` tokens (§4.1–4.7) in `static/css/custom.css` — extend any existing `:root` block, don't duplicate
- [ ] Confirm Cinzel + Crimson Pro (or EB Garamond) loaded in `templates/layout.html` (§4.6) — add only if not already present from dark-mode pass
- [ ] **Add §4.8 Bootstrap variable overrides** — confirm nav-pills tab bar fills with rubric-50/rubric-700 (not Bootstrap blue, not gold)
- [ ] Add `.candle-glow { display: none; }` to un-scoped CSS (§7)
- [ ] Confirm/place light-mode texture PNGs at `static/img/textures/` (§14)
- [ ] Confirm/place SVG illustrations at `static/img/illustrations/` (reused from dark mode, §14)
- [ ] Implement un-scoped `.surface-leather` and `.btn-secondary-wood` (§5.2) — confirm dark-mode `[data-bs-theme="dark"]` versions are still separate and untouched
- [ ] Implement body background (§5.3)
- [ ] Restyle nav (§8.2)
- [ ] Restyle buttons, dropdowns, badges, scrollbar (§8.14–8.17)
- [ ] Restyle workspace tab bar with explicit rule (§8.11)
- [ ] Restyle remaining components one at a time (§8.3–8.10, 8.12, 8.13, 8.18)
- [ ] Set illustration `color: var(--gilt-700)` in un-scoped `.illustration` rule (§6)
- [ ] Contrast-check: `--ink-900`/`--ink-700` on every surface, `--rubric-500` button fills, `--gilt-900` borders/rings
- [ ] Confirm dark mode renders completely unchanged after all the above
- [ ] Confirm manual theme-switch (via `#themeToggle`) transitions cleanly between both themes
- [ ] Run `pytest`; write PR description per §13 step 8

---

## 16. Default decisions — apply these without stopping to ask, then list them in the PR description

1. **Folio-blue for `.docx` icons (§4.5):** use `#4A7FA5` as given. Conventional pick — flag in the PR description for designer review.
2. **User chat bubble fill (§8.13):** default to `--rubric-50` fill with `--rubric-700` text (contrast 7.79:1, verified). If the designer wants to revisit the "red ink annotation" metaphor for the user bubble, note it in the PR but ship this default.
3. **`.surface-leather` class shared between themes (§5.2):** the un-scoped CSS here is the light-mode definition; `[data-bs-theme="dark"] .surface-leather` in the dark-mode spec is the dark override. If both are implemented in the same file, order matters — the dark-mode rule must appear after the un-scoped rule so it wins via cascade. Confirm this ordering; if the dark-mode spec created a separate file or block, note the ordering in the PR.
4. **Nav hamburger/logo change (§8.2):** inherited from dark-mode spec §3. If the dark-mode pass already made this change, nothing to do — confirm it's in place. If this light-mode task runs first, make the change as part of this pass (it's a shared markup change, not theme-specific).
