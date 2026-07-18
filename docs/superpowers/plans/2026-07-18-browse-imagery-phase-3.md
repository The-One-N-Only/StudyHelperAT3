# Browse Imagery Phase 3 Implementation Plan

> **Required execution:** Use subagent-driven development. Each implementation task gets a fresh implementer, task review, fix loop, and final broad review. Apply TDD: capture failing focused tests before production edits.

**Goal:** Make every Browse state visually legible: safe result imagery with reliable local fallbacks, an engraved supplied empty-state illustration, and the supplied Bible animation shown immediately for the full search wait.

**Architecture:** Keep Browse search SerpAPI-only. Normalize allowed preview URLs at the Python SerpAPI boundary, persist only sanitized/derived URLs, and keep card rendering defensive. Treat empty/loading artwork as presentation owned by `browse.js` plus theme CSS; commit optimized copies, not the user's root originals.

**Stack:** Flask/Python, vanilla ES modules, Jinja, Bootstrap, CSS, pytest, Node runtime harnesses, ffmpeg.

---

## Task 1: Resolve and render safe result imagery

**Files:**
- Modify: `src/search.py`
- Modify: `static/js/card.js`
- Modify: `static/js/pages/browse.js` (thumbnail normalization only)
- Modify: `templates/macros.html`
- Modify: `static/css/custom.css`
- Modify: `tests/test_search.py`
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `tests/test_light_theme_contract.py`

### Step 1: Add failing backend image-resolution tests

Extend `tests/test_search.py` with focused cases proving:

- A `gbooks` SerpAPI result whose `books.google.com` URL contains a valid `id` stores an HTTPS `books.google.com/books/content` cover URL derived from that ID, ahead of hostile SerpAPI metadata.
- A valid ID in the supported Google Books edition-path form is derived safely.
- SerpAPI `thumbnail`, then `favicon`, is accepted only over HTTPS with no credentials or non-standard port and a host allowed through the academic whitelist or exact suffix set: `serpapi.com`, `gstatic.com`, `googleusercontent.com`, `books.google.com`, and `wikimedia.org`.
- HTTP, credential-bearing, unexpected-port, malformed, and unrelated tracking hosts become an empty backend thumbnail so the client selects a local fallback.
- Search still makes only the existing SerpAPI call; no Wikipedia, Google Books Volumes, PubMed, or Scholar lookup is introduced.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_search.py -q -k "browse_serpapi and (thumbnail or favicon or cover or image)"
```

Expected: FAIL because Browse currently discards all SerpAPI image metadata and derives no Google Books cover.

### Step 2: Implement server-side image normalization

In `src/search.py`:

- Add small private helpers for provider-host suffix matching, strict HTTPS image URL validation, Google Books volume-ID extraction, and official cover URL construction.
- Reject credentials, non-443 explicit ports, fragments, whitespace/backslashes, and unapproved hosts.
- Prefer derived Google Books cover, then safe SerpAPI `thumbnail`, then safe SerpAPI `favicon`.
- Set `thumb_mime` and `thumb_height` consistently without fetching image bytes.
- Use the helper in `browse_serpapi_search`; preserve query, ranking, pagination, whitelist, persistence, and error behavior.
- Replace Browse's legacy blanket thumbnail blanking with strict preservation of normalized HTTPS `thumb_url` values. Keep all ranking, dedupe, restoration, and request-generation logic unchanged.

Run the focused tests again. Expected: PASS.

### Step 3: Add failing client/Jinja parity tests

Extend existing card runtime and Jinja contract coverage to prove:

- Missing or unsafe thumbnails select source-specific local fallbacks: open book for Google Books, scrollwork for Wikipedia, stacked books for Scholar/PubMed, compass for other sources.
- Remote URLs must be HTTPS.
- Result images use `loading="lazy"`, `decoding="async"`, `referrerpolicy="no-referrer"`, and empty alt text because title/source are already adjacent.
- A client-side remote image error switches once to the correct local fallback without an inline event attribute or loop.
- Client and Jinja structures expose the same fallback URL and metadata.
- `/static/img/placeholder.png` disappears from production code and templates.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "card and (image or thumbnail or fallback or parity)"
```

Expected: FAIL against current missing placeholder behavior.

### Step 4: Implement card fallback behavior and styling

In `static/js/card.js`:

- Select a local illustration from normalized source name/URL.
- Accept only HTTPS remote thumbnails; otherwise start on the local fallback.
- Set lazy/decode/referrer attributes through DOM properties/attributes.
- Attach a one-shot `error` listener which marks and switches the image to its local fallback.

In `templates/macros.html`:

- Mirror source fallback selection and image attributes without inline handlers.
- Emit a safe `data-fallback-src` contract for progressive enhancement.

