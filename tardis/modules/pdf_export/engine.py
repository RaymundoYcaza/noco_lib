"""
engine.py — Public API for the PDF Export module.

Public functions:
    validate_document(data: dict) -> NocoResult
        Validates input data against document_schema.json.

    generate_html(data: dict, brand: str) -> NocoResult
        Renders a full HTML document (with inline CSS, brand styles,
        header rows, footer, meta-band, and section components).

    generate_pdf(data, brand, output_path, open_after=False) -> NocoResult
        Full pipeline: validate → generate_html → printToPdf → stamp footer.
        (Implemented in 10.3.3.)

All public functions return NocoResult.
Callers should call generate_pdf / generate_html from the Qt main thread
because QtWebEngine requires main-thread access.
"""

import json
import logging
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from tardis.noco_lib.noco_core.result import NocoResult

from . import markdown_renderer
from . import schema_validator

logger = logging.getLogger("tardis")

# ── Module-level paths ─────────────────────────────────────────────
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parents[1]  # tardis/  (two levels up: .../tardis/modules/pdf_export/ -> .../tardis/)
_SHARED_DIR = _PROJECT_ROOT / "shared"
_TEMPLATES_DIR = _SHARED_DIR / "templates"
_BRANDS_DIR = _SHARED_DIR / "brands"
_SCHEMAS_DIR = _SHARED_DIR / "schemas"
_DOC_PRESENTATION_PATH = _SCHEMAS_DIR / "document_presentation.json"

# ── Module-level cache ─────────────────────────────────────────────
_doc_presentation = None
_jinja_env = None


