# Browse AI Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Browse sidebar placeholder with an automatic, retryable, race-safe overview of the accepted search results while retaining Search sources below it.

**Architecture:** Add a small summary API client module so existing Browse runtime harnesses can inject a deterministic stub without rewriting every search fixture. Keep search ownership, rendering, candidate selection, and persistence in `static/js/pages/browse.js`, where the current query generation and grouped result state already live. Reuse the existing `/api/browse/summary` hosted-only backend contract; no backend or provider changes are required.

**Tech Stack:** Vanilla JavaScript ES modules, Flask JSON route, Bootstrap components, localStorage version-2 Browse state, pytest, BeautifulSoup, and Node-based JavaScript runtime harnesses.

## Global Constraints

- Browse search remains SerpAPI-only; summary generation performs no new source search.
- Keep `ANTHROPIC_API_KEY` server-side and optional; add no API-key endpoint, local model, or local-AI fallback.
- Render AI Overview above a separate Search sources card.
- Start one summary request only after each accepted successful search; never regenerate on Load More or sorting.
- Send at most 10 source-diverse rank-one results containing only title, description, source name, safe source URL, and whitelist rank.
- Bound each browser summary request to 15,000 ms.
- Results render without waiting for summary generation.
- Only the summary request owned by the current accepted search generation may update UI or persisted state.
- Summary and error text render as escaped text; provider details remain private server logs.
- Missing configuration, provider/network failure, malformed JSON, timeout, and Retry must terminate without an endless spinner.
- Persist only a successful summary whose query matches the current accepted query.
- Existing version-2 Browse state remains valid; no database or localStorage migration.
- Preserve ranked reveal, filters, source readiness, result imagery, Google Books viewer, light/dark themes, responsive layout, and the three untracked root user assets.

---

### Task 1: Automatic overview request, rendering, Retry, and race ownership

**Files:**
- Create: `static/js/browse-summary.js`
- Modify: `static/js/pages/browse.js:1-37`
- Modify: `static/js/pages/browse.js:509-695`
- Modify: `static/js/pages/browse.js:743-788`
- Modify: `static/js/pages/browse.js:1178-1255`
- Test: `tests/test_dark_theme_contract.py`

**Interfaces:**
- Consumes: `POST /api/browse/summary` with `{query: string, results: SummaryResult[]}` and existing `{status: boolean, summary?: string, error?: string}` response.
- Produces: `fetchBrowseSummary(payload: object, signal: AbortSignal): Promise<string>` in `static/js/browse-summary.js`.
- Produces: `currentOverview: {status: 'idle'|'loading'|'success'|'error'|'empty', query: string, text: string, error: string}` owned by `static/js/pages/browse.js`.
- Produces: `buildSummaryResults(groupedResults?: object, sources?: string[]): SummaryResult[]`, returning at most ten source-diverse result snapshots. Defaults use current accepted Browse groups/source order; explicit arguments make boundary behavior directly testable.
- Produces: `loadSearchSummary(query: string, ownerSearchGeneration: number): Promise<void>` with abort, timeout, Retry, and stale-response guards.
- Task 2 consumes `currentOverview`, `renderOverviewCard()`, and `loadSearchSummary()` for persistence and restored-state actions.

- [ ] **Step 1: Add failing API-client and Browse lifecycle runtime contracts**

Add the new import replacement beside `BROWSE_IMPORT_REPLACEMENTS` so all existing Browse harnesses receive a stable successful stub unless a focused overview harness overrides it:

```python
BROWSE_SUMMARY_IMPORT = (
    "import { fetchBrowseSummary } from '../browse-summary.js';"
)

BROWSE_IMPORT_REPLACEMENTS = (
    (
        "import { showToast } from '../toast.js';",
        "const showToast = (...args) => globalThis.toastCalls.push(args);",
    ),
    (
        "import { createCard } from '../card.js';",
        "const createCard = (item) => { globalThis.renderedItems.push(item); return item; };",
    ),
    (
        BROWSE_SUMMARY_IMPORT,
        "const fetchBrowseSummary = (...args) => "
        "globalThis.fetchBrowseSummary "
        "? globalThis.fetchBrowseSummary(...args) "
        ": Promise.reject(new Error('Test summary unavailable'));",
    ),
)
```

