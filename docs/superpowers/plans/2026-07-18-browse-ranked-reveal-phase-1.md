# Browse Ranked Reveal Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch 10 results per selected Browse source once, initially display rank 1 per source, and reveal ranks 2 through 10 from the cached response without another search request.

**Architecture:** Keep `/api/browse/search-all` and its 10-result grouped response unchanged. Change only Browse client visibility and Load More behavior so every selected group is sliced by a shared visible-rank counter. Preserve existing deduplication, initial request timeout, source grouping, persistence, and initial partial-failure behavior.

**Tech Stack:** Flask, vanilla JavaScript ES modules, pytest-driven Node runtime harnesses

## Global Constraints

- Initial Browse request uses exactly `num_results: 10` for each selected source.
- Initial display shows rank 1 from every selected source group.
- Each Load More action reveals exactly one additional rank from every source group that contains that rank.
- Rank 1 plus nine Load More actions exposes at most 10 results per source.
- Load More never issues another Browse search request.
- Load More is disabled and reads `No more results.` when no source has a buffered next rank.
- Dedicated sources and `whitelist_<domain>` sources use the same paging rule.
- Preserve existing deduplication, stale initial-search protection, initial partial-source warnings, URL handling, and state restoration.
- Default checked sources remain `wikipedia`, `gbooks`, and `scholar`.
- Do not change SerpAPI backend behavior, source scopes, API keys, thumbnails, Filters layout, or Google Books timeout in Phase 1.

---

### Task 1: Reveal cached result ranks across every source

**Files:**
- Modify: `static/js/pages/browse.js:6-30, 660-710, 1024-1155`
- Test: `tests/test_dark_theme_contract.py:3490-4250, 4550-5180`

**Interfaces:**
- Consumes: `/api/browse/search-all` response fields `grouped_results`, `results`, `source_counts`, and `source_errors`
- Produces: `getVisibleResults() -> Array<object>` containing ranks `1..currentGroupPage` from every displayed source
- Produces: `hasBufferedGroupedResults() -> boolean` covering every displayed source group
- Produces: `loadMoreResults() -> Promise<void>` that mutates only cached visibility state

- [ ] **Step 1: Write failing runtime tests for the exact rank contract**

Update the Browse runtime harness so a response with two dedicated groups and one whitelist group proves:

```python
assert rendered["initialTitles"] == ["wiki-1", "book-1", "jstor-1"]
assert rendered["afterFirstLoadTitles"] == [
    "wiki-1", "wiki-2", "book-1", "book-2", "jstor-1", "jstor-2"
]
assert rendered["afterNinthLoadCounts"] == {
    "wikipedia": 10,
    "gbooks": 10,
    "whitelist_www.jstor.org": 10,
}
assert rendered["requestSizes"] == [10]
assert rendered["loadMoreDisabled"] is True
assert rendered["loadMoreText"] == "No more results."
```

Add an uneven-group assertion proving an exhausted short group does not block later ranks from longer groups:

```python
assert rendered["unevenAfterSecondLoadTitles"] == [
    "wiki-1", "wiki-2", "wiki-3", "book-1"
]
```

Replace cumulative-window assertions that require request sizes `20` or `30`. Retain initial partial-failure, deduplication, stale initial-search, and restored-state coverage. Remove only runtime scenarios whose sole contract was network fetching during Load More.

- [ ] **Step 2: Run focused tests and capture RED evidence**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['tests/test_dark_theme_contract.py', '-q', '-k', 'browse and (pagination or grouped or load_more)']))"
```

Expected: FAIL because dedicated groups currently expose all 10 results and Load More requests `num_results: 20`.

- [ ] **Step 3: Apply one shared rank slice to every displayed source**

In `static/js/pages/browse.js`, keep one result per rank and remove the whitelist-only condition:

```javascript
const RESULTS_PER_SOURCE_PER_RANK = 1;

function getVisibleResults() {
    const visible = [];
    const visibleCount = RESULTS_PER_SOURCE_PER_RANK * currentGroupPage;
    sourcesToDisplay().forEach((source) => {
        visible.push(...(currentGroupedResults[source] || []).slice(0, visibleCount));
    });
    return deduplicateResults(visible);
}

function hasBufferedGroupedResults() {
    const visibleCount = RESULTS_PER_SOURCE_PER_RANK * currentGroupPage;
    return sourcesToDisplay().some((source) => (
        (currentGroupedResults[source] || []).length > visibleCount
    ));
}
```

Keep names consistent throughout the module. A clearer rename of `hasBufferedGroupedResults` is allowed only if every call site and test harness extraction is updated in the same task.

- [ ] **Step 4: Make Load More reveal cached ranks only**

Replace cumulative search-window logic with cached visibility mutation:

```javascript
async function loadMoreResults() {
    if (
        isInitialSearchPending
        || isLoadingMore
        || !lastSearchQuery
        || !lastSearchSources
        || !hasBufferedGroupedResults()
    ) {
        return;
    }

    currentGroupPage += 1;
    saveBrowseState();
    renderCurrentResults();
}
```

In `renderResults()`, derive unavailable state directly from the cache:

```javascript
const loadMoreUnavailable = !hasBufferedGroupedResults();
```

Delete only now-dead cumulative Load More fetch code. Keep the initial `fetchBrowseResults()` call, its 30-second browser timeout, generation guard, partial-source warning, and safe errors unchanged. Remove state variables only when they become entirely unused; if compatibility fields remain in stored state, keep them fixed at their existing safe defaults.

- [ ] **Step 5: Run focused tests and capture GREEN evidence**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['tests/test_dark_theme_contract.py', '-q', '-k', 'browse']))"
```

Expected: all selected Browse contract tests PASS.

- [ ] **Step 6: Verify JavaScript syntax and full regression suite**

Run:

```powershell
node --check static/js/pages/browse.js
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['-q']))"
```

Expected: syntax check exits 0 and 296 or more tests PASS with no failures.

- [ ] **Step 7: Commit and self-review**

```powershell
git add static/js/pages/browse.js tests/test_dark_theme_contract.py
git commit -m "fix: reveal Browse results by source rank"
```

Self-review the commit for Phase 1 scope, exact request count, uneven groups, restored state, and obsolete cumulative-fetch test assumptions. Write RED and GREEN evidence into the assigned report file.
