# StudyLib SerpAPI Browse and Chat Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Browse search use SerpAPI, restore Home-to-Browse native search, remove PSE/Google Custom Search, bound failures, and persist Alexander chat per workspace.

**Architecture:** Keep Flask, SQLAlchemy, and vanilla ES modules. Add one source-to-domain SerpAPI adapter used by both Browse endpoints; retain provider-specific functions only for non-Browse AI context. Keep existing cards/grouping/viewers, enrich viewer behavior from Serp result URLs, and add one workspace-owned chat table plus API.

**Tech Stack:** Python 3, Flask, SQLAlchemy/SQLite, requests, vanilla JavaScript ES modules, Bootstrap 5.3.3, pytest, Node runtime harnesses, SerpAPI, Anthropic SDK, Google Books Embedded Viewer API.

**Approved design:** `docs/superpowers/specs/2026-07-18-serpapi-browse-and-chat-recovery-design.md`

## Global Constraints

- Use RED/GREEN TDD for every behavior change.
- Every Browse source and filter search uses SerpAPI only; no Browse fallback to Wikipedia, Google Books REST, PubMed, Google Scholar, Google Custom Search, or PSE.
- Keep `SERP_API_KEY` server-side. Missing key and provider failures return stable non-secret errors.
- Every SerpAPI result URL must pass `whitelist.is_allowed`.
- Preserve source groups, deduplication, cumulative Load More, source defaults, client sorting, and existing safe DOM construction.
- Keep Google Books Embedded Viewer and other viewer transports; those are rendering, not search.
- Persist successful chat turns per authenticated user and workspace; reject cross-user workspace access.
- Keep changes within existing coarse files; do not introduce a provider framework, frontend framework, or unrelated redesign.

---

### Task 1: Route both Browse APIs exclusively through SerpAPI

**Files:**

- Modify: `src/search.py`
- Modify: `app.py`
- Modify: `.env.example`
- Modify: `tests/test_search.py`
- Modify: `tests/test_ai.py`

**Interfaces:**

```python
class SerpApiConfigurationError(RuntimeError):
    pass

class SerpApiProviderError(RuntimeError):
    pass

BROWSE_SOURCE_DOMAINS = {
    "wikipedia": ("en.wikipedia.org", "wikipedia"),
    "gbooks": ("books.google.com", "gbooks"),
    "scholar": ("scholar.google.com", "scholar"),
    "pubmed": ("pubmed.ncbi.nlm.nih.gov", "pubmed"),
}

def browse_serpapi_search(query, num_results, source, filters, *, user_id):
    """Return whitelisted SerpAPI results for one Browse source group."""
```

- [ ] Add parametrized tests proving `wikipedia`, `gbooks`, `scholar`, and `pubmed` each call `https://serpapi.com/search` with `engine=google`, `api_key`, and the correct `site:` query. Assert persistence receives the stable source name and no provider-specific function is called.

- [ ] Add tests for `whitelist_<domain>` and generic `whitelist`; assert disallowed links are discarded and explicit domain scope matches `site:<domain>`.

- [ ] Add tests for ten-result `start` pagination, year/content-type query terms, malformed `organic_results`, provider `error` payloads, non-200 responses, and missing key.

- [ ] Add endpoint tests that monkeypatch every individual provider function to raise, call `/api/browse/search` and `/api/browse/search-all`, and prove only `browse_serpapi_search` is used.

