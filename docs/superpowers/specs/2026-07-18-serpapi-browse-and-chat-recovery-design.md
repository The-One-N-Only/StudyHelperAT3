# StudyLib SerpAPI Browse and Chat Recovery Design

**Approved direction:** 2026-07-18
**Applies to:** Browse search, Home-to-Browse search handoff, native source viewing, and Alexander workspace chat retention

## Goals

- Route every search initiated by Browse through SerpAPI, including Wikipedia, Google Books, Google Scholar, PubMed, and every checked whitelist domain.
- Remove Google Programmable Search Element and Google Custom Search JSON API from StudyLib.
- Make Home search populate and automatically execute the native Browse search.
- Bound browser search requests and show clear configuration/provider errors instead of an endless spinner or silent empty result set.
- Persist successful Alexander conversations per workspace and expose a clear unavailable state when Anthropic is not configured.
- Preserve the current grouped results, deduplication, Load More behavior, filters dropdown defaults, and embedded source viewers.

## Non-goals

- Do not route Alexander's separate context gathering through Browse or SerpAPI.
- Do not replace Google Books Embedded Viewer, Wikipedia proxy viewing, or other non-search rendering paths.
- Do not redesign Browse or Workspace.
- Do not add a second search provider or silently fall back when SerpAPI fails.
- Do not add browser-side API keys.

## Approaches considered

1. **One SerpAPI domain-scoped query per selected source — selected.** Keeps existing source groups and checkbox behavior. Every query uses SerpAPI with `site:` scope and every returned URL still passes `whitelist.is_allowed`.
2. **One combined `OR site:` query for the whole page.** Uses fewer requests but makes source grouping, per-source counts, and balanced Load More unreliable.
3. **SerpAPI with provider-specific fallback.** Preserves some results during an outage but violates the requirement that Browse never use individual domain APIs or Google Custom Search.

## 1. SerpAPI-only Browse backend

`src/search.py` owns a single Browse search entry point:

```python
browse_serpapi_search(query, num_results, source, filters, *, user_id) -> list[dict]
```

Dedicated source IDs map to these approved scopes:

- `wikipedia` -> `site:en.wikipedia.org`
- `gbooks` -> `site:books.google.com`
- `scholar` -> `site:scholar.google.com`
- `pubmed` -> `site:pubmed.ncbi.nlm.nih.gov`
- `whitelist_<domain>` -> that exact approved domain pattern
- `whitelist` -> the combined scope produced by `whitelist.get_whitelist_search_scope()`

The function calls SerpAPI's Google Search endpoint with server-side `SERP_API_KEY`, `engine=google`, the scoped query, and ten-result pagination using `start`. It reads `organic_results[*].title`, `link`, and `snippet`. Every link must pass `whitelist.is_allowed`; provider data remains untrusted. Result `source_name` is stable for dedicated sources so existing groups and viewers continue to work.

Year and content-type filters become search terms in the SerpAPI query. Sorting remains client-side. No Browse route may call `search.wikipedia`, `search.gbooks`, `search.google_scholar`, or `pubmed.search`.

Remove `_google_custom_search_items`, Google Custom Search fallback branches, `GOOGLE_SEARCH_API_KEY`, and `GOOGLE_SEARCH_ENGINE_ID`. Keep `GOOGLE_BOOKS_API_KEY` and `PUBMED_API_KEY` because Alexander's separate context gathering may still use those provider APIs.

## 2. Search errors and timeout

Missing `SERP_API_KEY` returns HTTP 503 with:

```json
{"status": false, "error": "Browse search is not configured. Add SERP_API_KEY and restart StudyLib."}
```

SerpAPI HTTP errors, error payloads, invalid response shapes, and request exceptions are logged privately. If every requested source fails, `/api/browse/search-all` returns HTTP 502 with a stable provider error. If only some sources fail, successful groups are returned with `source_errors`; Browse shows one warning while rendering available results.

Browser search and Load More requests share an `AbortController` timeout. Timeout and structured server errors clear loading state, retain the current retryable query, and show the server's safe message. No failure silently falls back to another provider.

## 3. Home handoff and PSE removal

Home continues navigating to `/browse?q=<encoded query>`. Browse reads `q` after whitelist checkboxes finish loading, restores compatible saved state, puts the URL query into `#searchInput`, and calls the native `performSearch()` once. User-entered Browse searches update the URL query with `history.replaceState`.

Remove `googleCseContainer`, `ensureGoogleCustomSearch`, the `cse.google.com` script, all CSE-specific CSS, and tests that require vendor CSE markup. Add tests that reject any remaining PSE or Google Custom Search surface.

## 4. Native viewers with SerpAPI results

Search transport changes only. Cards still call the existing StudyLib viewer.

Google Books SerpAPI results do not carry Books REST `accessInfo`. The viewer extracts a volume ID from the result URL's `id` query parameter, or uses a non-URL `source_id` when present. It attempts the official Google Books Embedded Viewer unless preview metadata explicitly says embedding is unavailable. Loader failure or rejected volume falls back inside the sidebar; it never forces a popup.

Wikipedia and other allowed pages continue through the existing safe proxy/iframe path.

## 5. Persistent workspace chat

Add a `workspace_chat_messages` SQLite model with `user_id`, `workspace_id`, `role`, `content`, and creation time. Successful user/assistant turns are stored together and returned oldest-first. Workspace deletion removes its chat rows.

`GET /api/workspaces/<workspace_id>/chat` verifies ownership and returns saved messages plus an `ai_configured` boolean. `/api/answer/chat` accepts `workspace_id`, verifies ownership, calls hosted Anthropic, and persists the latest successful turn. Calls without `workspace_id` retain the existing non-persistent API contract for compatibility.

Workspace initialization loads saved messages, maps `assistant` to the Alexander bubble, and seeds `StudyHelperAI.conversationHistory`. Chat state is per workspace instead of one page-global conversation. When Anthropic is not configured, saved history remains readable but input and Send are disabled with the existing safe configuration message.

## Security and privacy

- API keys remain server-side and never enter HTML, JavaScript, logs, or API responses.
- SerpAPI/provider exception detail is logged only on the server.
- Every SerpAPI URL passes the existing HTTP(S) whitelist validator.
- Chat routes verify both authenticated user and workspace ownership.
- Chat content is rendered through existing escaping; no new HTML interpolation is allowed.

## Verification

- RED/GREEN Python tests prove every Browse source calls SerpAPI and no Browse route calls individual provider APIs.
- Tests cover missing key, partial failure, total failure, pagination, filters, and whitelist enforcement.
- Runtime JavaScript tests prove Home query auto-search, PSE absence, URL synchronization, timeout recovery, partial results, and grouped Load More behavior.
- Viewer tests prove a SerpAPI Google Books URL produces the correct embedded volume ID and still uses safe sidebar fallback.
- DB/API/runtime tests prove per-workspace chat persistence, ownership, reload restoration, and disabled missing-key state.
- Run focused suites, then the full collected suite, JavaScript syntax checks, and a repository search for forbidden PSE/Google Custom Search symbols.

## Acceptance criteria

- Every Browse result request reaches SerpAPI or returns a clear SerpAPI configuration/provider error.
- No Browse search calls Wikipedia, Google Books REST, PubMed, Google Scholar, Google Custom Search, or PSE.
- Home search executes in native Browse with the requested query.
- Search never leaves an unbounded spinner.
- Google Books still attempts embedded rendering from SerpAPI result URLs.
- Successful Alexander conversations survive reload and stay isolated by workspace.
- Existing grouped paging, deduplication, default source checks, light/dark visuals, and safe viewer behavior remain intact.
