"""
test_template.py -- Render document_base.html.j2 with a minimal ctx dict.

Run:  python scripts/test_template.py

Saves output to scripts/test_output_letter.html.
Open that file in a browser and visually compare with letter.html.
"""

import os
import sys
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jinja2 import Environment, FileSystemLoader

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "tardis", "shared", "templates")
BRANDS_DIR = os.path.join(PROJECT_ROOT, "tardis", "shared", "brands")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scripts")

# ── Load helpers ───────────────────────────────────────────────────
def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Brand: inorizonti ─────────────────────────────────────────────
brand_inorizonti_json = load_json(os.path.join(BRANDS_DIR, "inorizonti", "brand.json"))
brand_inorizonti_css = read_file(os.path.join(BRANDS_DIR, "inorizonti", "brand.css"))
brand_inorizonti_logo = read_file(os.path.join(BRANDS_DIR, "inorizonti", "logo.svg"))

# ── Brand: bisstox ────────────────────────────────────────────────
brand_bisstox_json = load_json(os.path.join(BRANDS_DIR, "bisstox", "brand.json"))
brand_bisstox_css = read_file(os.path.join(BRANDS_DIR, "bisstox", "brand.css"))
brand_bisstox_logo = read_file(os.path.join(BRANDS_DIR, "bisstox", "logo.svg"))

# ── CSS files ──────────────────────────────────────────────────────
base_css = read_file(os.path.join(TEMPLATES_DIR, "base.css"))
grid_css = read_file(os.path.join(TEMPLATES_DIR, "grid.css"))
components_css = read_file(os.path.join(TEMPLATES_DIR, "components.css"))
print_css = read_file(os.path.join(TEMPLATES_DIR, "print.css"))

# ── Jinja2 environment ────────────────────────────────────────────
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
tmpl = env.get_template("document_base.html.j2")


def body_has_class(html: str, class_name: str) -> bool:
    """Check if a CSS class is present in the <body> tag's class attribute."""
    m = re.search(r'<body[^>]*class="([^"]*)"', html)
    if not m:
        return False
    classes = m.group(1).split()
    return class_name in classes


def run_checks(ctx: dict, output_path: str, label: str) -> int:
    """Render template with ctx and run structural checks.
    Returns failure count for this test case.
    """
    html = tmpl.render(ctx)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(output_path)
    print(f"\n{'=' * 60}")
    print(f"  TEST: {label}")
    print(f"  Output: {output_path} ({file_size} bytes)")
    print(f"{'=' * 60}")

    # ── Derive expected values from ctx ──
    brand_name = ctx.get("brand", {}).get("name", "inorizonti")
    audience = ctx.get("audience", "external")
    doc_type = ctx.get("doc_type", "letter")
    doc_title = ctx.get("doc", {}).get("title", "")
    doc_din = ctx.get("doc", {}).get("din", "")
    show_meta = ctx.get("show_meta_band", False)
    orientation = ctx.get("orientation", "portrait")

    failures = 0
    checks = [
        ("DOCTYPE declaration", "<!doctype html>" in html),
        ("HTML lang=es-EC", 'lang="es-EC"' in html),
        ("Brand body class", f'class="doc brand-{brand_name}' in html),
        ("Orientation class", f"orient-{orientation}" in html),
        ("Audience class", f"audience-{audience}" in html),
        ("Doc type class", f"doc-{doc_type}" in html),
        ("no-meta-band on body (correctly absent when show_meta=True)",
         body_has_class(html, "no-meta-band") == (not show_meta)),
        ("Print hint present", "print-hint" in html),
        ("Masthead present", '<header class="masthead">' in html),
        ("Brand card present", 'class="brand-card"' in html),
        ("Logo stack present", 'class="logo-stack"' in html),
        ("Document heading present", "document-heading" in html),
        ("Header row 1 class", "header-row-1" in html),
        ("Header row 2 class", "header-row-2" in html),
        ("Header row 3 class", "header-row-3" in html),
        ("Footer present", '<footer class="brand-footer">' in html),
        ("Footer left column", "footer-left" in html),
        ("Footer center placeholder", "footer-page-number-placeholder" in html),
        ("Footer right column", "footer-right" in html),
        ("Page body present", 'class="page-body"' in html),
        ("Document flow present", 'class="document-flow"' in html),
        ("CSS style block present", "<style>" in html),
        ("Base CSS inlined", "--font-main" in html),
        ("Data brand attribute", f'data-brand="{brand_name}"' in html),
        ("Data doc-type attribute", f'data-doc-type="{doc_type}"' in html),
    ]

    # Add content checks only if we have a specific value to check
    if doc_title:
        checks.append(("Title in output", doc_title in html))
    if doc_din:
        checks.append(("DIN in output", doc_din in html))

    # Check footer brand name if present
    footer_brand_name = ctx.get("footer", {}).get("brand_name", "")
    if footer_brand_name:
        checks.append(("Footer brand name in output", footer_brand_name in html))

    # Check sections HTML
    sections = ctx.get("sections_html", "")
    if sections:
        # Extract a non-empty line or visible text snippet
        snippet = None
        for line in sections.split("\n"):
            stripped = line.strip()
            if stripped and len(stripped) > 10:
                snippet = stripped
                break
        if snippet:
            checks.append(("Sections HTML rendered", snippet in html))

    for name, ok in checks:
        if ok:
            print(f"  PASS: {name}")
        else:
            print(f"  FAIL: {name}")
            failures += 1

    # ── Test-case-specific checks ──
    specific_checks = ctx.get("_specific_checks", [])
    for name, ok in specific_checks:
        if ok:
            print(f"  PASS: {name}")
        else:
            print(f"  FAIL: {name}")
            failures += 1

    return failures


