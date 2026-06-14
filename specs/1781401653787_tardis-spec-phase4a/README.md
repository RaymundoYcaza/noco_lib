# SPEC — Tardis Phase 4a: PDF Export Engine (`modules/pdf_export/`)

> Self-contained document. Any LLM can pick it up without prior context.
> **Execution rule**: complete tasks **one at a time, in listed order**.
> Each task has Context / Steps / Verification / Depends on.
> **After finishing a task, the LLM MUST mark it `[x]` before proceeding.**
> Do not skip a task whose dependency is not yet `[x]`.

---

## 0. Context recap

- **Tardis** is a PySide6 desktop app. Modules live in `modules/<name>/`,
  each exposes `register(app: MainWindow, client: NocoClient) -> None`.
- **`noco_lib`** provides `NocoResult(success, operation, table, data,
  affected_count, errors, meta)`. Every public function in this module
  MUST return `NocoResult`.
- **Golden rule**: any long-running call (PDF generation, file I/O)
  runs inside `run_async()`, never in the Qt main thread.
- **Logging**: use `logging.getLogger("tardis")` for all log output.
- **Existing infrastructure**: `app_core/widgets/toast.py` for
  notifications, `app_core/EXTENSION_POINTS.md` for module APIs.

---

## 1. What this module does (plain language)

`pdf_export` is a standalone PDF generation engine. Given a structured
data dict (following `document_schema.json`) plus a brand name, it:

1. Renders an HTML document from a Jinja2 template (applying brand
   styles, header, footer, sections, components).
2. Converts that HTML to PDF using QtWebEngine's `printToPdf`.
3. Post-processes the PDF with `pikepdf` to overlay a footer on every
   page containing "Page X of Y" (and any other data that requires
   knowing the total page count at stamp time).
4. Returns a `NocoResult` with the output path (and optionally the HTML
   string for preview).

Other modules (e.g. Quotations in Phase 5) import `generate_pdf` and
`generate_html` directly — they do NOT go through the UI panel.

---

## 2. Confirmed design decisions (all stakeholder-approved)

### 2.1 Brands
- Three brands: `bisstox`, `plyson`, `inorizonti`.
- Each brand lives in `shared/brands/<brand>/`:
  - `brand.json` — colors, typography, contact data, footer defaults.
  - `logo.svg` — SVG logo file (referenced from HTML via inline embed
    or `<img>` pointing to an absolute path safe for QtWebEngine).
  - `brand.css` — brand-specific CSS overrides (colors, accent, header
    gradient).
- The base HTML template (`shared/templates/document_base.html.j2`) is
  shared across all brands; `brand.css` is injected inline.

### 2.2 Header layout
- Fixed two-column layout: LEFT = logo area (max 52mm wide, 25mm tall,
  SVG scales to fit without distortion), RIGHT = 3 stacked rows.
- The 3 right-side rows are: top row, middle row, bottom row. Each is
  optional (empty = row still reserves its space via `min-height`,
  preserving alignment). This is controlled per `doc_type` in
  `document_presentation.json`.
- Typical mapping (configurable in `brand.json` or overridable per
  document):
  - Row 1: document type legend (e.g. "Documento Carta").
  - Row 2: DIN (document identification number).
  - Row 3: date.
- `compact_header: true` collapses to a single thin bar (logo + DIN +
  type on one line), useful for multi-page manuals.

### 2.3 Footer layout (3-column grid)
- LEFT column: unit label + optional brand name.
- CENTER column: "Página X de Y" (stamped by `pikepdf` post-process) +
  optional tagline.
- RIGHT column: contact info (mail, phone, site) — only shown if
  provided in `brand.json` or `footer` override in input data.
- Footer height is fixed (~12mm). Content that overflows is clipped.
- `pikepdf` stamps "Página X de Y" into the CENTER column placeholder
  on every page AFTER `printToPdf` completes.

### 2.4 Document types (all from `document_presentation.json`)
`report`, `technical_report`, `support_ticket`, `delivery_act`,
`letter`, `communication`, `minutes`, `quote`, `manual`, `checklist`.
All share the same Jinja2 base template; `doc_type` controls which
optional blocks render (cover page, meta-band, letter shell, ticket
block, approval block, etc.).

### 2.5 Body: section-based + 12-col grid
- `document.sections` is an array of section objects, each rendered in
  order.
- Each section has a `type` field. Built-in section types for Phase 4a:
  `text`, `html`, `markdown`, `table`, `checklist`, `callout`,
  `indicator`, `divider`, `page_break`, `signature_block`.
- The body uses a 12-column CSS grid (`shared/templates/grid.css`).
  Sections can specify `cols: 6` (half-width) etc.; default = 12 (full
  width).
- `page_break` section type emits `<div class="page-break"></div>` which
  maps to `page-break-before: always` in CSS — Chromium respects this
  in `printToPdf` with no post-processing needed.

### 2.6 Markdown support
- Any section with `type: "markdown"` has its `content` field parsed by
  `mistune` (pure Python Markdown parser, no C extensions needed) into
  HTML before insertion into the template.
- `content_html` field (legacy/direct HTML) is inserted as-is, wrapped
  in `<div class="content-html">`.
- Markdown supports: headings (h1-h4), bold, italic, lists (ul/ol),
  code blocks, blockquotes, links, inline code. Strikethrough optional.

### 2.7 Components / widgets (built-in, Phase 4a)
Each is a Jinja2 macro in `shared/templates/macros/components.html.j2`:

| Component | Section type | Key fields |
|---|---|---|
| Styled table | `table` | `headers: [str]`, `rows: [[str]]`, `caption: str?` |
| Checklist | `checklist` | `items: [{text, checked: bool, note?}]` |
| Callout | `callout` | `level: info\|warning\|error\|success`, `title?`, `body` |
| KPI Indicator | `indicator` | `label`, `value`, `unit?`, `trend?: up\|down\|neutral` |
| Divider | `divider` | `label?` (section title in the rule line) |
| Page break | `page_break` | _(no fields)_ |
| Signature block | `signature_block` | `signers: [{name, role, date?}]` |

Charts are out of scope for Phase 4a.

### 2.8 Audience watermarks / overlays
- `audience: confidential` → diagonal "CONFIDENCIAL" watermark (low
  opacity, large rotated text) via CSS `::before` on `<body>`.
- `audience: draft` or `status: draft` → "BORRADOR" watermark.
- `audience: external` | `internal` → no watermark.
- CSS already handles this via body class `audience-confidential` etc.
  (see existing HTML reference); no `pikepdf` post-processing needed.

### 2.9 Orientation
- `portrait` (default): A4 210×297mm.
- `landscape`: A4 297×210mm — header compacts automatically (logo
  smaller, right block on one line), meta-grid gets 6 columns.

### 2.10 Public API
```python
# modules/pdf_export/engine.py

def generate_pdf(
    data: dict,
    brand: str,
    output_path: str,
    open_after: bool = False,
) -> NocoResult:
    """
    Renders HTML from data+brand, prints to PDF via QtWebEngine,
    overlays footer page numbers via pikepdf.
    Returns NocoResult(success, operation="create",
                        data={"path": output_path, "pages": N},
                        meta={"brand": brand, "doc_type": ..., "din": ...}).
    """

def generate_html(
    data: dict,
    brand: str,
) -> NocoResult:
    """
    Renders HTML only (no PDF). Useful for in-app preview.
    Returns NocoResult(success, operation="read",
                        data={"html": "<full HTML string>"}).
    """

def validate_document(data: dict) -> NocoResult:
    """
    Validates data against document_schema.json (jsonschema).
    Returns NocoResult.fail with list of validation errors if invalid.
    Used by callers before generate_pdf to get early errors.
    """
```

### 2.11 Module UI panel (debug/standalone use)
- A dock panel "PDF Export" with:
  - Brand selector (`QComboBox`): bisstox / plyson / inorizonti.
  - Doc type selector (`QComboBox`): all 10 types from
    `document_presentation.json`.
  - JSON editor (`QPlainTextEdit`): user pastes the `document` object.
  - "Preview HTML" button → calls `generate_html` via `run_async`,
    opens result in a `QWebEngineView` floating window.
  - "Generate PDF" button → calls `generate_pdf` via `run_async`,
    opens the PDF with `os.startfile` (Windows) or `subprocess.run(["xdg-open", ...])` (Linux) on success.
  - Status line showing last result (success/error with message).
- This panel is optional for other modules — they import `engine.py`
  directly.

### 2.12 Dependencies to add to `pyproject.toml`
```
mistune>=3.0          # Markdown → HTML
jsonschema>=4.0       # schema validation
pikepdf>=8.0          # PDF post-processing (page X of Y footer stamp)
reportlab>=4.0        # Used ONLY for generating the footer stamp PDF that pikepdf overlays
Jinja2>=3.1           # Template rendering
PySide6-WebEngine     # Included with PySide6>=6.7 but must be explicitly imported
```

---

## 3. File structure

```
modules/pdf_export/
  __init__.py
  module.py               # register(app, client) — UI panel
  engine.py               # generate_pdf(), generate_html(), validate_document()
  chromium_printer.py     # QtWebEngine printToPdf wrapper (async-safe)
  footer_stamper.py       # pikepdf footer overlay logic
  markdown_renderer.py    # mistune wrapper → HTML string
  schema_validator.py     # jsonschema wrapper → NocoResult

shared/
  brands/
    bisstox/
      brand.json
      logo.svg
      brand.css
    plyson/
      brand.json
      logo.svg
      brand.css
    inorizonti/
      brand.json
      logo.svg
      brand.css
  templates/
    document_base.html.j2        # master Jinja2 template
    macros/
      components.html.j2          # table, checklist, callout, indicator, etc.
      header.html.j2
      footer.html.j2
      meta_band.html.j2
      cover.html.j2
    grid.css                      # 12-col CSS grid (pure CSS, no framework)
    base.css                      # design tokens, typography, page layout
    print.css                     # @media print rules, @page, Chromium table-footer-group trick
    components.css                # all component styles
```

---

## 4. `brand.json` schema (each brand has one)

```json
{
  "name": "bisstox",
  "display_name": "Bisstox",
  "legal_name": "Bisstox S.A.",
  "tagline": "Unidad de software y transformación digital",
  "site": "www.bisstox.com",
  "mail": "ventas@bisstox.com",
  "phone": "+593 099 563 2379",
  "colors": {
    "primary": "#123c69",
    "primary_dark": "#08233f",
    "accent": "#0ea5e9",
    "header_gradient_start": "#08233f",
    "header_gradient_end": "#123c69"
  },
  "footer_defaults": {
    "unit_label": "Unidad de software y transformación digital",
    "show_contact": true
  },
  "header_rows": {
    "row1": "legend",
    "row2": "din",
    "row3": "date"
  }
}
```