Update the custom `broken_image_grouped_browse_runtime()` replacement tuple to include `BROWSE_IMPORT_REPLACEMENTS[2]` after its custom card-module import. This is the only helper that currently selects Browse import replacements by index; every other Browse helper already passes the full tuple. The default rejected summary stub is caught by production lifecycle code, clears its timer, performs no extra localStorage success write, and leaves existing harnesses independent from the hosted summary route.

Add a pure client harness that imports `static/js/browse-summary.js` through a data URL and asserts:

```javascript
const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({ url, options });
  return {
    ok: true,
    async json() { return { status: true, summary: "Concise overview." }; },
  };
};

const { fetchBrowseSummary } = await import(process.argv[1]);
const controller = new AbortController();
const summary = await fetchBrowseSummary(
  { query: "archives", results: [{ title: "Archive" }] },
  controller.signal,
);
invariant(summary === "Concise overview.", "client changed summary text");
invariant(calls.length === 1, "client issued extra request");
invariant(calls[0].url === "/api/browse/summary", "client used wrong endpoint");
invariant(calls[0].options.signal === controller.signal, "client lost abort signal");
```

Run the same client against these exact response fixtures and assert the rejected `Error.message`:

```javascript
[
  [{ ok: true, json: async () => ({ status: false, error: "Alexander is not configured." }) }, "Alexander is not configured."],
  [{ ok: false, json: async () => ({ status: false, error: "Try again shortly." }) }, "Try again shortly."],
  [{ ok: true, json: async () => { throw new SyntaxError("bad JSON"); } }, "Unable to create overview. Try again."],
  [{ ok: true, json: async () => ({ status: true, summary: "   " }) }, "Unable to create overview. Try again."],
]
```

Add `BROWSE_OVERVIEW_RUNTIME_HARNESS` using `TASK6_RUNTIME_BASE + BROWSE_DOM_RUNTIME`. Override `#sidebarContainer.innerHTML` so it records markup and exposes one `[data-overview-action]` button. Stub `globalThis.fetchBrowseSummary` and assert all of these in one accepted-search lifecycle:

```javascript
invariant(summaryCalls.length === 1, "accepted search did not request one overview");
invariant(summaryCalls[0].query === "archive", "overview query changed");
invariant(summaryCalls[0].results.length <= 10, "overview payload exceeded ten results");
invariant(
  Object.keys(summaryCalls[0].results[0]).sort().join(",") ===
    "description,source_name,source_url,title,whitelist_rank",
  "overview payload leaked extra result metadata",
);
invariant(sidebarMarkup.includes("AI Overview"), "overview card missing");
invariant(sidebarMarkup.includes("Search sources"), "source card was replaced");
invariant(sidebarMarkup.includes("&lt;script&gt;"), "summary text was not escaped");
invariant(!sidebarMarkup.includes("<script>"), "summary injected HTML");
```

For the candidate boundary, append `export { buildSummaryResults };` to the instrumented Browse module. Construct 12 ordered groups, make the first two groups contain the same source identity, and call `buildSummaryResults(groups, Object.keys(groups))`. Assert the duplicate appears once, output length is exactly 10, group order is preserved, every record has only the five approved keys, every `whitelist_rank` is `1`, credential-bearing source URLs become empty strings, and the eleventh unique source is excluded.

Make the first summary attempt reject with `new Error("Try again shortly.")`, dispatch the generated Retry button, make the second attempt return `Recovered overview.`, and assert exactly two calls and a recovered success state.

Add `BROWSE_OVERVIEW_STALE_RUNTIME_HARNESS`: perform query A, leave its summary deferred, perform query B, resolve B, then resolve A. Assert the panel contains B and never A. Assert A's `AbortSignal.aborted` is `true`.

Add `BROWSE_OVERVIEW_NO_RESULTS_RUNTIME_HARNESS`: return an accepted empty search response, assert zero summary calls and the exact copy `No overview is available because this search returned no results.`

Add Python entry points and tests:

```python
def test_browse_summary_client_enforces_structured_contract_and_abort_signal():
    rendered = browse_summary_client_runtime()
    assert rendered["summary"] == "Concise overview."
    assert rendered["callCount"] == 1


def test_browse_ai_overview_runs_after_results_and_keeps_source_card():
    rendered = browse_overview_runtime()
    assert rendered["summaryCalls"] == 2
    assert rendered["recovered"] is True


def test_browse_ai_overview_ignores_stale_query_response():
    rendered = browse_overview_stale_runtime()
    assert rendered == {"text": "Query B overview.", "firstAborted": True}


def test_browse_ai_overview_skips_empty_results():
    rendered = browse_overview_no_results_runtime()
    assert rendered["summaryCalls"] == 0
    assert rendered["emptyCopy"] is True
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py -q -k "browse_summary_client or browse_ai_overview"
```

Expected: failures because `static/js/browse-summary.js`, its import, overview state, automatic request, Retry, and stale ownership do not exist.

- [ ] **Step 3: Implement the summary API client**

Create `static/js/browse-summary.js`:

```javascript
"use strict";

export const DEFAULT_BROWSE_SUMMARY_ERROR = "Unable to create overview. Try again.";

export async function fetchBrowseSummary(payload, signal) {
    const response = await fetch('/api/browse/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
    });

    let data = null;
    try {
        data = await response.json();
    } catch (_err) {
        throw new Error(DEFAULT_BROWSE_SUMMARY_ERROR);
    }

    const publicError = typeof data?.error === 'string' && data.error.trim()
        ? data.error.trim()
        : DEFAULT_BROWSE_SUMMARY_ERROR;
    if (!response.ok || data?.status !== true) throw new Error(publicError);
    if (typeof data.summary !== 'string' || !data.summary.trim()) {
        throw new Error(DEFAULT_BROWSE_SUMMARY_ERROR);
    }
    return data.summary.trim();
}
```

- [ ] **Step 4: Add bounded summary state and result snapshots to Browse**

Import the client and add exact constants/state near existing Browse state:

```javascript
import { fetchBrowseSummary } from '../browse-summary.js';

const BROWSE_SUMMARY_TIMEOUT_MS = 15000;
const SUMMARY_RESULT_LIMIT = 10;
const SUMMARY_TEXT_LIMIT = 6000;
const SUMMARY_FIELD_LIMITS = Object.freeze({
    title: 500,
    description: 2000,
    source_name: 200,
});

let currentOverview = overviewState();
let overviewRequestGeneration = 0;
let activeOverviewController = null;

function overviewState(status = 'idle', query = '', text = '', error = '') {
    return { status, query, text, error };
}

function normalizedSummaryField(value, limit) {
    return typeof value === 'string' ? value.trim().slice(0, limit) : '';
}

function safeSummarySourceUrl(value) {
    if (typeof value !== 'string') return '';
    try {
        const parsed = new URL(value.trim());
        if (!['http:', 'https:'].includes(parsed.protocol)) return '';
        if (parsed.username || parsed.password) return '';
        parsed.hash = '';
        return parsed.href.slice(0, 2048);
    } catch (_err) {
        return '';
    }
}

function buildSummaryResults(
    groupedResults = currentGroupedResults,
    sources = sourcesToDisplay(),
) {
    const summaryResults = [];
    const seen = new Set();
    for (const source of sources) {
        const item = (groupedResults[source] || [])[0];
        if (!item) continue;
        const identity = resultIdentityKey(item) || source;
        if (seen.has(identity)) continue;
        seen.add(identity);
        summaryResults.push({
            title: normalizedSummaryField(item.title, SUMMARY_FIELD_LIMITS.title) || 'Untitled',
            description: normalizedSummaryField(
                item.description,
                SUMMARY_FIELD_LIMITS.description,
            ),
            source_name: normalizedSummaryField(
                item.source_name,
                SUMMARY_FIELD_LIMITS.source_name,
            ),
            source_url: safeSummarySourceUrl(item.source_url),
            whitelist_rank: 1,
        });
        if (summaryResults.length === SUMMARY_RESULT_LIMIT) break;
    }
    return summaryResults;
}
```