# ═══════════════════════════════════════════════════════════════════
#  TEST CASE 1 — All 3 header rows populated · inorizonti · letter
# ═══════════════════════════════════════════════════════════════════
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

footer_data_inori = {
    "unit_label": brand_inorizonti_json["footer_defaults"]["unit_label"],
    "show_contact": brand_inorizonti_json["footer_defaults"]["show_contact"],
    "brand_name": brand_inorizonti_json["legal_name"],
    "site": brand_inorizonti_json["site"],
    "mail": brand_inorizonti_json["mail"],
    "phone": brand_inorizonti_json["phone"],
}

ctx_all_rows = {
    "base_css": base_css,
    "grid_css": grid_css,
    "components_css": components_css,
    "print_css": print_css,
    "brand_css": brand_inorizonti_css,
    "brand": brand_inorizonti_json,
    "brand_logo_svg": brand_inorizonti_logo,
    "doc_type": "letter",
    "doc_type_meta": {"legend": "Carta"},
    "doc": doc_data,
    "audience": "external",
    "orientation": "portrait",
    "has_cover": False,
    "compact_header": False,
    "show_meta_band": False,
    "footer": footer_data_inori,
    "header_row1": "Carta \u00b7 Inorizonti",
    "header_row2": doc_data["din"],
    "header_row3": doc_data["date"],
    "sections_html": sections_html,
}

output_all = os.path.join(OUTPUT_DIR, "test_letter_all_rows.html")
html_all = tmpl.render(ctx_all_rows)
ctx_all_rows["_specific_checks"] = [
    ("Row 1 has non-empty content", "Carta" in html_all),
    ("Row 2 has DIN content", "DIN-COM-000001" in html_all),
    ("Row 3 has date content", "2026-06-03" in html_all),
    ("No header-row-empty class on populated row 1",
     "header-row-1" in html_all and "header-row-1 header-row-empty" not in html_all),
]
fail_all = run_checks(ctx_all_rows, output_all, "All 3 header rows populated")

# ═══════════════════════════════════════════════════════════════════
#  TEST CASE 2 — Only header row 2 populated · inorizonti · letter
# ═══════════════════════════════════════════════════════════════════
ctx_empty_13 = ctx_all_rows.copy()
ctx_empty_13.update({
    "header_row1": "",
    "header_row3": "",
    "_specific_checks": [],
})

output_empty_13 = os.path.join(OUTPUT_DIR, "test_letter_only_row2.html")
html_empty_13 = tmpl.render(ctx_empty_13)
ctx_empty_13["_specific_checks"] = [
    ("Row 1 has header-row-empty class", "header-row-1 header-row-empty" in html_empty_13),
    ("Row 3 has header-row-empty class", "header-row-3 header-row-empty" in html_empty_13),
    ("Row 2 does NOT have header-row-empty",
     "header-row-2" in html_empty_13 and "header-row-2 header-row-empty" not in html_empty_13),
    ("Row 2 still shows DIN content", "DIN-COM-000001" in html_empty_13),
    ("Empty rows still reserve space (div present)",
     html_empty_13.count("header-row-empty") >= 2),
]
fail_empty_13 = run_checks(ctx_empty_13, output_empty_13, "Only row 2 populated (rows 1 and 3 empty)")

