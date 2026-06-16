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
*   `MainWindow.show_notification(text: str, level: str = "info", duration_ms: int = 4000, action_label: str | None = None, action_callback: Callable | None = None) -> None`
    Displays a modern, animated "Toast" notification in the bottom right corner of the application window. Supported levels are `"success"`, `"info"`, `"warning"`, and `"error"`.
    *   **Nuevo en Fase 5**: Los parámetros `action_label` y `action_callback` permiten agregar un botón de acción a la notificación. Al hacer clic en el botón, se ejecuta el callback y el toast se cierra.
    *   **Ejemplo**:
        ```python
        main_window.show_notification(
            "📬 3 mensaje(s) nuevo(s)",
            level="info",
            duration_ms=6000,
            action_label="Ver bandeja",
            action_callback=lambda: activate_inbox()
        )
        ```
    *   Al hacer clic en cualquier parte del cuerpo del toast (fuera del botón de acción), el toast se cierra inmediatamente.

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

## 4. Inbox Notifier (`app_core/notifier.py`)

El `InboxNotifier` monitorea periódicamente la bandeja de entrada de las casillas
configuradas y emite notificaciones cuando llegan nuevos correos.

### Cómo se inicia

En `app_core/main.py`, después de que todos los módulos estén registrados:

```python
from app_core.notifier import InboxNotifier
notifier = InboxNotifier(client, config, window)
notifier.new_emails_arrived.connect(notifier.notify)
notifier.start()
window._notifier = notifier
```

### Funcionalidades

- **Sondeo periódico**: Consulta la bandeja de entrada cada `poll_interval_seconds`
  (configurable via `TARDIS_POLL_INTERVAL_SECONDS`, default 60).
- **Sonido**: Reproduce `shared/sounds/notify.wav` al detectar nuevos correos.
  Se puede activar/desactivar desde Settings > Apariencia.
- **Destello en barra de tareas**: Si la ventana no está enfocada, llama a
  `QApplication.alert()` para hacer destellar el icono en la barra de tareas.
- **Toast con acción**: Muestra una notificación Toast con botón "Ver bandeja"
  que navega automáticamente a la bandeja de entrada de LocalMail.

### Integración para otros módulos

Los módulos que deseen enviar notificaciones deben usar `service.notify()`
(método 5 más abajo) para crear un mensaje en la bandeja de entrada, NO
deben usar `InboxNotifier` directamente para enviar.

---

## 5. Sending Notifications via LocalMail

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

### Nuevo en Fase 5 — send_email con reply/thread/attachments

El método `service.send_email()` ahora acepta parámetros adicionales para
responder, reenviar y adjuntar archivos:

```python
def send_email(
    client,
    from_user: str,
    to_users: list[str],
    subject: str,
    body: str,
    cc_users: list[str] | None = None,
    priority: str = "Media",
    reply_to_uuid: str = "",          # UUID del mensaje original (respuesta)
    thread_uuid_override: str | None = None,  # UUID de hilo existente
    attachments: list[str] | None = None,      # Rutas de archivos locales
) -> NocoResult:
```

- `reply_to_uuid`: Si se proporciona, se almacena en el campo
  `reply_to_uuid` del registro (usado para respuestas).
- `thread_uuid_override`: Si se proporciona, se usa como `thread_uuid`
  en lugar de generar un nuevo `uuid4()`.
- `attachments`: Lista de rutas de archivos locales. Cada archivo se sube
  a NocoDB mediante `client.upload_attachment()` antes de crear el registro.
  Los errores de subida se registran en `meta["attachment_errors"]` sin
  impedir el envío del correo.

### Nuevo en Fase 5 — restore_email

`service.restore_email(client, email_id: int, mailbox_id: str) -> NocoResult`:
Actualiza el campo `folder` a `"inbox"` y establece el `mailbox_owner`.
Usado para restaurar correos archivados o en la papelera.

### Nuevo en Fase 5 — Attachment upload

`client.upload_attachment(file_path: str) -> NocoResult`:
Sube un archivo al almacenamiento de NocoDB vía `POST /api/v2/storage/upload`.
Valida que el archivo exista y no supere `TARDIS_MAX_ATTACHMENT_MB` MB (default 10).

### ⚠️ NocoDB Attachment Storage Modes (Local vs S3)

NocoDB soporta dos modos de almacenamiento para archivos adjuntos, y cada modo
devuelve **campos distintos** en el objeto attachment:

| Almacenamiento | Campo URL primario | Campo fallback | Descripción |
|---|---|---|---|
| **S3 / Cloud** | `signedUrl` | `url` | URL firmada descargable directamente sin autenticación extra.
| **Local (filesystem)** | `signedPath` | `path` | Ruta relativa firmada. Requiere prefijar con `base_url` y enviar header `xc-token`.

**Esta instancia de NocoDB usa almacenamiento LOCAL.**
Por lo tanto, los attachments devueltos por NocoDB tienen esta estructura:
```json
{
  "path": "download/noco/PATH_TO_FILE",
  "title": "documento.pdf",
  "mimetype": "application/pdf",
  "size": 123456,
  "id": 1,
  "signedPath": "download/noco/SIGNED_PATH"
}
```

**Regla de extracción correcta:**
```python
# En _render_attachments / reader_view.py
url = att.get("signedPath") or att.get("path", "")
```

La función `_resolve_attachment_url()` en `reader_view.py` convierte la ruta
relativa a absoluta prefijando `base_url`. La función
`_download_attachment_file_sync()` usa una sesión autenticada con `xc-token`
para la descarga.

> **⚠️ Importante para futuros desarrolladores:**
> No asumas que NocoDB devuelve `signedUrl` o `url`. Verifica los campos reales
> con logging DEBUG en `_render_attachments` si migras a otra instancia de NocoDB
> o cambias el backend de almacenamiento.

---

## 6. Signature Utilities (`modules/localmail/signatures.py`)

Utilidades para gestionar firmas de correo electrónico. Las firmas se
almacenan en `tardis_signatures.json` en la raíz del proyecto.

### Funciones públicas

```python
from modules.localmail.signatures import (
    load_signatures,          # Carga todas las firmas
    save_signatures,          # Guarda todas las firmas
    get_default_signature,    # Obtiene la firma predeterminada para una casilla
    get_signatures_for_mailbox,  # Filtra firmas por casilla
    build_signature_html,     # Construye HTML completo (con logo inline SVG)
)
```

### Estructura del archivo JSON

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

### Uso desde módulos (Fase 6+)

Los módulos que compongan correos programáticamente (ej: Cotizaciones en
Fase 6) pueden usar `get_default_signature(mailbox)` para obtener la firma
de un usuario y `build_signature_html(sig)` para generar el HTML completo.

---

## 7. PDF Export Module (`modules/pdf_export`)

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