- [ ] **Step 5: Replace placeholder-only sidebar rendering with independent overview and source cards**

Add `renderOverviewCard()` and bind its action after setting sidebar markup:

```javascript
function renderOverviewCard() {
    const hasResults = currentSearchResults.length > 0;
    let body = '';
    if (currentOverview.status === 'loading') {
        body = `
            <div class="d-flex align-items-center gap-2">
                <span class="spinner-border spinner-border-sm ai-overview-spinner" aria-hidden="true"></span>
                <span>Creating overview…</span>
            </div>`;
    } else if (currentOverview.status === 'success') {
        body = `<p class="small mb-0">${escapeHtml(currentOverview.text)}</p>`;
    } else if (currentOverview.status === 'error') {
        body = `
            <p class="small mb-2">${escapeHtml(currentOverview.error)}</p>
            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" type="button" data-overview-action="retry">Retry</button>`;
    } else if (currentOverview.status === 'empty') {
        body = '<p class="small mb-0">No overview is available because this search returned no results.</p>';
    } else if (hasResults && lastSearchQuery) {
        body = `
            <p class="small mb-2">Generate an overview of these search results.</p>
            <button class="btn btn-sm btn-outline-primary btn-secondary-wood" type="button" data-overview-action="generate">Generate overview</button>`;
    } else {
        body = '<p class="small mb-0">AI search insights will appear here after you run a search.</p>';
    }

    return `
        <section class="card surface-leather ai-overview-panel mb-3" aria-labelledby="browseOverviewTitle">
            <div class="card-header">
                <h2 class="card-title h5 mb-0" id="browseOverviewTitle">AI Overview</h2>
            </div>
            <div class="card-body" data-overview-status="${currentOverview.status}" aria-live="polite" aria-busy="${currentOverview.status === 'loading' ? 'true' : 'false'}">
                ${body}
            </div>
        </section>`;
}

function bindOverviewAction(sidebar) {
    const action = sidebar.querySelector('[data-overview-action]');
    action?.addEventListener('click', () => {
        if (!lastSearchQuery || currentSearchResults.length === 0) return;
        void loadSearchSummary(lastSearchQuery, searchGeneration);
    });
}
```

Refactor `renderSidebar()` so it always begins with `renderOverviewCard()`, appends Search sources only when `lastSearchSources` is non-empty, assigns `sidebar.innerHTML` once, then calls `bindOverviewAction(sidebar)`. Preserve existing source counts, titles, descriptions, and archive classes verbatim.

- [ ] **Step 6: Implement request timeout, Retry, and generation ownership**

Add:

```javascript
function cancelOverviewRequest() {
    overviewRequestGeneration += 1;
    activeOverviewController?.abort();
    activeOverviewController = null;
}

async function loadSearchSummary(query, ownerSearchGeneration) {
    const results = buildSummaryResults();
    if (!results.length) {
        currentOverview = overviewState('empty', query);
        renderSidebar(currentSourceCounts, currentSearchResults);
        return;
    }

    cancelOverviewRequest();
    const requestGeneration = overviewRequestGeneration;
    const controller = new AbortController();
    activeOverviewController = controller;
    let timedOut = false;
    const timeoutId = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, BROWSE_SUMMARY_TIMEOUT_MS);
    currentOverview = overviewState('loading', query);
    renderSidebar(currentSourceCounts, currentSearchResults);

    try {
        const summary = await fetchBrowseSummary({ query, results }, controller.signal);
        if (
            ownerSearchGeneration !== searchGeneration
            || requestGeneration !== overviewRequestGeneration
        ) return;
        currentOverview = overviewState(
            'success',
            query,
            summary.slice(0, SUMMARY_TEXT_LIMIT),
        );
        saveBrowseState();
        renderSidebar(currentSourceCounts, currentSearchResults);
    } catch (error) {
        if (
            ownerSearchGeneration !== searchGeneration
            || requestGeneration !== overviewRequestGeneration
        ) return;
        if (error?.name === 'AbortError' && !timedOut) return;
        const message = timedOut
            ? 'Overview took too long. Try again.'
            : (error?.message || 'Unable to create overview. Try again.');
        currentOverview = overviewState('error', query, '', message);
        renderSidebar(currentSourceCounts, currentSearchResults);
    } finally {
        clearTimeout(timeoutId);
        if (requestGeneration === overviewRequestGeneration) {
            activeOverviewController = null;
        }
    }
}
```

In `initBrowse()`, call `cancelOverviewRequest()` and reset `currentOverview = overviewState()` before rendering the new page root.

In `performSearch()`, cancel/reset overview only after source readiness completes and at least one source is valid. This preserves the previous accepted overview when a user submits an invalid no-source action:

```javascript
cancelOverviewRequest();
const generation = ++searchGeneration;
currentOverview = overviewState('idle', query);
```

After accepted results are normalized:

```javascript
currentOverview = currentSearchResults.length
    ? overviewState('idle', query)
    : overviewState('empty', query);
