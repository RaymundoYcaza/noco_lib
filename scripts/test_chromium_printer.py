"""
test_chromium_printer.py — Integration test for ChromiumPrinter.

Run:  python scripts/test_chromium_printer.py

This test:
1. Creates a QApplication (required by QtWebEngine)
2. Generates HTML via engine.generate_html()
3. Creates a hidden QWebEngineView
4. Creates a ChromiumPrinter and passes the view
5. Calls printer.print_to_pdf() with a QEventLoop to wait for completion
6. Verifies the output PDF exists and is non-empty
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO)

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── Qt imports (must happen before QApplication is created) ────────
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

from tardis.modules.pdf_export.engine import generate_html
from tardis.modules.pdf_export.chromium_printer import ChromiumPrinter

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scripts")
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "test_chromium_printer_output.pdf")

# Remove any leftover from a previous run
if os.path.exists(OUTPUT_PDF):
    os.remove(OUTPUT_PDF)

# ── Test data ──────────────────────────────────────────────────────
TEST_DATA = {
    "brand": "inorizonti",
    "doc_type": "letter",
    "document": {
        "title": "Carta de prueba para ChromiumPrinter",
        "din": "DIN-CHR-000001",
        "date": "2026-06-14",
        "contact": {"name": "Usuario de Prueba"},
        "status": "final",
        "sections": [
            {
                "type": "text",
                "title": "Contenido de prueba",
                "content": "Este documento verifica que el pipeline ChromiumPrinter funciona correctamente.",
            },
            {
                "type": "page_break",
            },
            {
                "type": "text",
                "content": "Esta es la segunda pagina del documento de prueba.",
            },
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
failures = 0

# 1. Create QApplication (must be done before ANY Qt widgets)
print("=" * 60)
print("  TEST: ChromiumPrinter")
print("=" * 60)

app = QApplication(sys.argv)
app.setApplicationName("Tardis Test")

# 2. Generate HTML from engine
print("\n  Step 1: generate_html...")
html_result = generate_html(TEST_DATA, "inorizonti")
if not html_result.success:
    print(f"  FAIL: generate_html returned failure — {html_result.errors}")
    sys.exit(1)

html_text = html_result.data["html"]
print(f"  PASS: generate_html OK ({len(html_text)} chars)")

# 3. Create hidden QWebEngineView
print("  Step 2: Creating QWebEngineView...")
view = QWebEngineView()
view.setFixedSize(1, 1)  # Keep it small; printToPdf renders at full resolution
# Do NOT show the view — it's a hidden render target

# 4. Create ChromiumPrinter and set the view
print("  Step 3: Creating ChromiumPrinter...")
printer = ChromiumPrinter()
printer.set_view(view)

# 5. Set up QEventLoop to wait for the async operation
print("  Step 4: Calling print_to_pdf (async)...")

loop = QEventLoop()
result_holder = {}

def on_print_finished(success: bool, path: str) -> None:
    result_holder["success"] = success
    result_holder["path"] = path
    loop.quit()

printer.print_finished.connect(on_print_finished)

# Safety timeout: if QtWebEngine takes too long, abort
TIMEOUT_MS = 30000  # 30 seconds
timeout_timer = QTimer()
timeout_timer.setSingleShot(True)
timeout_timer.timeout.connect(lambda: loop.quit())

timeout_timer.start(TIMEOUT_MS)

# Start the print
printer.print_to_pdf(html_text, OUTPUT_PDF)

# Process events until the signal fires (or timeout)
loop.exec()

# Disconnect
try:
    printer.print_finished.disconnect(on_print_finished)
except (TypeError, RuntimeError):
    pass
timeout_timer.stop()

# 6. Verify results
print("\n  Step 5: Verifying output...")

if not result_holder.get("success"):
    print(f"  FAIL: print_finished reported failure")
    failures += 1
else:
    print(f"  PASS: print_finished reported success")

pdf_path = result_holder.get("path", "")
if not pdf_path:
    print(f"  FAIL: No output path in result")
    failures += 1
elif not os.path.exists(pdf_path):
    print(f"  FAIL: PDF file does not exist: {pdf_path}")
    failures += 1
else:
    file_size = os.path.getsize(pdf_path)
    print(f"  PASS: PDF exists at {pdf_path} ({file_size} bytes)")
    if file_size > 0:
        print(f"  PASS: PDF file is non-empty ({file_size} bytes)")
    else:
        print(f"  FAIL: PDF file is empty (0 bytes)")
        failures += 1

# Also verify we can open it with pikepdf to get page count
try:
    import pikepdf
    with pikepdf.open(OUTPUT_PDF) as pdf:
        page_count = len(pdf.pages)
        print(f"  PASS: pikepdf can open PDF ({page_count} page(s))")
        if page_count >= 1:
            print(f"  PASS: PDF has {page_count} page(s)")
        else:
            print(f"  FAIL: PDF has 0 pages")
            failures += 1
except Exception as exc:
    print(f"  FAIL: Could not open PDF with pikepdf — {exc}")
    failures += 1

# ── Clean up ───────────────────────────────────────────────────────
view.close()
view.deleteLater()

# ── Summary ────────────────────────────────────────────────────────
print(f"\n{'-' * 50}")
if failures:
    print(f"RESULT: {failures} FAILURE(S)")
    sys.exit(1)
else:
    print("RESULT: All checks passed  [OK]")
    print(f"  Output: {OUTPUT_PDF}")
    sys.exit(0)
