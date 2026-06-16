# SPEC — Tardis Phase 5: UI Polish + LocalMail Full Features

> Self-contained document. Any LLM can pick it up without prior context.
> **Execution rule**: complete tasks **one at a time, in listed order**.
> Each task has Context / Steps / Verification / Depends on.
> **After finishing a task, the LLM MUST mark it `[x]` before proceeding.**
> Do not skip a task whose dependency is not yet `[x]`.
>
> **Language rule**: all code comments, docstrings, README files, inline
> documentation, and user-facing strings written or updated during this
> phase MUST be in Spanish. Task descriptions in this spec are in English
> (for LLM clarity), but every artifact produced must be documented in
> Spanish.

---

## 0. Context recap (do not redesign)

- **Tardis** is a PySide6 desktop app. Modules in `modules/<name>/`,
  each exposes `register(app: MainWindow, client: NocoClient) -> None`.
- **Current state** (Phases 1–4b complete): three-pane LocalMail (sidebar
  tree + email list + reader), App Switcher nav bar (52px left column),
  PDF Export screen, AI Corrections screen, Settings screen. Theme is
  currently dark (black/near-black). No email actions beyond Archive and
  Move to Trash. No attachments. No signatures. No notifications.
- **`noco_lib`** / **`NocoResult`**: abstraction over NocoDB v2.
- **`ai_lib`** / **`AIResult`**: abstraction over Ollama.
- **`pdf_export`**: `generate_pdf` / `generate_html`.
- **Golden rule**: I/O calls run inside `run_async()`, never in the Qt
  main thread. Exception: `generate_pdf` (drives own QEventLoop).
- **Logging**: `logging.getLogger("tardis")`. All log messages in Spanish.
- **Extension points**: `register_nav_item`, `add_floating_window`,
  `add_menu_action`, `show_notification`.
- **`DIR_LOCAL-MAIL`** table (`id = "me0rcf5a8bhhyc0"`). Relevant fields
  for this phase: `Attachment` (NocoDB Attachment type), `reply_to_uuid`,
  `thread_uuid`, `folder`, `mailbox_owner`, `from`, `to`, `cc`.

---

## 1. Confirmed design decisions

### 1.1 Color scheme — "Inorizonti" theme (light)

Replaces the current dark theme completely. Token-based system:

| Token | Value | Usage |
|---|---|---|
| `color.bg.primary` | `#ffffff` | Main background, panels |
| `color.bg.secondary` | `#f5f3f0` | Sidebar, list pane backgrounds |
| `color.bg.tertiary` | `#ede9e4` | Hover states, selected row |
| `color.bg.accent` | `#e9290c` | Accent buttons, active nav icon, badges |
| `color.bg.accent.hover` | `#c5220a` | Hover on accent elements |
| `color.bg.accent.secondary` | `#f57c00` | Secondary accent, warnings |
| `color.text.primary` | `#1a1a18` | Body text, labels |
| `color.text.secondary` | `#5a5a56` | Muted text, timestamps, placeholders |
| `color.text.on.accent` | `#ffffff` | Text on red/orange backgrounds |
| `color.border.primary` | `#dddad6` | Dividers, input borders |
| `color.border.accent` | `#e9290c` | Active nav indicator, focus rings |
| `color.nav.bg` | `#f5f3f0` | NavBar background (light) |
| `color.nav.icon` | `#5a5a56` | Inactive nav icons |
| `color.nav.icon.active` | `#e9290c` | Active nav icon (red accent) |
| `color.success` | `#2e7d32` | Success toasts, confirmations |
| `color.error` | `#c62828` | Error toasts, validation |
| `color.warning` | `#f57c00` | Warning toasts |
| `color.info` | `#1565c0` | Info toasts |
| `color.unread.dot` | `#e9290c` | Unread email indicator dot |
| `color.priority.alta` | `#e9290c` | Priority Alta icon |
| `color.priority.media` | `#f57c00` | Priority Media icon |
| `color.priority.baja` | `#2e7d32` | Priority Baja icon |

Theme file: `app_core/themes/inorizonti.json`.
QSS is generated dynamically from the token file at startup.

### 1.2 NavBar in light theme

- Background: `color.nav.bg` (`#f5f3f0`).
- Right border: 1px solid `color.border.primary`.
- **Top section**: Inorizonti logo SVG (`shared/brands/inorizonti/logo.svg`)
  displayed above the module icons, constrained to 40px height, centered
  horizontally in the 52px bar. Below the logo, a thin red separator
  line (2px, `color.bg.accent`).
- Inactive icons: `color.nav.icon` (`#5a5a56`).
- Active icon: `color.nav.icon.active` (`#e9290c`) + 3px left border in
  `color.border.accent`.

### 1.3 LocalMail layout changes

**"+ Nuevo mensaje" button**: large red button (`color.bg.accent`,
white text, full width of the sidebar, 36px tall) positioned at the TOP
of the LocalMail sidebar, ABOVE the folder tree. Clicking it opens the
Composer floating window (existing behavior, just moved from the menu).

**Email reader action buttons**: always visible inside the reader pane,
in a horizontal bar at the TOP of the reader (above the email header
block). Buttons (left-to-right): Responder, Reenviar, Archivar,
Eliminar, Restaurar, Más (dropdown menu). Each button: icon on the left
(16×16px, qtawesome) + text label on the right, compact height (28px).
"Restaurar" is hidden when the current email's `folder` is not `archive`
or `trash`. "Más" opens a `QMenu` with additional actions (Phase 5: just
"Ver encabezados técnicos" showing raw field values — useful for debug).
All action buttons are disabled when no email is selected (reader shows
empty state).

### 1.4 Reply and Forward

**Responder**: opens Composer prefilled:
- `to` = `from` field of the original email.
- `subject` = `"Re: " + original.title` (if title already starts with
  `"Re: "`, do NOT add another prefix).
- `body` = `"\n\n---\n" + quote_body(original.body)` where
  `quote_body(text)` prepends `"> "` to each line.
- `reply_to_uuid` = `original.message_uuid`.
- `thread_uuid` = `original.thread_uuid`.

**Reenviar**: opens Composer prefilled:
- `to` = empty (user fills in).
- `subject` = `"Fwd: " + original.title`.
- `body` = `"\n\n--- Mensaje reenviado ---\n" + original.body` (no
  per-line quoting — full body inline).
- `reply_to_uuid` = `""` (new thread).
- `thread_uuid` = new `uuid4()` (independent thread).

`service.send_email` gains optional parameters `reply_to_uuid: str = ""`
and `thread_uuid_override: str | None = None` (if provided, uses this
instead of generating a new one).

### 1.5 Attachments

