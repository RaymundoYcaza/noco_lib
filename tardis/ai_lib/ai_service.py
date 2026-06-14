"""High-level AI operations for the ``ai_corrections`` module.

This layer loads prompt templates from ``ai_lib/prompts/*.txt`` at
import time, formats them with caller-provided values, and delegates
to ``AIClient.complete()``.  It is the primary import target for
``ai_corrections`` and any other module that needs AI functionality.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ai_lib.ai_result import AIResult

if TYPE_CHECKING:
    from ai_lib.ai_client import AIClient

import logging

logger = logging.getLogger("tardis")

# ── Module-level prompt cache ───────────────────────────────────────

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

PROMPTS: dict[str, str] = {}
"""Dictionary of ``{operation_name: prompt_template_string}`` loaded
from ``ai_lib/prompts/<operation>.txt`` at import time."""

for _op_name in ("correct", "classify", "extract", "summarize"):
    _path = _PROMPTS_DIR / f"{_op_name}.txt"
    try:
        PROMPTS[_op_name] = _path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to load prompt template: %s", _path)
        PROMPTS[_op_name] = ""


# ── Public API ──────────────────────────────────────────────────────


def correct_value(
    client: "AIClient",
    field_name: str,
    value: str,
    context: str = "",
) -> AIResult:
    """Correct spelling, grammar, and punctuation of *value*.

    Parameters
    ----------
    client : AIClient
    field_name : str
        Name of the field being corrected (for prompt context).
    value : str
        The text value to correct.
    context : str, optional
        Additional context for the AI (defaults to ``"None provided"``).

    Returns
    -------
    AIResult
    """
    prompt = PROMPTS.get("correct", "").format(
        field_name=field_name,
        value=value,
        context=context or "None provided",
    )
    return client.complete(prompt, "correct")


def classify_value(
    client: "AIClient",
    field_name: str,
    value: str,
    options: list[str],
    context: str = "",
) -> AIResult:
    """Classify *value* into one of the given *options*.

    After getting the AI response, validates that ``result.data`` is
    an exact match to one of the provided options.

    Parameters
    ----------
    client : AIClient
    field_name : str
    value : str
    options : list[str]
        Allowed classification labels (e.g. ``["Baja", "Media", "Alta"]``).
    context : str, optional

    Returns
    -------
    AIResult
        ``fail`` if the AI returns a value not in *options*.
    """
    prompt = PROMPTS.get("classify", "").format(
        field_name=field_name,
        value=value,
        context=context or "None provided",
        options=", ".join(options),
    )
    result = client.complete(prompt, "classify")

    # Validate that the response is one of the provided options
    if result.success and result.data not in options:
        return AIResult.fail(
            "classify",
            f"AI returned '{result.data}' which is not in options {options}",
            meta=result.meta,
        )
    return result


def extract_value(
    client: "AIClient",
    field_name: str,
    value: str,
    context: str = "",
) -> AIResult:
    """Extract the value of *field_name* from *value* (source text).

    Parameters
    ----------
    client : AIClient
    field_name : str
    value : str
        The source text to extract from.
    context : str, optional

    Returns
    -------
    AIResult
    """
    prompt = PROMPTS.get("extract", "").format(
        field_name=field_name,
        value=value,
        context=context or "None provided",
    )
    return client.complete(prompt, "extract")


def summarize_value(
    client: "AIClient",
    field_name: str,
    value: str,
    context: str = "",
) -> AIResult:
    """Summarize *value* in one concise sentence (max 120 chars).

    Parameters
    ----------
    client : AIClient
    field_name : str
    value : str
        The text to summarise.
    context : str, optional

    Returns
    -------
    AIResult
    """
    prompt = PROMPTS.get("summarize", "").format(
        field_name=field_name,
        value=value,
        context=context or "None provided",
    )
    return client.complete(prompt, "summarize")


# ── Estimation helper ───────────────────────────────────────────────


def estimate_time_seconds(records: list[dict], fields: list[str]) -> int:
    """Estimate the total AI processing time for the given records.

    Uses a heuristic of 50 tokens/second (typical for local Ollama).
    Total chars → tokens at roughly 4 chars/token.

    Parameters
    ----------
    records : list[dict]
        Record dictionaries from NocoDB.
    fields : list[str]
        Field names to process per record.

    Returns
    -------
    int
        Estimated time in seconds (minimum 1).
    """
    total_chars = sum(
        len(str(record.get(field, "")))
        for record in records
        for field in fields
    )
    estimated_tokens = total_chars // 4
    estimated_time = estimated_tokens // 50  # 50 tokens/sec baseline
    return max(1, estimated_time)