`header_rows.row1/row2/row3` can be `"legend"`, `"din"`, `"date"`,
`"status"`, `"reference"`, `"owner_name"`, or `null` (row reserved but
empty).

---

## 5. `document_base.html.j2` rendering contract

The template receives a single context dict `ctx` with these keys:

```python
ctx = {
    "brand": brand_json,              # full brand.json dict
    "brand_css": "<css string>",      # brand.css file content (injected inline)
    "doc_type_meta": {...},           # entry from document_presentation.json
    "doc": data["document"],          # the document object from input data
    "audience": data.get("audience", "external"),
    "orientation": data.get("orientation", "portrait"),
    "has_cover": data.get("has_cover", False),
    "compact_header": data.get("compact_header", False),
    "footer_override": data.get("footer", {}),
    "sections_html": "<rendered sections HTML>",  # pre-rendered by engine.py
}
```

`sections_html` is generated by `engine.py` by iterating
`data["document"]["sections"]` and calling the appropriate Jinja2 macro
per section `type`. This keeps the template clean (no loops with
conditionals for every type — logic lives in Python, template stays
declarative).

---

## 6. Footer stamp approach (pikepdf + reportlab)

1. `generate_pdf` calls `chromium_printer.print_to_pdf(html, tmp_path)`.
2. `footer_stamper.stamp_footer(tmp_path, output_path, footer_data)`:
   a. Opens `tmp_path` with `pikepdf`.
   b. Gets total page count `N = len(pdf.pages)`.
   c. Uses `reportlab` to generate an in-memory single-page PDF
      (transparent background, A4 size) containing ONLY the CENTER
      footer text "Página X de Y" at the correct position (bottom
      center, font size ~8.5pt, color matching the brand muted color).
      Repeat this for each page 1..N with the correct X value.
   d. Merges each stamp page onto the corresponding PDF page using
      `pikepdf.Page.add_overlay(stamp_page)` (or equivalent — verify
      the current pikepdf API for overlay; if `add_overlay` is not
      available in the installed version, use the
      `pikepdf.Pdf.make_indirect` + XObject approach).
   e. Saves the result to `output_path`. Deletes `tmp_path`.
3. LEFT and RIGHT footer columns are rendered by Chromium via
   `table-footer-group` CSS (see `print.css` — existing approach from
   the reference HTML). Only the CENTER "page X of Y" requires
   post-processing.

---

## 7. `chromium_printer.py` approach (Qt-safe async)

`printToPdf` in QtWebEngine is async: it takes a callback. It must be
called from the Qt main thread, but the result (the PDF bytes or file)
arrives in a callback. The challenge is bridging this with `run_async`.

Approach:
1. `print_to_pdf(html: str, output_path: str) -> None` must be called
   from the main thread (do NOT call from QRunnable/thread).
2. Create a dedicated hidden `QWebEngineView` (stored on `MainWindow`
   as `self._pdf_printer_view` — single shared instance, not created
   per call).
3. Load HTML via `view.setHtml(html, base_url)` where `base_url` is a
   `QUrl.fromLocalFile(shared/brands/<brand>/)` so relative SVG/CSS
   paths resolve correctly.
4. On `loadFinished`, call `view.page().printToPdf(output_path, layout)`.
5. On `pdfPrintingFinished(path, success)` signal, emit a custom
   `Signal(bool, str)` that the caller (engine.py) connects to.
6. `engine.py` wraps this in a `QEventLoop` pattern: start the loop,
   connect the finished signal to quit the loop + store result, then
   process events until the loop exits. This makes it synchronous from
   the caller's perspective while still pumping the Qt event loop.
   NOTE: this means `generate_pdf` itself MUST be called from the main
   thread (it drives the event loop internally). Therefore, in Tardis
   the call sequence is:
   - UI button click (main thread) → call `generate_pdf` directly (NOT
     via `run_async`) for the QtWebEngine part.
   - The `pikepdf` post-processing step (CPU/file I/O) CAN run in
     `run_async` if desired, but for simplicity in Phase 4a: run the
     whole `generate_pdf` synchronously from main thread, show a
     "Generating..." overlay while it runs (Qt processes events during
     the internal QEventLoop, so the UI does not freeze).

---

## 8. PLAN OF TASKS (checklist — execute in order, mark `[x]` when done)

### 10.0 — Setup and dependencies

- [x] **10.0.1** Add all Phase 4a dependencies to `pyproject.toml`
      (section 2.12): `mistune>=3.0`, `jsonschema>=4.0`, `pikepdf>=8.0`,
      `reportlab>=4.0`, `Jinja2>=3.1`. Run `pip install -e .` and confirm
      all install without errors. `PySide6-WebEngine` should already be
      present; confirm by running `from PySide6.QtWebEngineWidgets import
      QWebEngineView` without ImportError.
      Verification: `python -c "import mistune, jsonschema, pikepdf,
      reportlab, jinja2; from PySide6.QtWebEngineWidgets import
      QWebEngineView; print('all ok')"` prints `all ok`.
      Depends on: none.

- [x] **10.0.2** Create the full directory structure from section 3:
      `modules/pdf_export/` (with `__init__.py` in each package),
      `shared/brands/bisstox/`, `shared/brands/plyson/`,
      `shared/brands/inorizonti/`, `shared/templates/macros/`.
      Verification: `find modules/pdf_export shared/brands shared/templates
      -type d` (or equivalent Windows `dir /s /b`) lists all expected
      directories without errors.
      Depends on: 10.0.1.