**Upload**: new function `noco_core.client.upload_attachment(file_path: str) -> NocoResult`
that POSTs to `/api/v2/storage/upload` with `multipart/form-data`. On
success, `result.data` = the NocoDB attachment object dict
`{"url": ..., "title": ..., "mimetype": ..., "size": ...}`.

**Sending with attachments**: `service.send_email` gains optional
parameter `attachments: list[str] | None = None` (list of local file
paths). Before creating the record, each file is uploaded via
`upload_attachment`; the resulting dicts are passed as the `Attachment`
field value in the record create call.

**File size limit**: 10MB per file (`TARDIS_MAX_ATTACHMENT_MB`, default
10). Validated BEFORE upload, with clear error if exceeded.

**In Composer**: "Adjuntar" button (paperclip icon) opens
`QFileDialog.getOpenFileNames`. Selected files shown as chips below the
body field (filename + size, "×" button to remove). Files uploaded only
on "Enviar", not before.

**In Reader**: if `email["Attachment"]` is not empty/null, show an
"Adjuntos" section below the body. Each attachment: filename + size +
"Abrir" button (opens with `os.startfile`) + "Descargar" button (opens
`QFileDialog.getSaveFileName` with the attachment filename as default,
then downloads via `requests.get(url)` to the chosen path).

### 1.6 Restore email

`service.restore_email(client, email_id: int, mailbox_id: str) -> NocoResult`:
`update([{"Id": email_id, "folder": "inbox",
"mailbox_owner": mailbox_id}])`.

In the reader action bar: "Restaurar" button visible and enabled only
when `current_email["folder"] in ("archive", "trash")`. On success:
show success toast + reload the email list.

### 1.7 Notifications

**Polling**: `app_core/notifier.py` — class `InboxNotifier(QObject)`:
- `QTimer` firing every `config.poll_interval_seconds` (default 60,
  read from `TARDIS_POLL_INTERVAL_SECONDS`).
- On each tick: `run_async(service.list_inbox, client,
  config.mailboxes, folder="inbox", only_unread=True,
  on_success=self._check_new)`.
- `_check_new(result)`: if `result.affected_count > self._last_count`:
  `new_count = result.affected_count - self._last_count`;
  fire `new_emails_arrived = Signal(int)` with `new_count`.
  Update `self._last_count = result.affected_count`.
- Started in `main.py` AFTER all modules are registered.

**Sound**: `QSoundEffect` (PySide6 built-in, no extra dependency) playing
`shared/sounds/notify.wav` (a short, pleasant notification sound, ~0.5s,
provided as a file). Configurable via Settings > Apariencia checkbox
"Sonido de notificación" (stored in `QSettings`).

**Taskbar flash**: `QApplication.alert(main_window, 0)` (0 = flash until
focused). Called only when `not main_window.isActiveWindow()`.

**Toast**: `main_window.show_notification(f"📬 {n} mensaje(s) nuevo(s)",
level="info", duration_ms=6000, action_label="Ver bandeja",
action_callback=lambda: activate_localmail_inbox())`.

### 1.8 Toast system extension

`MainWindow.show_notification(text, level, duration_ms, action_label=None,
action_callback=None)`:
- If `action_label` is provided, the `Toast` widget shows a small
  clickable button on the right side of the toast. Clicking it calls
  `action_callback()` and closes the toast.
- `Toast.mousePressEvent` (clicking anywhere on the toast body, not the
  button) also closes it immediately.

### 1.9 Email signatures

Storage: `tardis_signatures.json` in the project root (gitignored).
Structure:
```json
[
  {
    "id": "<uuid4>",
    "name": "Firma oficial Inorizonti",
    "mailbox": "alicia.gentil@inorizonti.com",
    "html": "<p>Alicia Gentil<br>...</p>",
    "include_logo": true,
    "logo_brand": "inorizonti",
    "is_default": true
  }
]
```

**Editor**: Settings > tab "Firmas". Left panel: list of signatures
(`QListWidget`). Right panel: form with fields Name, Mailbox (combo of
`config.mailboxes`), `QTextEdit` for HTML body, "Incluir logo de marca"
checkbox + brand combo (`bisstox`/`plyson`/`inorizonti`), "Es firma
predeterminada" checkbox. Buttons: "Nueva", "Guardar", "Eliminar".

**Preview**: below the editor form, a `QTextBrowser` showing a live
preview of the HTML (updated on every keystroke with 300ms debounce).
When "Incluir logo" is checked, the SVG is embedded inline in the preview.

**In Composer**: below the `body` field, a `QComboBox "Firma"` populated
with signatures whose `mailbox` matches the selected "Desde" combo. On
"Desde" change, repopulate. Default signature auto-inserted into body on
Composer open (appended after `"\n\n---\n"`). The user may edit or delete
it before sending. If no signatures exist for the selected mailbox, the
combo shows "(Sin firma)".

### 1.10 Phase 5b and Phase 6 (ROADMAP — not implemented here)

See section 5 (Roadmap).

---

## 2. New dependencies

```toml
# Already present: PySide6>=6.7 (includes QSoundEffect, no extra dep needed)
# No new pip dependencies required for Phase 5.
# shared/sounds/notify.wav must be provided (free CC0 sound file).
```

---

## 3. New / modified files overview

```
app_core/
  themes/
    inorizonti.json          # NEW: color token file
    theme_engine.py          # NEW: loads tokens, generates QSS string
  theming.py                  # MODIFIED: now calls theme_engine
  notifier.py                 # NEW: InboxNotifier polling class
  widgets/
    toast.py                  # MODIFIED: add action_label/action_callback
  styles/
    dark.qss                  # DELETED (replaced by theme_engine)

shared/
  sounds/
    notify.wav                # NEW: notification sound file

modules/
  localmail/
    service.py                # MODIFIED: send_email new params, restore_email, upload_attachment in noco_core
    views/
      sidebar_view.py         # MODIFIED: add "+ Nuevo mensaje" button
      reader_view.py          # MODIFIED: action bar, attachments section
      composer_view.py        # MODIFIED: reply/forward prefill, attachments, signatures
  settings/                   # (if refactored) or app_core/views/settings_view.py
    settings_view.py          # MODIFIED: add Firmas tab, Apariencia tab

noco_core/
  client.py                   # MODIFIED: add upload_attachment()
```

---

## 4. PLAN OF TASKS (checklist — execute in order, mark `[x]` when done)

### 12.0 — Theme system

- [x]**12.0.1** Create `app_core/themes/inorizonti.json` with all color
      tokens from section 1.1.
      Steps:
      1. Create `app_core/themes/` directory.
      2. Create `inorizonti.json` with a flat key-value dict where every
         key is a token name (e.g. `"color.bg.primary"`) and every value
         is a hex color string. Include ALL tokens from the table in
         section 1.1 — no omissions.
      3. Add a top-level key `"meta"`:
         ```json
         "meta": {
           "name": "Inorizonti",
           "description": "Tema oficial Inorizonti — claro con acento rojo",
           "version": "1.0",
           "author": "Tardis"
         }
         ```
      Verification: `python -m json.tool app_core/themes/inorizonti.json`
      exits 0. The file contains exactly the tokens listed in section 1.1
      (count: 21 color tokens + meta). All values are valid hex strings
      starting with `#`.
      Depends on: none.