saveBrowseState();
clearSearchLoader(intentGeneration);
renderCurrentResults();
if (currentSearchResults.length) {
    void loadSearchSummary(query, generation);
}
```

Do not call `loadSearchSummary()` from `loadMoreResults()`, the sorting handler, or `renderCurrentResults()`.

- [ ] **Step 7: Run focused and existing Browse contracts**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py -q -k "browse_summary_client or browse_ai_overview"
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "browse"
node --check static/js/browse-summary.js
node --check static/js/pages/browse.js
git diff --check
```

Expected: new overview contracts pass; all existing Browse contracts pass; both JavaScript files parse; diff check exits zero.

- [ ] **Step 8: Commit Task 1**

```powershell
git add -- static/js/browse-summary.js static/js/pages/browse.js tests/test_dark_theme_contract.py
git commit -m "feat: restore Browse AI overview"
```

---

### Task 2: Successful-summary persistence, restored-state action, and motion-safe presentation

**Files:**
- Modify: `static/js/pages/browse.js:1036-1144`
- Modify: `static/css/custom.css` beside existing `.ai-overview-panel` rules
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `tests/test_light_theme_contract.py`

**Interfaces:**
- Consumes: Task 1 `currentOverview`, `overviewState()`, `loadSearchSummary()`, `renderOverviewCard()`, and 6,000-character summary limit.
- Produces: optional version-2 state field `overview: null | {query: string, text: string}`.
- Produces: restored success state with no provider call, or legacy Generate overview action with no automatic page-boot call.

- [ ] **Step 1: Add failing persistence and accessibility contracts**

Add a restored-state runtime harness with two exact fixtures.

Successful fixture:

```javascript
{
  version: 2,
  query: "restored archive",
  sources: ["wikipedia"],
  filters: { min_date: "", max_date: "", content_type: "", sorting: "" },
  results: [restoredItem],
  groupedResults: { wikipedia: [restoredItem] },
  sourceCounts: { wikipedia: 1 },
  groupPage: 1,
  overview: { query: "restored archive", text: "Stored overview." },
}
```

Assert `Stored overview.` renders and `globalThis.fetchBrowseSummary` is never called.

Legacy fixture: same state without `overview`. Assert `Generate overview` renders, no page-boot call occurs, dispatching the Generate button makes exactly one call, and the successful text replaces the action.

Add hostile restoration cases and assert they produce Generate overview rather than rendered text:

```javascript
[
  { query: "different query", text: "Wrong query." },
  { query: "restored archive", text: "" },
  { query: "restored archive", text: "x".repeat(6001) },
  "legacy string",
]
```

Add markup assertions using BeautifulSoup:

```python
overview = soup.select_one("section.ai-overview-panel")
assert overview.get("aria-labelledby") == "browseOverviewTitle"
assert overview.select_one("h2#browseOverviewTitle") is not None
status = overview.select_one("[data-overview-status]")
assert status.get("aria-live") == "polite"
assert status.get("aria-busy") in {"true", "false"}
action = overview.select_one("button[data-overview-action]")
if action:
    assert action.get("type") == "button"
```

