# StudyLib Functional and Visual Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair Alexander chat, remove duplicate browse results, render Google Books natively, reveal dark-mode materials, and replace the combined wordmark/menu control with an open-book-to-hamburger menu button plus a direct Home wordmark.

**Architecture:** Keep the existing Flask, SQLite, and vanilla ES-module structure. Make hosted Anthropic the only AI path; give search one shared identity contract on server and client; add the official Google Books Embedded Viewer as a provider-specific viewer branch without persisting preview metadata; and make the visual/navigation changes through existing theme and modal state contracts.

**Tech Stack:** Python 3, Flask, SQLite, vanilla JavaScript ES modules, Bootstrap 5.3.3, pytest, Node runtime harnesses, Anthropic SDK, Google Books Embedded Viewer API.

**Approved design:** `docs/superpowers/specs/2026-07-17-studylib-functional-polish-design.md`

## Global Constraints

- Follow strict red-green-refactor: add a focused failing test, run it and record the expected failure, make the smallest production change, then rerun it green.
- Remove all executable local-model code and dependencies: no `distilgpt2`, `src.local_ai`, `USE_LOCAL_AI`, `LOCAL_AI_MODEL`, `torch`, or `transformers` in runtime or collected test code.
- Keep AI keys server-side. Never place or echo an API key in HTML, JavaScript, logs, test output, or an API response.
- Keep the existing JSON application contract: AI failures return `{"status": false, "error": "..."}`. Do not expose raw provider exception text.
- Use exact defaults `claude-sonnet-4-6` and `claude-haiku-4-5-20251001`; both remain environment-overridable.
- Do not add a database migration. Google Books `accessInfo` is response-only.
- Search deduplication preserves first-seen order and separately tracks canonical URLs, so the same URL is a duplicate even when source names or IDs differ.
- Load More requests cumulative windows of 10, 20, 30, and so on; it adds only unseen results and ends with disabled text `No more results.` when a successful batch adds none.
- Load only `https://www.google.com/books/jsapi.js` for native book previews, cache one loader promise, and use the official `google.books.DefaultViewer` volume-ID API.
- Never proxy Google Books page HTML. Preserve existing Wikipedia iframe and other source behavior.
- Treat provider fields as untrusted. Build new headers, warnings, and Google fallback UI with DOM APIs and `textContent`; only allow `http:` and `https:` outbound links.
- Preserve all light-mode leather, wood, illustration, candle, color, focus, and contrast declarations. Only navigation semantics shared by both themes may change.
- Navigation open state has one source of truth: `#brandMenuButton[aria-expanded]`. Do not add a second `open` class.
- Preserve sidebar inert handling, focus containment, backdrop/Escape/close-button behavior, and focus restoration.
- Keep changes targeted. No provider abstraction, cursor framework, custom ebook renderer, schema migration, or unrelated redesign.

---

### Task 1: Remove local AI and make Alexander hosted-only and recoverable

**Files:**

- Create: `.env.example`
- Create: `tests/test_ai.py`
- Modify: `app.py`
- Modify: `src/answer.py`
- Modify: `src/summarise.py`
- Modify: `static/js/pages/workspace.js`
- Modify: `tests/test_summarise.py`
- Modify: `test_claude_integration.py`
- Modify: `requirements.txt`
- Delete: `src/local_ai.py`
- Delete: `testAiLocal.py`

**Exact contracts:**

```python
AI_NOT_CONFIGURED_ERROR = (
    "Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib."
)
AI_PROVIDER_ERROR = "Alexander could not reach the AI service. Try again shortly."
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_SUMMARISE_MODEL = os.getenv(
    "ANTHROPIC_SUMMARISE_MODEL", "claude-haiku-4-5-20251001"
)
```

Keep these public signatures:

```python
answer_prompt(prompt: str, user_id: int, search_web: bool = True, atn=None) -> dict
chat_with_sources(messages: list, user_id: int, atn=None) -> dict
summarise_url(url, title=None, atn=None) -> dict
summarise_file(file_id, user_id, atn=None) -> dict
summarise_search_results(query, results, atn=None) -> dict
```