- [x]**12.0.2** Create `app_core/themes/theme_engine.py`.
      Steps:
      1. Function `load_theme(theme_path: str) -> dict`:
         - Reads and parses the JSON file.
         - Returns the dict of tokens (excluding `"meta"`).
         - On `FileNotFoundError` or JSON error: log in Spanish via
           `logging.getLogger("tardis").error(...)`, return an empty dict
           (app will use Qt defaults — graceful degradation).
      2. Function `generate_qss(tokens: dict) -> str`:
         - Returns a complete QSS string for the Inorizonti theme.
         - Uses `tokens["color.bg.primary"]` etc. for all color values
           (no hardcoded hex in this function — all colors come from
           `tokens`).
         - QSS must cover AT MINIMUM these widgets with correct colors:
           `QMainWindow`, `QWidget`, `QScrollArea`, `QSplitter`,
           `QTreeWidget`, `QTreeWidgetItem`, `QTableWidget`,
           `QHeaderView`, `QPushButton`, `QPushButton#accentButton`
           (the red "+ Nuevo mensaje" button), `QLineEdit`,
           `QTextEdit`, `QPlainTextEdit`, `QComboBox`, `QLabel`,
           `QMenuBar`, `QMenu`, `QStatusBar`, `QTabWidget`,
           `QTabBar`, `QListWidget`, `QScrollBar`, `QProgressBar`,
           `QCheckBox`, `QToolTip`, `NavButton`, `NavButton:checked`.
         - `NavButton:checked` must use `color.border.accent` for the
           left border and `color.nav.icon.active` for the icon color
           (icon color is set via Python, not QSS — QSS sets background
           only; document this constraint in a Spanish comment).
         - `QPushButton#accentButton`:
           `background: <color.bg.accent>; color: <color.text.on.accent>;
           border-radius: 4px; font-weight: bold;`
           Hover: `background: <color.bg.accent.hover>`.
      3. Function `apply_theme(app: QApplication,
         theme_name: str = "inorizonti") -> None`:
         - Builds path `app_core/themes/<theme_name>.json`.
         - Calls `load_theme` → `generate_qss` → `app.setStyleSheet(qss)`.
         - Replaces the existing `app_core/theming.py` `apply_theme`
           function (update `theming.py` to delegate to
           `theme_engine.apply_theme`).
      Verification: launch Tardis — the app background is white/near-white
      (not dark), text is dark, buttons use the Inorizonti red accent.
      Confirm no widget has the old dark background. Check
      `logs/tardis.log` for any theme loading errors.
      Depends on: 12.0.1.

- [x]**12.0.3** Update `NavBar` and `NavButton` for the light theme.
      Steps:
      1. In `app_core/widgets/nav_bar.py`: add a TOP section (above the
         module icons scroll area) that displays the Inorizonti logo:
         - Read `shared/brands/inorizonti/logo.svg` as text.
         - Create a `QSvgWidget` (from `PySide6.QtSvgWidgets`) sized
           40×40px (or proportional to the logo's viewBox aspect ratio,
           constrained to 40px height, 48px max width).
         - Place it centered in the 52px NavBar with 6px top/bottom
           padding.
         - Below the logo: a `QFrame` with `setFrameShape(QFrame.HLine)`,
           height 2px, background `color.bg.accent` (set via
           `setStyleSheet("background: #e9290c; border: none;")`).
      2. In `app_core/widgets/nav_button.py`: update icon color to use
         `color.nav.icon` (`#5a5a56`) for inactive and re-set to
         `color.nav.icon.active` (`#e9290c`) when checked:
         ```python
         def _update_icon_color(self):
             color = "#e9290c" if self.isChecked() else "#5a5a56"
             self.setIcon(qta.icon(self._icon_name, color=color))
         ```
         Connect `toggled` signal to `_update_icon_color`.
      Verification: launch Tardis — NavBar has white/light background,
      Inorizonti logo visible at top, red separator line below logo,
      module icons are gray when inactive and turn red when clicked.
      Depends on: 12.0.2.

- [x]**12.0.4** Delete `app_core/styles/dark.qss` and update all
      references.
      Steps:
      1. Delete `app_core/styles/dark.qss`.
      2. `grep -r "dark.qss\|apply_theme.*dark" --include="*.py"` —
         fix every reference found (there should be only 1-2: in
         `theming.py` and `main.py`).
      3. Ensure `main.py` calls `apply_theme(app, "inorizonti")`.
      4. Delete `app_core/styles/` directory if it is now empty.
      Verification: `grep -r "dark.qss" --include="*.py"` returns 0
      results. App launches with the Inorizonti theme.
      Depends on: 12.0.3.

- [x]**12.0.5** **CHECKPOINT 0 — Theme complete**:
      Visual inspection pass:
      1. All panels (LocalMail three-pane, PDF Export form, AI Corrections
         form, Settings tabs) have light backgrounds.
      2. NavBar: logo top, red separator, gray icons turning red on
         activation.
      3. Action buttons (e.g. "Actualizar" in the email list) have
         appropriate styling (not the old dark style).
      4. Toast notifications (trigger one via Settings > Diagnósticos)
         display correctly on the light background.
      5. No widget appears with black background on a white surrounding
         (common issue: `QScrollBar`, `QHeaderView`, `QComboBox` dropdown
         — verify each explicitly).
      Depends on: 12.0.4.

### 12.1 — LocalMail sidebar: "+ Nuevo mensaje" button

- [x]**12.1.1** Add the "Nuevo mensaje" button to `SidebarTreeView`.
      Steps:
      1. In `modules/localmail/views/sidebar_view.py`, change the layout
         from a plain `QTreeWidget` filling the whole widget to a
         `QVBoxLayout` containing:
         - TOP: `QPushButton("＋  Nuevo mensaje")` with
           `setObjectName("accentButton")` (so QSS applies the red style
           from 12.0.2), fixed height 36px, full width, bold font.
         - BOTTOM (expanding): the existing `QTreeWidget`.
      2. Connect the button's `clicked` signal to a new signal
         `compose_requested = Signal()` on `SidebarTreeView`.
      3. In `modules/localmail/module.py`, connect
         `sidebar.compose_requested` to the existing "open Composer"
         logic (the same lambda that was previously in the menu action
         "LocalMail > Redactar").
      4. Remove the "LocalMail > Redactar" menu action (the button
         replaces it). Keep "LocalMail > Redactar" as a keyboard
         shortcut alternative only if the menu system is used elsewhere —
         if not, remove entirely.
      Verification: launch Tardis, navigate to LocalMail — a large red
      "+ Nuevo mensaje" button appears at the top of the sidebar, above
      the folder tree. Clicking it opens the Composer floating window.
      The button is styled with the red accent color and white text.
      Depends on: 12.0.5.