Add CSS assertions that `.ai-overview-spinner` exists and an exact `@media (prefers-reduced-motion: reduce)` rule sets `animation: none` for it. Retain existing light/dark `.ai-overview-panel` selectors.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "overview and (restore or access or motion)"
```

Expected: failures because successful overview state is neither serialized nor restored and spinner motion has no override.

- [ ] **Step 3: Persist only matching successful overview state**

Extend `getBrowseState()` with:

```javascript
overview: (
    currentOverview.status === 'success'
    && currentOverview.query === lastSearchQuery
    && currentOverview.text
)
    ? { query: currentOverview.query, text: currentOverview.text }
    : null,
```

In `restoreBrowseState()`, after `lastSearchQuery` and normalized results are established, validate the optional field:

```javascript
const storedOverview = state.overview;
const restoredOverviewQuery = typeof storedOverview?.query === 'string'
    ? storedOverview.query.trim()
    : '';
const restoredOverviewText = typeof storedOverview?.text === 'string'
    ? storedOverview.text.trim()
    : '';
const hasMatchingOverview = (
    restoredOverviewQuery === restoredQuery
    && restoredOverviewText.length > 0
    && restoredOverviewText.length <= SUMMARY_TEXT_LIMIT
);
currentOverview = hasMatchingOverview
    ? overviewState('success', restoredQuery, restoredOverviewText)
    : overviewState('idle', restoredQuery);
```

Keep `restoreBrowseState()` free of `loadSearchSummary()` calls. Existing saved states therefore restore without an unexpected hosted request.

- [ ] **Step 4: Add reduced-motion-safe spinner styling**

Add beside existing Browse overview styles:

```css
.ai-overview-spinner {
    animation-duration: 0.9s;
    border-width: 0.12em;
    color: currentColor;
    flex: 0 0 auto;
    height: 1rem;
    width: 1rem;
}

@media (prefers-reduced-motion: reduce) {
    .ai-overview-spinner {
        animation: none;
    }
}
```

Do not add new light/dark colors. Spinner inherits the existing panel body color, preserving both theme specifications.

- [ ] **Step 5: Run persistence, theme, route, and regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py tests/test_light_theme_contract.py -q -k "overview or browse"
.\.venv\Scripts\python.exe -m pytest tests/test_ai.py tests/test_summarise.py -q
node --check static/js/browse-summary.js
node --check static/js/pages/browse.js
git diff --check
```

Expected: overview restoration/accessibility/motion contracts pass; all Browse theme contracts pass; existing hosted summary route and fallback contracts pass unchanged.

- [ ] **Step 6: Commit Task 2**

```powershell
git add -- static/js/pages/browse.js static/css/custom.css tests/test_dark_theme_contract.py tests/test_light_theme_contract.py
git commit -m "feat: persist Browse AI overview"
```

---

## Final verification

- [ ] Run the complete suite with `.env` loading disabled so local credentials cannot alter expected missing-key contracts:

```powershell
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['-q']))"
```

- [ ] Run JavaScript syntax and diff checks:

```powershell
node --check static/js/browse-summary.js
node --check static/js/pages/browse.js
node --check static/js/card.js
node --check static/js/viewer.js
git diff --check
```

- [ ] Run authenticated live-browser QA in both themes:

```text
1. Search a query with at least Wikipedia, Google Books, and Google Scholar selected.
2. Confirm result cards appear before the overview completes.
3. Confirm AI Overview and Search sources coexist in the left sidebar.
4. Click Load More and change sorting; confirm overview text and request count do not change.
5. Start a second query before the first overview returns; confirm only the second overview appears.
6. Simulate or block the summary request; confirm safe error, Retry, recovery, and no popup.
7. Reload after success; confirm stored overview restores without another request.
8. Verify narrow laptop height, 390 x 844 mobile, light mode, dark mode, keyboard Retry, and reduced-motion rendering.
```

- [ ] Dispatch task reviews after each task and one final adversarial review across `static/js/browse-summary.js`, Browse search generations, localStorage restoration, theme CSS, and runtime tests. Fix every Critical or Important finding and re-review until PASS.

- [ ] Push only after fresh full verification and final review pass. Do not stage or alter root `wmremove-transformed (2) (1).svg`, `tilixia-summer-bible-3417.gif`, or `tilixia-summer-book-2478.gif`.