`summarise_search_results` now returns `{"status": True, "summary": text}` on success and the same structured failure shape as other summarizers. `app.py::browse_summary` must return that dict directly through `jsonify`, instead of wrapping it as a successful nested summary.

- [ ] Add `tests/test_ai.py` tests that statically prove `load_dotenv()` appears before every `src.*` import in `app.py`, both local-model files are absent, forbidden symbols/dependencies are absent from executable source/config, and `.env.example` has an empty key plus the exact model defaults.

- [ ] Add unit tests that monkeypatch `src.answer.client = None` and every context lookup to raise if called. Assert both answer entry points return `AI_NOT_CONFIGURED_ERROR` before any database, file, or web lookup.

- [ ] Add fake Anthropic client tests. Its `messages.create` must receive the exact configured model, preserve multi-turn message roles/content, and return the first text block in the existing success response shape.

- [ ] Add a provider-error test with a unique secret-like exception string. Assert `logging.exception` is called, the client response equals `AI_PROVIDER_ERROR`, and the unique exception string is absent from the response.

- [ ] Extend `tests/test_summarise.py`: explicitly monkeypatch a non-empty hosted key; expand success fixtures past the current 100-character minimum; assert configured key/model request headers/payload; assert missing-key URL/file/search calls fail before source/DB work; assert provider detail is logged but not returned.

- [ ] Add a Node runtime harness in `tests/test_ai.py` for `sendAlexanderMessage()`: two submissions while the first promise is pending cause one network call; chat input and Send are disabled while pending; success and rejection both remove the exact loading object and restore controls; a structured server error becomes a friendly Alexander bubble.

- [ ] Run RED tests and confirm failures describe the old local fallback and missing request lifecycle:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai.py tests/test_summarise.py
```

- [ ] Move `load_dotenv()` directly after its import and before all `src.*` imports in `app.py`; remove the unused `src.local_ai` import.

- [ ] Refactor `src/answer.py` to import the Anthropic SDK unconditionally, construct `client = anthropic.Anthropic(api_key=...)` only when the key exists, fail before context gathering when it does not, and log provider exceptions while returning only the stable message.

- [ ] Remove the local branches from `src/summarise.py`, add the early missing-key guard to all three public functions, keep its hosted HTTP request path, and make all functions return a consistent structured dict.

- [ ] Delete `src/local_ai.py` and `testAiLocal.py`; remove `torch` from `requirements.txt`; do not add `transformers`.

- [ ] Add `.env.example` with exactly:

```dotenv
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_SUMMARISE_MODEL=claude-haiku-4-5-20251001
```

- [ ] Mark `test_claude_integration.py` as a manual script with `__test__ = False`, change its default model to `claude-sonnet-4-6`, and replace partial-key printing with the non-secret text `ANTHROPIC_API_KEY is configured`.

- [ ] In `static/js/pages/workspace.js`, add module-level `alexanderRequestPending`. Guard duplicate calls; disable `#alexanderChatInput` and `#alexanderSendBtn`; use `try/finally`; remove the loading object by identity; always restore controls; render the server's error as an Alexander message; change the help copy from local placeholder to hosted research assistant.

- [ ] Run GREEN verification:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai.py tests/test_summarise.py
Get-Content -Raw static\js\pages\workspace.js | node --input-type=module --check -
rg -n -i "distilgpt2|src\.local_ai|USE_LOCAL_AI|LOCAL_AI_MODEL|import torch|from transformers" app.py src static tests requirements.txt test*.py
```

- [ ] Self-review the task diff for secret exposure, eager context lookup, and UI state that can remain disabled. Commit:

```powershell
git add .env.example app.py requirements.txt src/answer.py src/summarise.py static/js/pages/workspace.js tests/test_ai.py tests/test_summarise.py test_claude_integration.py src/local_ai.py testAiLocal.py
git commit -m "fix: make Alexander hosted-only"
```

---

### Task 2: Deduplicate server and browser search with cumulative Load More

**Files:**

- Modify: `src/search.py`
- Modify: `app.py`
- Modify: `static/js/pages/browse.js`
- Modify: `tests/test_search.py`
- Modify: `tests/test_dark_theme_contract.py`

**Server interface:**

```python
def normalize_identity_text(value):
    """Return case-folded, collapsed whitespace for untrusted scalar input."""

