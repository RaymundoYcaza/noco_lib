# SPEC — Tardis Phase 4b: Nav Refactor + `ai_lib` + `ai_corrections`

> Self-contained document. Any LLM can pick it up without prior context.
> **Execution rule**: complete tasks **one at a time, in listed order**.
> Each task has Context / Steps / Verification / Depends on.
> **After finishing a task, the LLM MUST mark it `[x]` before proceeding.**
> Do not skip a task whose dependency is not yet `[x]`.

---

## 0. Context recap (do not redesign)

- **Tardis** is a PySide6 desktop app. Modules live in `modules/<name>/`,
  each exposes `register(app: MainWindow, client: NocoClient) -> None`.
- **Current state** (Phases 1-4a complete): three-pane LocalMail layout
  (sidebar tree + email list + reader), PDF Export as a right dock panel,
  Module Admin as a bottom dock panel. Both dock panels are marked for
  removal in this phase (red-crossed in stakeholder screenshot).
- **`noco_lib`**: `NocoResult` contract. `client.table(...)` never raises.
- **`pdf_export`**: `generate_pdf(data, brand, output_path)` and
  `generate_html(data, brand)` — must be called from the main Qt thread
  (drives internal QEventLoop). Already implemented.
- **Golden rule**: any call to `noco_lib` or `ai_lib` that does I/O
  runs inside `run_async()`, never in the Qt main thread. Exception:
  `generate_pdf` which drives its own QEventLoop from the main thread.
- **Logging**: `logging.getLogger("tardis")` everywhere.
- **Extension points** (current, to be refactored in 11.0):
  `add_dock_panel`, `add_floating_window`, `add_menu_action`,
  `add_toolbar_action`, `show_notification`, `add_sidebar_node`.

---

## 1. Confirmed design decisions

### 1.1 Navigation architecture (replaces dock panels)

**App Switcher bar** — a narrow fixed column (~52px) at the far left of
`MainWindow`, containing module icons. Two fixed zones separated by a
flexible spacer:

```
┌──┐
│🏠│  ← LocalMail (always first, always visible, fixed)
│──│
│📄│
│🤖│  ← Business modules (scrollable QScrollArea if icons overflow)
│📊│
│··│
│  │  ← QSpacerItem(expanding) pushes bottom zone down
│──│
│⚙ │  ← Settings (always last, always visible, fixed)
└──┘
```

- Icon size: 32×32px (qtawesome, color `#e0e0e0` on dark background).
- Tooltip shows module name on hover (no permanent text label — Phase 6
  adds expandable mode with labels).
- Active module: accent-colored left border (3px) + slightly lighter
  background on that icon button.
- Middle zone is a `QScrollArea` (no scrollbar visible, mouse-wheel
  scrolls) — so 20 modules load fine without layout issues.
- LocalMail and Settings icons are OUTSIDE the scroll area (always
  visible regardless of scroll position).

### 1.2 Module screen contract (replaces `add_dock_panel`)

Each module now registers a **full-screen widget** (its "module screen"),
not a dock panel. The module screen replaces the entire central content
area when its icon is clicked. Only one module screen is visible at a time.

New extension point:
```python
def register_nav_item(
    self,
    module_id: str,        # unique key, e.g. "localmail", "pdf_export"
    icon: str,             # qtawesome icon name, e.g. "fa5s.envelope"
    label: str,            # tooltip + Settings label, e.g. "LocalMail"
    widget: QWidget,       # the module's main screen widget
    toolbar: QWidget | None = None,  # optional top toolbar for this module
                                     # shown above widget when module is active
                                     # (NOT implemented in Phase 4b — accepted
                                     # as parameter but stored for Phase 6)
    position: str = "middle",  # "top" (fixed above scroll) | "middle" (scrollable)
                                # | "bottom" (fixed below spacer, above Settings)
) -> None
```

`add_floating_window`, `add_menu_action`, `show_notification` remain
unchanged. `add_dock_panel` is removed (any call raises a clear
`NotImplementedError` with a message pointing to `register_nav_item`).
`add_sidebar_node` remains for LocalMail's tree — it is LocalMail-specific
now, not a generic extension point.

### 1.3 Settings screen (replaces Module Admin dock)

A built-in screen accessible via the ⚙ icon. Contains:
- **Modules tab**: the former Module Admin table
  (Name / Status / Error per module). Replaces the bottom dock panel.
- **Connection tab**: read-only display of current NocoDB config
  (`NOCO_BASE_URL`, `NOCO_BASE_ID`, masked `NOCO_TOKEN`) and AI config
  (`TARDIS_AI_PROVIDER`, `TARDIS_AI_MODEL`, `TARDIS_AI_BASE_URL`).
- **Diagnostics tab**: button "Send test notification" (former Dummy
  module action), button "Open log file" (`logs/tardis.log`).
- Phase 6 will add Appearance, Themes, and User Preferences tabs.

### 1.4 PDF Export screen (replaces right dock panel)

`pdf_export` registers as a nav item with `module_id="pdf_export"`,
`icon="fa5s.file-pdf"`, `position="middle"`. Its full-screen widget is
the existing form (brand selector, doc type, audience, JSON editor,
Preview and Generate buttons) — laid out with more space now that it
occupies the full central area rather than a narrow right panel.

### 1.5 LocalMail layout within the nav system

When LocalMail is the active module, the central area shows:
```
┌──┬──────────┬─────────────┬──────────────────────┐
│  │ Sidebar  │ Email list  │ Reader               │
│🏠│ (casillas│ (filtros +  │ (header + body +     │
│  │ /folders)│  tabla)     │  actions)            │
│✉ │          │             │                      │
│··│          │             │                      │
│⚙ │          │             │                      │
└──┴──────────┴─────────────┴──────────────────────┘
```
The App Switcher bar (far left, 52px) + LocalMail's own folder sidebar +
list + reader = 4 vertical columns total. The splitter proportions from
Phase 3 persist via `QSettings`.

