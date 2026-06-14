"""
test_template.py -- Render document_base.html.j2 with a minimal ctx dict.

Run:  python scripts/test_template.py

Saves output to scripts/test_output_letter.html.
Open that file in a browser and visually compare with letter.html.
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jinja2 import Environment, FileSystemLoader

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "tardis", "shared", "templates")
BRANDS_DIR = os.path.join(PROJECT_ROOT, "tardis", "shared", "brands")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scripts")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "test_output_letter.html")

# ── Load helpers ───────────────────────────────────────────────────
def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Brand: inorizonti ─────────────────────────────────────────────
brand_name = "inorizonti"
brand_json = load_json(os.path.join(BRANDS_DIR, brand_name, "brand.json"))
brand_css = read_file(os.path.join(BRANDS_DIR, brand_name, "brand.css"))
brand_logo_svg = read_file(os.path.join(BRANDS_DIR, brand_name, "logo.svg"))

# ── CSS files ──────────────────────────────────────────────────────
base_css = read_file(os.path.join(TEMPLATES_DIR, "base.css"))
grid_css = read_file(os.path.join(TEMPLATES_DIR, "grid.css"))
components_css = read_file(os.path.join(TEMPLATES_DIR, "components.css"))
print_css = read_file(os.path.join(TEMPLATES_DIR, "print.css"))

# ── Minimal test data ──────────────────────────────────────────────
doc_data = {
    "title": "Aprobacion requerida para ajuste de numeracion",
    "din": "DIN-COM-000001",
    "date": "2026-06-03",
    "reference": "Ticket DIN-1780432370499",
    "contact": {"name": "Cliente"},
    "status": "final",
}

sections_html = """
<div class='letter-shell'><div class='panel letter-panel'>
<p>Estimado cliente:</p>
<p>Por medio del presente se resume el alcance del ticket relacionado con la numeracion de proveedores.</p>
<p>Para proceder, requerimos su confirmacion expresa.</p>
<p>Atentamente,<br><strong>Equipo Inorizonti</strong></p>
</div></div>
"""

footer_data = {
    "unit_label": brand_json["footer_defaults"]["unit_label"],
    "show_contact": brand_json["footer_defaults"]["show_contact"],
    "brand_name": brand_json["legal_name"],
    "site": brand_json["site"],
    "mail": brand_json["mail"],
    "phone": brand_json["phone"],
}

# ── Build context dict ─────────────────────────────────────────────
ctx = {
    "base_css": base_css,
    "grid_css": grid_css,
    "components_css": components_css,
    "print_css": print_css,
    "brand_css": brand_css,
    "brand": brand_json,
    "brand_logo_svg": brand_logo_svg,
    "doc_type": "letter",
    "doc_type_meta": {"legend": "Carta"},
    "doc": doc_data,
    "audience": "external",
    "orientation": "portrait",
    "has_cover": False,
    "compact_header": False,
    "show_meta_band": False,
    "footer": footer_data,
    "header_row1": "Carta &middot; Inorizonti",
    "header_row2": doc_data["din"],
    "header_row3": doc_data["date"],
    "sections_html": sections_html,
}

# ── Render ─────────────────────────────────────────────────────────
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
tmpl = env.get_template("document_base.html.j2")
html = tmpl.render(ctx)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html)

file_size = os.path.getsize(OUTPUT_FILE)
print(f"Output written to: {OUTPUT_FILE}")
print(f"File size: {file_size} bytes")

# ── Basic content checks ───────────────────────────────────────────
failures = 0
checks = [
    ("DOCTYPE declaration", "<!doctype html>" in html),
    ("HTML lang=es-EC", 'lang="es-EC"' in html),
    ("Brand body class", 'class="doc brand-inorizonti' in html),
    ("Orientation class", "orient-portrait" in html),
    ("Audience class", "audience-external" in html),
    ("Doc type class", "doc-letter" in html),
    ("No-meta-band present", "no-meta-band" in html),
    ("Print hint present", "print-hint" in html),
    ("Masthead present", '<header class="masthead">' in html),
    ("Brand card present", 'class="brand-card"' in html),
    ("Logo stack present", 'class="logo-stack"' in html),
    ("Document heading present", 'document-heading' in html),
    ("Header rows present", "header-row-1" in html),
    ("Footer present", '<footer class="brand-footer">' in html),
    ("Footer left column", "footer-left" in html),
    ("Footer center placeholder", "footer-page-number-placeholder" in html),
    ("Footer right column", "footer-right" in html),
    ("Page body present", 'class="page-body"' in html),
    ("Document flow present", 'class="document-flow"' in html),
    ("Letter shell present", 'class="letter-shell"' in html),
    ("Letter panel present", 'class="panel letter-panel"' in html),
    ("Running header present", 'class="running-header"' in html),
    ("CSS style block present", "<style>" in html),
    ("Base CSS inlined", "--font-main" in html),
    ("Components CSS inlined", ".masthead" in html),
    ("Grid CSS inlined", ".grid" in html),
    ("Print CSS inlined", "@page" in html),
    ("Brand CSS inlined", "brand-inorizonti" in html),
    ("Title in output", "Aprobacion requerida" in html),
    ("DIN in output", "DIN-COM-000001" in html),
    ("Date in output", "2026-06-03" in html),
    ("Footer unit label in output", "Tiempo, Ahorro y Riesgo" in html),
    ("Footer contact info", "contacto@inorizonti.com" in html),
    ("Sections HTML rendered", "Estimado cliente" in html),
    ("Letter reference line present", 'class="letter-reference-line"' in html),
    ("Data attributes", 'data-brand="inorizonti"' in html),
    ("Data doc-type attribute", 'data-doc-type="letter"' in html),
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
    print(f"  Output kept at: {OUTPUT_FILE}")
    sys.exit(1)
else:
    print(f"RESULT: {total}/{total} passed  [OK]")
    print(f"  Open {OUTPUT_FILE} in a browser to compare with letter.html")
    sys.exit(0)