def canonical_source_url(value):
    """Return normalized absolute HTTP(S) URL without fragment, or empty string."""

def result_identity(item):
    """Return source/id, URL, display tuple, or None in approved priority order."""

def deduplicate_results(results):
    """Preserve first-seen order; reject repeated primary identity OR canonical URL."""
```

Use `urllib.parse.urlsplit`/`urlunsplit`. Normalize source/title text with whitespace collapse plus `casefold()`. Strip the source ID but do not case-fold it. Lowercase scheme and hostname, preserve path/query, remove fragment, and accept only absolute `http`/`https` URLs. Preserve malformed identity-less records instead of collapsing them.

**Browser interface/state:**

```javascript
function normalizeIdentityText(value)
function canonicalSourceUrl(value)
function resultIdentity(item)
function deduplicateResults(results)
function mergeUniqueResults(existing, incoming) // { results, addedCount }

let resultWindow = 10;
let searchExhausted = false;
```

- [ ] Add RED Python tests for normalized source/id identity, canonical host/fragment variants, different provider IDs sharing one URL, display fallback, first-seen ordering, and preservation of multiple malformed identity-less records.

- [ ] Add an endpoint test for `/api/browse/search-all` that stubs dedicated and whitelist providers with overlapping results and asserts one returned card per identity/URL while `source_counts` still describes provider retrieval counts.

- [ ] Extend the existing browse Node harness in `tests/test_dark_theme_contract.py` with three scripted successful responses: request 10 contains duplicates; request 20 repeats the first window plus one unseen item; request 30 repeats the same cumulative data. Assert unique cards, request sizes `[10, 20, 30]`, then a disabled button with exact text `No more results.`.

- [ ] Add a restored-state runtime test containing duplicates and old state without the new keys. Assert restoration deduplicates, restores `lastSearchQuery`, `lastSearchSources`, and `lastSearchFilters`, and defaults safely to window 10/not exhausted. Also assert exact whitelist values (`whitelist_<domain>`) restore individually instead of checking a generic `whitelist` token.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_search.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "browse_runtime or pagination or restored_browse"
```

- [ ] Implement the four Python helpers in `src/search.py`. In `app.py`, replace only the final combined result assignment with `all_results = search.deduplicate_results(all_results)` before JSON serialization.

- [ ] Implement equivalent defensive client helpers in `static/js/pages/browse.js`. Deduplicate initial API results and saved results. Merge later batches through `mergeUniqueResults`.

- [ ] Extend saved state with `resultWindow` and `searchExhausted`; restore query/sources/filters/window/exhaustion. A new search resets window to 10 and exhaustion false.

- [ ] On Load More, request `nextWindow = resultWindow + 10`. Advance `resultWindow` only after a successful response. If `addedCount === 0`, set exhaustion true, rerender, and leave the button disabled with `No more results.`. A network or status failure keeps the previous window retryable.

- [ ] Ensure loading-state cleanup queries the current button after rerender; never mutate a detached button captured before `renderResults()` replaced the DOM.

- [ ] Run GREEN and syntax checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_search.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "browse_runtime or pagination or restored_browse"
Get-Content -Raw static\js\pages\browse.js | node --input-type=module --check -
```

- [ ] Self-review identity parity between Python and JavaScript, response ordering, retry behavior, and restored legacy state. Commit:

```powershell
git add app.py src/search.py static/js/pages/browse.js tests/test_search.py tests/test_dark_theme_contract.py
git commit -m "fix: deduplicate browse result windows"
```

---

### Task 3: Render Google Books through the official native viewer

**Files:**

- Modify: `src/search.py`
- Modify: `src/proxy.py`
- Modify: `src/whitelist.py`
- Modify: `static/js/viewer.js`
- Modify: `static/css/custom.css`
- Modify: `tests/test_search.py`
- Modify: `tests/test_proxy.py`
- Modify: `tests/test_whitelist.py`
- Modify: `tests/test_dark_theme_contract.py`

**Official API contract:**

- Script: `https://www.google.com/books/jsapi.js`
- Initialize: `google.books.load()` and resolve the shared loader through `google.books.setOnLoadCallback(...)`.
- Viewer: `new google.books.DefaultViewer(container)`.
- Volume: `viewer.load(item.source_id, notFoundCallback, successCallback)`.
- Responsive resize: call documented `viewer.resize()` through one active `ResizeObserver` when available.
- References: `https://developers.google.com/books/docs/viewer/developers_guide` and `https://developers.google.com/books/docs/v1/reference/volumes`.

