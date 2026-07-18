# Browse AI Overview Design

Date: 2026-07-19
Status: Approved direction; awaiting written-spec review

## Goal

Replace the Browse sidebar placeholder with a useful summary of the accepted search results. The overview must appear automatically after a successful search, while the existing Search sources card remains visible below it.

This restores the useful flow previously present in commit `05a494c`, without restoring its stale-response race, generic permanent error, or legacy search implementation.

## Chosen approach

Use the existing hosted summarisation route, `POST /api/browse/summary`, after a successful SerpAPI Browse search. Render the summary in a dedicated AI Overview card above the Search sources card.

Three approaches were considered:

1. **Automatic overview after each accepted search — selected.** Closest to the earlier behaviour and requires no extra user action. One hosted request is made per completed search.
2. **Manual Generate button only.** Saves API calls but leaves the prominent panel empty until clicked and does not match the requested earlier behaviour.
3. **Regenerate after every Load More or sort action.** Keeps wording aligned with every visible rank, but creates unnecessary provider calls and more race conditions. The overview is about the search and selected sources, so lower-rank reveal does not justify regeneration.

No visual companion is needed because both theme specifications already define the AI Overview panel and the existing sidebar fixes its position, typography, and material treatment.

## User experience

The left Browse sidebar contains two independent cards after a successful search:

1. **AI Overview**
2. **Search sources**

The overview has four explicit states:

- **Idle:** Before the first search, explain that an overview will appear after searching.
- **Loading:** After results render, show `Creating overview…`, a restrained activity indicator, and `aria-busy="true"`. Results remain usable while this runs.
- **Success:** Show the returned two-to-three-sentence summary as plain escaped text.
- **Error:** Show the server's safe public error message and a Retry button. Missing `ANTHROPIC_API_KEY` therefore produces the existing configuration message; provider failures can still use the existing server-side extractive fallback when usable snippets exist.

If a search has no results, do not call the summary endpoint. Show `No overview is available because this search returned no results.`

Retry uses the current accepted query and result snapshot. It is disabled while the request is active.

## Data flow

1. User submits a valid Browse search.
2. Existing source-readiness and SerpAPI search flow completes.
3. Browse accepts the response, updates ranked groups, renders initial rank-one cards, and renders Search sources.
4. Browse creates a summary snapshot containing the accepted query and bounded top-ranked results.
5. Browse renders the loading overview, then posts the snapshot to `/api/browse/summary`.
6. The route returns the existing structured `{status, summary/error}` response.
7. Only the request still owned by the current search generation may update the overview.

The summary snapshot contains only fields needed by the current summariser: title, description, source name, source URL, and whitelist rank. It includes at most ten top-ranked, source-diverse results. It never includes credentials, API keys, workspace data, hidden provider metadata, or all lower-ranked buffered results.

Browse remains SerpAPI-only. Summary generation does not perform another search and does not call Wikipedia, Google Books, Scholar, PubMed, or whitelist-domain APIs.

## Request ownership and races

Summary state belongs to the accepted Browse search generation.

- Starting a newer valid search aborts or invalidates the older summary request.
- A late response from an older query cannot replace the current overview.
- An invalid source selection cannot orphan a loading overview or destroy a still-current one.
- Load More, sorting, card image fallback, and Google Books viewer activity do not regenerate or overwrite the overview.
- Retry is generation-bound and cannot revive an outdated query.

The summary request is non-blocking. Search results display as soon as the SerpAPI response is accepted.

## Persistence and restoration

Persist only a successful summary with the matching query in the existing Browse state. Do not persist loading or error states.

- Restoring a matching successful summary displays it without a new provider request.
- Legacy saved state without a summary displays a `Generate overview` action rather than an endless loading message or an automatic request during page boot.
- A new accepted search clears the restored summary before generating its own.

The addition is optional and backward-compatible with existing version-2 Browse state. No database or local-storage migration is required.

## Rendering and accessibility

- Preserve the existing `.surface-leather.ai-overview-panel` theme contract in light and dark modes.
- Keep Search sources as a separate `.source-summary-panel` below it.
- Summary content is inserted as text, never trusted HTML.
- Use a stable heading and a polite live region for loading, success, and error status.
- Keep focus on the user's current control; do not force focus into the panel.
- Retry and Generate overview are real buttons with clear disabled states.
- Respect reduced-motion preferences for any activity indicator.
- Preserve narrow-screen stacking and sidebar scrolling without adding horizontal overflow.

## Error handling and privacy

- Display only the existing structured public error returned by the route.
- Keep provider exception details in private server logs.
- Network failure, invalid JSON, and non-success HTTP responses enter the same recoverable error state.
- Do not expose the Anthropic API key or model configuration to the browser.
- Do not add a local model or local-AI fallback.
- The existing deterministic snippet fallback is allowed because it is not a model and uses only already-returned result descriptions.

## Testing

Add focused contracts for:

- automatic request after accepted search results render;
- overview and Search sources cards coexisting;
- bounded source-diverse request payload;
- loading, success, missing-configuration, provider/network failure, and Retry states;
- summary text escaping;
- stale query A response being unable to overwrite query B;
- Load More and sorting not generating extra summaries;
- no-results path making no summary request;
- successful summary persistence and restoration;
- legacy restored state offering Generate overview instead of hanging;
- reduced-motion and responsive theme contracts;
- Phase 1 ranked reveal, Phase 2 filters, image fallback, and Google Books viewer behavior remaining unchanged.

Run the focused frontend/runtime contracts, AI/summarise route tests, light and dark theme suites, JavaScript syntax checks, full dotenv-disabled pytest suite, and `git diff --check`.

## Out of scope

- Per-result or per-source summary controls.
- Regeneration on Load More or sorting.
- Assessment-task input in Browse.
- Streaming model output.
- New AI providers, local models, or API-key endpoints.
- Changes to SerpAPI search, ranking, filters, result imagery, or Google Books rendering.

## Success criteria

- Every successful new Browse search shows a useful overview above Search sources.
- Search results never wait for summary generation.
- Older requests cannot corrupt the current query's panel.
- Failure is understandable and retryable, with no endless placeholder or spinner.
- Existing Browse, theme, security, and viewer contracts remain green.
