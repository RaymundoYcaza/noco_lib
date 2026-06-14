"""
markdown_renderer.py — Markdown → HTML rendering via mistune.

Public function:
    render_markdown(text: str) -> str

Wraps mistune with error handling: on failure, returns the original
text escaped in a <pre> block and logs the exception via the tardis
logger.
"""

import logging

import mistune

logger = logging.getLogger("tardis")

# Single shared markdown renderer instance (strikethrough plugin enabled)
_md = mistune.create_markdown(plugins=["strikethrough"])


def render_markdown(text: str) -> str:
    """Convert *text* (Markdown) to an HTML string.

    On success, returns the rendered HTML.
    On failure, escapes the original text as a ``<pre>`` block and logs
    the full traceback via ``logging.getLogger("tardis").exception``.
    """
    try:
        return _md(text)
    except Exception:
        logger.exception("Failed to render Markdown — falling back to escaped <pre>")
        # Escape <, >, & so the raw text is safe to embed as HTML
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f"<pre>{escaped}</pre>"