- [ ] Add endpoint tests for exact missing-key HTTP 503, total-provider-failure HTTP 502, and partial success with `source_errors` plus successful grouped results.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_search.py
```

- [ ] Implement source scope and filter query helpers. Use this request contract:

```python
params = {
    "q": scoped_query,
    "num": min(10, remaining),
    "start": start,
    "api_key": SERP_API_KEY,
    "engine": "google",
}
response = requests.get(
    "https://serpapi.com/search",
    params=params,
    headers={"User-Agent": USER_AGENT},
    timeout=10,
)
```

- [ ] Raise `SerpApiConfigurationError` before network/DB work when the key is missing. Log provider detail in `src/search.py`, then raise `SerpApiProviderError` with no secret detail.

- [ ] Replace provider dispatch in both Browse routes with `browse_serpapi_search`. Keep per-source parallelism, but do not use a context-manager shutdown that blocks the response after timeout. Return partial results when at least one source succeeds.

- [ ] Delete `_google_custom_search_items`, `google_scholar`, Google Custom Search fallback branches/constants/tests, and remove `GOOGLE_SEARCH_API_KEY` plus `GOOGLE_SEARCH_ENGINE_ID` from `.env.example` and its contract test. Retain non-Browse `wikipedia`, `gbooks`, and PubMed functions.

- [ ] Run GREEN:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_search.py tests/test_ai.py
rg -n "GOOGLE_SEARCH_API_KEY|GOOGLE_SEARCH_ENGINE_ID|_google_custom_search_items|google_scholar" app.py src .env.example tests
```

- [ ] Commit:

```powershell
git add app.py src/search.py .env.example tests/test_search.py tests/test_ai.py
git commit -m "fix: route Browse through SerpAPI"
```

---

### Task 2: Restore native Browse handoff, remove PSE, and bound browser requests

**Files:**

- Modify: `static/js/pages/browse.js`
- Modify: `static/js/viewer.js`
- Modify: `static/css/custom.css`
- Modify: `tests/test_dark_theme_contract.py`
- Modify: `tests/test_light_theme_contract.py`

**Interfaces:**

```javascript
const BROWSE_REQUEST_TIMEOUT_MS = 30000;

function getInitialBrowseQuery() {
    const params = new URLSearchParams(window.location.search);
    return (params.get('q') || params.get('query') || '').trim();
}

async function fetchBrowseResults(payload) {
    // POST /api/browse/search-all with AbortController and safe JSON errors.
}

function googleBooksVolumeId(item) {
    // Return non-URL source_id or books.google.com URL id query parameter.
}
```

- [ ] Replace tests that require `googleCseContainer`/Google CSE CSS with tests rejecting `cse.google.com`, `google-cse-script`, `ensureGoogleCustomSearch`, `googleCseContainer`, and `.gsc-*` selectors.

- [ ] Add a Browse runtime test with `window.location.search = '?q=quantum%20mechanics'`. Resolve whitelist loading, then assert one native `/api/browse/search-all` call and input value `quantum mechanics`.

- [ ] Add runtime tests proving manual search updates `q`, a structured 503 message reaches the toast, AbortController timeout clears the spinner/loading state, and partial results render alongside one warning.

- [ ] Add viewer tests where a SerpAPI result has `source_id` equal to its full Google Books URL and no `accessInfo`. Assert viewer loads only the extracted `id` value. Preserve explicit `embeddable: false` fallback.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "browse or google_books"
.\.venv\Scripts\python.exe -m pytest -q tests/test_light_theme_contract.py -k "browse or cse"
```

- [ ] Remove PSE markup/loader from `browse.js` and all CSE-specific blocks from `custom.css`.

- [ ] Restore URL-query initialization after whitelist checkbox rendering. URL query wins over saved query and executes once. Manual native searches call `history.replaceState`.

- [ ] Route initial and Load More calls through `fetchBrowseResults`. Abort after 30 seconds, parse safe server errors, keep old results on Load More failure, and always re-enable sorting/loading controls.

- [ ] Add `googleBooksVolumeId` in `viewer.js`. Attempt embedding when metadata is absent; only short-circuit when `embeddable === false`.

- [ ] Run GREEN and syntax checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_dark_theme_contract.py -k "browse or google_books"
.\.venv\Scripts\python.exe -m pytest -q tests/test_light_theme_contract.py -k "browse or cse"
Get-Content -Raw static\js\pages\browse.js | node --input-type=module --check -
Get-Content -Raw static\js\viewer.js | node --input-type=module --check -
rg -n -i "googleCse|google-cse|cse\.google|\.gsc-" static tests
```

- [ ] Commit:

```powershell
git add static/js/pages/browse.js static/js/viewer.js static/css/custom.css tests/test_dark_theme_contract.py tests/test_light_theme_contract.py
git commit -m "fix: restore native Browse search flow"
```

---

### Task 3: Persist Alexander chat per workspace

**Files:**

- Modify: `src/db.py`
- Modify: `app.py`
- Modify: `static/js/ai-prompt.js`
- Modify: `static/js/pages/workspace.js`
- Modify: `tests/test_ai.py`

**Interfaces:**

```python
class WorkspaceChatMessage(Base):
    __tablename__ = "workspace_chat_messages"

def get_workspace_chat_messages(workspace_id: int, user_id: int) -> list[dict]:
    """Return oldest-first user/assistant messages for an owned workspace."""

def append_workspace_chat_turn(
    user_id: int,
    workspace_id: int,
    user_content: str,
    assistant_content: str,
) -> None:
    """Persist one successful pair atomically."""
```

```javascript
studyHelperAI.setConversationHistory(messages);
studyHelperAI.chat(userMessage, { workspaceId: currentWorkspaceId });
```

- [ ] Add temporary-SQLite tests proving two-message atomic insertion, oldest-first retrieval, user/workspace isolation, and workspace deletion cleanup.

- [ ] Add Flask route tests for unauthenticated access, wrong-owner 404, saved chat GET shape, `ai_configured`, successful turn persistence, provider failure without persistence, and compatibility when `workspace_id` is omitted.

- [ ] Extend workspace Node harness: initial API data restores bubbles/history for only current workspace; send includes `workspace_id`; missing AI configuration disables input/Send while leaving saved messages readable.

- [ ] Run RED:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai.py
```

- [ ] Add `WorkspaceChatMessage`, relationships, DB functions, and deletion cleanup in `src/db.py`. `Base.metadata.create_all` creates the table for new and existing SQLite files.

- [ ] Add `GET /api/workspaces/<int:workspace_id>/chat`. Update `/api/answer/chat` to validate optional workspace ownership and persist only successful latest user/assistant turns.

- [ ] Add `setConversationHistory` to `StudyHelperAI`; include `workspace_id` only when supplied. Load chat alongside workspace details, map `assistant` to the Alexander UI role, and disable unavailable chat controls with the safe configuration message.

- [ ] Run GREEN and syntax checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai.py
Get-Content -Raw static\js\ai-prompt.js | node --input-type=module --check -
Get-Content -Raw static\js\pages\workspace.js | node --input-type=module --check -
```

- [ ] Commit:

```powershell
git add src/db.py app.py static/js/ai-prompt.js static/js/pages/workspace.js tests/test_ai.py
git commit -m "feat: persist workspace chat"
```

---

### Task 4: Final regression and forbidden-path verification

**Files:**

- Modify only if verification exposes a scoped regression.

- [ ] Run all tests through completion and record exact count:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] Run JavaScript syntax checks and forbidden-path scan:

```powershell
Get-Content -Raw static\js\pages\browse.js | node --input-type=module --check -
Get-Content -Raw static\js\viewer.js | node --input-type=module --check -
Get-Content -Raw static\js\ai-prompt.js | node --input-type=module --check -
Get-Content -Raw static\js\pages\workspace.js | node --input-type=module --check -
rg -n -i "googleCse|google-cse|cse\.google|GOOGLE_SEARCH_API_KEY|GOOGLE_SEARCH_ENGINE_ID|_google_custom_search_items|google_scholar" app.py src static .env.example tests
```

- [ ] Inspect `git diff --check`, branch status, commit history, and changed-line count. Confirm no secret values or unrelated files entered the diff.

- [ ] Start StudyLib with a configured test environment when credentials are available. Verify Home query handoff, default sources, one explicit whitelist source, timeout/error copy, Google Books sidebar attempt/fallback, chat reload, and workspace isolation. If credentials remain unavailable, report that live-provider gap without weakening automated verification.

- [ ] Commit any scoped verification fixes, then push `codex/serpapi-browse-search` and open a pull request only after fresh verification succeeds.