- [x] **10.0.3** Create `brand.json` for all three brands following
      section 4's schema:
      - `bisstox`: primary `#123c69`, accent `#0ea5e9`, gradient
        `#08233f → #123c69`. Contact: `ventas@bisstox.com`,
        `+593 099 563 2379`, `www.bisstox.com`.
      - `plyson`: primary `#1a5276` (placeholder — use a professional
        blue distinct from Bisstox), accent `#2980b9`. Contact:
        `ventas@plyson.com`. All other fields mirror Bisstox structure.
      - `inorizonti`: primary `#1f1e1d`, accent `#e9290c` (confirmed
        from reference HTML). Contact: `contacto@inorizonti.com`,
        `www.inorizonti.com`.
      All three files must be valid JSON (validate with `python -m json.tool`).
      Verification: `python -m json.tool shared/brands/bisstox/brand.json`
      exits 0 for all three brands.
      Depends on: 10.0.2.

- [x] **10.0.4** Create placeholder `logo.svg` for each brand:
      - `bisstox/logo.svg`: SVG text "BISSTOX" in dark blue, styled
        similarly to the inorizonti SVG in the reference HTML (bold
        sans-serif, brand accent underline rectangle).
      - `plyson/logo.svg`: SVG text "PLYSON" in brand blue.
      - `inorizonti/logo.svg`: extract the EXACT SVG content from the
        reference `letter.html` (the `<svg class="brand-svg-inorizonti">`
        block, lines 1162-1175) and save it as a standalone SVG file with
        `xmlns` attribute and `viewBox="0 0 720 220"`.
      NOTE: these are placeholders to be replaced by the real SVG files
      the stakeholder places in the folder. The template must reference
      them by reading the file content and embedding inline (so
      QtWebEngine does not need to resolve external file URLs in PDF
      mode).
      Verification: each `logo.svg` opens in a browser and renders
      without errors. `python -c "from xml.etree import ElementTree as ET;
      ET.parse('shared/brands/inorizonti/logo.svg')"` exits 0.
      Depends on: 10.0.3.

- [x] **10.0.5** Copy the CSS from the reference `letter.html` into the
      correct CSS files under `shared/templates/`. Split as follows:
      - `base.css`: the `:root` variables block + `body`, `p`, `.page`,
        `.orient-landscape`, `.page-body`, `.print-hint`,
        `.running-header` rules (roughly lines 11-142 of the reference).
      - `components.css`: `.masthead`, `.brand-card`, `.logo-stack`,
        `.document-heading`, `.eyebrow`, `.document-title`,
        `.document-subtitle`, `.cover-page`, `.meta-band`, `.meta-grid`,
        `.field-*`, all component CSS (`.callout`, `.checklist-*`,
        `.table-*`, `.indicator-*`, etc.) from the reference HTML.
      - `print.css`: the `@page`, `@media print` rules (both the
        `print_common.css` and `print_chromium.css` sections).
      - `grid.css`: a new pure-CSS 12-column grid system (`.grid`,
        `.col-1` through `.col-12`, `.col-offset-*`).
      - Leave brand-specific overrides (`.brand-bisstox`, `.brand-plyson`,
        `.brand-inorizonti` body classes) in each brand's `brand.css`,
        NOT in the shared CSS. Extract the inorizonti brand overrides
        from the reference HTML (lines 900-923) as the model for
        `inorizonti/brand.css`; create equivalent files for the other
        two brands substituting their colors from `brand.json`.
      Verification: `base.css` + `components.css` + `print.css` +
      `grid.css` total line count is comparable to the reference HTML's
      `<style>` block (no major missing sections). No `body.brand-*`
      rules remain in the shared CSS files.
      Depends on: 10.0.4.

### 10.1 — Core engine components

- [x] **10.1.1** Implement `modules/pdf_export/markdown_renderer.py`.
      Steps:
      1. `render_markdown(text: str) -> str` using `mistune.create_markdown()`
         with plugins `["strikethrough"]`. Returns an HTML string.
      2. Wrap in try/except: on error, return the original text escaped
         as plain HTML (`<pre>` block), and log via
         `logging.getLogger("tardis").exception(...)`.
      Verification: `render_markdown("# Hello\n\n**bold** and _italic_")`
      returns a string containing `<h1>`, `<strong>`, `<em>`. Run in a
      `scripts/test_markdown.py` script and print the output.
      Depends on: 10.0.1.

- [x] **10.1.2** Implement `modules/pdf_export/schema_validator.py`.
      Steps:
      1. Load `document_schema.json` from
         `shared/schemas/document_schema.json` (copy the file there from
         the uploaded schema, and create `shared/schemas/` directory).
      2. `validate_document(data: dict) -> NocoResult`:
         - Use `jsonschema.validate(data, schema)`.
         - On success: `NocoResult.ok("schema", data={"valid": True})`.
         - On `ValidationError`: `NocoResult.fail("schema",
           errors=[str(e) for e in sorted(validator.iter_errors(data),
           key=str)])` — list ALL errors, not just the first.
      Verification: `validate_document({"brand": "bisstox", "doc_type":
      "letter", "document": {"title": "Test", "din": "DIN-001",
      "contact": {"name": "John"}}})` returns `success=True`.
      `validate_document({})` returns `success=False` with at least 3
      errors (missing required fields).
      Depends on: 10.0.2.

