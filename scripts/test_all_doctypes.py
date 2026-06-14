"""
test_all_doctypes.py — CHECKPOINT FINAL (Phase 4a).

Generates one PDF per document type (all 10) with brand bisstox.
Also generates a confidential document and a multi-page document.

Run:  python scripts/test_all_doctypes.py

For each document:
  - NocoResult.success == True
  - PDF file exists and is non-empty
  - Page count >= 1

Output PDFs are saved to scripts/test_all_doctypes_output/.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

from tardis.modules.pdf_export.engine import generate_pdf
from tardis.modules.pdf_export.chromium_printer import ChromiumPrinter

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scripts", "test_all_doctypes_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BRAND = "bisstox"

# ── Helper to build a document dict ────────────────────────────────
def make_doc(
    doc_type: str,
    title: str,
    din: str,
    sections: list[dict],
    audience: str = "external",
    has_cover: bool = False,
    compact_header: bool = False,
) -> dict:
    return {
        "brand": BRAND,
        "doc_type": doc_type,
        "audience": audience,
        "has_cover": has_cover,
        "compact_header": compact_header,
        "document": {
            "title": title,
            "din": din,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "contact": {"name": "Cliente de prueba"},
            "status": "final",
            "sections": sections,
        },
    }


# ── Shared content snippets ────────────────────────────────────────
TEXT_SECTION = {"type": "text", "content": "Contenido de texto de prueba para verificar el correcto renderizado del documento."}

def table_section(items: list[list[str]]) -> dict:
    return {"type": "table", "headers": ["Item", "Descripción", "Cantidad"], "rows": items}

SECTIONS_2PAGE = [
    {"type": "text", "title": "Página 1", "content": "Contenido de la primera página del documento."},
    {"type": "page_break"},
    {"type": "text", "title": "Página 2", "content": "Contenido de la segunda página — se verifica que page_break fuerza un salto."},
]


# ── All 10 document types ──────────────────────────────────────────
DOC_TYPES = [
    ("report", "Informe trimestral de ventas", "DIN-RPT-000001", [
        {"type": "text", "title": "Resumen ejecutivo", "content": "Cifras de ventas del Q2 2026 muestran crecimiento sostenido."},
        table_section([["Ventas netas", "$450K", "1"], ["Margen bruto", "$180K", "1"]]),
    ]),
    ("technical_report", "Informe técnico de infraestructura", "DIN-TEC-000042", [
        {"type": "text", "title": "Resumen", "content": "Análisis de rendimiento de servidores en producción."},
        {"type": "callout", "level": "warning", "body": "<strong>Nota:</strong> Se requiere mantenimiento preventivo antes del próximo release."},
    ]),
    ("support_ticket", "Ticket de soporte #4281", "DIN-TKT-004281", [
        {"type": "text", "title": "Descripción", "content": "Usuario reporta error al intentar generar reporte de facturación."},
        {"type": "text", "title": "Solución propuesta", "content": "Reiniciar servicio de base de datos y limpiar caché."},
    ]),
    ("delivery_act", "Acta de entrega proyecto Alpha", "DIN-DLV-000777", [
        {"type": "text", "title": "Entregables", "content": "Módulo de facturación, panel de administración, API REST."},
        table_section([["Facturación", "Completo", "1"], ["Admin", "Pendiente revisión", "1"]]),
    ]),
    ("letter", "Carta de presentación comercial", "DIN-LTR-000123", [
        {"type": "text", "content": "Estimado cliente:\n\nPor medio de la presente, presentamos nuestra propuesta comercial para el desarrollo del sistema de gestión documental."},
        {"type": "text", "content": "Quedamos atentos a sus comentarios.\n\nAtentamente,\nEquipo Bisstox"},
    ]),
    ("communication", "Comunicado interno", "DIN-COM-000456", [
        {"type": "text", "title": "Aviso importante", "content": "Se informa que el horario de atención al público se extenderá hasta las 18:00 a partir del próximo mes."},
    ]),
    ("minutes", "Acta de reunión semanal", "DIN-MIN-000789", [
        {"type": "text", "title": "Asistentes", "content": "Juan Pérez, María Gómez, Carlos Ruiz."},
        {"type": "checklist", "items": [
            {"text": "Revisar presupuesto Q3", "checked": True},
            {"text": "Aprobar contratación", "checked": True},
            {"text": "Programar demo con cliente", "checked": False},
        ]},
    ]),
    ("quote", "Cotización servicios de consultoría", "DIN-QTE-000321", [
        {"type": "text", "title": "Alcance", "content": "Consultoría en transformación digital por 3 meses."},
        table_section([["Consultoría estratégica", "40 horas", "$8,000"], ["Implementación", "80 horas", "$16,000"]]),
        {"type": "signature_block", "signers": [
            {"name": "Juan Pérez", "role": "Director Comercial"},
            {"name": "María Gómez", "role": "Cliente"},
        ]},
    ]),
    ("manual", "Manual de usuario — Sistema Tardis", "DIN-MNL-000654", [
        {"type": "text", "title": "Introducción", "content": "Bienvenido al manual de usuario del sistema Tardis."},
        {"type": "page_break"},
        {"type": "text", "title": "Módulo de correo", "content": "El módulo LocalMail permite gestionar correos electrónicos internos."},
    ]),
    ("checklist", "Lista de verificación — Auditoría", "DIN-CHK-000987", [
        {"type": "text", "title": "Auditoría de seguridad", "content": "Lista de verificación para la auditoría anual de seguridad."},
        {"type": "checklist", "items": [
            {"text": "Revisar accesos", "checked": True},
            {"text": "Actualizar firewalls", "checked": False},
            {"text": "Respaldos verificados", "checked": True},
            {"text": "Pruebas de penetración", "checked": False},
        ]},
        {"type": "indicator", "label": "Cumplimiento", "value": "50%", "trend": "up", "note": "Dos de cuatro items completados"},
    ]),
]

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print("  CHECKPOINT FINAL (Phase 4a) — All 10 document types")
print(f"  Brand: {BRAND}")
print("=" * 60)

app = QApplication(sys.argv)
app.setApplicationName("Tardis Test")

view = QWebEngineView()
printer = ChromiumPrinter()
printer.set_view(view)

results = []
failures = 0

for doc_type, title, din, sections in DOC_TYPES:
    print(f"\n  [{doc_type}] {title}")

    data = make_doc(doc_type, title, din, sections)
    filename = f"{doc_type}_{din}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)

    # Remove any leftover from a previous run
    if os.path.exists(output_path):
        os.remove(output_path)

    result = generate_pdf(data, BRAND, output_path, printer, open_after=False)

    doc_ok = True
    reasons = []

    # Check 1: success
    if not result.success:
        doc_ok = False
        reasons.append(f"success=False ({'; '.join(result.errors)})")

    # Check 2: file exists
    if not os.path.exists(output_path):
        doc_ok = False
        reasons.append("file not found")
    else:
        file_size = os.path.getsize(output_path)
        if file_size <= 0:
            doc_ok = False
            reasons.append("file empty")

    # Check 3: page count >= 1
    try:
        import pikepdf
        with pikepdf.open(output_path) as pdf:
            pages = len(pdf.pages)
            if pages < 1:
                doc_ok = False
                reasons.append(f"0 pages")
    except Exception as exc:
        doc_ok = False
        reasons.append(f"pikepdf error: {exc}")
        pages = 0

    # Check 4: NocoResult page count matches actual pages
    if result.success:
        reported = result.data.get("pages", 0)
        if reported != pages:
            doc_ok = False
            reasons.append(f"reported {reported} pages but actual {pages}")

    # Check 5: meta dict
    meta = result.meta or {}
    if meta.get("brand") != BRAND:
        doc_ok = False
        reasons.append(f"meta.brand mismatch")
    if meta.get("doc_type") != doc_type:
        doc_ok = False
        reasons.append(f"meta.doc_type mismatch")

    if doc_ok:
        print(f"    PASS: {pages} page(s), {file_size} bytes")
    else:
        print(f"    FAIL: {'; '.join(reasons)}")
        failures += 1

    results.append((doc_type, doc_ok, pages, file_size if os.path.exists(output_path) else 0))

# ── Extra test: confidential watermark ─────────────────────────────
print(f"\n  [confidential] Documento confidencial con marca de agua")
conf_data = make_doc(
    "letter", "Documento confidencial", "DIN-CONF-000001",
    [{"type": "text", "content": "Este documento contiene información confidencial y debe mostrar una marca de agua."}],
    audience="confidential",
)
conf_path = os.path.join(OUTPUT_DIR, "confidential_watermark.pdf")
if os.path.exists(conf_path):
    os.remove(conf_path)
result = generate_pdf(conf_data, BRAND, conf_path, printer, open_after=False)
if result.success and os.path.exists(conf_path) and os.path.getsize(conf_path) > 0:
    try:
        import pikepdf
        with pikepdf.open(conf_path) as pdf:
            pages = len(pdf.pages)
            print(f"    PASS: {pages} page(s), {os.path.getsize(conf_path)} bytes")
    except Exception:
        print(f"    FAIL: pikepdf could not open confidential PDF")
        failures += 1
else:
    print(f"    FAIL: {'; '.join(result.errors) if not result.success else 'file issue'}")
    failures += 1

# ── Extra test: page_break forces 2 pages ──────────────────────────
print(f"\n  [multi-page] Documento con page_break (2+ páginas)")
mp_data = make_doc("report", "Informe multi-página", "DIN-MP-000001", SECTIONS_2PAGE)
mp_path = os.path.join(OUTPUT_DIR, "multi_page_test.pdf")
if os.path.exists(mp_path):
    os.remove(mp_path)
result = generate_pdf(mp_data, BRAND, mp_path, printer, open_after=False)
if result.success:
    import pikepdf
    with pikepdf.open(mp_path) as pdf:
        pages = len(pdf.pages)
        if pages >= 2:
            print(f"    PASS: {pages} pages (page_break forces multi-page)")
        else:
            print(f"    FAIL: expected >= 2 pages, got {pages}")
            failures += 1
else:
    print(f"    FAIL: {'; '.join(result.errors)}")
    failures += 1

# ── Cleanup ────────────────────────────────────────────────────────
view.close()
view.deleteLater()

# ── Final summary ──────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"  RESULTS: {len(results) + 2} documents total")
passed_count = len(results) + 2 - failures
print(f"  Passed: {passed_count}, Failed: {failures}")
print(f"  Output directory: {OUTPUT_DIR}")
print(f"{'=' * 60}")

if failures:
    print(f"\n  FAILED DOCUMENTS:")
    for doc_type, ok, pages, size in results:
        if not ok:
            print(f"    - {doc_type}")
    sys.exit(1)
else:
    print(f"\n  All checks passed  [OK]")
    print(f"\n  To visually verify, open PDFs from:")
    print(f"    {OUTPUT_DIR}")
    print(f"  Recommended: letter, support_ticket, quote, ")
    print(f"    confidential_watermark.pdf, multi_page_test.pdf")
    sys.exit(0)