### 1.6 LocalMail top toolbar (documented, NOT implemented in Phase 4b)

A `QToolBar` docked at the top of the LocalMail screen widget (not
`MainWindow`'s toolbar). Buttons: Compose, Reply, Forward, Archive,
Move to Trash, Get Messages, Search. Contextual buttons (Reply, Forward,
Archive, Move to Trash) enabled only when an email is selected in the
reader. **This is registered via the `toolbar` parameter of
`register_nav_item` but the actual toolbar widget is NOT built in
Phase 4b** — `toolbar=None` is passed. Phase 6 implements it.

### 1.7 `ai_lib` architecture

- Lives in `ai_lib/` at the project root (same level as `noco_lib/`) —
  shared infrastructure, not a UI module.
- Default provider: **Ollama**, `POST http://localhost:11434/api/chat`
  (chat completions endpoint, not `/api/generate` — chat gives better
  structured output control).
- Config via `.env`: `TARDIS_AI_PROVIDER=ollama`,
  `TARDIS_AI_MODEL=gemma3:27b`, `TARDIS_AI_BASE_URL=http://localhost:11434`.
- HTTP calls via `requests` (same pattern as `noco_lib`). No official
  Ollama SDK.
- `AIResult` contract (mirrors `NocoResult`):
  ```python
  @dataclass
  class AIResult:
      success: bool
      operation: str   # "correct"|"classify"|"extract"|"summarize"
      data: Any        # str | list | dict — the AI's structured response
      errors: list[str]
      meta: dict       # {"model": str, "provider": str,
                       #  "prompt_tokens": int, "completion_tokens": int,
                       #  "latency_ms": int}
  ```
- Every public function returns `AIResult`. Never raises to caller.

### 1.8 `ai_corrections` module

- Registers as nav item: `module_id="ai_corrections"`,
  `icon="fa5s.magic"`, `label="AI Corrections"`, `position="middle"`.
- Screen has two states: **Setup** (form) and **Review** (comparison
  table). Switching between them happens within the same widget (using
  `QStackedWidget`), no floating window.
- Operations available: `correct`, `classify`, `extract`, `summarize`.
- Processing: batches of 20 records, one `run_async` call per batch.
  Progress shown as `QProgressBar`.
- Pre-analysis estimate: shows estimated time in seconds
  (`total_chars / 4 / 50` tokens/sec for local Ollama).
- Review table: columns "Id", "Field", "Original", "AI Suggestion",
  "Accept" (checkbox). "Accept All" / "Reject All" buttons.
  Write-back uses `noco_lib` only for accepted rows.
- Best-effort: failures per record logged in `meta["partial_errors"]`,
  processing continues.

### 1.9 Ollama prompt system

- Prompt templates live in `ai_lib/prompts/<operation>.txt`.
- Each prompt uses `{field_name}`, `{value}`, `{context}`, `{options}`
  placeholders (replaced via Python `.format()` before sending).
- The response MUST be requested as JSON: every prompt ends with
  `"Respond ONLY with a JSON object: {\"result\": \"<corrected value>\"}"`.
  `ai_lib` parses the JSON and returns `data["result"]` as the
  corrected value. If JSON parsing fails, return `AIResult.fail(...)`.

### 1.10 Phase 5 and Phase 6 roadmap (reference)

**Phase 5 — Quotations module**:
- Nav item: `module_id="quotations"`, `icon="fa5s.file-invoice-dollar"`.
- Screen: list of quotations (from `COT_QUOTATIONS` NocoDB table, name
  configurable via `TARDIS_QUOTATIONS_TABLE`) + "New Quotation" button.
- New quotation form: client info + line items (description, qty, unit
  price, subtotal auto-calculated) + totals.
- "Generate PDF" → `generate_pdf(data, brand, output_path)` with
  `doc_type="quote"`.
- "Send via LocalMail" → `service.send_email(...)` with PDF attached
  (Phase 5 spec must define attachment upload to NocoDB's attachment API).
- The `Attachment` field of `DIR_LOCAL-MAIL` (unused so far) is
  addressed here.

**Phase 6 — UI Reorganization + Visual Polish**:
- New color scheme (to be defined in Phase 6 spec).
- Switchable themes (dark / light, minimum 2).
- App Switcher bar: expandable mode (icon + label, ~180px wide),
  toggle persisted in `QSettings`.
- App Switcher overflow: "···" menu for modules beyond visible area,
  configurable pin/unpin in Settings > Modules.
- LocalMail top toolbar (`QToolBar`) implementation: Compose, Reply,
  Forward, Archive, Move to Trash, Get Messages, Search — with
  contextual enable/disable.
- Settings > Appearance tab: theme selector, accent color picker,
  font size.
- Full `dark.qss` replacement with a proper token-based theming system.
- `dummy_notify_test` module retired (its functionality absorbed into
  Settings > Diagnostics, already done in Phase 4b).

---

## 2. File structure changes

```
tardis/
├── app_core/
│   ├── main.py                  # updated: build nav bar, settings screen
│   ├── main_window.py           # MAJOR REFACTOR: nav bar + module screens
│   ├── module_registry.py       # updated: pass module screen to register_nav_item
│   ├── concurrency.py            # unchanged
│   ├── config.py                 # updated: add AI config fields
│   ├── logging_setup.py          # unchanged
│   ├── theming.py                # unchanged
│   ├── sidebar/                  # unchanged (LocalMail-specific)
│   ├── widgets/
│   │   ├── toast.py              # unchanged
│   │   ├── nav_bar.py            # NEW: App Switcher widget
│   │   └── nav_button.py         # NEW: single icon button for nav bar
│   └── views/
│       ├── module_admin_view.py  # repurposed as Settings > Modules tab
│       └── settings_view.py      # NEW: Settings screen (tabbed)
│
├── ai_lib/                        # NEW: AI abstraction layer
│   ├── __init__.py
│   ├── ai_client.py               # HTTP client for Ollama (and future providers)
│   ├── ai_result.py               # AIResult dataclass
│   ├── ai_config.py               # load AI config from TardisConfig
│   └── prompts/
│       ├── correct.txt
│       ├── classify.txt
│       ├── extract.txt
│       └── summarize.txt
│
├── modules/
│   ├── localmail/                 # updated: register_nav_item instead of dock panels
│   ├── pdf_export/                # updated: register_nav_item instead of dock panel
│   ├── ai_corrections/            # NEW
│   │   ├── __init__.py
│   │   ├── module.py
│   │   └── views/
│   │       ├── setup_view.py      # form: table, fields, operation, context
│   │       └── review_view.py     # comparison table + accept/reject
│   └── dummy_notify_test/         # RETIRED: delete folder
```

---

## 3. `TardisConfig` additions

```python
@dataclass
class TardisConfig:
    # existing fields unchanged ...
    # NEW:
    ai_provider: str    # default "ollama"
    ai_model: str       # default "gemma3:27b"
    ai_base_url: str    # default "http://localhost:11434"
```

`.env.example` additions:
```
TARDIS_AI_PROVIDER=ollama
TARDIS_AI_MODEL=gemma3:27b
TARDIS_AI_BASE_URL=http://localhost:11434
```

---

## 4. PLAN OF TASKS (checklist — execute in order, mark `[x]` when done)

### 11.0 — Nav bar refactor (MUST be done before ai_lib tasks)

- [x] **11.0.1** Create `app_core/widgets/nav_button.py`.
      Context: individual icon button for the App Switcher bar. Must
      show active state and tooltip.
      Steps:
      1. Class `NavButton(QPushButton)`:
         - Fixed size: 52×52px (`setFixedSize(52, 52)`).
         - Flat style (`setFlat(True)`).
         - Icon: `qta.icon(icon_name, color="#e0e0e0")` set via
           `setIcon(...)`, `setIconSize(QSize(28, 28))`.
         - Tooltip: `setToolTip(label)`.
         - Property `active: bool` — when `True`, apply via
           `setProperty("active", True)` + `style().unpolish/polish(self)`
           so QSS can target `NavButton[active="true"]`.
         - `setCheckable(True)` so Qt handles the checked state visually
           (we'll override with QSS but checkable gives us `isChecked()`
           for free).
      2. Add QSS rules to `app_core/styles/dark.qss`:
         ```css
         NavButton {
           background: transparent;
           border: none;
           border-left: 3px solid transparent;
           border-radius: 0;
         }
         NavButton:hover { background: rgba(255,255,255,0.06); }
         NavButton:checked {
           background: rgba(255,255,255,0.10);
           border-left: 3px solid #0a66c2;  /* accent color */
         }
         ```
      Verification: create a throwaway script that shows a `QWidget`
      with 3 `NavButton`s and confirms: (a) icons render without black
      boxes on dark background, (b) clicking one highlights it (checked
      state), (c) tooltip appears on hover.
      Depends on: none (requires qtawesome installed from Phase 3).

- [x] **11.0.2** Create `app_core/widgets/nav_bar.py`.
      Context: the full App Switcher bar widget containing all nav
      buttons.
      Steps:
      1. Class `NavBar(QWidget)`:
         - Fixed width 52px (`setFixedWidth(52)`).
         - `QVBoxLayout` with `spacing=0`, `contentsMargins=(0,0,0,0)`.
         - TOP ZONE: fixed `QWidget` containing the LocalMail button
           (always visible, `position="top"`). No scroll.
         - MIDDLE ZONE: `QScrollArea` (fixed, no scroll bar visible:
           `setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`,
           `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`,
           `setWidgetResizable(True)`). Contains a `QWidget` with
           `QVBoxLayout` for middle-position modules.
         - `QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)`
           after the scroll area.
         - BOTTOM ZONE: fixed `QWidget` containing the Settings button
           (always visible, `position="bottom"`).
      2. Method `add_button(button: NavButton, position: str) -> None`:
         - `"top"`: add to top zone layout.
         - `"middle"`: add to the scrollable inner widget's layout.
         - `"bottom"`: add to bottom zone layout.
      3. Signal `module_activated = Signal(str)` (emits `module_id`)
         connected to each button's `clicked` — the bar manages mutual
         exclusion (when one button is checked, uncheck all others).
      4. Method `set_active(module_id: str)`: checks the correct button,
         unchecks all others.
      Verification: instantiate `NavBar`, add 8 dummy buttons via
      `add_button(btn, "middle")`, reduce the window height to force
      overflow — confirm middle zone scrolls with mouse wheel while top
      (LocalMail) and bottom (Settings) buttons remain visible.
      Depends on: 11.0.1.

- [x] **11.0.3** Refactor `app_core/main_window.py` — MAJOR.
      Context: replace the dock-based layout with nav bar + stacked
      module screens.
      Steps:
      1. Remove all `QAdsDockManager` / Qt Advanced Docking System usage.
         The central widget becomes a `QHBoxLayout` with two children:
         - `NavBar` (fixed 52px, created in `__init__`).
         - `QStackedWidget` (fills remaining space) — holds one widget
           per registered module + the Settings screen.
      2. Add `self._nav_bar = NavBar(self)`.
      3. Add `self._stack = QStackedWidget(self)`.
      4. Add `self._module_screens: dict[str, QWidget] = {}`.
      5. Add `self._module_toolbars: dict[str, QWidget | None] = {}`.
      6. Implement `register_nav_item(module_id, icon, label, widget,
         toolbar=None, position="middle")`:
         - Create `NavButton(icon, label)`.
         - Connect button `clicked` → `lambda: self._activate_module(module_id)`.
         - `self._nav_bar.add_button(btn, position)`.
         - `self._stack.addWidget(widget)`.
         - `self._module_screens[module_id] = widget`.
         - `self._module_toolbars[module_id] = toolbar`.  # store for Phase 6
      7. Implement `_activate_module(module_id: str)`:
         - `self._stack.setCurrentWidget(self._module_screens[module_id])`.
         - `self._nav_bar.set_active(module_id)`.
         - Persist `module_id` to `QSettings("Tardis","Tardis")` key
           `"nav/last_active_module"`.
      8. On startup (after all modules registered), restore last active
         module from `QSettings`, or default to `"localmail"`.
      9. Remove `add_dock_panel`: replace body with
         `raise NotImplementedError("add_dock_panel is removed. Use register_nav_item.")`.
      10. Keep `add_floating_window`, `add_menu_action`,
          `add_toolbar_action`, `show_notification` unchanged.
      11. The hidden `QWebEngineView` for PDF printing
          (`self._pdf_printer_view`) stays on `MainWindow` — unchanged.
      Verification: launch Tardis with NO modules registered (comment
      out `discover_and_register` temporarily). Confirm: app opens with
      just the nav bar (52px left column) and empty right area, no
      crashes, no references to dock manager. Re-enable modules.
      Depends on: 11.0.2.

- [x] **11.0.4** Create `app_core/views/settings_view.py`.
      Context: Settings screen replacing the bottom dock panel and
      providing a home for diagnostics.
      Steps:
      1. Class `SettingsView(QWidget)`:
         - `QVBoxLayout` with a `QTabWidget` containing 3 tabs:
           **Modules**, **Connection**, **Diagnostics**.
         - **Modules tab**: `ModuleAdminView` (existing from Phase 2,
           move it here — change from standalone widget to a tab content).
           `ModuleAdminView` receives `module_info: dict` as before.
         - **Connection tab**: read-only form showing:
           `NOCO_BASE_URL` (from `app.config`), `NOCO_BASE_ID`,
           `NOCO_TOKEN` (masked: show first 4 chars + "****"),
           `TARDIS_AI_PROVIDER`, `TARDIS_AI_MODEL`,
           `TARDIS_AI_BASE_URL`. All as `QLabel` pairs (key: value),
           no editing.
         - **Diagnostics tab**: `QPushButton("Send test notification")`
           (does what `dummy_notify_test` did — calls
           `service.notify(client, to_users=app.config.mailboxes[:1],
           subject="Test", body="Tardis diagnostics test",
           module_origin="diagnostics")` via `run_async`);
           `QPushButton("Open log file")` (calls `os.startfile` /
           `xdg-open` on `logs/tardis.log`);
           `QLabel` showing last action result.
      2. Constructor: `SettingsView(config: TardisConfig, module_info:
         dict, client: NocoClient, main_window: MainWindow)`.
      Verification: `SettingsView` instantiates without error with a
      mock `config` and empty `module_info`. All 3 tabs render. "Open
      log file" button opens `tardis.log` (create a dummy one if needed).
      Depends on: 11.0.3.

- [x] **11.0.5** Update `modules/localmail/module.py` to use
      `register_nav_item`.
      Steps:
      1. Remove all `app.add_dock_panel(...)` calls.
      2. Build a single `LocalMailScreen(QWidget)` that contains the
         three-pane `QSplitter` (sidebar + list + reader) — this is the
         existing three-pane widget from Phase 3, just wrapped or
         renamed for clarity.
      3. Call:
         ```python
         app.register_nav_item(
             module_id="localmail",
             icon="fa5s.envelope",
             label="LocalMail",
             widget=localmail_screen,
             toolbar=None,    # Phase 6: will be the QToolBar
             position="top",  # LocalMail is always first
         )
         ```
      4. Keep all menu actions (`add_menu_action("LocalMail", "Compose",
         ...)` etc.) — they move to the app menu bar, unchanged.
      Verification: launch Tardis — LocalMail appears as the first nav
      icon (envelope), clicking it shows the three-pane layout. Clicking
      another module icon (if any) hides LocalMail. Switching back
      restores it. No dock panels visible.
      Depends on: 11.0.4.

- [x] **11.0.6** Update `modules/pdf_export/module.py` to use
      `register_nav_item`.
      Steps:
      1. Remove `app.add_dock_panel(...)`.
      2. The existing PDF Export form widget IS the module screen —
         pass it directly to `register_nav_item`:
         ```python
         app.register_nav_item(
             module_id="pdf_export",
             icon="fa5s.file-pdf",
             label="PDF Export",
             widget=pdf_export_form_widget,
             position="middle",
         )
         ```
      3. The form now has the full central area (not a narrow 300px
         right panel) — adjust layout if needed (e.g. use a
         `QFormLayout` with max-width `QWidget` centered, or a two-column
         layout for wider screens).
      Verification: launch Tardis, click the PDF icon in the nav bar —
      PDF Export form appears in full central area. Brand/type selectors,
      JSON editor, and buttons all visible and functional.
      Depends on: 11.0.5.

- [x] **11.0.7** Register Settings screen and wire `module_info`.
      Steps:
      1. In `app_core/main.py`, after `module_info =
         discover_and_register(window, client)`:
         - Instantiate `SettingsView(config, module_info, client, window)`.
         - Call `window.register_nav_item(module_id="settings",
           icon="fa5s.cog", label="Settings", widget=settings_view,
           position="bottom")`.
      2. Delete `modules/dummy_notify_test/` folder entirely (its
         "Send test notification" is now in Settings > Diagnostics).
      3. Confirm `module_registry` no longer tries to load
         `dummy_notify_test` (it won't, since the folder is gone).
      Verification: launch Tardis — nav bar shows: LocalMail (top),
      PDF Export (middle), AI Corrections (middle, once 11.2.x done),
      Settings (bottom). Settings screen opens on click showing all 3
      tabs with correct data. Module Admin table now inside Settings.
      Module list in Settings > Modules shows `localmail` and
      `pdf_export` as "Loaded".
      Depends on: 11.0.6.

- [x] **11.0.8** **CHECKPOINT 0 — Nav refactor complete**:
      Full smoke test:
      1. App launches — nav bar visible, LocalMail active by default.
      2. Click PDF Export icon — form visible full-width.
      3. Click LocalMail icon — three-pane layout visible.
      4. Click Settings icon — all 3 tabs render with correct data.
      5. Settings > Diagnostics: "Send test notification" sends a
         message that appears in LocalMail inbox (manual refresh).
      6. Settings > Diagnostics: "Open log file" opens `tardis.log`.
      7. No dock panels visible anywhere. No crashes. No references to
         `QAdsDockManager` remain in any Python file (`grep -r
         "DockManager\|add_dock_panel" --include="*.py"` returns 0
         results, excluding `NotImplementedError` message strings).
      8. Resize window and minimize/restore — proportions preserved.
      9. Close and reopen Tardis — last active module restored.
      Depends on: 11.0.7.

### 11.1 — `ai_lib` core

- [x] **11.1.1** Update `TardisConfig` and `.env.example` with AI fields
      (section 3).
      Steps:
      1. In `app_core/config.py`, add `ai_provider: str`,
         `ai_model: str`, `ai_base_url: str` to `TardisConfig` dataclass.
      2. In `load_tardis_config()`, read from env:
         `ai_provider = os.environ.get("TARDIS_AI_PROVIDER", "ollama")`,
         `ai_model = os.environ.get("TARDIS_AI_MODEL", "gemma3:27b")`,
         `ai_base_url = os.environ.get("TARDIS_AI_BASE_URL", "http://localhost:11434")`.
      3. Update `.env.example` with the 3 new vars (section 3).
      Verification: `load_tardis_config().ai_model` returns `"gemma3:27b"`
      when `TARDIS_AI_MODEL` is not set. Returns `"llama3"` when
      `TARDIS_AI_MODEL=llama3` is in `.env`.
      Depends on: 11.0.8.

- [x] **11.1.2** Implement `ai_lib/ai_result.py`.
      Steps:
      1. `AIResult` dataclass per section 1.7. Include `ok()` and
         `fail()` classmethods mirroring `NocoResult`:
         ```python
         @classmethod
         def ok(cls, operation, data=None, meta=None) -> "AIResult": ...
         @classmethod
         def fail(cls, operation, errors, meta=None) -> "AIResult": ...
         ```
      2. `to_dict() -> dict` method (mirrors `NocoResult.to_dict()`).
      3. `__init__.py` for `ai_lib/` exports `AIResult`.
      Verification: `AIResult.ok("correct", data="hola mundo").to_dict()`
      returns a dict with `success=True, operation="correct",
      data="hola mundo"`. `AIResult.fail("correct", "timeout")` returns
      `success=False, errors=["timeout"]`.
      Depends on: 11.1.1.

- [x] **11.1.3** Create prompt template files.
      Steps:
      1. Create `ai_lib/prompts/correct.txt`:
         ```
         You are a text correction assistant. Correct the spelling,
         grammar, and punctuation of the following value for the field
         "{field_name}". Preserve the original language and meaning.
         Additional context: {context}
         Value to correct: {value}
         Respond ONLY with a JSON object: {{"result": "<corrected value>"}}
         ```
      2. Create `ai_lib/prompts/classify.txt`:
         ```
         You are a classification assistant. Classify the following value
         for the field "{field_name}" into exactly one of these options:
         {options}
         Additional context: {context}
         Value to classify: {value}
         Respond ONLY with a JSON object: {{"result": "<chosen option>"}}
         where <chosen option> is one of the provided options exactly as
         written.
         ```
      3. Create `ai_lib/prompts/extract.txt`:
         ```
         You are a data extraction assistant. Extract the value of
         "{field_name}" from the following text.
         Additional context: {context}
         Source text: {value}
         Respond ONLY with a JSON object: {{"result": "<extracted value>"}}
         ```
      4. Create `ai_lib/prompts/summarize.txt`:
         ```
         You are a summarization assistant. Summarize the following text
         for the field "{field_name}" in one concise sentence (max 120
         characters).
         Additional context: {context}
         Text to summarize: {value}
         Respond ONLY with a JSON object: {{"result": "<summary>"}}
         ```
      Verification: all 4 files exist, are UTF-8, and contain the
      `{field_name}`, `{value}`, `{context}` placeholders. For
      `classify.txt`, also `{options}`.
      Depends on: 11.1.2.

- [x] **11.1.4** Implement `ai_lib/ai_client.py`.
      Steps:
      1. Class `AIClient`:
         - Constructor: `AIClient(provider: str, model: str, base_url: str)`.
         - `_session = requests.Session()`.
         - Method `complete(prompt: str, operation: str) -> AIResult`:
           a. Read prompt template from `ai_lib/prompts/<operation>.txt`.
              (The `prompt` parameter passed in IS the fully-formatted
              prompt string — the caller already substituted
              `{field_name}`, `{value}`, etc. The template file is read
              by `ai_corrections` service layer, not here. `AIClient`
              only receives the final prompt string.)
           b. Build request body for Ollama chat API:
              ```python
              body = {
                  "model": self.model,
                  "messages": [{"role": "user", "content": prompt}],
                  "stream": False,
                  "format": "json",  # Ollama JSON mode
              }
              ```
           c. `POST {base_url}/api/chat` with timeout=60s (AI can be
              slow). Retry once on `ConnectionError` or timeout.
           d. Parse response: `data = resp.json()`;
              `content = data["message"]["content"]`.
           e. Parse `content` as JSON: `result = json.loads(content)`.
              Extract `result["result"]` as the AI's answer.
           f. Build `meta` from response:
              `{"model": data.get("model"), "provider": self.provider,
              "prompt_tokens": data.get("prompt_eval_count", 0),
              "completion_tokens": data.get("eval_count", 0),
              "latency_ms": data.get("total_duration", 0) // 1_000_000}`.
           g. Return `AIResult.ok(operation, data=result["result"],
              meta=meta)`.
           h. On any exception (network, JSON parse, missing key): log
              full traceback, return `AIResult.fail(operation,
              str(exc), meta={"provider": self.provider,
              "model": self.model})`.
      2. Class method `from_config(config: TardisConfig) -> AIClient`:
         returns `AIClient(config.ai_provider, config.ai_model,
         config.ai_base_url)`.
      Verification: requires Ollama running locally with
      `gemma3:27b` (or any available model). Run
      `scripts/test_ai_client.py`: call `client.complete(
      "You are a correction assistant. Value: 'holla mundo'. "
      "Respond ONLY with JSON: {\"result\": \"<corrected>\"}",
      "correct")`. Confirm `result.success=True` and `result.data` is a
      non-empty string. If Ollama is NOT available, confirm
      `result.success=False` with a clear error message (no crash).
      Depends on: 11.1.3.

- [x] **11.1.5** Implement `ai_lib/ai_service.py` — high-level
      operations.
      Context: this layer builds formatted prompts from templates and
      calls `AIClient.complete`. It is what `ai_corrections` imports.
      Steps:
      1. Load prompt templates ONCE at module level (read all 4 `.txt`
         files into a dict `PROMPTS: dict[str, str]` on import).
      2. Function `correct_value(client: AIClient, field_name: str,
         value: str, context: str = "") -> AIResult`:
         - Format prompt: `PROMPTS["correct"].format(field_name=field_name,
           value=value, context=context or "None provided")`.
         - Return `client.complete(prompt, "correct")`.
      3. Function `classify_value(client: AIClient, field_name: str,
         value: str, options: list[str], context: str = "") -> AIResult`:
         - Format with `options=", ".join(options)`.
         - After getting result, VALIDATE that `result.data` is in
           `options` (exact match). If not, return
           `AIResult.fail("classify", f"AI returned '{result.data}' which
           is not in options {options}")`.
      4. Function `extract_value(client: AIClient, field_name: str,
         value: str, context: str = "") -> AIResult`.
      5. Function `summarize_value(client: AIClient, field_name: str,
         value: str, context: str = "") -> AIResult`.
      6. Function `estimate_time_seconds(records: list[dict],
         fields: list[str]) -> int`:
         - Total chars = sum of len(str(r.get(f, ""))) for r in records
           for f in fields.
         - Estimated tokens = total_chars // 4.
         - Estimated time = estimated_tokens // 50 (50 tokens/sec local
           Ollama baseline).
         - Return max(1, estimated_time).
      Verification: `scripts/test_ai_service.py` — call
      `correct_value(client, "nombre", "jhon doe", "names should be
      Title Case")`. Confirm `result.success=True` and `result.data`
      resembles "John Doe". Call `classify_value(client, "prioridad",
      "urgente", ["Baja", "Media", "Alta"])`. Confirm `result.data` is
      one of the three options exactly.
      Depends on: 11.1.4.

- [x] **11.1.6** **CHECKPOINT 1 — `ai_lib` complete**:
      Run `scripts/test_ai_service.py` for all 4 operations with at
      least one test case each. All return `AIResult.success=True`.
      Simulate Ollama being down (stop the service) and confirm all
      4 functions return `AIResult.fail(...)` with clear error messages
      and NO Python exception propagated to the caller.
      Depends on: 11.1.5.

### 11.2 — `ai_corrections` module

- [x] **11.2.1** Implement `modules/ai_corrections/views/setup_view.py`
      (`SetupView`).
      Steps:
      1. `SetupView(QWidget)` constructor receives `config: TardisConfig,
         client: NocoClient, ai_client: AIClient, main_window: MainWindow`.
      2. Layout (top to bottom):
         - `QLabel("Tabla:")` + `QComboBox` `table_combo` (populated on
           show).
         - `QLabel("Campos a procesar:")` + `QListWidget`
           `fields_list` (multi-select, `setSelectionMode(
           QAbstractItemView.MultiSelection)`). Populated when table
           is selected.
         - `QLabel("Operación:")` + `QComboBox` `operation_combo`
           with items:
           `["correct — Corrección ortográfica",
             "classify — Clasificar en opciones",
             "extract — Extraer campo de texto",
             "summarize — Resumir texto"]`.
         - `QLabel("Contexto adicional (opcional):")` +
           `QPlainTextEdit` `context_input` (3 lines tall).
         - `QLabel("")` `estimate_label` (shows time estimate after table
           + fields selected).
         - `QPushButton("Analizar con IA")` `analyze_btn`.
      3. On `table_combo` selection change:
         - Call `run_async(client.get_table_meta, table_id,
           on_success=self._populate_fields)`.
         - `_populate_fields(result)`: if `result.success`, populate
           `fields_list` with field names (excluding system fields: `Id`,
           `CreatedAt`, `UpdatedAt`, `nc_created_by`, `nc_updated_by`,
           `nc_order`).
      4. On table/fields/operation change, update `estimate_label`:
         fetch a sample (call `run_async(client.table(...).read,
         limit=5, ...)` once, compute estimate from 5 rows and
         extrapolate to total — use `result.meta` or re-read total from
         `pageInfo.totalRows` if available; show e.g. "~45 segundos
         estimados para 100 registros").
      5. On `showEvent` (widget becomes visible):
         - Call `run_async(client.list_tables, on_success=
           self._populate_tables)`.
         - `_populate_tables(result)`: populate `table_combo` with
           `{t["title"]: t["id"]}` for each table.
      6. Signal `analysis_ready = Signal(object)` — emits a dict:
         `{"records": [...], "fields": [...], "operation": str,
         "context": str, "table_id": str, "field_meta": {}}`.
         Emitted when "Analizar con IA" is clicked AND user confirms
         the estimate prompt (see below).
      7. "Analizar con IA" click handler:
         a. Validate: at least 1 field selected, table selected.
            Show error toast if not.
         b. Read all records (use `client.table(...).read(limit=None)` —
            or read in pages; `noco_lib` already paginates).
         c. Show `QMessageBox.question(self, "Confirmar análisis",
            f"Se procesarán {len(records)} registros en "
            f"{len(selected_fields)} campo(s).\n"
            f"Tiempo estimado: ~{estimate_time_seconds(...)} segundos.\n"
            "¿Continuar?", QMessageBox.Yes | QMessageBox.No)`.
         d. If Yes: emit `analysis_ready` signal with the data dict.
      Verification: launch Tardis, navigate to AI Corrections module,
      select a NocoDB table — fields list populates. Select 2 fields,
      operation "correct", click "Analizar" — confirmation dialog appears
      with correct record count and time estimate. Clicking "No" dismisses
      without doing anything. Clicking "Yes" emits `analysis_ready`
      (verify via temporary `print` in the signal handler).
      Depends on: 11.1.6, 11.0.8.

- [x] **11.2.2** Implement the AI processing pipeline in
      `modules/ai_corrections/views/setup_view.py` (continuation).
      Context: after `analysis_ready` is emitted, the main module.py
      connects it to start processing. This task implements the actual
      processing, which lives in a separate method called by module.py.
      Steps:
      1. Add method `process_records(data: dict,
         on_complete: Callable[[list[dict]], None]) -> None` to
         `SetupView` (called by `module.py` after `analysis_ready`):
         a. `records = data["records"]`; `fields = data["fields"]`;
            `operation = data["operation"]`; `context = data["context"]`.
         b. Get operation function from `ai_service`:
            `op_fn = {"correct": ai_service.correct_value,
                      "classify": ai_service.classify_value,
                      "extract": ai_service.extract_value,
                      "summarize": ai_service.summarize_value}[operation]`.
         c. For `classify`, also need `options` per field (from
            `data["field_meta"]` — a dict of `{field_name: {"options":
            [...]}}`). If `options` is empty for a field and operation
            is `classify`, skip that field and log a warning.
         d. Process in batches of 20: for each batch, call
            `run_async(self._process_batch, batch, fields, op_fn,
            context, field_meta, on_success=self._batch_done,
            on_error=self._batch_error)`.
         e. `_process_batch(batch, fields, op_fn, context, field_meta)`
            (runs in thread, returns list of result dicts):
            ```
            results = []
            for record in batch:
                for field in fields:
                    value = str(record.get(field, ""))
                    if not value.strip():
                        continue  # skip empty values
                    if operation == "classify":
                        options = field_meta.get(field, {}).get("options", [])
                        ai_result = op_fn(ai_client, field, value, options, context)
                    else:
                        ai_result = op_fn(ai_client, field, value, context)
                    results.append({
                        "record_id": record["Id"],
                        "field": field,
                        "original": value,
                        "suggestion": ai_result.data if ai_result.success else None,
                        "error": ai_result.errors[0] if not ai_result.success else None,
                        "meta": ai_result.meta,
                    })
            return results
            ```
         f. `_batch_done(batch_results)`: accumulate into
            `self._all_results`. Update progress bar. If all batches
            done: call `on_complete(self._all_results)`.
         g. `_batch_error(exc)`: log, show error toast, continue.
      Verification: run against a real NocoDB table with 5 records,
      field `title`, operation `correct`. After processing, `_all_results`
      contains 5 dicts with `suggestion` populated (or `error` if AI
      failed for that record). No crashes. Progress bar advances.
      Depends on: 11.2.1.

- [x] **11.2.3** Implement `modules/ai_corrections/views/review_view.py`
      (`ReviewView`).
      Steps:
      1. `ReviewView(QWidget)` constructor receives `main_window,
         client, results: list[dict]`.
      2. Top bar: `QPushButton("← Volver")`, `QPushButton("Aprobar
         todo")`, `QPushButton("Rechazar todo")`, `QLabel(f"{N} sugerencias
         — {M} errores")`.
      3. Main widget: `QTableWidget` with columns:
         `Id | Campo | Valor original | Sugerencia IA | Aceptar`.
         - "Id" and "Campo": read-only.
         - "Valor original": read-only, monospace font.
         - "Sugerencia IA": read-only; if `result["error"]` not None,
           show error text in red/muted; otherwise show `suggestion`.
         - "Aceptar": `QCheckBox` centered in cell. Disabled if
           `result["error"]` is not None (can't accept a failed result).
         - Rows where `suggestion == original` get a muted style
           (no change needed — user can still accept, just visually
           de-emphasized).
      4. "Aprobar todo" → check all enabled checkboxes.
         "Rechazar todo" → uncheck all.
      5. `QPushButton("Aplicar cambios aprobados")`:
         - Collect accepted rows: `accepted = [r for r in results if
           checkbox_for(r).isChecked()]`.
         - If `len(accepted) == 0`: show toast "No hay cambios
           seleccionados." and return.
         - Show `QMessageBox.question("¿Aplicar {N} cambios a NocoDB?",
           Yes/No)`.
         - If Yes: call `self._apply_changes(accepted)`.
      6. `_apply_changes(accepted)`:
         - Group by `record_id`: for each unique `record_id`, build
           update dict `{"Id": record_id, field: suggestion, ...}`.
         - Call `run_async(client.table(table_id).update, update_dicts,
           on_success=self._on_applied, on_error=...)`.
         - `_on_applied(result)`: if `result.success`, show toast
           f"✓ {result.affected_count} registros actualizados"; else
           show error toast with `result.errors[0]`.
      7. "← Volver" button: emit `Signal()` `back_requested` — module.py
         connects this to switch back to setup screen.
      Verification: instantiate with 5 mock results (2 with errors, 3
      with suggestions). Confirm: error rows show red text and disabled
      checkbox; "Aprobar todo" checks only the 3 non-error rows; "Aplicar"
      shows confirmation with count=3; if confirmed, calls
      `client.table(...).update(...)` with 3 update dicts (verify via
      temporary print, not real NocoDB call yet).
      Depends on: 11.2.2.

- [x] **11.2.4** Implement `modules/ai_corrections/module.py`.
      Steps:
      1. `register(app: MainWindow, client: NocoClient) -> None`:
         a. Create `ai_client = AIClient.from_config(app.config)`.
         b. Create `QStackedWidget screen`.
         c. Create `setup_view = SetupView(app.config, client,
            ai_client, app)`.
         d. Create placeholder `review_view = None` (created dynamically
            after analysis, since it needs the results).
         e. `screen.addWidget(setup_view)` (index 0).
         f. Connect `setup_view.analysis_ready`:
            ```python
            def on_analysis_ready(data):
                setup_view.process_records(data, on_complete=show_review)
            setup_view.analysis_ready.connect(on_analysis_ready)
            ```
         g. `show_review(results)`:
            - Remove existing review widget if any (index 1 of stack).
            - Create `review_view = ReviewView(app, client, results)`.
            - `review_view.back_requested.connect(lambda:
              screen.setCurrentIndex(0))`.
            - `screen.addWidget(review_view)`.
            - `screen.setCurrentIndex(1)`.
         h. Register with nav:
            ```python
            app.register_nav_item(
                module_id="ai_corrections",
                icon="fa5s.magic",
                label="AI Corrections",
                widget=screen,
                position="middle",
            )
            ```
      Verification: launch Tardis — AI Corrections icon appears in nav
      bar. Clicking it shows the Setup form. Selecting a table, fields,
      and clicking "Analizar" (confirming) triggers processing (progress
      bar visible). After processing, the Review screen appears. Clicking
      "← Volver" returns to Setup.
      Depends on: 11.2.3.

- [x] **11.2.5** **CHECKPOINT 2 — Full `ai_corrections` flow**:
      End-to-end test with a REAL NocoDB table (e.g. `DIR_LOCAL-MAIL`,
      field `title`, operation `correct`, 5 records):
      1. Navigate to AI Corrections in Tardis.
      2. Select `DIR_LOCAL-MAIL` table, field `title`, operation
         `correct`.
      3. Click "Analizar" → confirm → processing runs, progress bar
         advances.
      4. Review screen shows 5 rows with original `title` and AI
         suggestion.
      5. Accept 2 rows, click "Aplicar" → confirm → NocoDB is updated.
      6. Verify in NocoDB (via `scripts/diag_inbox.py` or UI) that
         those 2 records now have the corrected `title` values.
      7. Click "← Volver" → returns to Setup form.
      8. No crashes in `tardis.log` during any step.
      Depends on: 11.2.4.

### 11.3 — Final integration

- [x] **11.3.1** **CHECKPOINT FINAL (Phase 4b)**:
      Full end-to-end pass covering all modules:
      1. Launch Tardis — nav bar: LocalMail (top), PDF Export (middle),
         AI Corrections (middle), Settings (bottom).
      2. LocalMail: inbox loads, send email to 2 recipients, reader
         opens on single click, archive action works with toast.
      3. PDF Export: generate a `letter` PDF for `inorizonti` brand —
         toast + file opens.
      4. AI Corrections: correct 3 records in any table — all applied
         to NocoDB successfully.
      5. Settings > Modules: shows all 3 modules as Loaded.
      6. Settings > Connection: correct config values shown.
      7. Settings > Diagnostics: test notification sent and received in
         LocalMail inbox.
      8. No crashes. `tardis.log` has no ERROR-level entries (only DEBUG
         and INFO).
      9. Close and reopen Tardis — last active module restored.
      Depends on: 11.2.5.

- [ ] **11.3.2** Update `app_core/EXTENSION_POINTS.md` — add:
      - `register_nav_item(module_id, icon, label, widget, toolbar=None,
        position="middle")` full description with example.
      - Note that `add_dock_panel` is removed.
      - `ai_lib` usage pattern: `from ai_lib.ai_service import
        correct_value; ai_client = AIClient.from_config(app.config)`.
      - Warning: `generate_pdf` must be called from main thread (not
        `run_async`) — already documented, confirm it's still accurate.
      Depends on: 11.3.1.

---

## 5. Roadmap (reference only — not detailed yet)

- **Phase 5 — Quotations module**: see section 1.10.
- **Phase 6 — UI Reorganization + Visual Polish**: see section 1.10.
  Includes: new color scheme (TBD in Phase 6 spec), switchable
  themes, App Switcher expandable mode + overflow menu, LocalMail
  top toolbar, Settings > Appearance tab.