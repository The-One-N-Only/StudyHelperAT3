# Google Books Preview Phase 4 Implementation Plan

> **Required execution:** Use subagent-driven development with TDD, task review, fix loop, final broad review, and fresh verification.

**Goal:** Make native Google Books previews render reliably when Google's legacy ready callback is missing, retry after loader failures, and reach a clear inline fallback within a measured 12-second budget.

**Architecture:** Keep the official Embedded Viewer API and current inline offcanvas. Harden only the shared API-loader state machine: official callback plus bounded `DefaultViewer` readiness polling, deterministic cleanup, retryable rejected state, and the measured production timeout. Do not add a Google Books search API or expose any key.

**Measured basis:** Official scripts loaded successfully; `DefaultViewer` became ready in 0.863 seconds. Four embeddable volumes reached official success callbacks in 1.513–3.724 seconds once the viewer constructor was ready. Production timeout: 12,000 ms. API readiness watchdog: 10,000 ms. Poll interval: 50 ms.

**Stack:** Vanilla ES modules, Google Books Embedded Viewer API, Bootstrap offcanvas, pytest Node runtime harness.

---

## Task 1: Repair Google Books API readiness and timeout behavior

**Files:**

- Modify: `static/js/viewer.js`
- Modify: `tests/test_dark_theme_contract.py`
- Modify if required for responsive fallback only: `static/css/custom.css`

### Step 1: Add failing loader-readiness and retry contracts

Extend the existing Google Books viewer runtime harness; do not create another fake DOM base. Add focused scenarios proving:

- `jsapi.js` loads and `google.books.load()` runs, `setOnLoadCallback` never fires, but a later 50 ms readiness check observes `google.books.DefaultViewer`; the real viewer then loads once and renders success.
- API readiness remains pending until `DefaultViewer` exists; no premature constructor call occurs.
- A script error rejects, removes the failed loader script, clears the shared cached promise, and a second View action appends one new script and succeeds without a page reload.
- A 10-second readiness watchdog rejects and resets the shared loader when neither callback nor polling produces `DefaultViewer`.
- Concurrent View actions still share one in-flight loader; stale openings cannot render, resize, or clear the newest viewer.
- The 12-second render timeout uses safe inline metadata fallback, states `twelve seconds`, retains the external Google Books link, and never calls `window.open`.
- A success callback before 12 seconds cancels the timer and cannot later be replaced by timeout fallback.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py -q -k "google_books and (readiness or retry or timeout or success)"
```

Expected: FAIL because the current loader depends entirely on `setOnLoadCallback`, caches rejected/pending promises forever, and uses an eight-second constant/copy.

### Step 2: Implement a bounded, retryable API-loader state machine

In `static/js/viewer.js`:

- Set `GOOGLE_BOOKS_RENDER_TIMEOUT_MS = 12000`, `GOOGLE_BOOKS_API_READY_TIMEOUT_MS = 10000`, and `GOOGLE_BOOKS_API_POLL_INTERVAL_MS = 50`.
- Keep one shared in-flight `googleBooksApiPromise`.
- Resolve immediately if `window.google.books.DefaultViewer` already exists.
- After adding the official script, call `google.books.load()` and register the official on-load callback.
- Start a 50 ms readiness poll which resolves when the live `window.google.books.DefaultViewer` constructor appears, even if Google's callback never arrives.
- Start one 10-second watchdog covering script and API readiness.
- Route callback, poll, script error, initialization exception, and watchdog through idempotent settle/cleanup helpers so intervals/timeouts cannot leak or settle twice.
- On rejection, clear `googleBooksApiPromise` and remove only the failed script element when no usable constructor exists. A later call must retry cleanly.
- Preserve the working constructor, `viewer.load(volumeId, notFoundCallback, successCallback)`, resize observer, generation guards, offcanvas wait, and inline fallback.

Run the focused tests again. Expected: PASS.

### Step 3: Derive timeout copy and preserve safe fallback

- Format the timeout duration from `GOOGLE_BOOKS_RENDER_TIMEOUT_MS`; do not leave `eight seconds` as a second source of truth.
- Keep title, description, preview status, safe cover, and `Open Google Books` link inside the sidebar.
- Keep `target="_blank"` plus `rel="noopener noreferrer"`; do not open a popup programmatically.
- Ensure every success/failure/timeout path clears timers and stale state without leaking provider exception text to users.

### Step 4: Verify focused and broad viewer behavior

Run:

```powershell
node --check static/js/viewer.js
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py -q -k "google_books"
.\.venv\Scripts\python.exe -m pytest tests/test_proxy.py -q -k "google_books"
git diff --check
```

Expected: all selected tests pass.

### Step 5: Live browser verification

Use the local Browse page and the four diagnostic volume IDs. Verify:

- First cold View action reaches a visible native viewer within 12 seconds.
- Three additional warm View actions reach visible native viewers.
- Closing/reopening and switching volumes does not show stale content.
- A deliberately blocked loader reaches inline fallback rather than hanging; retry succeeds after blocking is removed.
- No forced popup occurs.

Capture measured visible-ready times and network/console state in `.superpowers/sdd/phase-4-task-1-report.md`.

### Step 6: Full verification, review, and commit

Run:

```powershell
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['-q']))"
node --check static/js/viewer.js
git diff --check
```

Self-review exact diff for loader cleanup, retry ownership, timer leaks, stale-generation safety, and scope. Commit:

```text
fix: make Google Books viewer readiness resilient
```

Then dispatch fresh spec/correctness review and fix every material finding.

---

## Phase 4 final verification

After task review passes, run fresh full-suite, JS syntax, diff, and live-browser checks. Run final whole-phase adversarial review across Phase 3 imagery and Phase 4 viewer changes before pushing.
