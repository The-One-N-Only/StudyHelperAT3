# StudyLib Functional and Visual Polish Design

**Approved direction:** 2026-07-17
**Applies to:** AI chat, browse search, Google Books viewing, dark materials, and primary navigation

This decision record extends the existing dark and light UI specifications. Where it conflicts with the earlier navigation decision in `docs/design/dark-mode-ui-spec.md`, this newer approved design wins.

## Goals

- Make Alexander use hosted Anthropic AI only, with no local language model or model download.
- Remove duplicate browse results and make repeated “Load More” actions add only unseen results.
- Render embeddable Google Books previews inside StudyLib’s existing source viewer.
- Make dark leather, wood, and decorative SVG artwork clearly visible while retaining the candlelit mood.
- Use the supplied open-book SVG as the menu logo, morph it into three hamburger lines while the menu is open, and make the StudyLib wordmark a direct Home link.

## Non-goals

- No multi-provider AI abstraction.
- No browser-side AI credentials.
- No custom ebook renderer, PDF extraction pipeline, or bypass of Google Books preview restrictions.
- No database schema migration.
- No broad page or component redesign beyond the approved material and navigation changes.

## 1. Hosted-only Alexander AI

`ANTHROPIC_API_KEY` and the optional model variables remain server-side environment configuration. `load_dotenv()` must run before importing modules that read environment variables.

Remove the local AI path completely:

- Delete `src/local_ai.py`.
- Delete the tracked `testAiLocal.py` local-inference demo so test discovery cannot import or download a local model.
- Remove `USE_LOCAL_AI`, `LOCAL_AI_MODEL`, local fallback branches, and the `src.local_ai` imports.
- Remove `torch` from `requirements.txt`; do not add `transformers` or another local inference dependency.
- Keep the existing `anthropic` SDK dependency.

`src/answer.py` will call Anthropic for single answers and multi-turn chat. `src/summarise.py` will retain its hosted Anthropic request path and return a structured configuration error when no key exists. `ANTHROPIC_MODEL` defaults to `claude-sonnet-4-6`; `ANTHROPIC_SUMMARISE_MODEL` defaults to `claude-haiku-4-5-20251001`. Both remain configurable. Add a safe `.env.example` containing these names and an empty API-key value.

When AI is unavailable, the API must return a stable non-secret message such as “Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib.” Provider exception details go only to server logs. The workspace must remove its loading message, re-enable its input and Send button, and show the friendly error as an Alexander bubble. While a request is active, duplicate submissions are blocked.

The workspace help text must describe Alexander as a hosted research assistant rather than a local placeholder.

## 2. Search identity, deduplication, and loading more

Every result receives a stable identity in this order:

1. normalized `source_name` plus `source_id` when both exist;
2. otherwise a canonicalized `source_url` with fragments removed and host casing normalized;
3. otherwise normalized title plus source name as a last-resort display identity.

Deduplication also tracks the canonical URL separately from the primary identity. Matching canonical URLs count as duplicates even when two provider paths assigned different source names or IDs to the same page.

The `/api/browse/search-all` response deduplicates the combined provider output before returning it. This removes overlap between dedicated Wikipedia, Google Books, PubMed, or Scholar searches and their matching whitelisted-domain searches.

The browser also deduplicates when merging restored state or later batches. This protects users from stale saved state and future provider overlap.

“Load More” uses a cumulative result window. The first request asks for 10 results per selected source, the next 20, then 30, and so on. The browser merges only unseen identities. If a request returns no unseen results, the button becomes disabled and reads “No more results.” Starting a new search resets the window and exhaustion state.

This design intentionally avoids provider-specific cursor infrastructure. Existing source functions already support a requested result count, so the cumulative window is the smallest reliable change.

## 3. Native Google Books viewer

Google Books search results continue to carry their Google `source_id` volume identifier. They will also expose response-only `accessInfo` preview fields returned by the Books API, including whether the volume is embeddable and its web-reader fallback link when available. These extra preview fields are merged into the search response but are not persisted, so no database migration is required.

