# Tardis Extension Points & Module Authoring Guide

This document summarizes the extension points available in the Tardis core application for future module authors.

## 1. UI Integration APIs (`MainWindow`)

The main window class (`MainWindow`) exposes several key methods to allow modules to integrate components into the main interface.

### Docking and Floating Windows

*   `MainWindow.add_dock_panel(widget: QWidget, title: str, area: str = "left") -> CDockWidget`
    Creates a dockable panel containing the provided widget and adds it to the central dock manager in the specified area (`"left"`, `"right"`, `"top"`, `"bottom"`, or `"center"`).
*   `MainWindow.add_floating_window(widget: QWidget, title: str) -> CDockWidget`
    Creates an independent floating window wrapping the provided widget. Features:
    *   **Custom Close Handling**: Automatically enabled on the floating dock wrapper to intercept titlebar closing and propagate it to the child widget via `close()`.
    *   **Geometry Persistence**: Automatically saves and restores the floating container's size and position from the QSettings key `floating/<title>/geometry` (or `floating/Compose/geometry` for `"Redactar correo"`).

### Menus, Toolbars, and Notifications

*   `MainWindow.add_menu_action(menu_path: str, label: str, callback: Callable) -> None`
    Adds an option to the main window's menu system using a nested route syntax, e.g. `"LocalMail > Redactar"`.
*   `MainWindow.add_toolbar_action(icon_or_text, label: str, callback: Callable) -> None`
    Adds an action button to the application toolbar (reserved for global shortcuts).
*   `MainWindow.show_notification(text: str, level: str = "info", duration_ms: int = 4000) -> None`
    Displays a modern, animated "Toast" notification in the bottom right corner of the application window. Supported levels are `"success"`, `"info"`, `"warning"`, and `"error"`.

---

## 2. Sidebar Integration & Ordering Requirements

Modules can add custom items to the main left navigation sidebar.

### SidebarNode Structure

The sidebar uses a tree structure populated with `SidebarNode` objects:

```python
@dataclass
class SidebarNode:
    id: str                 # Unique key, e.g. "all:inbox", "custom_module_root"
    label: str               # Display text shown in the sidebar
    icon: str | None         # QtAwesome icon identifier, e.g. "fa5s.inbox"
    node_type: str           # "mailbox" | "folder" | "module_root" | "module_item"
    mailboxes: list[str]     # List of mailboxes queried (empty for non-mail nodes)
    folder: str | None       # Target folder ("inbox", "sent", etc., or None)
    children: list["SidebarNode"] = field(default_factory=list)
    badge_count: int | None = None  # Optional unread count badge
```

### Adding a Sidebar Node

To add a sidebar node, use:
```python
MainWindow.add_sidebar_node(node: SidebarNode)
```

> [!IMPORTANT]
> **Registration Ordering Requirement**:
> `add_sidebar_node` MUST be called inside the module's `register(app, client)` function *before* the main sidebar tree structure is constructed. The main application builds the tree model after module registration is complete.

---

## 3. Logging & Exception Conventions

To ensure stability, modules must catch all exceptions within Qt slot functions and prevent crashes from propagating to the global handler:

*   **Convention**: Inside any Qt slot that could raise, use a `try-except` block and log the exception with `logging.getLogger("tardis").exception(...)`.
*   **Example**:
    ```python
    def on_button_clicked(self) -> None:
        try:
            # Dangerous Qt/business logic
            ...
        except Exception as e:
            logging.getLogger("tardis").exception("Error during button action execution")
    ```

---

## 4. Sending Notifications via LocalMail

Any module requiring the ability to dispatch notifications to the LocalMail inbox should use the helper functions in `modules/localmail/service.py`:

*   **Notify API**: Use `service.notify(client, to_user, subject, body, priority)` to dynamically create a message entry under the `"inbox"` folder of a specific recipient user in NocoDB.
*   **Example**:
    ```python
    from modules.localmail import service
    
    service.notify(
        client=noco_client,
        to_user="alice.gentil@inorizonti.com",
        subject="System Alert",
        body="A critical event has occurred in the backup process.",
        priority="Alta"
    )
    ```

---

## 5. PDF Export Module (`modules/pdf_export`)

The PDF Export engine generates branded PDF documents from structured JSON data using Jinja2 templates, QtWebEngine's `printToPdf`, and pikepdf post-processing.

### Public API

```python
from modules.pdf_export.engine import generate_pdf, generate_html, validate_document
```

#### `validate_document(data: dict) -> NocoResult`

Validates a document data dict against the JSON Schema at
`shared/schemas/document_schema.json`.

*   **Returns** `NocoResult.ok("schema", data={"valid": True})` on success.
*   **Returns** `NocoResult.fail("schema", errors=[...])` listing every validation error on failure.

#### `generate_html(data: dict, brand: str) -> NocoResult`

Renders a full HTML document string from structured data and a brand name.
The output includes inlined CSS (base, grid, components, print, brand) so that
QtWebEngine can render it without external resource resolution.

*   **Returns** `NocoResult.ok("read", data={"html": "<full HTML string>"})` on success.
*   **Returns** `NocoResult.fail(...)` on validation failure or missing resources.
*   **Safe to call from any thread** — it only performs CPU/file I/O.

