# Browse Filters Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Browse Filters viewport-safe and add one accessible master checkbox that controls every dedicated and dynamic whitelist source.

**Architecture:** Keep source selection inside `static/js/pages/browse.js`. Give every real source checkbox one shared class, exclude the master checkbox from search payloads, and derive master checked/indeterminate state from current source checkbox state. Use delegated source-change handling so asynchronously rendered whitelist sources participate without listener rebinding. Add theme-neutral menu scrolling in `static/css/custom.css` and prove behavior with existing Python/Node contract harnesses.

**Tech Stack:** Vanilla JavaScript ES modules, Bootstrap-compatible HTML, CSS, Python `pytest`, Node runtime harnesses, BeautifulSoup contract checks.

## Global Constraints

- Filters menu receives a viewport-bounded maximum height and its own vertical scrolling.
- A master source checkbox appears above all source options.
- Master checkbox selects or clears dedicated and dynamic whitelist source checkboxes.
- Master checkbox is checked when every source is checked, unchecked when none are checked, and indeterminate when selection is partial.
- Source selection remains keyboard accessible and persists through existing Browse state.
- Default checked sources remain Wikipedia, Google Books, and Google Scholar. PubMed and other whitelist sources remain unchecked.
- Existing ranked reveal, SerpAPI-only searching, deduplication, stale-response protection, warnings, URL handling, and state restoration remain unchanged.
- Master checkbox never appears in a Browse API `sources` payload.
- User-provided SVG/GIF files remain untouched and untracked; they are reserved for the approved imagery/loading phase.

---

### Task 1: Viewport-safe Filters and master source selection

**Files:**
- Modify: `static/js/pages/browse.js:379-399,464-503,726-782`
- Modify: `static/css/custom.css:61-71`
- Test: `tests/test_dark_theme_contract.py:3351-3444,4929-4943,5146-5204`

**Interfaces:**
- Consumes: `pageRoot`, `renderWhitelistCheckboxes()`, `getBrowseState()`, `restoreBrowseState()`, existing `BROWSE_STATE_VERSION = 2`, and asynchronously loaded `whitelistDomains`.
- Produces: `getSourceCheckboxes(): HTMLInputElement[]`, `syncMasterSourceCheckbox(): void`, and `setAllSourcesSelected(selected: boolean): void` as module-private helpers; `#filterAllSources` as native checkbox; `.browse-source-checkbox` on every real source checkbox.

- [ ] **Step 1: Add failing structural, CSS, and runtime contracts**

Add `filterAllSources` to `expected_ids` in `test_task6_browse_structure_preserves_light_output_and_supports_mobile_stack()`. In that test, add these assertions after locating `#browseFiltersMenu`:

```python
    source_master = search_shell.select_one("#filterAllSources")
    assert source_master is not None
    assert source_master.get("type") == "checkbox"
    source_master_label = search_shell.select_one('label[for="filterAllSources"]')
    assert source_master_label is not None
    assert source_master_label.get_text(" ", strip=True) == "All sources"

    dedicated_sources = search_shell.select(
        "#filterWikipedia, #filterGBooks, #filterPubMed, #filterScholar"
    )
    assert len(dedicated_sources) == 4
    assert all("browse-source-checkbox" in node.get("class", ()) for node in dedicated_sources)
    assert "browse-source-checkbox" not in source_master.get("class", ())
```

Add viewport scrolling contract:

```python
def test_browse_filters_menu_is_viewport_bounded_and_scrollable():
    declarations = css_rule_group_declarations(
        read_text("static/css/custom.css"),
        (".browse-dropdown-menu",),
    )

    assert declarations["max-height"] == "min(32rem, calc(100vh - 8rem))"
    assert declarations["overflow-y"] == "auto"
```

Add a focused runtime harness beside existing Browse harnesses. Test-only export appending is allowed; production helpers remain private:

```python
BROWSE_FILTER_RUNTIME_HARNESS = TASK6_RUNTIME_BASE + r"""
const controls = new Map();
function control(selector, value = "") {
  const element = new FakeElement(selector);
  element.value = value;
  controls.set(selector, element);
  return element;
}

const search = control("#searchInput");
const go = control("#goBtn");
const filters = control("#filtersDropdown");
const menu = control(".browse-dropdown-menu");
controls.set("#browseFiltersMenu", menu);
const master = control("#filterAllSources");
control("#filterYearFrom");
control("#filterYearTo");
control("#filterContentType");
control("#filterSorting");
control("#sidebarContainer");
control("#resultsContainer");
control("#whitelistCheckboxes");

function source(name, value, checked) {
  const element = new FakeElement(name, "form-check-input browse-source-checkbox");
  element.value = value;
  element.checked = checked;
  return element;
}

const sources = [
  source("Wikipedia", "wikipedia", true),
  source("Google Books", "gbooks", true),
  source("PubMed", "pubmed", false),
  source("Google Scholar", "scholar", true),
  source("JSTOR", "whitelist_jstor.org", false),
  source("Education sites", "whitelist_*.edu", false),
];

function matchingSources(selector) {
  if (!selector.includes("browse-source-checkbox")) return [];
  return selector.includes(":checked")
    ? sources.filter((checkbox) => checkbox.checked)
    : sources;
}

menu.querySelectorAll = matchingSources;
const root = new FakeElement("root");
root.querySelector = (selector) => controls.get(selector) || null;
root.querySelectorAll = matchingSources;

const documentControl = new FakeElement("document");
globalThis.document = {
  addEventListener: documentControl.addEventListener.bind(documentControl),
  createElement() { return new FakeElement("created"); },
};
globalThis.window = {
  location: { pathname: "/browse", search: "" },
  history: { replaceState() {} },
};
globalThis.localStorage = { getItem() { return null; }, setItem() {} };
globalThis.fetch = async (url) => {
  if (url === "/static/whitelist.json") {
    return {
      ok: true,
      async json() { return { domains: ["jstor.org"], domain_patterns: ["*.edu"] }; },
    };
  }
  throw new Error("unexpected fetch: " + url);
};

const { initBrowse, getBrowseState, applySelectedSources } = await import(process.argv[1]);
initBrowse(root);
await new Promise((resolve) => setTimeout(resolve, 0));

const initial = { checked: master.checked, indeterminate: master.indeterminate };

master.checked = true;
await master.dispatch("change");
const selectedAll = sources.map((checkbox) => checkbox.checked);
const savedAll = getBrowseState().sources;

applySelectedSources(["gbooks", "whitelist_jstor.org"]);
const restored = sources.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
const restoredMaster = { checked: master.checked, indeterminate: master.indeterminate };

sources[1].checked = false;
await menu.dispatch("change", { target: sources[1] });
const oneSelectedMaster = { checked: master.checked, indeterminate: master.indeterminate };

master.checked = false;
await master.dispatch("change");
const cleared = sources.map((checkbox) => checkbox.checked);
const clearedMaster = { checked: master.checked, indeterminate: master.indeterminate };

process.stdout.write(JSON.stringify({
  initial,
  selectedAll,
  savedAll,
  restored,
  restoredMaster,
  oneSelectedMaster,
  cleared,
  clearedMaster,
}));
"""


def browse_filter_runtime(source: str | None = None) -> dict:
    browse_source = source or read_text("static/js/pages/browse.js")
    browse_source += "\nexport { getBrowseState, applySelectedSources };\n"
    return run_task6_module_harness(
        browse_source,
        BROWSE_IMPORT_REPLACEMENTS,
        BROWSE_FILTER_RUNTIME_HARNESS,
        "browse filters",
    )


def test_browse_master_source_checkbox_controls_all_sources_and_restores_state():
    rendered = browse_filter_runtime()

    assert rendered["initial"] == {"checked": False, "indeterminate": True}
    assert rendered["selectedAll"] == [True, True, True, True, True, True]
    assert rendered["savedAll"] == [
        "wikipedia",
        "gbooks",
        "pubmed",
        "scholar",
        "whitelist_jstor.org",
        "whitelist_*.edu",
    ]
    assert rendered["restored"] == ["gbooks", "whitelist_jstor.org"]
    assert rendered["restoredMaster"] == {"checked": False, "indeterminate": True}
    assert rendered["oneSelectedMaster"] == {"checked": False, "indeterminate": True}
    assert rendered["cleared"] == [False, False, False, False, False, False]
    assert rendered["clearedMaster"] == {"checked": False, "indeterminate": False}
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py::test_browse_filters_menu_is_viewport_bounded_and_scrollable tests/test_dark_theme_contract.py::test_browse_master_source_checkbox_controls_all_sources_and_restores_state tests/test_dark_theme_contract.py::test_task6_browse_structure_preserves_light_output_and_supports_mobile_stack -q
```

Expected: FAIL because `#filterAllSources`, `.browse-source-checkbox`, viewport scroll declarations, and filter state helpers do not exist.

- [ ] **Step 3: Add master checkbox and source-state helpers**

Above dedicated source checkboxes, add native labelled checkbox:

```html
<div class="form-check mb-2 pb-2 border-bottom">
    <input class="form-check-input" type="checkbox" id="filterAllSources">
    <label class="form-check-label" for="filterAllSources">All sources</label>
</div>
```

