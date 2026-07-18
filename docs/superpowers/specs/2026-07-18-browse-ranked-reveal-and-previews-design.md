# StudyLib Browse Ranked Reveal and Preview Design

**Approved direction:** 2026-07-18
**Applies to:** Browse result paging, Filters usability, result imagery, and Google Books preview timing

## Goal

Make Browse show one ranked result from every selected source at a time while keeping the next nine ranks buffered. Improve filter access, result imagery, and Google Books preview reliability in later phases.

## Phase 1: Ranked result reveal

- Browse requests exactly 10 results per selected source when a search starts.
- Initial display shows rank 1 from each selected source group.
- Each Load More action reveals one additional rank from every source group that has that rank.
- Nine successful Load More actions can reveal ranks 2 through 10. Rank 1 plus those nine actions produces at most 10 visible results per source.
- Load More never sends another search request. It reads only from the initial buffered response.
- Load More becomes disabled and reads `No more results.` when no selected source has a buffered next rank.
- Dedicated sources and explicit whitelist-domain sources follow identical paging rules.
- Result order inside each source group remains SerpAPI rank order. Existing global client-side sorting may reorder only the currently visible set.
- Existing result identity deduplication, stale initial-search protection, partial initial-source warnings, URL query handling, and state restoration remain intact.
- Default checked sources remain Wikipedia, Google Books, and Google Scholar. PubMed and other whitelist sources remain unchecked.

## Phase 2: Filters accessibility

- Filters menu receives a viewport-bounded maximum height and its own vertical scrolling.
- A master source checkbox appears above all source options.
- Master checkbox selects or clears dedicated and dynamic whitelist source checkboxes.
- Master checkbox is checked when every source is checked, unchecked when none are checked, and indeterminate when selection is partial.
- Source selection remains keyboard accessible and persists through existing Browse state.

## Phase 3: Result imagery

- Remove reliance on the missing `/static/img/placeholder.png` asset.
- Google Books results use an official Google Books cover URL derived from the volume ID when available.
- Safe HTTPS thumbnail or favicon metadata supplied by SerpAPI may be used after host validation.
- When no safe remote image exists, render a local source-appropriate StudyLib illustration instead of a broken image.
- Browse search remains SerpAPI-only. No Wikipedia, Google Books, PubMed, or Scholar search API is added for image lookup.
- Remote images use lazy loading, no-referrer behavior, and an error fallback.

### Phase 3 visual states

- The supplied scholar-at-desk SVG replaces the mortarboard in the initial Browse empty state.
- The SVG is decorative and rendered as a CSS mask: slightly darker than the light parchment surface and slightly lighter than the dark archive surface, producing an engraved effect without reducing heading contrast.
- The supplied `tilixia-summer-bible-3417.gif` is the main Browse search animation. It appears as soon as a valid search starts, including while Browse waits for whitelist source readiness, and remains until results or a terminal error replace it.
- The loader wrapper uses the active Browse surface colour. Its image uses `mix-blend-mode: multiply` so the GIF paper blends into both themes instead of showing a pale square.
- Loader markup exposes a live `Searching...` status. The artwork itself is decorative.
- Reduced-motion users receive a still frame extracted from the Bible animation instead of the animated GIF.
- The Bible asset is resized for its rendered dimensions before being committed; animation duration and meaningful frames remain intact.
- The supplied `tilixia-summer-book-2478.gif` remains reserved and is not bundled until a separate product state is assigned to it.

### Phase 3 result-image resolution

- Google Books cover derivation has first priority when a valid Google Books volume ID is present in the result URL or source ID.
- Otherwise, SerpAPI `thumbnail` and then `favicon` metadata may be used only when the URL is HTTPS, has no credentials or non-standard port, and its host is either an approved source host or exactly/subdomain of `serpapi.com`, `gstatic.com`, `googleusercontent.com`, `books.google.com`, or `wikimedia.org`.
- No result-image URL is fetched server-side. The browser loads approved remote images with `loading="lazy"`, `decoding="async"`, and `referrerpolicy="no-referrer"`.
- Broken remote images switch once to a local illustration selected by source category. Google Books uses the open-book illustration, Wikipedia uses the scrollwork illustration, Scholar and PubMed use the stacked-books illustration, and other whitelist sources use the compass illustration.
- Client-created and Jinja-rendered result cards follow the same URL, fallback, accessibility, and error behavior.

## Phase 4: Google Books preview timing

- Run a temporary diagnostic build with the viewer timeout disabled.
- Test at least three Google Books volumes reported as embeddable.
- Record time from View activation to the official success or failure callback.
- Set the production timeout above the slowest normal successful render with a safety margin, capped at 30 seconds.
- If no tested volume reaches a callback within 60 seconds, treat embedding as blocked in that browser rather than extending the spinner indefinitely.
- Keep the safe inline metadata fallback and external Google Books link. Never force a popup.

## Security and performance

- API keys remain server-side.
- Browse performs one SerpAPI request sequence per selected source, with 10 requested results.
- Provider URLs remain subject to existing whitelist validation and response sanitization.
- Remote preview images are never trusted as HTML and cannot introduce script URLs.

## Verification

- Runtime tests prove initial one-per-source display and ranks 2 through 10 reveal without further fetches.
- Tests cover uneven source lengths, dedicated sources, whitelist sources, restored state, and disabled exhausted state.
- Later phases add filter, image, and Google Books timing tests without weakening Phase 1 coverage.

## Acceptance criteria

- Three default sources yield at most three cards on initial display.
- First Load More yields at most six total cards, two per source when available.
- No Load More action issues a network search request.
- After rank 10, or earlier when all groups are exhausted, Load More is disabled with `No more results.`
- No regression in deduplication, initial-search error recovery, default source selection, or Browse state restoration.