#### `generate_pdf(data: dict, brand: str, output_path: str, printer: ChromiumPrinter, open_after: bool = False) -> NocoResult`

Full-pipeline PDF generation: validates, renders HTML, prints to PDF via
QtWebEngine, and stamps "Página X de Y" on every page.

*   **Returns** `NocoResult.ok("create", data={"path": output_path, "pages": N}, meta={...})` on success.
*   **Must be called from the Qt main thread.** This function drives its own internal
    `QEventLoop` to wait for the async `printToPdf` operation — do NOT call it from
    a background thread, `run_async`, `QRunnable`, or similar.
*   **The `printer` argument** requires a `ChromiumPrinter` instance with a
    `QWebEngineView` already set via `printer.set_view(view)`. The view should be a
    single shared hidden instance created at module startup, not created per call.

### Usage Example

```python
from pathlib import Path
from modules.pdf_export.engine import generate_pdf, generate_html, validate_document
from modules.pdf_export.chromium_printer import ChromiumPrinter
from PySide6.QtWebEngineWidgets import QWebEngineView

data = {
    "brand": "bisstox",
    "doc_type": "letter",
    "document": {
        "title": "Carta de presentación",
        "din": "DIN-LTR-001",
        "date": "2026-06-14",
        "contact": {"name": "Cliente"},
        "sections": [
            {"type": "text", "content": "Estimado cliente, ..."},
        ],
    },
}

# Validate first (optional — generate_pdf also validates internally)
val_result = validate_document(data)
if not val_result.success:
    print("Validation errors:", val_result.errors)

# Generate HTML only (safe from any thread)
html_result = generate_html(data, "bisstox")
if html_result.success:
    print(f"HTML generated: {len(html_result.data['html'])} chars")

# Generate PDF (MUST be called from Qt main thread)
view = QWebEngineView()          # Create once, reuse
printer = ChromiumPrinter()
printer.set_view(view)

result = generate_pdf(
    data=data,
    brand="bisstox",
    output_path="/tmp/documento.pdf",
    printer=printer,
    open_after=False,  # Set True to open the file automatically
)

if result.success:
    print(f"PDF generated: {result.data['pages']} page(s) at {result.data['path']}")
    print(f"Meta: {result.meta}")  # {brand, doc_type, din}
```

### `data` Dict Structure

The `data` dict follows the JSON Schema at `shared/schemas/document_schema.json`.
Key fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `brand` | `str` | Yes | Brand slug: `"bisstox"`, `"plyson"`, or `"inorizonti"` |
| `doc_type` | `str` | Yes | Document type: `report`, `technical_report`, `support_ticket`, `delivery_act`, `letter`, `communication`, `minutes`, `quote`, `manual`, `checklist` |
| `audience` | `str` | No | `"external"` (default), `"internal"`, `"confidential"`, or `"draft"` |
| `orientation` | `str` | No | `"portrait"` (default) or `"landscape"` |
| `has_cover` | `bool` | No | Whether to render a cover page (default `false`) |
| `compact_header` | `bool` | No | Use compact single-row header (default `false`) |
| `document` | `object` | Yes | The document payload (see below) |
| `footer` | `object` | No | Footer overrides (highest priority) |

### `document` Object

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | `str` | Yes | Document title |
| `din` | `str` | Yes | Document Identification Number |
| `date` | `str` | No | Date in YYYY-MM-DD format (defaults to today) |
| `contact` | `object` | Yes | Must have at least `{"name": "..."}` |
| `status` | `str` | No | `"draft"`, `"final"`, `"review"`, `"approved"`, `"rejected"` |
| `reference` | `str` | No | External reference (e.g. ticket number) |
| `owner_name` | `str` | No | Responsible person |
| `sections` | `array` | No | List of section objects (see below) |

### Supported Section Types

Each section has a `type` field and type-specific fields:

| `type` | Key Fields |
|---|---|
| `text` | `content` (plain text, auto-escaped) |
| `html` | `content` (raw HTML, inserted via `| safe`) |
| `markdown` | `content` (Markdown, rendered via mistune) |
| `table` | `headers: [str]`, `rows: [[str]]`, `caption?` |
| `checklist` | `items: [{text, checked: bool, note?}]` |
| `callout` | `level: info\|warning\|error\|success`, `body`, `title?` |
| `indicator` | `label`, `value`, `unit?`, `trend?: up\|down\|neutral` |
| `divider` | `label?` (section title in the rule line) |
| `page_break` | _(no fields)_ — forces a page break in the PDF |
| `signature_block` | `signers: [{name, role, date?}]` |

All section types optionally accept `title`, `kicker`, and `cols` (1–12, for grid layout).

### ⚠️ Threading Warning

`generate_pdf()` **must** be called from the Qt main thread. It drives its own
internal `QEventLoop` to bridge QtWebEngine's async `printToPdf` callback.
This keeps the UI responsive (Qt continues processing events), but the function
itself blocks — do NOT call it from `run_async`, `QRunnable`, or any background
thread.

`generate_html()` and `validate_document()` are safe to call from any thread
as they only perform CPU and file I/O.