### 12.2 — Reader pane: action bar

- [x]**12.2.1** Implement the email action bar in `ReaderView`.
      Steps:
      1. In `modules/localmail/views/reader_view.py`, add an action bar
         `QWidget` at the TOP of the reader layout (above the email
         header block). Use `QHBoxLayout` with `spacing=4`,
         `contentsMargins=(8, 4, 8, 4)`.
      2. Create 6 action buttons using a helper function
         `_make_action_btn(icon_name: str, label: str) -> QPushButton`:
         - `QPushButton` with `QHBoxLayout` containing a `QLabel` with
           qtawesome icon (16×16px, color `#5a5a56`) + `QLabel` with
           text. Height: 28px. Flat style, hover background
           `color.bg.tertiary`. No `setObjectName("accentButton")` —
           these are neutral action buttons, not primary CTAs.
         - Buttons: `("fa5s.reply", "Responder")`,
           `("fa5s.share", "Reenviar")`,
           `("fa5s.archive", "Archivar")`,
           `("fa5s.trash", "Eliminar")`,
           `("fa5s.undo-alt", "Restaurar")`,
           `("fa5s.ellipsis-h", "Más")`.
      3. Add `QSpacerItem(expanding)` after the last button so buttons
         are left-aligned.
      4. "Más" button: `setMenu(QMenu())` with action
         "Ver encabezados técnicos" (shows a `QDialog` with a
         `QPlainTextEdit` (read-only) displaying all fields of the
         current email as formatted JSON — useful for debugging).
      5. Store button references as `self._btn_reply`,
         `self._btn_forward`, `self._btn_archive`, `self._btn_trash`,
         `self._btn_restore`, `self._btn_more`.
      6. Method `_update_action_bar_state(email: dict | None)`:
         - If `email is None`: disable ALL buttons.
         - Else: enable all buttons; hide `self._btn_restore` if
           `email.get("folder") not in ("archive", "trash")`; show it
           if folder IS archive or trash.
      7. Call `_update_action_bar_state(None)` on init (no email
         selected).
      8. Call `_update_action_bar_state(email)` every time
         `show_email(email_id)` successfully loads an email.
      Verification: launch Tardis — reader pane shows the action bar at
      the top. With no email selected: all buttons disabled/grayed.
      Select an email from Inbox: Responder, Reenviar, Archivar, Eliminar,
      Más enabled; Restaurar hidden. Select an email from Archive:
      Restaurar visible and enabled; Archivar still shown (can re-archive,
      acceptable). Click "Más" → menu shows "Ver encabezados técnicos".
      Depends on: 12.1.1.

- [x]**12.2.2** Wire action bar buttons to service functions.
      Steps:
      1. In `modules/localmail/module.py` (or in `reader_view.py` if
         `client` is accessible there — preferred: pass `client` and
         `config` to `ReaderView` constructor), connect each button:
         - `_btn_archive.clicked` → `run_async(service.archive_email,
           client, current_email_id, on_success=_on_archive_done)`.
           `_on_archive_done`: success toast "Correo archivado",
           reload email list, clear reader (call
           `_update_action_bar_state(None)`, show empty state).
         - `_btn_trash.clicked` → same pattern with
           `service.move_to_trash`, toast "Correo movido a papelera".
         - `_btn_restore.clicked` → `run_async(service.restore_email,
           client, current_email_id, config.mailboxes[0],
           on_success=_on_restore_done)`. Toast "Correo restaurado a
           bandeja de entrada", reload list, clear reader.
         - `_btn_reply` and `_btn_forward` wired in task 12.3.x.
      2. Store `self._current_email: dict | None = None` in `ReaderView`,
         set on every successful `show_email` load. Used by button
         handlers to get `current_email_id` and `folder`.
      Verification: select an inbox email → click "Archivar" → toast
      appears, email disappears from inbox list, reader shows empty state.
      Navigate to Archive folder → email appears there. Click it →
      "Restaurar" button visible → click → toast, email back in inbox.
      Navigate to inbox → email present.
      Depends on: 12.2.1.

### 12.3 — Reply and Forward

- [x]**12.3.1** Extend `service.send_email` with reply/thread parameters.
      Steps:
      1. In `modules/localmail/service.py`, update signature:
         ```python
         def send_email(
             client,
             from_user: str,
             to_users: list[str],
             subject: str,
             body: str,
             cc_users: list[str] | None = None,
             priority: str = "Media",
             reply_to_uuid: str = "",
             thread_uuid_override: str | None = None,
             attachments: list[str] | None = None,
         ) -> NocoResult:
         ```
      2. If `thread_uuid_override` is provided, use it instead of
         generating a new `uuid4()` for `thread_uuid`.
      3. If `reply_to_uuid` is provided, set it in the record; else `""`.
      4. `attachments` parameter handled in task 12.4.x (for now, accept
         the parameter but ignore it with a Spanish comment
         `# Adjuntos: implementado en tarea 12.4.1`).
      Verification: call `send_email(..., reply_to_uuid="abc123",
      thread_uuid_override="xyz789")` from a test script and confirm the
      created record has `reply_to_uuid="abc123"` and
      `thread_uuid="xyz789"` (verify via `scripts/diag_inbox.py` or
      direct NocoDB UI check).
      Depends on: 12.2.2.

