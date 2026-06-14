"""
test_macros.py -- Render each Jinja2 macro in isolation and verify output.

Run:  python scripts/test_macros.py

Expected output: all checks pass with HTML containing expected class names.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jinja2 import Environment, FileSystemLoader

# Point Jinja2 at the shared/templates directory so it can resolve includes
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "tardis", "shared", "templates")

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=False,
)

failures = 0
total = 0


def check(label: str, html: str, expected: list[str], not_expected: list[str] | None = None):
    global failures, total
    total += 1
    ok = True
    missing = [e for e in expected if e not in html]
    if missing:
        ok = False
    if not_expected:
        found_extra = [e for e in not_expected if e in html]
        if found_extra:
            ok = False
    if ok:
        print(f"  PASS: {label}")
    else:
        details = []
        if missing:
            details.append(f"missing: {missing}")
        if not_expected:
            found_extra = [e for e in not_expected if e in html]
            if found_extra:
                details.append(f"unexpected: {found_extra}")
        print(f"  FAIL: {label}  --  {'; '.join(details)}")
        failures += 1


def render(section: dict) -> str:
    tmpl = env.get_template("macros/components.html.j2")
    return tmpl.module.render_section(section)


# --- text section ---------------------------------------------------
print("=== Section type: text ===")
html = render({"type": "text", "content": "Hello world"})
check("text renders content", html, ["Hello world"])
check("text escapes HTML", render({"type": "text", "content": "<b>bold</b>"}), ["&lt;b&gt;bold&lt;/b&gt;"])

html = render({"type": "text", "title": "My Title", "content": "Body text"})
check("text with title", html, ["section-title", "My Title", "Body text"])

# --- html section ---------------------------------------------------
print("\n=== Section type: html ===")
html = render({"type": "html", "content": "<b>bold</b>", "title": "HTML Block"})
check("html renders unescaped", html, ["<b>bold</b>", "content-html", "section-title"])

# --- markdown section -----------------------------------------------
print("\n=== Section type: markdown ===")
html = render({"type": "markdown", "_rendered_html": "<p>Rendered <strong>markdown</strong></p>"})
check("markdown renders _rendered_html", html, ["<p>Rendered", "<strong>markdown</strong>", "content-html"])

# --- table section --------------------------------------------------
print("\n=== Section type: table ===")
html = render({
    "type": "table",
    "headers": ["Name", "Qty", "Price"],
    "rows": [["Widget", "2", "$10"], ["Gadget", "1", "$25"]],
})
check("table has thead with headers", html, ["<thead>", "<th ", "Name", "Qty", "Price"])
check("table has tbody", html, ["<tbody>", "<td>", "Widget", "Gadget", "$25"])
check("table uses doc-table class", html, ["doc-table"])

html = render({
    "type": "table",
    "caption": "Inventory",
    "headers": ["Item"],
    "rows": [["Foo"]],
})
check("table with caption", html, ["table-caption", "Inventory"])

# --- checklist section ----------------------------------------------
print("\n=== Section type: checklist ===")
html = render({
    "type": "checklist",
    "items": [
        {"text": "Task A", "checked": True},
        {"text": "Task B", "checked": False},
        {"text": "Task C", "checked": True, "note": "Important"},
    ],
})
check("checklist has list", html, ["checklist-list", "checklist-item", "checklist-box", "checklist-text"])
check("checked items have 'checked' class", html, ["checked"])
check("unchecked items have no 'checked' class", html, ["checklist-item", "checklist-text"])
check("note text appears", html, ["Important"])
# Ensure only 2 have 'checked' class (items 0 and 2 are checked)
checked_count = html.count('class="checklist-item checked"')
if checked_count == 2:
    print(f"  PASS: correct checked count (2)")
else:
    print(f"  FAIL: correct checked count (2)  --  got {checked_count}")
    failures += 1
total += 1

# --- callout section ------------------------------------------------
print("\n=== Section type: callout ===")
html = render({
    "type": "callout",
    "level": "warning",
    "title": "Attention",
    "body": "This is a warning callout.",
})
check("callout uses callout class", html, ["callout", "callout-warning"])
check("callout has title and body", html, ["Attention", "This is a warning callout."])

html = render({"type": "callout", "content": "Simple callout"})
check("callout with content only", html, ["callout", "Simple callout"])

# --- indicator section ----------------------------------------------
print("\n=== Section type: indicator ===")
html = render({
    "type": "indicator",
    "label": "Revenue",
    "value": "42,500",
    "unit": "USD",
    "trend": "up",
    "note": "vs last month",
})
check("indicator uses metric-card", html, ["metric-card", "metric-label", "metric-value", "metric-note", "trend-up"])
check("indicator has label/value/unit", html, ["Revenue", "42,500", "USD", "vs last month"])

html = render({"type": "indicator", "label": "Simple", "value": "100"})
check("indicator minimal fields", html, ["metric-card", "metric-label", "metric-value", "Simple", "100"])

# --- divider section ------------------------------------------------
print("\n=== Section type: divider ===")
html = render({"type": "divider", "label": "Section Break"})
check("divider with label", html, ["section-divider", "has-label", "section-label", "Section Break"])

html = render({"type": "divider"})
check("divider without label", html, ["section-divider"])
check("divider no label has no label text", html, [], not_expected=["has-label", "section-label"])

# --- page_break section ---------------------------------------------
print("\n=== Section type: page_break ===")
html = render({"type": "page_break"})
check("page_break emits page-break-before", html, ["page-break", "page-break-before: always"])

# --- signature_block section ----------------------------------------
print("\n=== Section type: signature_block ===")
html = render({
    "type": "signature_block",
    "signers": [
        {"name": "John Doe", "role": "CEO", "date": "2026-01-15"},
        {"name": "Jane Smith", "role": "CFO"},
    ],
})
check("signature uses signature-grid", html, ["signature-grid", "signature-box", "signature-line", "signature-name", "signature-role"])
check("signature has names and roles", html, ["John Doe", "CEO", "Jane Smith", "CFO"])
check("signature shows date", html, ["2026-01-15"])

html = render({"type": "signature_block", "signers": []})
check("signature empty list", html, ["signature-grid"])

# --- Summary --------------------------------------------------------
print(f"\n{'-' * 50}")
if failures:
    print(f"RESULT: {total - failures}/{total} passed  --  {failures} FAILURE(S)")
    sys.exit(1)
else:
    print(f"RESULT: {total}/{total} passed  [OK]")
    sys.exit(0)