- [x] **10.1.3** Implement `modules/pdf_export/footer_stamper.py`.
      Steps:
      1. `stamp_page_numbers(input_path: str, output_path: str,
         brand_json: dict, footer_data: dict) -> None`:
         a. Open `input_path` with `pikepdf.open(...)`.
         b. `total_pages = len(pdf.pages)`.
         c. For each page index `i` (0-based), generate an in-memory
            stamp PDF using `reportlab`:
            - Page size matches the PDF page (A4 portrait or landscape —
              read from pikepdf page's `/MediaBox`).
            - Draw ONLY the centered footer text
              `f"Página {i+1} de {total_pages}"` at position
              `x = page_width / 2`, `y = 6mm from bottom` (in points:
              `y = 17`), centered, font "Helvetica" size 8.5,
              color `(0.4, 0.47, 0.52)` (muted gray).
            - Use `io.BytesIO` as the reportlab canvas output — no temp
              files for the stamp.
         d. Open each stamp BytesIO as a `pikepdf.Pdf`, get its first
            page, and merge it onto the corresponding main PDF page using
            `pikepdf`'s XObject overlay approach:
            ```python
            stamp_pdf = pikepdf.open(stamp_io)
            stamp_page = stamp_pdf.pages[0]
            # Use pikepdf.Page.add_overlay if available (pikepdf >= 8),
            # otherwise use the form XObject approach:
            # pdf.pages[i].add_overlay(stamp_page)
            ```
            If `add_overlay` is not available: implement the XObject
            approach (create a form XObject from the stamp page,
            reference it in the main page's content stream). Document
            which approach was used in a comment.
         e. Save to `output_path` with `pdf.save(output_path)`.
         f. On any exception: log full traceback and re-raise (let
            `engine.py` convert to `NocoResult.fail`).
      Verification: create a test script `scripts/test_footer_stamp.py`
      that generates a simple 3-page PDF with `reportlab` (just colored
      rectangles), then calls `stamp_page_numbers(...)` on it. Open the
      output PDF and confirm pages show "Página 1 de 3", "Página 2 de 3",
      "Página 3 de 3" at the bottom center of each page.
      Depends on: 10.0.1.

- [x] **10.1.4** Implement Jinja2 template macros in
      `shared/templates/macros/components.html.j2`.
      Steps: implement one Jinja2 macro per component type from section
      2.7. Each macro receives a `section` dict. Example structure:

      ```jinja
      {% macro render_section(section) %}
        {% if section.type == "text" %}
          <div class="section-text">{{ section.content | e }}</div>
        {% elif section.type == "markdown" %}
          <div class="content-html">{{ section._rendered_html | safe }}</div>
        {% elif section.type == "html" %}
          <div class="content-html">{{ section.content | safe }}</div>
        {% elif section.type == "table" %}
          {% include "macros/_table.html.j2" %}
        ...
        {% elif section.type == "page_break" %}
          <div class="page-break" style="page-break-before: always;"></div>
        {% endif %}
      {% endmacro %}
      ```

      Split large macros into individual files under `macros/` and
      include them (e.g. `_table.html.j2`, `_checklist.html.j2`,
      `_callout.html.j2`, `_indicator.html.j2`,
      `_signature_block.html.j2`). Each sub-macro generates clean,
      semantic HTML that the CSS in `components.css` already styles.

      CSS classes to use per component (match the existing reference CSS):
      - table → `<table class="doc-table">` with `<thead>`, `<tbody>`.
      - checklist → `<ul class="checklist">` with
        `<li class="checklist-item [checked]"><span class="checklist-box"></span>...`.
      - callout → `<div class="callout callout-{level}">`.
      - indicator → `<div class="metric-card">`.
      - divider → `<hr class="section-divider"><span class="section-label">`.
      - signature_block → `<div class="signature-box">`.

      Verification: render each macro in isolation using Jinja2's
      environment directly (no PDF, no HTTP) in `scripts/test_macros.py`.
      Pass a test `section` dict for each type and confirm the output
      HTML string contains the expected class names and structure.
      Depends on: 10.0.5.

- [x] **10.1.5** Implement `shared/templates/document_base.html.j2` —
      the master Jinja2 template.
      Steps:
      1. Structure (mirrors the reference HTML exactly):
         ```
         <!doctype html>
         <html lang="es-EC">
         <head>
           <meta charset="UTF-8">
           <style>
             {{ base_css | safe }}
             {{ grid_css | safe }}
             {{ components_css | safe }}
             {{ print_css | safe }}
             {{ brand_css | safe }}
           </style>
         </head>
         <body class="doc brand-{{ brand.name }} orient-{{ orientation }}
                      audience-{{ audience }}
                      doc-{{ doc_type }}
                      {% if compact_header %}compact-header{% endif %}
                      {% if has_cover %}has-cover{% endif %}
                      {% if not show_meta_band %}no-meta-band{% endif %}"
               data-brand="{{ brand.name }}"
               data-doc-type="{{ doc_type }}">

           <main class="page">
             <div class="running-header">{{ doc.din }} · {{ doc.title }}</div>

             {# HEADER #}
             {% include "macros/header.html.j2" %}

             {# FOOTER (Chromium table-footer-group trick) #}
             {% include "macros/footer.html.j2" %}

             {# BODY #}
             <div class="page-body">
               {% if has_cover %}{% include "macros/cover.html.j2" %}{% endif %}
               {% if show_meta_band %}{% include "macros/meta_band.html.j2" %}{% endif %}
               <div class="document-flow">
                 {{ sections_html | safe }}
               </div>
             </div>
           </main>
         </body>
         </html>
         ```
      2. `show_meta_band` is `True` for all doc_types EXCEPT `letter` and
         `communication` (which use `no-meta-band` per reference HTML).
         Engine.py computes this boolean before rendering.
      3. CSS is injected inline (all 5 CSS files read from disk and
         concatenated) so QtWebEngine does not need to resolve any
         external `<link>` tags.
      Verification: run `scripts/test_template.py` that builds a minimal
      `ctx` dict (with all required keys) for `doc_type="letter"`,
      `brand="inorizonti"`, calls `Jinja2.Environment.get_template(
      "document_base.html.j2").render(ctx)`, and saves the output to
      `scripts/test_output_letter.html`. Open this file in a browser and
      confirm it visually resembles the reference `letter.html` (correct
      header gradient, logo area, footer bar, body text area).
      Depends on: 10.1.4, 10.0.5, 10.0.4.

### 10.2 — Header and footer macros

- [x] **10.2.1** Implement `shared/templates/macros/header.html.j2`.
      Steps:
      1. The masthead structure (from reference HTML, adapted):
         ```html
         <header class="masthead">
           <div class="masthead-content">
             <div class="brand-card">
               <div class="logo-stack">
                 {{ brand_logo_svg | safe }}
               </div>
             </div>
             <div class="document-heading header-right-block">
               <div class="header-row header-row-1
                    {% if not ctx.header_row1 %}header-row-empty{% endif %}">
                 {{ ctx.header_row1 or "" }}
               </div>
               <div class="header-row header-row-2
                    {% if not ctx.header_row2 %}header-row-empty{% endif %}">
                 {{ ctx.header_row2 or "" }}
               </div>
               <div class="header-row header-row-3
                    {% if not ctx.header_row3 %}header-row-empty{% endif %}">
                 {{ ctx.header_row3 or "" }}
               </div>
             </div>
           </div>
         </header>
         ```
      2. Add CSS for `.header-row` and `.header-row-empty` to
         `components.css`:
         - `.header-row { min-height: 8mm; display: flex;
           align-items: center; }` — reserves space even when empty.
         - `.header-row-1` → bold, larger (legend/type label).
         - `.header-row-2` → monospace or distinct weight (DIN code).
         - `.header-row-3` → muted, smaller (date).
         - `.compact-header .header-right-block { display: flex;
           flex-direction: row; gap: 4mm; align-items: center; }` so all
           3 rows collapse to one line in compact mode.
      3. In `engine.py`, compute `ctx.header_row1/2/3` from
         `brand_json["header_rows"]` mapping to the actual document
         field values (e.g. `"legend"` → `doc_type_meta["legend"]`,
         `"din"` → `doc.din`, `"date"` → `doc.date or today's date`).
      Verification: in `scripts/test_template.py`, generate a letter with
      all 3 header rows populated and another with only row 2 populated
      (rows 1 and 3 empty). In the browser, confirm both render correctly
      with reserved space for empty rows (no layout shift/collapse of the
      header).
      Depends on: 10.1.5.

- [x] **10.2.2** Implement `shared/templates/macros/footer.html.j2`.
      Steps:
      1. Structure (uses the Chromium `table-footer-group` trick from
         reference `print_chromium.css`):
         ```html
         <footer class="brand-footer">
           <div class="brand-footer-inner">
             <div class="footer-left">
               {% if footer.unit_label %}
               <strong class="footer-brand-name-text">
                 {{ footer.brand_name or brand.display_name }}
               </strong>
               <span class="footer-brand-line-text">{{ footer.unit_label }}</span>
               {% endif %}
               {% if footer.show_contact %}
               <span class="footer-contact-line">
                 {% if footer.site %}{{ footer.site }}{% endif %}
                 {% if footer.mail %} · {{ footer.mail }}{% endif %}
                 {% if footer.phone %} · {{ footer.phone }}{% endif %}
               </span>
               {% endif %}
             </div>
             <div class="footer-center footer-page-number-placeholder">
               <!-- Página X de Y is stamped here by pikepdf post-processing.
                    This placeholder div is present for layout only. -->
             </div>
             <div class="footer-right">
               {% if footer.right_html %}
                 {{ footer.right_html | safe }}
               {% elif footer.tagline %}
                 {{ footer.tagline }}
               {% endif %}
             </div>
           </div>
         </footer>
         ```
      2. Add `.footer-center` and 3-column grid CSS to `components.css`
         (the existing reference only has 2 columns — extend to 3):
         `.brand-footer-inner { display: grid;
         grid-template-columns: 1fr auto 1fr; gap: 4mm; align-items: center; }`.
      3. In `engine.py`, compute `footer` context dict by merging (in
         order of priority, highest first): `data["footer"]` override →
         `doc_type_meta["footer"]` → `brand_json["footer_defaults"]`.
         Fields not present in higher priority source fall through to
         the next.
      Verification: generate a `technical_report` (which has mail and
      phone in its footer per `document_presentation.json`) for brand
      `bisstox` and confirm the footer shows unit label + contact info in
      the left column; the center div is empty (placeholder); the right
      column shows the tagline or `right_html` if provided.
      Depends on: 10.2.1.

### 10.3 — Engine orchestration

- [x] **10.3.1** Implement `modules/pdf_export/engine.py` —
      `validate_document` and `generate_html`.
      Steps:
      1. `validate_document(data)` — delegate to `schema_validator.py`
         (10.1.2). No additional logic.
      2. `generate_html(data, brand)`:
         a. `validate_result = validate_document(data)` — if
            `not validate_result.success`, return it immediately.
         b. Load `brand_json = json.load(open(f"shared/brands/{brand}/brand.json"))`.
         c. Load `doc_type_meta` from `document_presentation.json` using
            `data["doc_type"]` as key. If not found: `NocoResult.fail(...)`.
         d. Load `brand_css = open(f"shared/brands/{brand}/brand.css").read()`.
         e. Load all shared CSS files (base, grid, components, print).
         f. Load `brand_logo_svg = open(f"shared/brands/{brand}/logo.svg").read()`.
         g. Pre-render sections: iterate `data["document"].get("sections", [])`,
            for each section:
            - If `type == "markdown"`: call `markdown_renderer.render_markdown(
              section["content"])`, store result as `section["_rendered_html"]`.
            - Render the section using the Jinja2 `render_section` macro
              (load `macros/components.html.j2`, call the macro with the
              section dict).
            - Collect all rendered section HTML into `sections_html` string.
            - Also render `content_html` if present (append to
              `sections_html`).
         h. Compute `header_row1/2/3`, `footer` dict, `show_meta_band`,
            all booleans per section 2 decisions.
         i. Render `document_base.html.j2` with full `ctx` dict.
         j. Return `NocoResult.ok("read", data={"html": rendered_html},
            table=None)`.
      Verification: call `generate_html(test_data, "inorizonti")` from
      `scripts/test_engine.py` where `test_data` has at least one section
      of each type (text, markdown, table, checklist, callout). Save
      `result.data["html"]` to `scripts/engine_test_output.html` and open
      in browser. Confirm: header shows inorizonti logo + correct rows;
      footer shows left column; all section types render with correct CSS
      classes.
      Depends on: 10.2.2, 10.1.1, 10.1.2, 10.1.4, 10.1.5.

- [x] **10.3.2** Implement `modules/pdf_export/chromium_printer.py`.
      Steps (per section 7):
      1. Class `ChromiumPrinter(QObject)` with signal
         `print_finished = Signal(bool, str)` (`success`, `output_path`).
      2. Attribute `self._view: QWebEngineView = None` — set by calling
         `ChromiumPrinter.set_view(view)` from `MainWindow` at startup
         (so the view is created on the main thread with the correct
         parent).
      3. Method `print_to_pdf(html: str, output_path: str,
         orientation: str = "portrait") -> None`:
         - Must be called from the main thread.
         - `self._view.setHtml(html, QUrl("about:blank"))`.
         - Connect `self._view.loadFinished` to `self._on_load_finished`
           (disconnect previous connection first if any, using a stored
           `connection` handle or `disconnect()` before `connect()`).
         - Store `output_path` as `self._pending_output_path`.
      4. `_on_load_finished(ok)`:
         - Disconnect `loadFinished` from `_on_load_finished`.
         - Build `QPageLayout` (A4, portrait or landscape, margins per
           brand/doc: top=12mm, bottom=18mm, left=0, right=0 — matches
           the `@page` margin in `print.css`).
         - `self._view.page().printToPdf(self._pending_output_path, layout)`.
         - Connect `self._view.page().pdfPrintingFinished` to
           `self._on_pdf_done`.
      5. `_on_pdf_done(path, success)`:
         - Disconnect `pdfPrintingFinished`.
         - Emit `self.print_finished.emit(success, path)`.
      6. In `engine.py`, `generate_pdf` drives this via a local
         `QEventLoop`:
         ```python
         loop = QEventLoop()
         result_holder = {}
         def on_done(success, path):
             result_holder["success"] = success
             result_holder["path"] = path
             loop.quit()
         printer.print_finished.connect(on_done)
         printer.print_to_pdf(html, tmp_path, orientation)
         loop.exec()
         printer.print_finished.disconnect(on_done)
         ```
      Verification: call `generate_html(test_data, "inorizonti")` to get
      HTML, then call `printer.print_to_pdf(html, "scripts/test_out.pdf")`,
      run the QEventLoop, confirm `scripts/test_out.pdf` exists and has
      size > 0 bytes. Open PDF visually and confirm header/body/footer
      appear (page number placeholder is empty — that's stamped next).
      Depends on: 10.3.1.

- [x] **10.3.3** Implement `engine.generate_pdf` (full pipeline).
      Steps:
      1. `generate_pdf(data, brand, output_path, open_after=False) -> NocoResult`:
         a. `html_result = generate_html(data, brand)` — return on failure.
         b. `tmp_path = output_path + ".tmp.pdf"`.
         c. Call `chromium_printer.print_to_pdf(html, tmp_path,
            orientation)` and drive `QEventLoop` (per 10.3.2). If
            `not success`: `NocoResult.fail("create", "PDF printing
            failed", ...)`.
         d. `footer_stamper.stamp_page_numbers(tmp_path, output_path,
            brand_json, footer_data)`. If exception: catch, log,
            `NocoResult.fail(...)`.
         e. Delete `tmp_path` (use `pathlib.Path.unlink(missing_ok=True)`).
         f. `pages = len(pikepdf.open(output_path).pages)`.
         g. If `open_after`: `os.startfile(output_path)` (Windows) or
            `subprocess.Popen(["xdg-open", output_path])` (Linux/Mac)
            — wrap in try/except, log on failure, don't fail the result.
         h. Return `NocoResult.ok("create", data={"path": output_path,
            "pages": pages}, meta={"brand": brand, "doc_type":
            data["doc_type"], "din": data["document"].get("din")})`.
      Verification: run full pipeline in `scripts/test_pdf_full.py` with
      a `letter` document for `inorizonti` brand that has 2+ pages (add
      enough content or a `page_break` section to force a 2nd page).
      Confirm: (a) output PDF exists, (b) has 2+ pages, (c) each page
      shows "Página 1 de N" / "Página 2 de N" in the footer center
      column, (d) `NocoResult.success == True`,
      `result.data["pages"] == N`.
      Depends on: 10.3.2, 10.1.3.

### 10.4 — Module UI panel

- [x] **10.4.1** Implement `modules/pdf_export/module.py` —
      `register(app, client)`.
      Steps:
      1. Create a `QWidget` panel with:
         - `QLabel("Marca:")` + `QComboBox` with
           `["bisstox", "plyson", "inorizonti"]`.
         - `QLabel("Tipo de documento:")` + `QComboBox` with all 10
           types from `document_presentation.json` (load the file at
           import time and populate).
         - `QLabel("JSON del documento:")` + `QPlainTextEdit` (tall,
           monospace font, placeholder: the JSON schema of the `document`
           object for reference).
         - `QPushButton("Vista previa HTML")` → on click, calls
           `generate_html(data, brand)` (parse JSON from the text edit
           first; show error toast if invalid JSON or validation fails),
           then opens a `QWebEngineView` floating window via
           `app.add_floating_window(...)` showing the HTML.
         - `QPushButton("Generar PDF")` → calls `generate_pdf(data,
           brand, output_path, open_after=True)` where `output_path` is
           `~/Downloads/<din or 'document'>_<timestamp>.pdf`. Shows
           "Generando PDF..." in the status label during execution (set
           before the call, since `generate_pdf` runs in the main thread
           driving an internal QEventLoop — not `run_async`). Shows
           success/error toast when done.
         - `QLabel("")` status line at the bottom.
      2. Register the dock panel:
         `app.add_dock_panel(panel, "PDF Export", area="right")`.
      3. Register a menu action:
         `app.add_menu_action("Herramientas", "PDF Export", lambda:
         panel.show())`.
      Verification: launch Tardis, open the PDF Export panel, paste a
      minimal valid JSON (just `{"title": "Test", "din": "DIN-001",
      "contact": {"name": "Prueba"}}`), select brand `inorizonti`,
      type `letter`, click "Vista previa HTML" — a floating window opens
      showing the rendered HTML. Click "Generar PDF" — PDF file is
      created in `~/Downloads/` and opens automatically.
      Depends on: 10.3.3.

### 10.5 — Integration checkpoint

- [x] **10.5.1** **CHECKPOINT FINAL (Phase 4a)**:
      Run through all 10 document types with brand `bisstox` using a
      test script `scripts/test_all_doctypes.py` that generates one PDF
      per doc type with representative content for each. For each:
      - `NocoResult.success == True`.
      - PDF file exists and is non-empty.
      - Page count >= 1.
      - No exceptions in `logs/tardis.log`.
      Then manually open at least 3 PDFs (`letter`, `support_ticket`,
      `quote`) and visually confirm:
      - Header: logo left, 3-row block right (correct values per
        `header_rows` in `brand.json`).
      - Footer: unit label left, "Página X de Y" center, right column
        per doc type config.
      - Watermark present for a test with `audience: "confidential"`.
      - `page_break` section forces a new page in a 2-page test.
      Depends on: 10.4.1.

- [x] **10.5.2** Update `app_core/EXTENSION_POINTS.md` to document the
      PDF export API for other module authors:
      ```python
      from modules.pdf_export.engine import generate_pdf, generate_html, validate_document
      # generate_pdf MUST be called from the main Qt thread.
      # It drives its own internal QEventLoop — do NOT call from run_async.
      result = generate_pdf(data, brand="bisstox",
                             output_path="/tmp/doc.pdf", open_after=False)
      ```
      Include: the `data` dict structure reference (point to
      `shared/schemas/document_schema.json`), the list of supported
      section types, the brand names, and the warning about calling from
      the main thread (NOT from `run_async`).
      Depends on: 10.5.1.

---

## 9. Roadmap (Phase 4b and beyond — reference only)

- **Phase 4b — `ai_lib` + `ai_corrections`**: `AIResult` contract
  mirroring `NocoResult`; module reads records via `noco_lib`, sends to
  AI, writes back with user confirmation.
- **Phase 5 — Quotations module**: uses `generate_pdf` to render a
  `quote` doc type from NocoDB data, then sends via `localmail.notify()`.
  Will be the first module to exercise the full pipeline:
  `noco_lib` → `pdf_export` → `localmail`.
  The `Attachment` field of `DIR_LOCAL-MAIL` (unused so far) will need
  a Phase 5 spec task defining how `service.send_email` attaches a file
  (likely: upload file bytes to NocoDB's attachment API, get the
  attachment URL, store in the `Attachment` column).