- [x]**12.3.2** Implement "Responder" and "Reenviar" in `ComposerView`.
      Steps:
      1. Add factory class methods (or module-level functions) in
         `modules/localmail/views/composer_view.py`:
         ```python
         @classmethod
         def for_reply(cls, original_email: dict, client, config, main_window) -> "ComposerView":
             """Crea un Composer prellenado para responder un correo."""
         @classmethod
         def for_forward(cls, original_email: dict, client, config, main_window) -> "ComposerView":
             """Crea un Composer prellenado para reenviar un correo."""
         ```
      2. `for_reply`:
         - `to` = `original_email["from"]`.
         - `subject` = original subject prefixed with `"Re: "` only if
           not already starting with `"Re: "` (case-insensitive check).
         - `body` = `"\n\n---\n" + "\n".join("> " + line for line in
           original_email["body"].splitlines())`.
         - `self._reply_to_uuid = original_email["message_uuid"]`.
         - `self._thread_uuid_override = original_email["thread_uuid"]`.
      3. `for_forward`:
         - `to` = empty.
         - `subject` = `"Fwd: " + original_email["title"]` (same
           prefix-check, avoid `"Fwd: Fwd: ..."`).
         - `body` = `"\n\n--- Mensaje reenviado ---\n" +
           original_email["body"]`.
         - `self._reply_to_uuid = ""`.
         - `self._thread_uuid_override = None` (new thread UUID will be
           generated in `send_email`).
      4. In `_on_sent` / the send button handler, pass
         `reply_to_uuid=self._reply_to_uuid` and
         `thread_uuid_override=self._thread_uuid_override` to
         `service.send_email`.
      5. In `modules/localmail/module.py` (or `reader_view.py`), connect
         `_btn_reply.clicked`:
         ```python
         def _on_reply():
             composer = ComposerView.for_reply(
                 reader._current_email, client, config, app)
             app.add_floating_window(composer, "Responder")
         ```
         Same for `_btn_forward` using `for_forward`.
      Verification: select an email → click "Responder" → Composer opens
      with `to` filled (original sender), subject prefixed "Re: ", body
      shows quoted original. Send → check NocoDB record has correct
      `reply_to_uuid` and `thread_uuid`. Then click "Reenviar" → Composer
      opens with empty `to`, "Fwd: " prefix, body shows forwarded content.
      Depends on: 12.3.1.

### 12.4 — Attachments

- [x]**12.4.1** Add `upload_attachment` to `noco_core/client.py`.
      Steps:
      1. New method `upload_attachment(self, file_path: str) -> NocoResult`:
         - Check file exists: if not, `NocoResult.fail("create",
           f"Archivo no encontrado: {file_path}")`.
         - Check file size ≤ `TARDIS_MAX_ATTACHMENT_MB` MB: read from
           `os.environ.get("TARDIS_MAX_ATTACHMENT_MB", "10")`, convert to
           bytes. If exceeded: `NocoResult.fail("create",
           f"El archivo supera el límite de {limit_mb}MB: {file_path}")`.
         - Open file in binary mode, POST to
           `{self.base_url}/api/v2/storage/upload` with
           `files={"file": (filename, fh, mimetype)}` where `mimetype` is
           detected via `mimetypes.guess_type(file_path)[0] or
           "application/octet-stream"`.
         - On success: `NocoResult.ok("create", data=response.json(),
           affected_count=1)` where `response.json()` is the NocoDB
           attachment object.
         - On HTTP error or exception: `NocoResult.fail("create",
           [error_message])`.
      2. Update `noco_core/__init__.py` to export `upload_attachment` is
         available via the client instance (it's a method, so this is
         automatic — just ensure it's documented in a Spanish docstring).
      Verification: `scripts/test_upload.py` — upload a small test file
      (e.g. a 1KB text file) via `client.upload_attachment("test.txt")`.
      Confirm `result.success=True` and `result.data` contains `"url"`,
      `"title"`, `"mimetype"`, `"size"` keys. Confirm the file appears
      in NocoDB's storage (check NocoDB UI or the returned URL resolves).
      Depends on: 12.3.2.

- [x]**12.4.2** Add attachment support to `service.send_email`.
      Steps:
      1. In `modules/localmail/service.py`, implement the `attachments`
         parameter (now that `noco_core` supports upload):
         - Before the record create loop, for each path in `attachments`:
           call `client.upload_attachment(path)`. If `result.success`,
           add `result.data` to `attachment_objects: list[dict]`. If
           failure: add to `meta["attachment_errors"]` and continue
           (best-effort — don't fail the whole send if one attachment
           fails; warn via toast in the UI layer).
         - Pass `attachment_objects` as the `"Attachment"` field in the
           create record payload. If `attachment_objects` is empty, omit
           the field entirely (don't send `"Attachment": []` which might
           clear existing attachments on other records).
      2. Remove the placeholder comment from task 12.3.1.
      Verification: send an email with 1 attachment from a test script.
      Confirm via `scripts/diag_inbox.py` (add `Attachment` to the
      printed fields) or NocoDB UI that the created record has a non-null
      `Attachment` field with the uploaded file object. Also test
      sending with an oversized file (>10MB dummy) — confirm
      `send_email` returns a `NocoResult` with `meta["attachment_errors"]`
      populated and the email still sends (without the oversized
      attachment).
      Depends on: 12.4.1.

- [x]**12.4.3** Add attachment UI to `ComposerView`.
      Steps:
      1. Below the `body` field, add an "Adjuntos" section:
         - `QPushButton` with icon `fa5s.paperclip` + text "Adjuntar
           archivo" (neutral style, not accent).
         - `QWidget` `self._attachments_container` with `QVBoxLayout`
           (hidden initially, shown when ≥1 file added).
         - `self._attachment_paths: list[str] = []`.
      2. Button click: `QFileDialog.getOpenFileNames(self, "Seleccionar
         archivos", "", "Todos los archivos (*.*)")`. For each selected
         path, call `_add_attachment(path)`.
      3. `_add_attachment(path)`:
         - Check size (client-side, before upload): if >limit, show
           error toast "El archivo {name} supera el límite de {N}MB" and
           skip.
         - Create a chip widget: `QHBoxLayout` with `QLabel(filename +
           " (" + human_size + ")")` + `QPushButton("×")` (small, flat).
           "×" click calls `_remove_attachment(path)` and destroys the
           chip widget.
         - Add chip to `_attachments_container`, show container.
         - Append `path` to `self._attachment_paths`.
      4. In the send handler, pass `attachments=self._attachment_paths`
         to `service.send_email`.
      Verification: open Composer, click "Adjuntar archivo", select 2
      files — both appear as chips with "×" buttons. Remove one — chip
      disappears. Send the email — both uploaded files appear in NocoDB
      record (verify as in 12.4.2). Try attaching an oversized file —
      error toast appears, file NOT added to the list.
      Depends on: 12.4.2.

- [x]**12.4.4** Show attachments in `ReaderView`.
      Steps:
      1. In `modules/localmail/views/reader_view.py`, after the body
         `QTextBrowser`, add a collapsible "Adjuntos" section:
         - Only shown when `email.get("Attachment")` is not None/empty.
         - Header: `QLabel` "📎 Adjuntos (N)" where N = count.
         - For each attachment object in the list:
           - `QHBoxLayout` with:
             - `QLabel(title + " · " + human_readable_size(size))`.
             - `QPushButton("Abrir")` (icon `fa5s.external-link-alt`):
               `os.startfile(url)` on Windows,
               `subprocess.Popen(["xdg-open", url])` on Linux. Wrap in
               try/except, show error toast on failure.
             - `QPushButton("Descargar")` (icon `fa5s.download`):
               opens `QFileDialog.getSaveFileName` with `title` as
               default filename, then downloads via
               `run_async(_download_file, url, save_path)` where
               `_download_file` uses `requests.get(url, stream=True)`.
               On success: toast "Archivo descargado: {filename}".
         - `_download_file(url, save_path) -> NocoResult`: streams
           response to file in 8KB chunks. Returns `NocoResult.ok` or
           `NocoResult.fail`.
      2. `human_readable_size(bytes: int) -> str`: returns "1.2 KB",
         "3.4 MB" etc. (implement as a small utility function in a new
         `shared/utils.py` with a Spanish docstring).
      Verification: receive an email with an attachment (from 12.4.3
      test). Open it in the reader — "Adjuntos (1)" section appears.
      Click "Abrir" — file opens in system default app. Click "Descargar"
      — file dialog appears, save the file, toast confirms download.
      Depends on: 12.4.3.

### 12.5 — Notifications

- [x]**12.5.1** Add `notify.wav` to `shared/sounds/`.
      Steps:
      1. Create `shared/sounds/` directory.
      2. Source a short (≤1 second), pleasant notification sound in WAV
         format (PCM, 44100Hz, stereo or mono) under a CC0/public domain
         license. Options:
         - Generate programmatically using Python's `wave` module (a
           simple 440Hz sine wave, 0.3 seconds):
           ```python
           import wave, struct, math
           # Generate and save to shared/sounds/notify.wav
           ```
           This is the RECOMMENDED approach (no external download
           needed, fully reproducible).
         - Or use any CC0 WAV file available locally.
         Include a Spanish comment in the generation script (save it as
         `scripts/generate_notify_sound.py`) explaining the approach.
      Verification: `shared/sounds/notify.wav` exists, is a valid WAV
      file. `python -c "import wave; w=wave.open('shared/sounds/
      notify.wav'); print(w.getnframes())"` prints a positive integer.
      Depends on: none.

