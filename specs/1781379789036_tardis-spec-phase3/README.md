# SPEC — Tardis Phase 3 (Hardening + Three-Pane Layout + Extension Points)

> Self-contained document for any LLM to pick up without prior context.
> **Execution rule**: complete tasks **one at a time, in listed order**.
> Each task has Context / Steps / Verification / Depends on.
> **After finishing a task, the LLM MUST mark it `[x]` in this document
> before moving to the next one — this is mandatory, not optional.**
> Do not skip a task whose dependency is not yet `[x]`.

---

## 0. Context recap (do not redesign)

- **`noco_lib`**: abstraction layer over NocoDB v2. Universal contract
  `NocoResult(success, operation, table, data, affected_count, errors,
  meta)`. `client.table("DIR_LOCAL-MAIL")` never raises; if unresolved,
  any method returns `NocoResult.fail(...)`.
- **`DIR_LOCAL-MAIL`** table (`table.id = "me0rcf5a8bhhyc0"`). Key fields:
  `title, body, from, to, cc, bcc, bco, priority (Baja/Media/Alta),
  labels, read (Checkbox), read_date, message_source, synced
  (Checkbox), synced_date, Attachment, message_uuid, thread_uuid,
  reply_to_uuid, mailbox_owner, folder
  (inbox/sent/drafts/archive/trash), schema_version, notify_enabled
  (Checkbox), notify_remind_after, client_updated_at, sync_status,
  external_message_id, CreatedAt, UpdatedAt`.
- **Golden rule**: NO call to `noco_lib` ever happens outside
  `run_async()`.
- **`TardisConfig.mailboxes: list[str]`**: parsed from
  `TARDIS_MAILBOXES` (`;`-separated). May be empty — must be handled
  gracefully (message, no network call).
- **`service.py` (modules/localmail/service.py)** already implements:
  `list_inbox`, `list_sent`, `list_trash`, `get_email`, `mark_as_read`,
  `archive_email`, `move_to_trash`, `send_email`, `notify`. All return
  `NocoResult`. Signatures all take `mailboxes: list[str]` or similar —
  DO NOT change these signatures in Phase 3 unless a task explicitly says
  so.

---

## 1. Confirmed design decisions for Phase 3 (from stakeholder review)

1. Sidebar tree: top-level nodes = each mailbox in `TARDIS_MAILBOXES`,
   children = fixed folders: Inbox, Sent, Archive, Trash, Drafts (Drafts
   has no real functionality yet, just appears).
2. Additional root node **"All Mailboxes"** aggregating Inbox/Sent/etc.
   across all configured mailboxes (unified view, like Thunderbird's
   "Unified Folders").
3. On startup, auto-select **"All Mailboxes > Inbox"**, OR the last
   selected node remembered via `QSettings` if one exists.
4. Tree shows an **unread count badge** next to each "Inbox" node,
   updated on refresh.
5. Email list (center pane) columns: **Priority (icon), From, Subject,
   Date** — same as Phase 1/2, no new columns in Phase 3.
6. The old separate dock-panel tabs ("Inbox/Sent/Trash" as independent
   docks) are **removed and replaced** by the tree + single list,
   reusing `service.py` unchanged.
7. Filter bar above the list: free-text search (matches `title`/`from`)
   + priority combo (All/Baja/Media/Alta). No date/label filters in
   Phase 3.
8. **No** multi-select / bulk actions in Phase 3 (future phase).
9. List refresh is **manual**: "Refresh" button + automatically on tree
   node click. No polling/auto-refresh in Phase 3.
10. The three panes use `QSplitter`s; sizes are persisted via
    `QSettings`.
11. **No** Reply/Forward in Phase 3. Reader stays read actions only
    (Archive / Move to Trash).
12. Composer remains a **floating window** (not embedded in the
    three-pane).
13. Introduce an icon package (`qtawesome`) for folder/priority/toolbar
    icons.
14. Module Admin panel and theming from Phase 2 remain structurally
    unchanged. Phase 3 is LocalMail three-pane + generic extension
    points (not LocalMail-specific) for future modules.
15. Phase 4 order: `pdf_export` first, then `ai_lib`/`ai_corrections`.
16. Phase 5 (Quotations module) roadmap: quotation form (client + line
    items from a NocoDB table) → export to PDF via `pdf_export` → send
    PDF to client via LocalMail (attachment) — canonical "mature module"
    example using all three pillars (`noco_lib`, `pdf_export`,
    `localmail`).
17. Sidebar tree must have a generic extension mechanism: future modules
    can register their own top-level nodes (not only dock panels).

---

