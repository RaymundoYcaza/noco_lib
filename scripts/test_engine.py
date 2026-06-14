"""
test_engine.py — Integration test for engine.py's generate_html().

Run:  python scripts/test_engine.py

Calls generate_html with a test data dict containing at least one section
of each type (text, markdown, table, checklist, callout, indicator,
divider, signature_block, page_break). Saves the output HTML and runs
structural checks.
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tardis.modules.pdf_export.engine import generate_html, validate_document

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# ── Test data — letter with all section types ──────────────────────
TEST_DATA = {
    "brand": "inorizonti",
    "doc_type": "letter",
    "document": {
        "title": "Documento de prueba con todas las secciones",
        "din": "DIN-TEST-000999",
        "date": "2026-06-14",
        "contact": {"name": "Usuario de Prueba"},
        "status": "final",
        "sections": [
            {
                "type": "text",
                "title": "Introduccion",
                "content": "Este es un parrafo de texto plano que demuestra el tipo de seccion 'text'. Debe aparecer escapado como HTML.",
            },
            {
                "type": "markdown",
                "title": "Contenido Markdown",
                "kicker": "Renderizado con mistune",
                "content": "# Encabezado Markdown\n\nEste texto tiene **negrita** y _cursiva_.\n\n- Elemento de lista 1\n- Elemento de lista 2\n- Elemento de lista 3",
            },
            {
                "type": "html",
                "title": "HTML Directo",
                "content": '<div class="notice warning"><strong>Advertencia:</strong> Este contenido HTML se inserta directamente sin escapado.</div>',
            },
            {
                "type": "table",
                "title": "Tabla de ejemplo",
                "headers": ["Producto", "Cantidad", "Precio Unitario", "Total"],
                "rows": [
                    ["Widget A", "2", "$25.00", "$50.00"],
                    ["Widget B", "1", "$45.00", "$45.00"],
                    ["Servicio", "3", "$30.00", "$90.00"],
                ],
                "caption": "Tabla con productos y precios",
            },
            {
                "type": "callout",
                "title": "Nota importante",
                "level": "warning",
                "body": "<p>Esta es una nota de advertencia que debe mostrarse con el estilo <strong>callout</strong>.</p>",
            },
            {
                "type": "checklist",
                "title": "Lista de verificacion",
                "items": [
                    {"text": "Revisar requisitos", "checked": True},
                    {"text": "Aprobar presupuesto", "checked": True},
                    {"text": "Firmar contrato", "checked": False},
                    {"text": "Enviar documentacion", "checked": False},
                ],
            },
            {
                "type": "indicator",
                "title": "Indicadores",
                "label": "Cumplimiento",
                "value": "94%",
                "trend": "up",
                "note": "vs. mes anterior",
            },
            {
                "type": "divider",
                "label": "Nueva Seccion",
            },
            {
                "type": "page_break",
            },
            {
                "type": "text",
                "content": "Este texto aparece despues de un salto de pagina.",
            },
            {
                "type": "signature_block",
                "title": "Firmas",
                "signers": [
                    {"name": "Juan Perez", "role": "Director"},
                    {"name": "Maria Gomez", "role": "Supervisora"},
                ],
            },
        ],
    },
}

# ── Validation test first ──────────────────────────────────────────
print("=" * 60)
print("  TEST: validate_document (valid data)")
print("=" * 60)
val_result = validate_document(TEST_DATA)
if val_result.success:
    print("  PASS: validate_document returned success")
else:
    print(f"  FAIL: validate_document returned failure — {val_result.errors}")
    sys.exit(1)

# ── Validation test — empty data ───────────────────────────────────
print("=" * 60)
print("  TEST: validate_document (empty data)")
print("=" * 60)
empty_result = validate_document({})
if not empty_result.success and len(empty_result.errors) >= 3:
    print(f"  PASS: Empty data rejected with {len(empty_result.errors)} error(s)")
else:
    print(f"  FAIL: Expected >= 3 errors, got {len(empty_result.errors)}")
    print(f"  Errors: {empty_result.errors}")
    sys.exit(1)

# ── generate_html test ─────────────────────────────────────────────
print("=" * 60)
print("  TEST: generate_html (inorizonti, letter)")
print("=" * 60)
result = generate_html(TEST_DATA, "inorizonti")

if not result.success:
    print(f"  FAIL: generate_html returned failure — {result.errors}")
    sys.exit(1)

html = result.data["html"]
output_path = os.path.join(OUTPUT_DIR, "engine_test_output.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

file_size = os.path.getsize(output_path)
print(f"  Output: {output_path} ({file_size} bytes)")

# ── Structural checks ──────────────────────────────────────────────
failures = 0

checks = [
    ("DOCTYPE declaration", "<!doctype html>" in html),
    ("HTML lang=es-EC", 'lang="es-EC"' in html),
    ("Brand body class = brand-inorizonti", 'class="doc brand-inorizonti' in html),
    ("Doc type class = doc-letter", "doc-letter" in html),
    ("no-meta-band present (letter)", "no-meta-band" in html),
    ("Masthead present", '<header class="masthead">' in html),
    ("Brand card present", 'class="brand-card"' in html),
    ("Logo stack present", 'class="logo-stack"' in html),
    ("Header rows present", "header-row-1" in html),
    ("Footer present", '<footer class="brand-footer">' in html),
    ("Footer left column", "footer-left" in html),
    ("Footer center placeholder", "footer-page-number-placeholder" in html),
    ("Footer right column", "footer-right" in html),
    ("Letter reference line present", 'class="letter-reference-line"' in html),
    ("Letter shell present", 'class="letter-shell"' in html),
    ("Letter panel present", 'class="panel letter-panel"' in html),
    ("Sections HTML rendered", "Introduccion" in html),
    ("Text section rendered", "texto plano" in html),
    ("Markdown section rendered", "Contenido Markdown" in html),
    ("Markdown rendered — <h1> present", "<h1>" in html),
    ("Markdown rendered — <strong> present", "<strong>" in html),
    ("HTML section rendered — notice warning", "notice warning" in html),
    ("Table section rendered", "Producto" in html and "Cantidad" in html),
    ("Table headers rendered", "<th" in html),
    ("Callout section rendered", "callout" in html),
    ("Callout level — warning", "callout-warning" in html),
    ("Checklist section rendered", "checklist-list" in html),
    ("Checklist item — checked", "checked" in html),
    ("Indicator section rendered", "metric-card" in html),
    ("Indicator value — 94%", "94%" in html),
    ("Divider section rendered", "section-divider" in html),
    ("Divider label — Nueva Seccion", "Nueva Seccion" in html),
    ("Page break present", 'page-break' in html),
    ("Text after page break rendered", "despues de un salto" in html),
    ("Signature block rendered", "signature-grid" in html),
    ("Signer name — Juan Perez", "Juan Perez" in html),
    ("Signer role — Director", "Director" in html),
    ("CSS style block present", "<style>" in html),
    ("Base CSS inlined", "--font-main" in html),
    ("Brand CSS inlined", "brand-inorizonti" in html),
    ("Data brand attribute", 'data-brand="inorizonti"' in html),
    ("Data doc-type attribute", 'data-doc-type="letter"' in html),
    ("Title in output", "Documento de prueba" in html),
    ("DIN in output", "DIN-TEST-000999" in html),
    ("Footer shows brand name", "Inorizonti" in html),
    ("Footer shows contact info", "contacto@inorizonti.com" in html),
]

for label, ok in checks:
    if ok:
        print(f"  PASS: {label}")
    else:
        print(f"  FAIL: {label}")
        failures += 1

# ── Summary ────────────────────────────────────────────────────────
total = len(checks)
print(f"\n{'-' * 50}")
if failures:
    print(f"RESULT: {total - failures}/{total} passed  --  {failures} FAILURE(S)")
    print(f"  Output kept at: {output_path}")
    sys.exit(1)
else:
    print(f"RESULT: {total}/{total} passed  [OK]")
    print(f"  Output: {output_path}")
    sys.exit(0)