**Response-only result shape:**

```python
result["accessInfo"] = {
    "embeddable": access.get("embeddable") is True,
    "webReaderLink": access.get("webReaderLink", ""),
    "viewability": access.get("viewability", "UNKNOWN"),
    "accessViewStatus": access.get("accessViewStatus", "NONE"),
}
```

Apply this after `db.get_item_by_source(...) or db.create_item(...)`, never inside `item_data`.

**Viewer state/interface:**

```javascript
let googleBooksApiPromise;
let activeGoogleBooksViewer;
let googleBooksResizeObserver;
let viewerRequestGeneration = 0;

function isGoogleBooksResult(item)
function safeHttpUrl(value)
function loadGoogleBooksApi()
function renderGoogleBooksFallback(body, item, reason)
async function renderGoogleBooksViewer(body, item, generation)
export async function openViewer(item)
```

- [ ] Add RED `tests/test_search.py` cases that capture Google request params and assert `maxResults` clamps to 40; volume `source_id` survives; filtered `accessInfo` appears for both existing and newly created DB records; and the `create_item` payload never contains `accessInfo`.

- [ ] Replace the old Google proxy test with a RED test asserting `src.proxy.fetch_source("https://books.google.com/...")` performs zero `requests.get` calls and returns `status: false`, no `html`, and a safe fallback URL. Add `tests/test_whitelist.py` coverage proving `javascript://en.wikipedia.org/...` and other non-HTTP(S) schemes are rejected.

- [ ] Add a viewer Node harness to `tests/test_dark_theme_contract.py`. Assert: the volume ID reaches `DefaultViewer.load`; two openings append one script; a slow first opening cannot replace a newer opening; `ResizeObserver` calls `viewer.resize()`; non-embeddable/no-ID/script-error/load-error paths build metadata fallback; unsafe external links are omitted; Wikipedia still calls `/api/proxy/source` and renders iframe `srcdoc`.

- [ ] Assert new provider title, URL, error, and fallback values reach the DOM through `textContent`/property assignment, not template interpolation. Existing sanitized proxy reader HTML may keep its current rendering path.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_search.py tests/test_proxy.py tests/test_whitelist.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "viewer or google_books"
```

- [ ] In `src/search.py::gbooks`, set `maxResults = min(max(int(num_results), 0), 40)`. Merge only the four filtered `accessInfo` fields into each response dict after persistence lookup/create.

- [ ] In `src/whitelist.py`, require parsed schemes `http` or `https` and a hostname before allowlist matching.

- [ ] In `src/proxy.py`, detect `books.google.com` before `requests.get` and return a non-HTML native-viewer fallback. Remove `GOOGLE_BOOKS_DOMAINS`, `is_google_books_domain`, the `google_books` mode, and generated proxy markup once no longer used.

- [ ] Refactor the viewer header and new error/fallback panels to use DOM creation and `textContent`. `safeHttpUrl` returns only absolute HTTP(S) URLs. External anchors use `target="_blank"` and `rel="noopener noreferrer"`.

- [ ] Branch Google Books before PubMed/proxy fetching. Cache one script/load promise. Use the generation counter in every async success/failure callback. Disconnect any previous resize observer and clear old active viewer state on every opening.

- [ ] The fallback includes available cover, title, description, preview status, and an `Open Google Books` link using `accessInfo.webReaderLink` first, then the safe source URL. It must explain why the embedded preview is unavailable without exposing raw exceptions.

- [ ] Replace obsolete `.proxy-google-books` CSS with scoped `.google-books-viewer`, `.google-books-viewer-canvas`, and `.google-books-fallback` layout rules. Theme colors must come from existing variables; no new theme direction.

- [ ] Run GREEN:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_search.py tests/test_proxy.py tests/test_whitelist.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "viewer or google_books"
Get-Content -Raw static\js\viewer.js | node --input-type=module --check -
```