- [x]**12.5.2** Extend `Toast` widget with action button support.
      Steps:
      1. In `app_core/widgets/toast.py`, update `Toast.__init__` to
         accept `action_label: str | None = None` and
         `action_callback: Callable | None = None`.
      2. If `action_label` is provided:
         - Add a `QPushButton(action_label)` to the right side of the
           toast layout. Style: white text, transparent background,
           underlined or slightly bold (clear clickable affordance).
         - Button `clicked` → call `action_callback()` → close the toast
           (`self.close()`).
      3. `Toast.mousePressEvent`: clicking anywhere on the toast body
         (not the action button) also calls `self.close()`.
      4. Update `MainWindow.show_notification` signature:
         ```python
         def show_notification(
             self,
             text: str,
             level: str = "info",
             duration_ms: int = 4000,
             action_label: str | None = None,
             action_callback: Callable | None = None,
         ) -> None:
         ```
         Pass `action_label` and `action_callback` through to `Toast`.
      Verification: trigger a toast with action via a temporary debug
      call in `main.py`: `window.show_notification("Prueba con acción",
      "info", action_label="Abrir", action_callback=lambda:
      print("Acción ejecutada"))`. Confirm: toast appears, clicking
      "Abrir" prints the message and closes the toast, clicking elsewhere
      on the toast also closes it.
      Depends on: 12.0.5.

- [x]**12.5.3** Implement `app_core/notifier.py`.
      Steps:
      1. Class `InboxNotifier(QObject)`:
         - Constructor: `InboxNotifier(client, config: TardisConfig,
           main_window: MainWindow)`.
         - `self._last_count: int = 0`.
         - `self._timer = QTimer(self)`, interval =
           `config.poll_interval_seconds * 1000`.
           `config.poll_interval_seconds` read from
           `int(os.environ.get("TARDIS_POLL_INTERVAL_SECONDS", "60"))` —
           add this field to `TardisConfig` now.
         - `self._sound = QSoundEffect(self)`;
           `self._sound.setSource(QUrl.fromLocalFile(
           str(Path("shared/sounds/notify.wav").resolve())))`.
           Volume: 0.7.
         - `self._sound_enabled: bool` — read from
           `QSettings("Tardis", "Tardis").value(
           "notifications/sound_enabled", True, type=bool)`.
         - Signal `new_emails_arrived = Signal(int)` (emits count of new).
      2. Method `start()`: `self._timer.timeout.connect(self._poll)`;
         `self._timer.start()`. Do an immediate first poll with
         `QTimer.singleShot(2000, self._poll)` (2 second delay after
         startup to let the app fully initialize).
      3. Method `_poll()`:
         ```python
         run_async(
             service.list_inbox,
             self._client,
             self._config.mailboxes,
             folder="inbox",
             only_unread=True,
             on_success=self._check_new,
         )
         ```
      4. `_check_new(result: NocoResult)`:
         - If not `result.success`: log warning (Spanish), return.
         - `current_count = result.affected_count`.
         - If `current_count > self._last_count`:
           `new_count = current_count - self._last_count`
           `self.new_emails_arrived.emit(new_count)`.
         - `self._last_count = current_count`.
      5. Method `notify(new_count: int)` (connected to
         `new_emails_arrived` in `main.py`):
         - If `self._sound_enabled`: `self._sound.play()`.
         - If `not main_window.isActiveWindow()`:
           `QApplication.alert(main_window, 0)`.
         - `main_window.show_notification(
             f"📬 {new_count} mensaje(s) nuevo(s)",
             level="info",
             duration_ms=6000,
             action_label="Ver bandeja",
             action_callback=self._go_to_inbox,
           )`.
      6. `_go_to_inbox()`: calls `main_window._activate_module("localmail")`
         and then selects the "All Mailboxes > Inbox" node in the
         `SidebarTreeView` (expose a method
         `SidebarTreeView.select_node(node_id: str)` that programmatically
         selects and triggers the node).
      7. Method `set_sound_enabled(enabled: bool)`:
         `self._sound_enabled = enabled`;
         `QSettings("Tardis","Tardis").setValue(
         "notifications/sound_enabled", enabled)`.
      Verification: set `TARDIS_POLL_INTERVAL_SECONDS=10` in `.env` for
      testing. Send a test email to one of the configured mailboxes from
      `scripts/diag_inbox.py` or NocoDB UI. Within 10 seconds: toast
      appears with "📬 1 mensaje(s) nuevo(s)" and "Ver bandeja" button.
      If the window is not focused: taskbar icon flashes. If sound is
      enabled: sound plays. Clicking "Ver bandeja" activates LocalMail
      and selects Inbox. Check `tardis.log` for the polling log entries
      (should appear every 10 seconds during the test). Reset
      `TARDIS_POLL_INTERVAL_SECONDS=60` after testing.
      Depends on: 12.5.1, 12.5.2.

