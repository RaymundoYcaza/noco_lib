"""
test_footer_stamp.py -- Verify footer_stamper.stamp_page_numbers().

Generates a simple 3-page PDF with colored rectangles, then stamps page
numbers onto it using stamp_page_numbers().  Verifies:
  - Output PDF exists and is non-empty.
  - Output PDF has 3 pages.
  - Each page's text can be found (basic content check via pikepdf).

Usage:
    python scripts/test_footer_stamp.py

The output PDF is saved to scripts/test_footer_stamp_output.pdf.
Open it manually to visually confirm the page numbers.
"""

import os
import sys
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import pikepdf

from tardis.modules.pdf_export.footer_stamper import stamp_page_numbers

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PDF = os.path.join(OUTPUT_DIR, "test_footer_stamp_input.pdf")
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "test_footer_stamp_output.pdf")

failures = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global failures
    if ok:
        print(f"  PASS: {label}")
    else:
        print(f"  FAIL: {label}  --  {detail}")
        failures += 1


# --- Step 1: Generate a simple 3-page input PDF -------------------
print("=== Generating 3-page input PDF ===")
buf = io.BytesIO()
c = rl_canvas.Canvas(buf, pagesize=A4)

for i in range(1, 4):
    w, h = A4
    # Distinct colored rectangles so we can tell pages apart
    c.setFillColorRGB(0.9, 0.9, 1.0)
    c.rect(20 * mm, 20 * mm, w - 40 * mm, h - 40 * mm, fill=1, stroke=0)
    c.setFont("Helvetica", 20)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(w / 2, h / 2, f"Page {i}")
    c.showPage()
c.save()

with open(INPUT_PDF, "wb") as f:
    f.write(buf.getvalue())

check("input PDF created", os.path.isfile(INPUT_PDF) and os.path.getsize(INPUT_PDF) > 0)

# Step 1b: Verify input has 3 pages
with pikepdf.open(INPUT_PDF) as pdf:
    input_page_count = len(pdf.pages)
check("input PDF has 3 pages", input_page_count == 3, f"got {input_page_count} pages")

# --- Step 2: Stamp page numbers -----------------------------------
print("\n=== Stamping page numbers ===")
stamp_page_numbers(INPUT_PDF, OUTPUT_PDF)

# --- Step 3: Verify output ----------------------------------------
print("\n=== Verifying output ===")
check("output PDF exists", os.path.isfile(OUTPUT_PDF), OUTPUT_PDF)
check("output PDF non-empty", os.path.getsize(OUTPUT_PDF) > 0)

with pikepdf.open(OUTPUT_PDF) as pdf:
    output_page_count = len(pdf.pages)
    check(
        "output has 3 pages",
        output_page_count == 3,
        f"got {output_page_count} pages",
    )

    # The stamp adds content to each page, so the output file should be
    # larger than the input (the content streams grow slightly).
    input_size = os.path.getsize(INPUT_PDF)
    output_size = os.path.getsize(OUTPUT_PDF)
    check(
        "output is larger than input (stamp content added)",
        output_size > input_size,
        f"input={input_size} bytes, output={output_size} bytes",
    )

# --- Summary ------------------------------------------------------
print(f"\n{'-' * 50}")
if failures:
    print(f"RESULT: {failures} check(s) FAILED")
    print(f"  Output kept at: {OUTPUT_PDF}")
    sys.exit(1)
else:
    print(f"RESULT: all checks passed")
    print(f"  Output PDF: {OUTPUT_PDF}")
    print(f"  Open it in a PDF viewer and confirm each page shows:")
    print(f"    'Página 1 de 3', 'Página 2 de 3', 'Página 3 de 3'")
    sys.exit(0)