- [ ] Self-review loader idempotence, generation races, observer cleanup, unsafe-link handling, DB payload shape, and unchanged Wikipedia behavior. Commit:

```powershell
git add src/search.py src/proxy.py src/whitelist.py static/js/viewer.js static/css/custom.css tests/test_search.py tests/test_proxy.py tests/test_whitelist.py tests/test_dark_theme_contract.py
git commit -m "feat: embed Google Books previews"
```

---

### Task 4: Make dark leather, wood, and illustrations clearly visible

**Files:**

- Modify: `static/css/custom.css`
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `tests/test_light_theme_contract.py` only for the intentional dark-block checksum

**Exact dark declarations to start and verify in browser:**

```css
[data-bs-theme="dark"] .surface-leather {
    background-image:
        linear-gradient(hsl(30 43% 12% / 0.52), hsl(30 43% 12% / 0.52)),
        url("/static/img/textures/leather-texture.png");
    background-blend-mode: normal;
}

[data-bs-theme="dark"] .btn-secondary-wood {
    background-image:
        linear-gradient(hsl(31 51% 12% / 0.38), hsl(31 51% 12% / 0.38)),
        url("/static/img/textures/wood-texture.png");
    background-blend-mode: normal;
}

[data-bs-theme="dark"] .archive-illustration { opacity: 0.14; }

@media (hover: none), (pointer: coarse) {
    [data-bs-theme="dark"] .archive-illustration { opacity: 0.10; }
}
```

Retain the existing background colors, positions, repeats, sizes, borders, radii, shadows, text colors, `pointer-events: none`, absolute positioning, and background z-index.

- [ ] Update dark contract tests first. Assert each tint alpha parses to `0 < alpha < 1`, `background-blend-mode: normal`, texture URLs remain exact, old opaque `linear-gradient(var(--surface-*), ...)` values are absent, desktop opacity is `0.14`, coarse opacity is `0.10`, and pointer/z-index guards remain.

- [ ] Add mutation cases that fail when tint alpha becomes 1, blend mode returns to `multiply`, either texture URL is removed, or illustration opacity/guards regress.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "material or illustration"
```

- [ ] Make only the four approved dark-theme changes in `static/css/custom.css`.

- [ ] Run the focused dark and unchanged light contracts. The light suite's intentional checksum of the dark block will fail; update only that checksum after the final CSS is settled. Do not rewrite light declaration constants.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "material or illustration"
.\.venv\Scripts\python.exe -m pytest -q tests/test_light_theme_contract.py -k "material or illustration or dark_theme_block"
```

- [ ] Browser-check the same result card and wood button at normal display brightness in dark and light mode. The grain and SVGs must be readable without competing with body text. If tuning is necessary, change tests first, keep tint alpha strictly between 0 and 1, and keep desktop SVG opacity within `0.10..0.16`.

- [ ] Run both full theme contract files, self-review that light material declarations are byte-for-byte unchanged apart from checksum metadata, then commit:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py tests/test_light_theme_contract.py
git add static/css/custom.css tests/test_dark_theme_contract.py tests/test_light_theme_contract.py
git commit -m "fix: reveal dark archive materials"
```

---

### Task 5: Split Home wordmark and morph the open-book menu button

**Files:**

- Modify: `templates/layout.html`
- Modify: `static/js/main.js`
- Modify: `static/css/custom.css`
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `tests/test_light_theme_contract.py`

**Exact markup shape:**

```html
<button
    class="archive-menu-button icon-button"
    id="brandMenuButton"
    type="button"
    aria-label="Open navigation menu"
    aria-controls="navSidebarOverlay"
    aria-expanded="false"
>
    <span class="archive-menu-icon" aria-hidden="true">
        <span class="archive-menu-book"></span>
        <span class="archive-menu-bars">
            <span></span><span></span><span></span>
        </span>
    </span>