- [x]**12.5.4** Wire `InboxNotifier` in `main.py` and add Settings
      toggle.
      Steps:
      1. In `app_core/main.py`, after `window.show()`:
         ```python
         from app_core.notifier import InboxNotifier
         notifier = InboxNotifier(client, config, window)
         notifier.new_emails_arrived.connect(notifier.notify)
         notifier.start()
         ```
         Keep a reference (`window._notifier = notifier` or a local
         variable held by the QApplication event loop lifetime).
      2. In `app_core/views/settings_view.py`, add "Apariencia" tab with:
         - `QCheckBox("Reproducir sonido al recibir emails")` — checked
           by default. On `stateChanged`: call
           `notifier.set_sound_enabled(checked)`.
         - For now, just sound on/off. Phase 6 will add theme selector,
           font size, etc.
         - Since `SettingsView` is constructed in `main.py`, pass
           `notifier` to its constructor.
      Verification: launch Tardis, go to Settings > Apariencia, uncheck
      sound — send a test email → notification toast appears but NO sound.
      Re-check sound — next notification plays sound. Close and reopen
      Tardis — sound preference is remembered.
      Depends on: 12.5.3.

- [x]**12.5.5** **CHECKPOINT 1 — Notifications complete**:
      Full notification flow test:
      1. Sound plays on new email (window not focused).
      2. Taskbar flashes when window is not in the foreground.
      3. Toast shows correct message with "Ver bandeja" action.
      4. "Ver bandeja" action navigates to LocalMail Inbox.
      5. Sound toggle in Settings is persisted across restarts.
      6. No excessive polling log spam (each poll = 1 log line at DEBUG
         level).
      Depends on: 12.5.4.

### 12.6 — Email signatures

- [x]**12.6.1** Implement signature storage and loading utilities.
      Steps:
      1. Create `shared/utils.py` if it doesn't exist (it was mentioned
         in 12.4.4 for `human_readable_size` — add signatures logic here
         too, or create `modules/localmail/signatures.py` — PREFERRED
         location since signatures are LocalMail-specific):
         Create `modules/localmail/signatures.py`.
      2. `SIGNATURES_FILE = Path("tardis_signatures.json")`.
      3. `load_signatures() -> list[dict]`:
         - If file does not exist: return `[]`.
         - Parse JSON. On error: log Spanish warning, return `[]`.
      4. `save_signatures(signatures: list[dict]) -> None`:
         - Write JSON with `indent=2`, `ensure_ascii=False`.
         - On error: log Spanish error, re-raise (the UI layer shows a
           toast).
      5. `get_default_signature(mailbox: str) -> dict | None`:
         - Returns the first signature where `sig["mailbox"] == mailbox`
           and `sig["is_default"] == True`. Returns `None` if not found.
      6. `build_signature_html(sig: dict) -> str`:
         - If `sig["include_logo"]` and `sig["logo_brand"]`:
           read `shared/brands/{sig["logo_brand"]}/logo.svg` and embed
           inline: `f'<div class="firma-logo">{svg_content}</div>\n'`.
         - Append `sig["html"]`.
         - Return the combined string.
      Verification: `scripts/test_signatures.py` — create 2 test
      signatures via `save_signatures([...])`, call `load_signatures()`
      and confirm both are returned. Call `get_default_signature(...)`.
      Call `build_signature_html(sig_with_logo)` and confirm the output
      contains the SVG content + the HTML body.
      Depends on: 12.5.5.

- [x]**12.6.2** Implement signature editor in Settings.
      Steps:
      1. In `app_core/views/settings_view.py` (or wherever
         `SettingsView` lives), add a 4th tab "Firmas".
      2. Tab layout: `QSplitter(Qt.Horizontal)`:
         - LEFT (1/3 width): `QListWidget` `self._sig_list` showing
           `sig["name"]` for each signature, with `(predeterminada)` appended
           if `sig["is_default"]`. Buttons below the list: "Nueva",
           "Eliminar".
         - RIGHT (2/3 width): form fields stacked vertically:
           - `QLineEdit` "Nombre de la firma" → `sig["name"]`.
           - `QComboBox` "Casilla" populated with `config.mailboxes` →
             `sig["mailbox"]`.
           - `QCheckBox` "Firma predeterminada para esta casilla" →
             `sig["is_default"]`.
           - `QLabel` "Contenido HTML:" + `QTextEdit` (monospace font,
             min 6 lines) → `sig["html"]`.
           - `QHBoxLayout`: `QCheckBox "Incluir logo de marca"` +
             `QComboBox` with `["bisstox", "plyson", "inorizonti"]`
             (enabled only when checkbox checked).
           - `QPushButton("Guardar firma")` (accent red button).
           - `QLabel("Vista previa:")` + `QTextBrowser` showing live
             HTML preview (update on every `textChanged` of the
             `QTextEdit` with a 300ms `QTimer` debounce).
      3. "Nueva" button: clear form, set `sig["id"] = str(uuid4())`,
         focus Name field.
      4. "Eliminar" button: remove selected signature from list and file.
         Confirm with `QMessageBox.question` first.
      5. "Guardar firma" button:
         - Validate Name not empty.
         - If `is_default` is checked: set `is_default=False` for all
           other signatures with the same `mailbox` (only one default
           per mailbox).
         - Load signatures, update or append the current sig (match by
           `id`), save.
         - Refresh `_sig_list`.
      6. `_sig_list` selection change: populate form fields from the
         selected signature.
      Verification: open Settings > Firmas — list is empty. Click "Nueva"
      → form clears. Fill Name "Mi firma", select a mailbox, type some
      HTML, check "Es predeterminada", click "Guardar" → item appears in
      list with "(predeterminada)". Select it → form fields populated.
      Check "Incluir logo" and select "inorizonti" → preview shows SVG +
      HTML. Click "Eliminar" with confirmation → item removed.
      Depends on: 12.6.1.

- [x]**12.6.3** Add signature support to `ComposerView`.
      Steps:
      1. Below the `body` field (and above the attachments section), add:
         - `QHBoxLayout` with `QLabel("Firma:")` + `QComboBox`
           `self._sig_combo` (populated with signature names for the
           current "Desde" mailbox, plus "(Sin firma)" as first option).
      2. Method `_load_signatures_for_mailbox(mailbox: str)`:
         - `sigs = [s for s in load_signatures() if s["mailbox"] == mailbox]`.
         - `self._sig_combo.clear()`.
         - `self._sig_combo.addItem("(Sin firma)", userData=None)`.
         - For each sig: `self._sig_combo.addItem(sig["name"],
           userData=sig)`.
         - Select the default signature if one exists (find by
           `get_default_signature(mailbox)`) and call
           `_apply_signature(sig)`.
      3. `_apply_signature(sig: dict | None)`:
         - If `sig is None`: remove any previously appended signature
           from the body (search for the separator `"\n\n---\n"` and
           truncate at that point if the content after it looks like a
           signature — i.e. it was auto-inserted, not user-typed).
           Simplification: store `self._signature_start_pos: int | None`
           when inserting; use it to truncate on removal.
         - If `sig` is not None: append `"\n\n---\n" +
           build_signature_html(sig)` to the body. Store the cursor
           position before the separator as `self._signature_start_pos`.
      4. Connect `self._from_combo.currentTextChanged` to call
         `_load_signatures_for_mailbox(new_mailbox)`.
      5. Connect `self._sig_combo.currentIndexChanged` to call
         `_apply_signature(self._sig_combo.currentData())`.
      6. On Composer init: call `_load_signatures_for_mailbox(
         config.mailboxes[0] if config.mailboxes else "")`.
      Verification: open Composer with a mailbox that has a default
      signature → body field shows the signature auto-appended after the
      separator. Change "Desde" to a mailbox with no signature → body
      signature section removed. Change "Firma" combo to a different
      signature → body updates. Select "(Sin firma)" → signature removed.
      Depends on: 12.6.2.