## 2. New findings requiring fixes (Phase 2.5 — Hardening, done FIRST)

Manual testing of Phase 2 found:

- **A**: App sometimes crashes silently with NO console output —
  especially when opening an email (double-click) or when running
  "Dummy > Send test notification". No clear pattern.
- **B**: Inbox shows emails, but opening them in the Reader sometimes
  requires repeated double-clicks.
- **C**: Reader shows content very basically; marks as read only when it
  actually succeeds in opening.
- **D**: Sent view only loads on manual "Refresh" click — acceptable for
  Phase 3 if the tree-click triggers refresh automatically.
- **E**: Composer "Send" leaves the form populated instead of closing;
  Inbox needs manual "Refresh" to show the new email — acceptable
  short-term, but Composer must close on success in Phase 3.
- **F**: No toast/visual notification system exists at all (errors only
  go to status bar, if anything).
- **G**: Floating Composer: closing with unsaved content does NOT prompt
  for discard confirmation; geometry (size/position) is NOT remembered.

A and B/C are very likely the SAME root cause: an unhandled exception
inside a `run_async` callback (or inside a Qt slot connected to a signal)
that is being silently swallowed, leaving the UI in an inconsistent state
or crashing the Qt event loop without a Python traceback being printed.
**Task 9.0.1 must fix this BEFORE anything else**, since debugging
everything downstream depends on having visible error logs.

---

## 3. PLAN OF TASKS (checklist — execute in order, mark `[x]` when done)

### 9.0 — Hardening (MUST be done first)

