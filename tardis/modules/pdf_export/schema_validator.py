"""
schema_validator.py — JSON Schema validation for PDF document data.

Public function:
    validate_document(data: dict) -> NocoResult

Validates *data* against document_schema.json using jsonschema.
On success returns NocoResult.ok("schema", data={"valid": True}).
On failure returns NocoResult.fail("schema", errors=[...]) listing ALL
validation errors (not just the first).
"""

import json
import logging
from pathlib import Path

import jsonschema
from jsonschema import ValidationError

from tardis.noco_lib.noco_core.result import NocoResult

logger = logging.getLogger("tardis")

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "document_schema.json"

# Module-level cache — load once at import time
_schema = None


def _get_schema() -> dict:
    """Load and return the document schema (cached after first call)."""
    global _schema
    if _schema is None:
        if not _SCHEMA_PATH.exists():
            raise FileNotFoundError(
                f"Document schema not found at {_SCHEMA_PATH}. "
                f"Expected file: document_schema.json"
            )
        with _SCHEMA_PATH.open("r", encoding="utf-8") as f:
            _schema = json.load(f)
    return _schema


def validate_document(data: dict) -> NocoResult:
    """Validate *data* against the document JSON Schema.

    Returns:
        NocoResult(success=True,  operation="schema", data={"valid": True})
            if the data passes validation.
        NocoResult(success=False, operation="schema", errors=[...])
            listing every validation error if validation fails.
    """
    try:
        schema = _get_schema()
    except FileNotFoundError as exc:
        logger.exception("Could not load document schema")
        return NocoResult.fail("schema", str(exc))

    try:
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=str)
        if errors:
            error_messages = [str(e) for e in errors]
            return NocoResult.fail("schema", error_messages)
        return NocoResult.ok("schema", data={"valid": True})

    except Exception as exc:
        logger.exception("Unexpected error during document validation")
        return NocoResult.fail("schema", str(exc))