Add `browse-source-checkbox` to the four dedicated source checkbox class lists and to each dynamically rendered whitelist checkbox. Do not add it to `#filterAllSources`.

Add module-private helpers before `renderWhitelistCheckboxes()`:

```javascript
function getSourceCheckboxes() {
    const filtersMenu = pageRoot?.querySelector('.browse-dropdown-menu');
    return filtersMenu
        ? Array.from(filtersMenu.querySelectorAll('.browse-source-checkbox'))
        : [];
}

function syncMasterSourceCheckbox() {
    const masterCheckbox = pageRoot?.querySelector('#filterAllSources');
    if (!masterCheckbox) return;

    const sourceCheckboxes = getSourceCheckboxes();
    const checkedCount = sourceCheckboxes.filter((checkbox) => checkbox.checked).length;
    masterCheckbox.checked = sourceCheckboxes.length > 0
        && checkedCount === sourceCheckboxes.length;
    masterCheckbox.indeterminate = checkedCount > 0
        && checkedCount < sourceCheckboxes.length;
}

function setAllSourcesSelected(selected) {
    getSourceCheckboxes().forEach((checkbox) => {
        checkbox.checked = selected;
    });
    syncMasterSourceCheckbox();
}
```

In `registerEvents()`, capture `#filterAllSources`. Add one native `change` listener for master and one delegated `change` listener for real source checkboxes:

```javascript
    const sourceMasterCheckbox = pageRoot.querySelector('#filterAllSources');

    sourceMasterCheckbox?.addEventListener('change', () => {
        setAllSourcesSelected(sourceMasterCheckbox.checked);
    });

    dropdownMenu?.addEventListener('change', (event) => {
        if (event.target?.classList?.contains('browse-source-checkbox')) {
            syncMasterSourceCheckbox();
        }
    });
```

Call `syncMasterSourceCheckbox()` once at end of `registerEvents()` so native default states expose `indeterminate` immediately.

After dynamic whitelist markup renders, preserve restored sources and synchronize:

```javascript
    container.innerHTML = html;
    if (lastSearchSources !== null) {
        applySelectedSources(lastSearchSources);
    } else {
        syncMasterSourceCheckbox();
    }
```

Restrict selection payload and restoration to real source checkboxes:

```javascript
function getSelectedSources() {
    return Array.from(new Set(
        getSourceCheckboxes()
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) => checkbox.value)
    ));
}

function applySelectedSources(sources) {
    if (!Array.isArray(sources)) return;
    const selectedSources = new Set(sources);
    getSourceCheckboxes().forEach((checkbox) => {
        checkbox.checked = selectedSources.has(checkbox.value);
    });
    syncMasterSourceCheckbox();
}
```

- [ ] **Step 4: Add viewport-bounded Filters scrolling**

Extend theme-neutral `.browse-dropdown-menu` rule:

```css
.browse-dropdown-menu {
    max-height: min(32rem, calc(100vh - 8rem));
    overflow-y: auto;
}
```

Keep existing positioning, theme surfaces, transitions, and mobile width rules unchanged.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py::test_browse_filters_menu_is_viewport_bounded_and_scrollable tests/test_dark_theme_contract.py::test_browse_master_source_checkbox_controls_all_sources_and_restores_state tests/test_dark_theme_contract.py::test_task6_browse_structure_preserves_light_output_and_supports_mobile_stack tests/test_dark_theme_contract.py::test_browse_defaults_only_dedicated_sources_and_leaves_dynamic_whitelist_opt_in tests/test_dark_theme_contract.py::test_browse_async_whitelist_render_upgrades_versionless_all_domain_state -q
```

Expected: `5 passed`.

- [ ] **Step 6: Run Browse regression tests and JavaScript syntax check**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dark_theme_contract.py -k "browse" -q
node --check static/js/pages/browse.js
```

Expected: all selected Browse tests pass; Node exits `0` with no output.

- [ ] **Step 7: Run full suite with dotenv disabled**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import dotenv, pytest; dotenv.load_dotenv = lambda *args, **kwargs: False; raise SystemExit(pytest.main(['-q']))"
```

Expected: `299 passed`; existing 10 warnings remain known baseline noise.

- [ ] **Step 8: Review exact diff and commit**

Run:

```powershell
git diff --check
git diff -- static/js/pages/browse.js static/css/custom.css tests/test_dark_theme_contract.py
git status --short
git add static/js/pages/browse.js static/css/custom.css tests/test_dark_theme_contract.py
git commit -m "feat: improve Browse filter selection"
```

Expected: only three Phase 2 files staged; user-provided SVG/GIF files remain untracked and untouched.