</button>
<a class="navbar-brand archive-wordmark mb-0" href="/" aria-label="StudyLib home">StudyLib</a>
```

The book layer uses a CSS mask from `/static/img/illustrations/open-book.svg` and `background-color: currentColor`. The hamburger layer contains exactly three horizontal bars. Closed state shows the book and hides/scales the bars; `[aria-expanded="true"]` crossfades/transforms to bars. No open-state class.

- [ ] Rewrite navigation markup tests first: assert separate button and anchor, exact Home destination/text/labels, decorative wrapper hidden, exactly three bar children, the SVG mask URL, and all morph selectors driven by `[aria-expanded="true"]`.

- [ ] Extend the existing navigation Node harness. Assert open sets `aria-expanded="true"` and label `Navigation menu open.`; close button, Escape, backdrop, and a sidebar `a[href]` each set `false`, restore label `Open navigation menu`, remove inert state, and return focus to the menu button.

- [ ] Add mutation cases for changed mask URL, changed expanded selector, wrong bar count, missing navigation-link close listener, and missing reduced-motion coverage.

- [ ] Update the task-specific CSS allowlists in `tests/test_dark_theme_contract.py` for the new neutral navigation classes before expecting the stylesheet to pass semantic scope checks.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k navigation
.\.venv\Scripts\python.exe -m pytest -q tests/test_light_theme_contract.py -k "navbar or navigation or reduced_motion"
```

- [ ] Replace the combined wordmark button with the exact split markup while retaining `brandMenuButton` and `navSidebarOverlay` IDs.

- [ ] In `static/js/main.js`, keep one `closeSidebar()` state path. Update label and `aria-expanded` in open/close, bind overlay navigation anchors to close, and preserve the existing dialog focus trap, outside-content inert handling, Escape/backdrop/close-button behavior, and focus restoration.

- [ ] Add neutral morph CSS. Use transitions on opacity/transform only. Rely on the existing shared reduced-motion rules or add an explicit rule if the contract proves the descendants are not covered. Preserve the existing light/dark wordmark colors and focus treatment now that it is an anchor.

- [ ] Run GREEN and JS syntax:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k navigation
.\.venv\Scripts\python.exe -m pytest -q tests/test_light_theme_contract.py -k "navbar or navigation or reduced_motion"
Get-Content -Raw static\js\main.js | node --input-type=module --check -
```

- [ ] Browser-check mouse and keyboard behavior at desktop and mobile widths. Confirm visible book-to-bars morph, StudyLib immediately navigates Home, every close path reverses state, focus returns, and reduced-motion switches without animation.

- [ ] Run full theme contracts, self-review that the morph has only one state source, then commit:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py tests/test_light_theme_contract.py
git add templates/layout.html static/js/main.js static/css/custom.css tests/test_dark_theme_contract.py tests/test_light_theme_contract.py
git commit -m "feat: morph book menu and link home"
```

---

## Final Whole-Branch Gate

- [ ] Run all syntax and automated checks with the repository interpreter:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Get-Content -Raw static\js\pages\workspace.js | node --input-type=module --check -
Get-Content -Raw static\js\pages\browse.js | node --input-type=module --check -
Get-Content -Raw static\js\viewer.js | node --input-type=module --check -
Get-Content -Raw static\js\main.js | node --input-type=module --check -
git diff --check
```

- [ ] Run the forbidden-runtime scan. Hits are allowed only in approved historical design/plan prose that explains removal; runtime, config, dependency, and collected test code must have zero hits:

```powershell
rg -n -i "distilgpt2|src\.local_ai|USE_LOCAL_AI|LOCAL_AI_MODEL|import torch|from transformers" app.py src static tests requirements.txt test*.py .env.example
```

- [ ] Run authenticated browser QA on `http://127.0.0.1:8010`: missing-key chat recovery; valid hosted chat when a key is locally available; initial and repeated Load More dedupe; native embeddable Google Book; non-embeddable fallback; Wikipedia viewer; dark/light texture comparison; menu morph; Home link; Escape/backdrop/link close; keyboard focus; reduced motion; desktop and mobile widths. Do not expose the key in evidence.

- [ ] Generate the whole-branch review package from the branch merge base and dispatch the required final reviewer. Fix all Critical and Important findings in one final fix wave, rerun covering tests, and re-review.

- [ ] Run `superpowers:verification-before-completion`, then `superpowers:finishing-a-development-branch`. Commit any review-only fixes, push the current `andy/repository-setup` branch, and report the exact verification and browser-QA gaps, if any.