def _get_jinja_env() -> Environment:
    """Return a cached Jinja2 Environment loaded from the templates directory."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=False,
        )
    return _jinja_env


def _get_doc_presentation() -> dict:
    """Load and cache document_presentation.json."""
    global _doc_presentation
    if _doc_presentation is None:
        if not _DOC_PRESENTATION_PATH.exists():
            raise FileNotFoundError(
                f"Document presentation not found at {_DOC_PRESENTATION_PATH}"
            )
        with _DOC_PRESENTATION_PATH.open("r", encoding="utf-8") as f:
            _doc_presentation = json.load(f)
    return _doc_presentation


def _read_file(path: Path) -> str:
    """Read a text file with UTF-8 encoding."""
    with path.open("r", encoding="utf-8") as f:
        return f.read()


# ── Header row helpers ─────────────────────────────────────────────
_HEADER_ROW_SOURCES = {
    "legend": lambda doc_type_meta, doc: doc_type_meta.get("legend", ""),
    "din": lambda doc_type_meta, doc: doc.get("din", ""),
    "date": lambda doc_type_meta, doc: doc.get("date", str(date.today())),
    "status": lambda doc_type_meta, doc: doc.get("status", ""),
    "reference": lambda doc_type_meta, doc: doc.get("reference", ""),
    "owner_name": lambda doc_type_meta, doc: doc.get("owner_name", ""),
}


def _compute_header_row(row_key: str | None, doc_type_meta: dict, doc: dict) -> str:
    """Resolve a single header-row value from brand config.

    ``row_key`` is one of the strings in ``_HEADER_ROW_SOURCES``, or
    ``None`` (row reserved but empty).
    """
    if row_key is None:
        return ""
    resolver = _HEADER_ROW_SOURCES.get(row_key)
    if resolver is None:
        return ""
    return str(resolver(doc_type_meta, doc))


def _compute_header_rows(brand_json: dict, doc_type_meta: dict, doc: dict) -> tuple[str, str, str]:
    """Compute the three header-row strings from brand config + document data.

    Returns ``(header_row1, header_row2, header_row3)``.
    """
    rows = brand_json.get("header_rows", {})
    return (
        _compute_header_row(rows.get("row1"), doc_type_meta, doc),
        _compute_header_row(rows.get("row2"), doc_type_meta, doc),
        _compute_header_row(rows.get("row3"), doc_type_meta, doc),
    )


# ── Footer merging ─────────────────────────────────────────────────
def _merge_footer(
    brand_json: dict,
    doc_type_meta: dict,
    data_footer: dict | None,
) -> dict:
    """Merge footer config from three sources (lowest → highest priority).

    1. ``brand_json["footer_defaults"]`` — baseline.
    2. ``doc_type_meta.get("footer", {})`` — per-doc-type overrides.
    3. ``data["footer"]`` — per-document overrides (highest).
    """
    footer = {}
    footer.update(brand_json.get("footer_defaults", {}))
    footer.update(doc_type_meta.get("footer", {}))
    if data_footer:
        footer.update(data_footer)

    # Add contact info from brand_json if not overridden
    if "mail" not in footer:
        footer["mail"] = brand_json.get("mail", "")
    if "phone" not in footer:
        footer["phone"] = brand_json.get("phone", "")
    if "site" not in footer:
        footer["site"] = brand_json.get("site", "")
    if "brand_name" not in footer:
        footer["brand_name"] = brand_json.get("legal_name", brand_json.get("display_name", ""))
    if "tagline" not in footer:
        footer["tagline"] = brand_json.get("tagline", "")

    return footer


# ── Section rendering ──────────────────────────────────────────────
def _render_sections(sections: list[dict], components_tmpl) -> str:
    """Pre-render every section dict into its HTML string.

    - Markdown sections get ``_rendered_html`` set via ``markdown_renderer``.
    - Each section is then passed to the ``render_section`` Jinja2 macro.
    - ``content_html`` fields are appended separately.
    Returns the concatenated HTML string.
    """
    parts = []
    for section in sections:
        sect_type = section.get("type", "")

        # Markdown pre-processing
        if sect_type == "markdown":
            md_content = section.get("content", "")
            section["_rendered_html"] = markdown_renderer.render_markdown(md_content)

        # Render via Jinja2 macro
        section_html = components_tmpl.module.render_section(section)
        parts.append(section_html)

        # Legacy direct-HTML field
        if section.get("content_html"):
            parts.append(section["content_html"])

    return "\n".join(parts)


# ── Public API ──────────────────────────────────────────────────────

def validate_document(data: dict) -> NocoResult:
    """Validate *data* against the document JSON Schema.

    Delegates to ``schema_validator.validate_document``.
    """
    return schema_validator.validate_document(data)


def generate_html(data: dict, brand: str) -> NocoResult:
    """Render a complete HTML document from structured *data* and a *brand* name.

    Args:
        data: Document data dict (must pass ``validate_document`` first).
        brand: One of ``\"bisstox\"``, ``\"plyson\"``, ``\"inorizonti\"``.

    Returns:
        NocoResult.ok(\"read\", data={\"html\": rendered_string}) on success.
        NocoResult.fail(...) on validation failure or missing resources.
    """
    # ── 1. Validate ────────────────────────────────────────────────
    validate_result = validate_document(data)
    if not validate_result.success:
        return validate_result

    doc_type: str = data.get("doc_type", "")

    # ── 2. Load brand ──────────────────────────────────────────────
    brand_dir = _BRANDS_DIR / brand
    if not brand_dir.is_dir():
        return NocoResult.fail("read", f"Unknown brand '{brand}' — expected one of: bisstox, plyson, inorizonti")

    try:
        brand_json = json.loads(_read_file(brand_dir / "brand.json"))
        brand_css = _read_file(brand_dir / "brand.css")
        brand_logo_svg = _read_file(brand_dir / "logo.svg")
    except FileNotFoundError as exc:
        logger.exception("Missing brand resource for '%s'", brand)
        return NocoResult.fail("read", str(exc))

    # ── 3. Load doc_type meta ──────────────────────────────────────
    try:
        presentation = _get_doc_presentation()
    except FileNotFoundError as exc:
        logger.exception("Missing document_presentation.json")
        return NocoResult.fail("read", str(exc))

    doc_type_meta = presentation.get(doc_type)
    if doc_type_meta is None:
        return NocoResult.fail(
            "read",
            f"Unknown doc_type '{doc_type}' — expected one of: {', '.join(presentation.keys())}",
        )

    # ── 4. Load CSS files ──────────────────────────────────────────
    try:
        base_css = _read_file(_TEMPLATES_DIR / "base.css")
        grid_css = _read_file(_TEMPLATES_DIR / "grid.css")
        components_css = _read_file(_TEMPLATES_DIR / "components.css")
        print_css = _read_file(_TEMPLATES_DIR / "print.css")
    except FileNotFoundError as exc:
        logger.exception("Missing shared CSS file")
        return NocoResult.fail("read", str(exc))

    # ── 5. Pre-render sections ─────────────────────────────────────
    doc: dict = data.get("document", {})
    sections: list[dict] = doc.get("sections", [])

    env = _get_jinja_env()
    components_tmpl = env.get_template("macros/components.html.j2")
    sections_html = _render_sections(sections, components_tmpl)

    # ── 6. Compute header rows ─────────────────────────────────────
    header_row1, header_row2, header_row3 = _compute_header_rows(
        brand_json, doc_type_meta, doc,
    )

    # ── 7. Merge footer config ─────────────────────────────────────
    footer = _merge_footer(brand_json, doc_type_meta, data.get("footer"))

    # ── 8. Compute booleans ────────────────────────────────────────
    show_meta_band = doc_type not in ("letter", "communication")
    has_cover = data.get("has_cover", False)
    compact_header = data.get("compact_header", False)

    # ── 9. Build context dict ──────────────────────────────────────
    ctx = {
        "base_css": base_css,
        "grid_css": grid_css,
        "components_css": components_css,
        "print_css": print_css,
        "brand_css": brand_css,
        "brand": brand_json,
        "brand_logo_svg": brand_logo_svg,
        "doc_type": doc_type,
        "doc_type_meta": doc_type_meta,
        "doc": doc,
        "audience": data.get("audience", "external"),
        "orientation": data.get("orientation", "portrait"),
        "has_cover": has_cover,
        "compact_header": compact_header,
        "show_meta_band": show_meta_band,
        "footer": footer,
        "header_row1": header_row1,
        "header_row2": header_row2,
        "header_row3": header_row3,
        "sections_html": sections_html,
    }

    # ── 10. Render master template ─────────────────────────────────
    try:
        master_tmpl = env.get_template("document_base.html.j2")
        rendered_html = master_tmpl.render(ctx)
    except Exception as exc:
        logger.exception("Failed to render master template")
        return NocoResult.fail("read", str(exc))

    return NocoResult.ok("read", data={"html": rendered_html})


def generate_pdf(
    data: dict,
    brand: str,
    output_path: str,
    printer: "ChromiumPrinter",
    open_after: bool = False,
) -> NocoResult:
    """Full PDF generation pipeline: validate → HTML → printToPdf → stamp footer.

    **Must be called from the Qt main thread.** This function drives its
    own internal ``QEventLoop``, so the UI will not freeze (Qt processes
    events during the loop), but it must not be called from a background
    thread or ``run_async``.

    Args:
        data: Document data dict (must pass ``validate_document``).
        brand: One of ``\"bisstox\"``, ``\"plyson\"``, ``\"inorizonti\"``.
        output_path: Where to save the final PDF.
        printer: A ``ChromiumPrinter`` instance with a view already set
                 via ``set_view()``.
        open_after: If ``True``, try to open the PDF after generation
                    (``os.startfile`` on Windows, ``xdg-open`` on
                    Linux/macOS). Failure to open is logged but does
                    not fail the result.

    Returns:
        NocoResult.ok("create", data={"path": output_path, "pages": N},
                       meta={"brand": brand, "doc_type": ..., "din": ...})
        on success.
        NocoResult.fail(...) on any failure in the pipeline.
    """
    # Lazy import to avoid circular dependency at module level
    from PySide6.QtCore import QEventLoop, QTimer
    from . import footer_stamper

    # ── 1. Generate HTML ───────────────────────────────────────────
    html_result = generate_html(data, brand)
    if not html_result.success:
        return html_result

    html = html_result.data["html"]

    doc_type: str = data.get("doc_type", "")
    doc: dict = data.get("document", {})
    orientation: str = data.get("orientation", "portrait")

    # ── 2. Print to PDF via ChromiumPrinter + QEventLoop ───────────
    tmp_path = output_path + ".tmp.pdf"

    loop = QEventLoop()
    pdf_ok = {"success": False}

    def _on_print_done(success: bool, path: str) -> None:
        pdf_ok["success"] = success
        loop.quit()

    # Safety timeout (60 seconds for full pipeline)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(60_000)

    printer.print_finished.connect(_on_print_done)
    printer.print_to_pdf(html, tmp_path, orientation)
    loop.exec()

    # Clean up connections
    timer.stop()
    try:
        printer.print_finished.disconnect(_on_print_done)
    except (TypeError, RuntimeError):
        pass

    if not pdf_ok["success"]:
        # Clean up temp file if it was created
        Path(tmp_path).unlink(missing_ok=True)
        return NocoResult.fail("create", "PDF printing failed via ChromiumPrinter")

    # ── 3. Stamp page numbers ──────────────────────────────────────
    brand_dir = _BRANDS_DIR / brand
    brand_json = {}
    try:
        brand_json = json.loads(_read_file(brand_dir / "brand.json"))
    except FileNotFoundError:
        pass  # Footer stamper accepts None for brand_json

    try:
        footer_stamper.stamp_page_numbers(
            tmp_path, output_path,
            brand_json=brand_json,
            footer_data=None,
        )
    except Exception as exc:
        logger.exception("Footer stamping failed for %s", output_path)
        Path(tmp_path).unlink(missing_ok=True)
        return NocoResult.fail("create", f"Footer stamping failed: {exc}")

    # ── 4. Clean up temp file ──────────────────────────────────────
    Path(tmp_path).unlink(missing_ok=True)

    # ── 5. Count pages ─────────────────────────────────────────────
    try:
        import pikepdf
        with pikepdf.open(output_path) as pdf:
            pages = len(pdf.pages)
    except Exception as exc:
        logger.exception("Failed to count pages in %s", output_path)
        pages = 0

    # ── 6. Open file (optional) ────────────────────────────────────
    if open_after:
        try:
            import os
            import sys as _sys
            if _sys.platform == "win32":
                os.startfile(output_path)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", output_path])
        except Exception as exc:
            logger.warning("Could not open PDF '%s': %s", output_path, exc)

    # ── 7. Return success ──────────────────────────────────────────
    return NocoResult.ok(
        "create",
        data={"path": output_path, "pages": pages},
        meta={
            "brand": brand,
            "doc_type": doc_type,
            "din": doc.get("din", ""),
        },
    )