In `static/css/custom.css`:

- Give the media region a stable height/background.
- Keep real covers natural.
- Make local black-line illustrations readable on parchment and recolor them to warm gold in dark mode.

Run focused tests. Expected: PASS.

### Step 5: Verify task and commit

```powershell
node --check static/js/card.js
.\.venv\Scripts\python.exe -m pytest tests/test_search.py tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "browse_serpapi or card"
git diff --check
```

Review security, client/server parity, and SerpAPI-only behavior. Commit:

```text
feat: add safe Browse result imagery
```

---

## Task 2: Add supplied Browse empty and loading artwork

**Files:**
- Add: `static/img/illustrations/browse-scholar.svg`
- Add: `static/img/loaders/bible-page-turn.gif`
- Add: `static/img/loaders/bible-page-turn-still.png`
- Modify: `static/js/pages/browse.js`
- Modify: `static/css/custom.css`
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `tests/test_light_theme_contract.py`

**Input assets (read-only):**
- `wmremove-transformed (2) (1).svg`
- `tilixia-summer-bible-3417.gif`
- `tilixia-summer-book-2478.gif` (reserved; do not add)

### Step 1: Add failing visual-state and runtime tests

Add tests proving:

- Initial Browse markup uses a decorative `browse-scholar.svg` mask and no mortarboard.
- Search loader markup uses the Bible GIF, wrapper, decorative image, and a live `Searching...` status.
- Loader appears before unresolved whitelist readiness and stays during the SerpAPI request.
- Terminal result, error, stale request, and no-source paths remove only the loader they own and leave a clear state.
- Light/dark CSS uses theme surface backgrounds plus `mix-blend-mode: multiply`.
- Light engraving is darker than its parchment surface; dark engraving is lighter than its archive surface.
- `prefers-reduced-motion` swaps the animation for the committed still frame.
- Empty and loading artwork remains bounded on small laptop/mobile viewports.
- Canonical SVG/GIF/PNG assets exist, are readable, have expected dimensions, and the optimized GIF remains animated.
- The reserved book GIF is not present under `static/`.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "browse and (empty or loader or loading or motion or asset)"
```

Expected: FAIL because current Browse uses a mortarboard and Bootstrap spinner.

### Step 2: Prepare canonical web assets

- Copy the supplied scholar SVG to `static/img/illustrations/browse-scholar.svg`; retain line geometry and add a suitable view box only if required for responsive masking.
- Use ffmpeg to resize the 1920px Bible GIF to its actual UI scale while retaining all meaningful animation frames and timing.
- Extract a representative still PNG from the same animation for reduced-motion users.
- Leave all three root inputs untouched and leave the book GIF untracked/reserved.

Record source/output dimensions, frame count, duration, and byte size in the task report.

### Step 3: Implement semantic empty/loading renderers

In `static/js/pages/browse.js`:

- Replace initial mortarboard markup with the engraved empty-state structure.
- Add small renderer helpers for empty, loading, and loader cleanup states.
- Show the loader immediately after query validation and before awaiting whitelist readiness.
- Give each loader the current search-intent generation so stale work cannot remove or replace newer UI.
- Preserve Phase 2 source-readiness/no-source behavior and Phase 1 stale-result/ranked-reveal behavior.
- Keep `aria-busy` synchronized and use a polite status region.

### Step 4: Implement responsive, theme-aware CSS

In `static/css/custom.css`:

- Render the supplied SVG through a `mask`/`-webkit-mask` with a theme-specific engraved color.
- Bound empty-state art with responsive width/height and prevent pointer interaction.
- Style `.loader-container` using the matching Browse surface in each theme.
- Apply `mix-blend-mode: multiply` to the animation.
- Hide GIF/show still under `prefers-reduced-motion`.
- Avoid decorative animation beyond the supplied state-signalling loader.

Run focused tests. Expected: PASS.

### Step 5: Browser-check both themes and commit

Start the app without exposing `.env`, then inspect initial, pending, results, error, and mobile/small-laptop states in both themes. Confirm no pale GIF square, engraved art remains obvious without competing with text, and loader appears during whitelist delay.

Run:

```powershell
node --check static/js/pages/browse.js
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "browse"
git diff --check
```

Commit:

```text
feat: add Browse archive visual states
```

---

## Phase 3 final verification

Run fresh checks:

```powershell
node --check static/js/card.js
node --check static/js/pages/browse.js
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['-q']))"
git diff --check HEAD~2..HEAD
```

Then run a final adversarial review for correctness, security, accessibility, source-rank preservation, asset weight, and visual-state ownership. Fix all material findings before Phase 4.