When `openViewer()` receives a Google Books result:

- Load Google’s official Embedded Viewer API once, shared across viewer openings.
- Create the viewer inside the existing StudyLib offcanvas body.
- Load the volume by `source_id`.
- Size the embedded reader to the available offcanvas area and preserve it during responsive resizing.

If Google marks a volume non-embeddable, the loader fails, the external script is unavailable, or no volume ID exists, show a native StudyLib metadata panel with cover, title, description, preview status, and an “Open Google Books” link. Never proxy and inject the Google Books webpage HTML.

Wikipedia and other source viewer paths remain unchanged.

## 4. Dark materials and illustrations

Keep the existing texture files. Change only their dark-theme composition:

- Replace fully opaque dark multiply layers with semi-transparent warm tint layers so leather grain and wood lines remain visible.
- Keep panel and button fallback colors, borders, focus rings, and text contrast intact.
- Increase dark decorative SVG opacity enough to read without squinting, while keeping artwork pointer-inert and behind content.
- Preserve current light-mode material rules unchanged.

Browser verification must compare the same leather panel and wood button in both themes. Dark texture detail must be visible at normal brightness without overpowering labels or body text.

## 5. Open-book menu logo and Home wordmark

Split the current single wordmark button into two controls:

- A square menu button using `static/img/illustrations/open-book.svg`.
- A separate `StudyLib` anchor pointing directly to `/`.

The menu button keeps `aria-controls` and `aria-expanded`. Its accessible name changes between “Open navigation menu” and “Navigation menu open.”

On open, the book graphic crossfades and transforms into three horizontal hamburger bars. On close—whether by the close button, Escape, backdrop click, or navigation—the animation reverses. The state is driven by `aria-expanded`, not a second unsynchronized class. Under `prefers-reduced-motion: reduce`, the states switch without animation.

Existing modal focus containment, outside-content inert handling, Escape behavior, close button, and focus restoration remain intact. Focus returns to the book menu button after close.

## Error handling and security

- AI keys remain server-side and never enter HTML, JavaScript, logs, or API responses.
- AI API errors use stable user-facing messages and detailed server-only logging.
- Google’s viewer script is loaded from the official Google Books endpoint only once; failures produce the native fallback panel.
- Result identity generation treats provider data as untrusted strings and does not introduce HTML interpolation.
- Existing URL allowlisting and safe DOM construction remain mandatory.

## Test and verification strategy

Follow red-green-refactor for each behavior:

1. AI tests prove dotenv ordering, removal of local fallback, friendly missing-key behavior, successful hosted chat through a stubbed Anthropic client, and submit-button recovery after failure.
2. Search tests reproduce default-source overlap and repeated cumulative batches, then prove stable server and client deduplication plus the exhausted state.
3. Viewer tests prove Google volume IDs reach the Embedded Viewer, the script loads once, non-embeddable and failed loads use the metadata fallback, and Wikipedia remains unchanged.
4. Navigation tests prove separate button/link semantics, Home destination, `aria-expanded` state, book-to-bars transition hooks, keyboard close paths, and reduced-motion handling.
5. Theme contract tests prove the dark material layers are translucent, light material rules remain unchanged, and dark SVG visibility increases without losing pointer or accessibility guards.
6. Run focused tests after every task, then the full suite.
7. Run authenticated browser QA for chat error/success states, repeated searches, Google Books preview/fallback, both themes, keyboard navigation, and desktop/mobile widths.

## Acceptance criteria

- No local model code or local inference dependency remains.
- With a valid Anthropic key, Alexander returns a hosted response; without one, it fails quickly and clearly.
- Search result cards contain no repeated stable identities, including after multiple “Load More” clicks.
- Embeddable Google Books volumes open inside StudyLib; unavailable previews fall back cleanly.
- Dark leather, wood, and SVG detail is plainly visible at normal brightness.
- Open-book button opens the sidebar and visibly becomes hamburger bars; StudyLib goes directly Home.
- Focus, keyboard, reduced-motion, light-theme, and existing Wikipedia behavior remain intact.