# ═══════════════════════════════════════════════════════════════════
#  TEST CASE 3 — technical_report · bisstox · footer 3-column layout
# ═══════════════════════════════════════════════════════════════════
bisstox_doc_data = {
    "title": "Informe tecnico de infraestructura",
    "din": "DIN-INF-000042",
    "date": "2026-06-10",
    "contact": {"name": "Cliente"},
    "status": "final",
}

bisstox_footer_data = {
    "unit_label": brand_bisstox_json["footer_defaults"]["unit_label"],
    "show_contact": brand_bisstox_json["footer_defaults"]["show_contact"],
    "brand_name": brand_bisstox_json["legal_name"],
    "site": brand_bisstox_json["site"],
    "mail": brand_bisstox_json["mail"],
    "phone": brand_bisstox_json["phone"],
    "tagline": brand_bisstox_json["tagline"],
}

bisstox_sections = """
<div class="panel">
  <h2>Resumen ejecutivo</h2>
  <p>Se presenta el informe tecnico de la infraestructura de red correspondiente al periodo junio 2026.</p>
</div>
"""

ctx_bisstox = {
    "base_css": base_css,
    "grid_css": grid_css,
    "components_css": components_css,
    "print_css": print_css,
    "brand_css": brand_bisstox_css,
    "brand": brand_bisstox_json,
    "brand_logo_svg": brand_bisstox_logo,
    "doc_type": "technical_report",
    "doc_type_meta": {"legend": "Informe tecnico"},
    "doc": bisstox_doc_data,
    "audience": "internal",
    "orientation": "portrait",
    "has_cover": False,
    "compact_header": False,
    "show_meta_band": True,
    "footer": bisstox_footer_data,
    "header_row1": "Informe tecnico",
    "header_row2": bisstox_doc_data["din"],
    "header_row3": bisstox_doc_data["date"],
    "sections_html": bisstox_sections,
}

output_bisstox = os.path.join(OUTPUT_DIR, "test_bisstox_technical_report.html")
html_bisstox = tmpl.render(ctx_bisstox)
ctx_bisstox["_specific_checks"] = [
    ("Meta-band is shown (body does NOT have no-meta-band)",
     not body_has_class(html_bisstox, "no-meta-band")),
    ("Footer left column shows brand name",
     brand_bisstox_json["legal_name"] in html_bisstox),
    ("Footer shows contact mail", "ventas@bisstox.com" in html_bisstox),
    ("Footer right column shows tagline",
     brand_bisstox_json["tagline"] in html_bisstox),
    ("Footer-center has comment placeholder (not rendered text)",
     "footer-page-number-placeholder" in html_bisstox),
    ("Footer shows unit label",
     "Unidad de software" in html_bisstox),
]
fail_bisstox = run_checks(ctx_bisstox, output_bisstox, "technical_report · bisstox · 3-column footer")

# ═══════════════════════════════════════════════════════════════════
#  TEST CASE 4 — Same as case 3 but with right_html instead of tagline
# ═══════════════════════════════════════════════════════════════════
ctx_right_html = ctx_bisstox.copy()
ctx_right_html.update({
    "footer": {**bisstox_footer_data, "right_html": "<strong>Prioridad: alta</strong>"},
    "_specific_checks": [],
})

output_right = os.path.join(OUTPUT_DIR, "test_bisstox_right_html.html")
html_right = tmpl.render(ctx_right_html)
ctx_right_html["_specific_checks"] = [
    ("Right column shows right_html instead of tagline", "Prioridad: alta" in html_right),
    ("Tagline NOT shown when right_html present",
     brand_bisstox_json["tagline"] not in html_right),
]
fail_right = run_checks(ctx_right_html, output_right, "technical_report · bisstox · right_html in footer")

# ═══════════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════════
total_failures = fail_all + fail_empty_13 + fail_bisstox + fail_right
print(f"\n{'=' * 60}")
if total_failures:
    print(f"RESULT: {total_failures} FAILURE(S) across all test cases")
    sys.exit(1)
else:
    print("RESULT: All checks passed across all 4 test cases  [OK]")
    print(f"  {output_all}")
    print(f"  {output_empty_13}")
    print(f"  {output_bisstox}")
    print(f"  {output_right}")
    print("  Open these in a browser to visually compare.")
    sys.exit(0)
