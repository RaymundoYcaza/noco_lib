"""
test_schema.py -- Verify schema_validator against known test cases.

Run:  python scripts/test_schema.py

Expected output:
  PASS: valid letter document -> success=True
  PASS: empty dict -> success=False with >=3 errors
  PASS: invalid brand -> success=False
  PASS: missing document.contact -> success=False
  PASS: invalid doc_type -> success=False
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tardis.modules.pdf_export.schema_validator import validate_document

failures = 0


def check(label: str, got, expected: dict) -> None:
    global failures
    ok = True
    for key, val in expected.items():
        if key not in got or got[key] != val:
            ok = False
            break

    if ok:
        print(f"  PASS: {label}  ->  {got}")
    else:
        print(f"  FAIL: {label}  ->  expected {expected}, got {got}")
        failures += 1


def check_min(label: str, got, key: str, min_val) -> None:
    """Assert got[key] >= min_val. This is a separate pass/fail check."""
    global failures
    actual = got.get(key)
    if actual is not None and actual >= min_val:
        print(f"  PASS: {label}  ->  {got}")
    else:
        print(f"  FAIL: {label}  ->  expected {key}>={min_val}, got {got}")
        failures += 1


# --- Valid minimal document ----------------------------------------
valid_data = {
    "brand": "bisstox",
    "doc_type": "letter",
    "document": {
        "title": "Test",
        "din": "DIN-001",
        "contact": {"name": "John"},
    },
}
result = validate_document(valid_data)
check("valid letter document", result.to_dict(), {
    "success": True,
    "operation": "schema",
    "data": {"valid": True},
    "errors": [],
})

# --- Empty dict ----------------------------------------------------
result = validate_document({})
check_min(
    f"empty dict  ->  {len(result.errors)} errors (expected >=3)",
    {"success": result.success, "errors_count": len(result.errors)},
    "errors_count",
    3,
)
if result.errors:
    print(f"       first 5 errors: {result.errors[:5]}")

# --- Invalid brand -------------------------------------------------
result = validate_document({
    "brand": "nonexistent",
    "doc_type": "letter",
    "document": {"title": "T", "din": "D", "contact": {"name": "N"}},
})
check("invalid brand", result.to_dict(), {
    "success": False,
    "operation": "schema",
})
if result.errors:
    print(f"       error: {result.errors[0]}")

# --- Missing document.contact --------------------------------------
result = validate_document({
    "brand": "plyson",
    "doc_type": "letter",
    "document": {"title": "T", "din": "D"},
})
check("missing document.contact", result.to_dict(), {
    "success": False,
    "operation": "schema",
})

# --- Invalid doc_type ----------------------------------------------
result = validate_document({
    "brand": "bisstox",
    "doc_type": "invalid_type",
    "document": {"title": "T", "din": "D", "contact": {"name": "N"}},
})
check("invalid doc_type", result.to_dict(), {
    "success": False,
    "operation": "schema",
})

# --- Summary -------------------------------------------------------
total = 5
if failures:
    print(f"\n{'-' * 50}")
    print(f"RESULT: {total - failures}/{total} passed  --  {failures} FAILURE(S)")
    sys.exit(1)
else:
    print(f"\n{'-' * 50}")
    print(f"RESULT: {total}/{total} passed  [OK]")
    sys.exit(0)