### 12.7 — Final integration checkpoint

- [x]**12.7.1** **CHECKPOINT FINAL (Phase 5)**:
      Full end-to-end test covering all new features:
      1. **Theme**: all panels light (white/near-white), NavBar shows
         Inorizonti logo + red separator + gray icons turning red when
         active.
      2. **"+ Nuevo mensaje"**: large red button at top of LocalMail
         sidebar opens Composer.
      3. **Reader actions**: select Inbox email → Responder/Reenviar/
         Archivar/Eliminar enabled, Restaurar hidden. Archive it →
         appears in Archive, Restaurar now visible → restore → back in
         Inbox.
      4. **Reply**: reply to an email → Composer prellenado correctly
         → send → record has correct `reply_to_uuid` / `thread_uuid`.
      5. **Forward**: forward an email → Composer with "Fwd: " prefix,
         empty `to` → send successfully.
      6. **Attachments send**: compose new email, attach 2 files → send
         → NocoDB record has `Attachment` field with 2 objects.
      7. **Attachments view**: open email with attachments → "Adjuntos
         (2)" section appears → "Abrir" opens file → "Descargar" saves
         file with toast confirmation.
      8. **Notifications**: set poll to 10s, receive a new email from
         external source → toast appears within 10s, sound plays, taskbar
         flashes (if window unfocused). "Ver bandeja" navigates to Inbox.
      9. **Signatures**: create a signature in Settings > Firmas with
         Inorizonti logo → open Composer → signature auto-appears → send
         → body in NocoDB record contains the signature HTML.
      10. **No crashes** during the full pass. `tardis.log` has no
          unhandled exceptions.
      Depends on: 12.6.3.

- [x]**12.7.2** Update all documentation in Spanish.
      Steps:
      1. Update `app_core/EXTENSION_POINTS.md` — add:
         - `show_notification` with new `action_label`/`action_callback`
           parameters (with Spanish example usage).
         - `InboxNotifier` usage pattern for modules that want to trigger
           notifications (they should call `service.notify()` via
           LocalMail, NOT directly use `InboxNotifier`).
         - Signature utilities: `load_signatures()`,
           `get_default_signature()`, `build_signature_html()` —
           documented for use by future modules that might compose emails
           programmatically (e.g. Quotations in Phase 6).
      2. Update `modules/localmail/README.md` — add Spanish descriptions
         of all new functions in `service.py` (reply params, restore,
         attachment upload).
      3. Add `tardis_signatures.json` to `.gitignore`.
      4. Update `.env.example` with `TARDIS_POLL_INTERVAL_SECONDS=60`
         and `TARDIS_MAX_ATTACHMENT_MB=10`.
      Depends on: 12.7.1.

---

## 5. ROADMAP (not implemented in this phase — documented for future specs)

### Phase 5b — Tab system (standalone spec pending)
A `QTabWidget` wrapper for the LocalMail screen enabling:
- One permanent "Bandeja de entrada" tab.
- Opening emails in individual tabs via double-click on the list.
- Multiple mailbox/folder tabs open simultaneously.
- Tab close button (×) on each non-permanent tab.
- Extension point for other modules to open content in tabs.
The three-pane `QSplitter` widget is already structured to be easily
wrapped in `QTabWidget` — the refactor should be minimal.

### Phase 6 — Quotations module (`modules/quotations/`)
- Nav item: `module_id="quotations"`, `icon="fa5s.file-invoice-dollar"`.
- NocoDB table: `COT_QUOTATIONS` (configurable via
  `TARDIS_QUOTATIONS_TABLE`).
- Screen: quotation list + "Nueva cotización" button (in-screen form,
  not floating).
- Form: client info + line items (description, qty, unit price,
  subtotal auto-calculated), totals section.
- "Generar PDF" → `generate_pdf(data, brand, output_path)` with
  `doc_type="quote"`. Opens in floating preview window.
- "Enviar por LocalMail" → `service.send_email(...)` with PDF attached
  (uses `client.upload_attachment` implemented in Phase 5).
- Will be the canonical "mature module" example for
  `app_core/EXTENSION_POINTS.md`.

### Phase 7 — Advanced UI (standalone spec pending)
- App Switcher expandable mode: click/double-click toggles 52px →
  180px width with icon + text labels. State persisted in `QSettings`.
- App Switcher overflow: "···" QMenu for modules beyond visible area.
  Pin/unpin via Settings > Módulos drag-and-drop reorder.
- Settings > Apariencia: theme selector (Inorizonti / future themes),
  font size slider, accent color picker.
- Full token-based theme system: multiple `theme_name.json` files;
  live theme switching without restart.
- LocalMail top toolbar (`QToolBar` above three-pane): Redactar, Responder,
  Reenviar, Archivar, Eliminar, Actualizar, Buscar — contextual
  enable/disable. Registered via `toolbar` parameter of
  `register_nav_item` (parameter already exists, just not wired yet).

### Unread count badge on nav icon (post-Phase 5)
- The LocalMail nav icon should show a red badge with the unread count
  (similar to Thunderbird's "12" on the Inbox). `InboxNotifier` already
  computes this count — it needs to be surfaced on the `NavButton`.
- `NavButton.set_badge(count: int | None)`: renders a small circular
  overlay on the icon. `count=None` hides the badge.

### Thread view (future)
- Grouping emails by `thread_uuid` in the list view (collapsed thread
  rows, expandable). Requires a `list_thread(client, thread_uuid)`
  function in `service.py` and UI changes to `EmailListView`.

### Draft saving (future)
- `ComposerView` auto-saves to `DIR_LOCAL-MAIL` with `folder="drafts"`
  every 30 seconds while composing. "Drafts" folder in the sidebar
  shows saved drafts. Opening a draft reopens the Composer with content.