- [x] **9.0.1** Add global exception logging.
      Context: Findings A/B/C suggest unhandled exceptions are crashing
      the app or silently breaking callbacks, with nothing printed to
      console.
      Steps:
      1. Create `app_core/logging_setup.py` with a function
         `setup_logging(log_dir: str | None = None) -> None` that:
         - Configures Python's `logging` module to write to BOTH stdout
           AND a rotating file `tardis.log` (use
           `logging.handlers.RotatingFileHandler`, max 2MB, 3 backups).
           Default `log_dir` = a `logs/` folder next to the executable /
           project root.
         - Sets level `DEBUG` for a logger named `"tardis"`, `INFO` for
           root.
      2. In `app_core/main.py`, call `setup_logging()` as the VERY FIRST
         line (before `QApplication` is created).
      3. Install a global Qt exception hook: override
         `sys.excepthook = <handler>` where `<handler>` logs the full
         traceback via `logging.getLogger("tardis").exception(...)` and
         does NOT silently exit — re-raise or call the default hook after
         logging, so behavior (crash or not) is unchanged but now LOGGED.
      4. In `app_core/concurrency.py` `run_async`/`QRunnable.run`: wrap
         the call to `fn(*args, **kwargs)` in `try/except Exception`,
         log the full traceback via `logging.getLogger("tardis").exception(...)`
         BEFORE calling `on_error` (if provided). Currently if
         `on_error` is `None` and an exception occurs, it's likely
         silently lost — fix this so it's always logged regardless of
         whether `on_error` is provided.
      5. In every Qt slot connected via `.connect(...)` inside
         `modules/localmail/views/*.py` (inbox/sent/trash list double-click
         handler, composer send button, reader load), wrap the slot body
         in `try/except Exception` that logs via
         `logging.getLogger("tardis").exception(...)`. This is a temporary
         safety net while diagnosing — DO NOT remove these try/except
         blocks after diagnosis; keep them as permanent defensive logging
         since UI slots should never propagate exceptions into Qt's
         C++ event loop (that's what causes silent native crashes with no
         Python traceback).
      Verification: run Tardis, deliberately trigger the crash scenarios
      (open an email via double-click repeatedly, run "Dummy > Send test
      notification" repeatedly). Confirm `logs/tardis.log` is created and
      contains either (a) no errors if the action now works cleanly, or
      (b) a full Python traceback if an exception occurs — in EITHER
      case, the app must no longer crash with zero output.
      Depends on: none.

- [x] **9.0.2** Diagnose and fix the actual crash/double-click root cause
      using the logs from 9.0.1.
      Context: with logging now in place, reproduce the crash.
      Steps:
      1. Run Tardis, open `logs/tardis.log` in a separate terminal
         (`tail -f` equivalent), double-click an email in the Inbox.
      2. If a traceback appears: read it, identify the failing line
         (likely candidates: a signal connected to a slot whose
         signature doesn't match the emitted signal's arguments — e.g.
         `email_selected = Signal(int)` but the slot expects a dict or
         no args; or `reader.show_email(email_id)` being called with a
         wrong type for `email_id`, e.g. a `QModelIndex` instead of
         `int`).
      3. Fix the root cause at its source (correct signal/slot signature
         mismatch, correct type conversion, add missing `None` checks
         on `result.data` before indexing, etc.).
      4. If NO traceback appears in the log but the app still
         crashes/closes: this points to a NATIVE Qt crash (e.g. a
         QWidget being garbage-collected while still referenced by Qt,
         common when a locally-scoped widget is created without keeping
         a reference on `self`). Audit `InboxView`, `ReaderView`,
         `ComposerView`, and `module.py` for any widget created without
         being stored as `self.<name> = ...` (especially inside
         lambdas/closures passed to `.connect()` or `run_async`).
         Fix by storing references on the owning object.
      Verification: double-click 5 different emails in a row in the
      Inbox — each one opens in the Reader without crashing, without
      requiring repeated clicks, and `read`/`read_date` are updated in
      NocoDB for each (verify with `scripts/diag_inbox.py` or by
      re-checking the list — read emails should render differently, e.g.
      not bold, per existing Phase 1/2 styling).
      Depends on: 9.0.1.

- [x] **9.0.3** Fix "Dummy > Send test notification" crash.
      Context: Finding A also mentions this action sometimes crashes.
      Steps:
      1. With logging active (9.0.1), trigger "Dummy > Send test
         notification" 5 times in a row.
      2. Apply the same diagnosis approach as 9.0.2 (Python traceback in
         log → fix root cause; no traceback → audit for widget/lifetime
         issues in `modules/dummy_notify_test/module.py`, particularly
         the `on_success` lambda passed to `run_async` — ensure it does
         not reference `self` or local widgets that may have been
         deallocated, and that `app.show_notification(...)` is safe to
         call from the callback).
      Verification: trigger the action 5 times consecutively without any
      crash; each triggers a log entry (success or handled error) in
      `tardis.log`.
      Depends on: 9.0.2.

- [x] **9.0.4** Build a minimal toast notification system (addresses
      Finding F, required by later tasks).
      Context: `MainWindow.show_notification(text, level)` currently
      likely only uses the status bar (per Phase 2 spec, minimal
      implementation). We need a small floating toast widget.
      Steps:
      1. Create `app_core/widgets/toast.py` with a class `Toast(QWidget)`:
         - Frameless, translucent background, rounded rectangle
           background colored per level (`info` = blue-ish, `error` =
           red-ish, `success` = green-ish), white/light text.
         - Positioned at the bottom-right corner of the parent
           `MainWindow`, with a small margin (e.g. 16px).
         - Auto-closes after a configurable duration (default 4000ms)
           using `QTimer.singleShot`.
         - If multiple toasts are shown in quick succession, stack them
           vertically (each new toast appears above the previous,
           shifting up; when one closes, the ones above shift down) —
           keep this simple: a list of active toasts on `MainWindow`,
           reposition all on add/remove.
      2. Update `MainWindow.show_notification(text: str, level: str =
         "info", duration_ms: int = 4000)`:
         - Keep existing status bar behavior for accessibility/logging
           (optional, can keep both), AND additionally instantiate and
           show a `Toast`.
      Verification: call `main_window.show_notification("Test message",
      "success")`, `("Test error", "error")`, and `("Test info",
      "info")` in quick succession (e.g. via a temporary debug menu
      action or directly after startup) — three toasts appear stacked in
      the bottom-right corner with correct colors, and disappear after ~4
      seconds without errors in `tardis.log`.
      Depends on: 9.0.1.

- [x] **9.0.5** **CHECKPOINT 0**: Re-run the full Phase 2 smoke test (9
      points from the previous verification list) with logging active.
      All 9 points should now pass cleanly: double-click opens reader
      reliably (9.0.2), Dummy notify doesn't crash (9.0.3), and toasts
      appearing for key actions is NOT required yet (that's wired into
      later tasks) — but no crashes at all should occur during this full
      pass.
      Depends on: 9.0.2, 9.0.3, 9.0.4.


### 9.1 — Sidebar tree data model (foundation for three-pane)

- [x] **9.1.1** Define the sidebar tree data structure.
      Context: Before building the QTreeWidget UI, define the data shape
      that represents tree nodes, independent of Qt, so it's testable and
      extensible (decision 17).
      Steps:
      1. Create `app_core/sidebar/tree_model.py` with a dataclass:
         ```python
         @dataclass
         class SidebarNode:
             id: str                 # unique key, e.g. "all:inbox", "alicia.gentil@inorizonti.com:sent"
             label: str               # display text, e.g. "Inbox", "Sent"
             icon: str | None         # qtawesome icon name, e.g. "fa5s.inbox"
             node_type: str           # "mailbox" | "folder" | "module_root" | "module_item"
             mailboxes: list[str]     # which mailbox(es) this node queries (empty for module nodes)
             folder: str | None       # "inbox"|"sent"|"archive"|"trash"|"drafts"|None
             children: list["SidebarNode"] = field(default_factory=list)
             badge_count: int | None = None  # unread count, only for folder="inbox" nodes
         ```
      2. Implement `build_localmail_tree(mailboxes: list[str]) -> SidebarNode`
         that returns the ROOT node containing:
         - `SidebarNode(id="all", label="All Mailboxes", node_type="mailbox", mailboxes=mailboxes, children=[...])`
           where children are folder nodes Inbox/Sent/Archive/Trash/Drafts,
           each with `mailboxes=mailboxes` and the corresponding `folder`
           value. Drafts has `folder="drafts"` but is otherwise
           structurally identical.
         - For each mailbox `m` in `mailboxes`: a
           `SidebarNode(id=m, label=m, node_type="mailbox", mailboxes=[m], children=[same 5 folder nodes scoped to [m]])`.
      3. `id` format for folder nodes: `f"{scope}:{folder}"` where
         `scope` is `"all"` or the mailbox address.
      Verification: write a small standalone test (e.g.
      `scripts/test_tree_model.py`) that calls
      `build_localmail_tree(["a@x.com", "b@y.com"])` and asserts: root has
      3 top-level children ("All Mailboxes", "a@x.com", "b@y.com"); each
      has 5 children (Inbox/Sent/Archive/Trash/Drafts); IDs are unique
      across the whole tree (no collisions). Print the tree structure for
      manual inspection.
      Depends on: 9.0.5.

- [x] **9.1.2** Implement extension point for module-contributed sidebar
      nodes (decision 17).
      Context: future modules (e.g. Quotations in Phase 5) may want a
      top-level sidebar entry.
      Steps:
      1. Add to `app_core/main_window.py`:
         ```python
         def add_sidebar_node(self, node: SidebarNode) -> None:
             """Registers an additional top-level node in the sidebar
             tree, contributed by a module. Must be called during
             module registration (register(app, client)), before the
             sidebar widget is built/shown."""
         ```
      2. `MainWindow` collects these in a list
         `self._extra_sidebar_nodes: list[SidebarNode] = []` during
         module registration (module_registry runs BEFORE the sidebar
         widget is constructed — confirm/adjust `main.py` ordering: 1)
         create `MainWindow` (without sidebar yet, or with empty
         sidebar), 2) `discover_and_register(...)` so modules can call
         `add_sidebar_node`, 3) THEN build/populate the sidebar widget
         using `build_localmail_tree(...)` PLUS `self._extra_sidebar_nodes`
         as additional top-level siblings).
      3. Document this ordering requirement with a comment in
         `main.py`.
      Verification: in `modules/dummy_notify_test/module.py`, temporarily
      call `app.add_sidebar_node(SidebarNode(id="dummy_root",
      label="Dummy Module", icon="fa5s.flask", node_type="module_root",
      mailboxes=[], children=[]))` and confirm (after 9.2.x builds the
      actual tree widget) that a 4th top-level node "Dummy Module"
      appears alongside "All Mailboxes" and the mailbox nodes. Remove
      this temporary call after confirming (leave the `add_sidebar_node`
      API itself in place — just remove the dummy registration, or leave
      it commented with a note "example usage").
      Depends on: 9.1.1.

