---
applyTo: "static/css/**/*.css,static/js/**/*.js,templates/**/*.html"
---

When editing light-theme UI, treat `docs/design/light-mode-ui-spec.md` as the source of truth. Light mode is the unscoped default. Never edit any `[data-bs-theme="dark"]` rule. Never add `[data-bs-theme="light"]` selectors. Apply section 16 defaults without stopping to ask.
