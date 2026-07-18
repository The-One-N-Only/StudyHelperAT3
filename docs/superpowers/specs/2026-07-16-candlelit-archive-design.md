# Candlelit Archive Dark Theme Implementation Design

**Approved:** 2026-07-16
**Source of truth:** `docs/design/dark-mode-ui-spec.md`

If this decision record conflicts with the source specification, the source specification wins.

## Scope

- Implement the supplied Candlelit Archive design across the existing Flask, Jinja2, Bootstrap 5.3.3, and vanilla JavaScript interface.
- Scope every visual override to `[data-bs-theme="dark"]`.
- Preserve light mode, backend behavior, API contracts, and application data flow.
- Limit markup and JavaScript changes to the additive illustration layer, navigation trigger change, dark-theme class hooks, and candle cursor behavior described by the source specification.
- Implement component by component in the order defined by section 13 of the source specification.

## Asset decisions

- Convert the two supplied JPEG texture swatches to real PNG files named `leather-texture.png` and `wood-texture.png`, matching the source manifest.
- Use the five supplied SVG illustrations: `compass-rose.svg`, `sextant.svg`, `stacked-books.svg`, `open-book.svg`, and `scrollwork-flourish.svg`.
- Store the supplied illustrations unchanged beneath `static/img/illustrations/`, matching the paths required by the source specification.
- The supplied SVGs have been checked for scripts, event handlers, external references, and embedded data. Each uses `currentColor`, `fill="none"`, a `viewBox`, and `aria-hidden="true"` as required.
- Keep illustrations decorative, low-opacity, pointer-inert, and hidden from assistive technology.

## Resolved source questions

1. Keep the specified `--info-slate: #6E87A6` token for DOCX icons.
2. Use `--text-primary` for user chat bubbles. Verify the final blended bubble background still clears WCAG AA during implementation.
3. Follow the requested navigation behavior: the StudyLib logo opens the sidebar, and the sidebar gains a Home entry.

## Implementation shape

1. Add the dark-mode tokens and Bootstrap variable mapping before component overrides.
2. Add texture materials, vignette, typography, focus states, buttons, dropdowns, badges, scrollbars, and responsive component treatments in `static/css/custom.css`.
3. Apply small semantic class hooks to the existing Jinja and JavaScript-rendered components. Do not refactor page behavior.
4. Add the decorative illustration layer in page margins and empty states.
5. Add the candle overlay and a requestAnimationFrame-based pointer tracker that attaches only in dark mode, remains disabled on touch input, and disables flicker under reduced motion.
6. Preserve the current light-mode DOM behavior and visual rules.

## Failure handling and accessibility

- Candle setup exits safely when the layer is unavailable.
- Theme toggling attaches or detaches candle tracking without accumulating listeners or animation frames.
- Decorative assets remain non-interactive and carry empty alternative text or `aria-hidden="true"`.
- Every control retains keyboard navigation and a visible dark-mode focus state.
- Text and placeholder contrast must meet WCAG AA.

## Verification

- Add failing contract tests before implementation for required dark-theme tokens, assets, navigation hooks, candle guards, and dark-only selector scoping.
- Run the complete Python test suite after each implementation unit.
- Capture light-mode baselines before visual edits and compare them after implementation.
- Exercise dark and light modes in a real browser at desktop, tablet, and mobile widths.
- Verify keyboard focus, reduced-motion behavior, touch-device candle suppression, texture tiling, and text contrast.