### 9.2 — Three-pane layout shell

- [x] **9.2.1** Install `qtawesome` and verify it renders.
      Steps:
      1. Add `qtawesome` to `pyproject.toml` dependencies, run
         `pip install -e .` (or equivalent).
      2. In a throwaway script or temporary menu action, render a
         `QPushButton` with `qta.icon('fa5s.inbox')` as its icon and
         confirm it displays correctly with the dark theme applied
         (Phase 2's `apply_theme`).
      Verification: icon visible, correctly colored (not a black box on
      dark background — if contrast is bad, set icon color explicitly via
      `qta.icon('fa5s.inbox', color='#e0e0e0')` matching the `dark.qss`
      text color variable).
      Depends on: 9.1.2.

- [x] **9.2.2** Build `modules/localmail/views/sidebar_view.py`
      (`SidebarTreeView`).
      Steps:
      1. `QTreeWidget` (or `QTreeView` + custom model — `QTreeWidget` is
         simpler for Phase 3) populated from `build_localmail_tree(...)`
         plus any `extra_sidebar_nodes`.
      2. Each `QTreeWidgetItem` stores its `SidebarNode.id` via
         `setData(0, Qt.UserRole, node.id)` and the full node object via
         `setData(0, Qt.UserRole + 1, node)`.
      3. Set icons per `node_type`/`folder` using `qtawesome`:
         Inbox=`fa5s.inbox`, Sent=`fa5s.paper-plane`,
         Archive=`fa5s.archive`, Trash=`fa5s.trash`,
         Drafts=`fa5s.file-alt`, mailbox root=`fa5s.envelope`,
         "All Mailboxes"=`fa5s.layer-group`.
      4. Signal `node_selected = Signal(object)` emitting the
         `SidebarNode` when a tree item is clicked (single click, not
         double — folder navigation should be single-click per standard
         mail clients).
      5. Method `refresh_unread_counts(client, main_window)`: for every
         node where `node.folder == "inbox"`, call (via `run_async`)
         `service.list_inbox(client, node.mailboxes, folder="inbox",
         only_unread=True)` and set `node.badge_count =
         result.affected_count if result.success else None`; update the
         displayed label to `f"{node.label} ({badge_count})"` if
         `badge_count` and `badge_count > 0`, else just `node.label`.
         This issues ONE `run_async` call per inbox-type node (there are
         `1 + len(mailboxes)` such nodes) — acceptable for Phase 3 given
         manual refresh only (decision 9).
      Verification: tree renders with correct icons, 1 + N top-level
      nodes (N = number of mailboxes) each with 5 children; clicking any
      node emits `node_selected` (verify via temporary `print` or log).
      Depends on: 9.2.1, 9.1.2.

- [x] **9.2.3** Build the main three-pane shell in `main_window.py` (or a
      new `app_core/views/three_pane_view.py` composed into
      `MainWindow`).
      Steps:
      1. Create `QSplitter(Qt.Horizontal)` with 3 children:
         - Left: `SidebarTreeView` (from 9.2.2).
         - Center: container `QWidget` with a `QVBoxLayout` holding (top
           to bottom): filter bar (placeholder for now, built in 9.3.3) +
           email list table (placeholder, built in 9.3.1).
         - Right: `ReaderView` (existing from Phase 1/2, to be updated in
           9.4).
      2. Set initial proportions roughly `[1, 2, 2]` (sidebar narrower).
      3. Persist splitter sizes via `QSettings("Tardis", "Tardis")`, key
         `"three_pane/splitter_sizes"`, saved on
         `MainWindow.closeEvent` and restored on construction (mirrors
         the floating-window geometry pattern from Phase 2 — reuse the
         same `QSettings` instance/organization).
      4. Register this three-pane widget as the CENTRAL WIDGET of
         `MainWindow` (`self.setCentralWidget(three_pane_widget)`),
         REMOVING the old separate dock panels for Inbox/Sent/Trash from
         `modules/localmail/module.py` (decision 6). The "Reader" dock
         panel from Phase 1/2 is also removed as a separate dock — it's
         now the right pane.
      5. Update `modules/localmail/module.py`: `register(app, client)`
         now constructs the three-pane components (sidebar, list,
         reader, filter bar) and wires them together (selection →
         list refresh; list row click → reader), instead of creating
         separate dock panels. Keep `add_menu_action` entries for
         "Compose" (floating Composer) and remove menu actions that
         referenced the old Inbox/Sent/Trash dock panels (their
         functionality is now the sidebar tree).
      Verification: app launches showing ONE main view with 3 resizable
      panes (sidebar | list | reader), no leftover separate dock tabs for
      Inbox/Sent/Trash. Resizing panes and restarting the app preserves
      proportions.
      Depends on: 9.2.2.

### 9.3 — Email list pane

- [x] **9.3.1** Implement `modules/localmail/views/email_list_view.py`
      (`EmailListView`), replacing the old `InboxView` table portion.
      Steps:
      1. `QTableWidget` (or `QTableView`) with columns: Priority (icon),
         From, Subject, Date — per decision 5.
      2. Method `load(client, mailboxes: list[str], folder: str | None)`:
         - If `mailboxes == []`: show the "No mailboxes configured..."
           message (decision/Phase 2 behavior preserved) and return
           without calling `run_async`.
         - Map `folder` to the right service call: `folder is None` →
           error (should not happen, sidebar always provides a folder);
           `folder == "sent"` → `service.list_sent(client, mailboxes)`;
           `folder == "trash"` → `service.list_trash(client, mailboxes)`;
           otherwise (`inbox`/`archive`/`drafts`) →
           `service.list_inbox(client, mailboxes, folder=folder)`.
         - On success, populate rows; store `Id` of each row via
           `setData(Qt.UserRole)` on the first cell for later retrieval.
         - On failure, show `result.errors[0]` via
           `main_window.show_notification(..., "error")` (now a toast,
           per 9.0.4) AND clear the table.
      3. Signal `email_selected = Signal(int)` emitted on row click
         (single click — three-pane clients typically use single click
         for list→reader, double-click reserved for opening in a separate
         window which Phase 3 does not implement). This is the FIX for
         Finding B (no more double-click requirement).
      4. "Refresh" button above the table, calls `load(...)` again with
         the currently active `mailboxes`/`folder` (store them as
         `self._current_mailboxes`/`self._current_folder` after each
         `load`).
      5. Priority column renders a colored icon (qtawesome `fa5s.circle`
         colored red/yellow/green for Alta/Media/Baja — or any clear
         visual mapping) instead of plain text.
      Verification: standalone instantiation (e.g. temporarily wired in
      `module.py`) with `mailboxes=["alicia.gentil@inorizonti.com"]`,
      `folder="sent"` shows real rows with priority icons; clicking a row
      emits `email_selected` with the correct `Id` (log/print
      temporarily to confirm, then remove).
      Depends on: 9.2.3, 9.0.4.

- [x] **9.3.2** Wire sidebar → list.
      Steps:
      1. In `modules/localmail/module.py`, connect
         `sidebar.node_selected` to a handler that:
         - Skips nodes where `node.folder is None` (e.g. mailbox-root
           nodes that are not directly clickable as folders — if
           `QTreeWidget` allows clicking parent nodes, either make them
           non-selectable/expand-only, or handle gracefully by doing
           nothing).
         - Calls `email_list.load(client, node.mailboxes, node.folder)`.
         - Persists `node.id` to `QSettings` key
           `"three_pane/last_selected_node"` for restoring on next
           launch (decision 3).
      2. On `MainWindow` construction (after sidebar+list are built), read
         `"three_pane/last_selected_node"`; if present and a matching
         node exists in the tree, select it programmatically and trigger
         the same load; otherwise default-select the "All Mailboxes >
         Inbox" node.
      Verification: clicking different tree nodes updates the list with
      the correct data (verified against `scripts/diag_inbox.py` output
      for at least 2 different mailbox/folder combinations). Restarting
      the app re-selects the last-used node.
      Depends on: 9.3.1, 9.2.2.

- [x] **9.3.3** Implement the filter bar.
      Steps:
      1. Create `modules/localmail/views/filter_bar.py`
         (`FilterBarView`): `QLineEdit` (search placeholder "Search
         subject or sender...") + `QComboBox` (`["All", "Baja", "Media",
         "Alta"]`, default "All") + the existing "Refresh" button (move
         it here from 9.3.1 if it makes more sense layout-wise, or keep
         it in the list view — choose ONE location and document it in a
         code comment).
      2. Filtering is done CLIENT-SIDE on the already-loaded
         `result.data` (no new `where` clauses / API calls) —
         `EmailListView` keeps the full unfiltered dataset in
         `self._all_rows` and a method
         `apply_filter(search_text: str, priority: str)` that
         repopulates the visible table from `self._all_rows` filtered by:
         `search_text.lower() in title.lower() or search_text.lower() in
         from_field.lower()` (if `search_text` non-empty) AND
         `priority == "All" or row["priority"] == priority`.
      3. Connect `QLineEdit.textChanged` and `QComboBox.currentTextChanged`
         to call `apply_filter(...)` — live filtering, no need to press
         Enter/Refresh.
      4. "Refresh" button re-fetches from the API (calls `load(...)`
         again) AND re-applies current filter values afterward.
      Verification: with a folder loaded showing N emails, typing part of
      a known subject reduces the visible rows to matches in real time;
      selecting "Alta" priority shows only Alta-priority rows; clearing
      the search box and resetting priority to "All" restores all N rows
      without a new API call (confirm via a temporary log line in
      `load()` that it's NOT called again during filtering).
      Depends on: 9.3.2.

### 9.4 — Reader pane improvements

- [ ] **9.4.1** Fix mark-as-read reliability (Finding C).
      Steps:
      1. In `ReaderView.show_email(email_id)`, ensure the
         `run_async(service.get_email, ...)` callback ALWAYS attempts
         `run_async(service.mark_as_read, client, email_id, ...)` as a
         SEPARATE, independent call — do not chain it such that a failure
         in rendering the email body prevents marking as read (these are
         two independent concerns). Order: (a) fetch+render email body
         first (so the user sees content immediately), (b) fire-and-forget
         `mark_as_read` regardless of render outcome, as long as
         `get_email` itself succeeded (i.e., the email exists).
      2. After a successful `mark_as_read`, emit a signal
         `email_read = Signal(int)` from `ReaderView` so
         `EmailListView` can update that row's visual state (e.g. remove
         bold) WITHOUT a full reload — connect this in `module.py`.
      Verification: open 5 different unread emails one after another
      (single click per 9.3.1's `email_selected`); all 5 become
      visually "read" (not bold) in the list immediately, without
      clicking "Refresh", and `read_date` is set in NocoDB for all 5
      (spot-check 1-2 via `scripts/diag_inbox.py`).
      Depends on: 9.3.2, 9.0.2.

- [ ] **9.4.2** Improve reader content rendering (Finding C: "very
      basic").
      Steps:
      1. `ReaderView` layout, top to bottom:
         - Header block (non-editable `QLabel`s or a small `QFormLayout`):
           Subject (`title`, larger/bold font), From (`from`), To (`to`),
           Cc (`cc`, only shown if non-empty), Date (`CreatedAt`,
           formatted human-readably e.g. `"2026-05-29 21:18"` — parse
           with `datetime.fromisoformat` and `.strftime("%Y-%m-%d %H:%M")`),
           Priority (as colored badge/icon matching list view).
         - Separator (`QFrame` with `HLine`).
         - Body: `QTextBrowser` with `setPlainText(body)` — Phase 3 stays
           plain text (no HTML rendering yet, that's a future
           enhancement), but ensure long bodies scroll properly and
           preserve line breaks (plain text in `QTextBrowser` does this
           by default).
      2. Action buttons row (top or bottom of reader): "Archive", "Move
         to Trash" — call `run_async(service.archive_email/move_to_trash,
         ...)`, on success show a toast ("Email archived"/"Moved to
         trash") AND trigger `EmailListView.load(...)` again with current
         mailboxes/folder (since the email should disappear from the
         current view if it was Inbox→Archive, etc.) — OR if the current
         folder IS Archive/Trash already and the action doesn't apply,
         disable the corresponding button (e.g. "Move to Trash" disabled
         when viewing an email already in Trash).
      3. Empty state: when no email is selected, show centered text
         "Select an email to read it." (existing Phase 1/2 behavior,
         keep it).
      Verification: select an email — header fields display correctly
      formatted; click "Archive" — toast appears, email disappears from
      an Inbox-folder list view (if that was the active view) without
      manual refresh; reopen "All Mailboxes > Archive" and confirm it now
      appears there.
      Depends on: 9.4.1, 9.0.4.

### 9.5 — Composer fixes

- [ ] **9.5.1** Fix Composer close-on-success (Finding E).
      Steps:
      1. In `ComposerView._on_sent(result)`: if `result.success`, call
         `self.close()` (or the parent floating window's close) AFTER
         showing a success toast via `main_window.show_notification("Email
         sent", "success")` (per 9.0.4 — this satisfies Finding F's
         "toast for send feedback would be desirable").
      2. After closing, trigger `EmailListView.load(...)` for the
         CURRENTLY SELECTED sidebar node IF the current folder is
         `"sent"` or `"inbox"` (covers the common cases of checking your
         own Sent folder or a self-addressed test email); otherwise do
         nothing (manual refresh still works for other cases, acceptable).
      Verification: send an email — toast "Email sent" appears, Composer
      window closes automatically, form does NOT remain populated.
      Depends on: 9.0.4, 9.3.3.

- [ ] **9.5.2** Fix Composer discard confirmation + geometry persistence
      (Finding G).
      Steps:
      1. Override `closeEvent(self, event)` in the Composer's floating
         window wrapper (or `ComposerView` itself if it IS the window):
         - Check if `to_field`, `subject_field`, `body_field` (after
           `.strip()`) have ANY non-empty content.
         - If yes AND the close was NOT triggered by a successful send
           (use an internal flag `self._sent_successfully = True` set in
           9.5.1 before calling `close()`, checked here and bypassing the
           prompt if `True`), show
           `QMessageBox.question(self, "Discard draft?", "You have
           unsent content. Discard this email?", QMessageBox.Yes |
           QMessageBox.No)`. If `No`, call `event.ignore()` and return.
      2. Geometry persistence: on successful close (either path), call
         `settings.setValue("floating/Compose/geometry",
         self.saveGeometry())`. On Composer creation (in
         `add_floating_window` or in `ComposerView.__init__`), check for
         `settings.value("floating/Compose/geometry")` and call
         `self.restoreGeometry(value)` if present. (This generalizes the
         Phase 2 floating-geometry mechanism, which may not have been
         fully wired for the Composer specifically — verify and connect
         it now.)
      Verification: (a) type a subject, click the window's close button →
      confirmation dialog appears; click "No" → window stays open; click
      "Yes" → window closes. (b) Resize/move the Composer, send an email
      successfully (closes via 9.5.1, no prompt) → reopen Composer → size
      and position match the previous session.
      Depends on: 9.5.1.

### 9.6 — Final integration checkpoint

- [ ] **9.6.1** **CHECKPOINT FINAL (Phase 3)**: full end-to-end pass:
      1. Launch Tardis — no console/log errors (9.0.x), three-pane layout
         visible, last-selected node restored (or "All Mailboxes > Inbox"
         on first run).
      2. Sidebar shows "All Mailboxes" + one node per configured mailbox,
         each with 5 folders, Inbox nodes show unread badges after
         clicking "Refresh"/loading.
      3. Click through at least 3 different sidebar nodes (different
         mailbox/folder combos) — list updates correctly each time.
      4. Type in the search box and change priority filter — list filters
         live without new API calls.
      5. Single-click 5 different unread emails in a row — each opens in
         the reader reliably (no repeated clicks needed), each becomes
         "read" in the list immediately.
      6. From the reader, Archive one email — toast appears, email
         disappears from current view, appears in that mailbox's Archive
         folder.
      7. Open Composer, move/resize it, type a subject, try to close —
         confirmation prompt appears; cancel, then send a real email to 2
         recipients — success toast appears, window closes automatically,
         form is gone.
      8. Reopen Composer — geometry matches step 7's window
         size/position.
      9. Run "Dummy > Send test notification" 3 times in a row — no
         crashes, each logged in `tardis.log`.
      10. (Decision 17 check) If the temporary `add_sidebar_node` example
          from 9.1.2 was left active, confirm "Dummy Module" node appears
          in the sidebar; otherwise confirm the API exists and is
          documented even if unused.
      Depends on: 9.5.2, 9.4.2, 9.3.3.

- [ ] **9.6.2** Update `modules/localmail/README.md` and create
      `app_core/EXTENSION_POINTS.md` summarizing, for future module
      authors:
      - `MainWindow.add_dock_panel/add_floating_window/add_menu_action/
        add_toolbar_action/show_notification(text, level, duration_ms)`
        (now with toast support).
      - `MainWindow.add_sidebar_node(node: SidebarNode)` and the
        `SidebarNode` dataclass shape (9.1.1), including the registration
        ordering requirement (must be called during `register(app,
        client)`, before sidebar is built).
      - The logging convention from 9.0.1: modules should use
        `logging.getLogger("tardis").exception(...)` in any Qt slot that
        could raise.
      - Reference to `modules/localmail/service.py` functions as the
        pattern for any module needing to send notifications via
        LocalMail (`service.notify(...)`).
      Depends on: 9.6.1.

---

## 4. Roadmap (Phase 4 and beyond — reference only, not detailed yet)

- **Phase 4a — `pdf_export` module**: standalone module using
  QtWebEngine (`printToPdf`) + Jinja2 templates + `pikepdf` footer
  overlay (page X of Y, custom footer data). Reads source data via
  `noco_lib` from a configurable table. Own detailed spec to be written
  when Phase 3 is complete.
- **Phase 4b — `ai_lib` + `ai_corrections` module**: new abstraction
  layer (`AIResult`, mirroring `NocoResult`) + a module that reads
  records via `noco_lib`, sends them to `ai_lib` for correction/
  suggestions, and writes back via `noco_lib` with user confirmation. Own
  detailed spec to be written after Phase 4a.
- **Phase 5 — Quotations module (`modules/quotations/`)**: the first
  "mature module" combining all three pillars:
  1. Quotation form: client + line items, sourced from a NocoDB table
     (TBD which table — to be defined in Phase 5 spec).
  2. PDF generation via `pdf_export` (Phase 4a) using a quotation-specific
     template (with footer page numbering).
  3. Sending the generated PDF to the client via LocalMail
     (`service.send_email` with an attachment — note: `DIR_LOCAL-MAIL`
     already has an `Attachment` field, unused so far; Phase 5 spec must
     define how `noco_lib`/`service.py` attaches files to a record).
  4. Will also serve as the reference example for
     `app_core/EXTENSION_POINTS.md` (9.6.2), demonstrating sidebar node
     registration, dock panels, floating windows, and LocalMail
     notifications all together.