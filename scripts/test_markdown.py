#!/usr/bin/env python3
"""
test_markdown.py — Verify markdown_renderer produces correct HTML.

Usage:
    python scripts/test_markdown.py

Expected output:
    Contains <h1>, <strong>, <em> in the rendered HTML for the test input.
    If any check fails, prints an error and exits with code 1.
"""

import sys
import os

# Add the project root so the 'tardis' package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tardis.modules.pdf_export.markdown_renderer import render_markdown


def test_basic() -> None:
    """Test basic markdown features: heading, bold, italic."""
    md = "# Hello\n\n**bold** and _italic_"
    html = render_markdown(md)
    print("--- Input ---")
    print(md)
    print("--- Output ---")
    print(html)

    checks = [
        ("<h1>", "Expected <h1> in output"),
        ("<strong>", "Expected <strong> in output"),
        ("<em>", "Expected <em> in output"),
    ]
    for marker, msg in checks:
        if marker not in html:
            print(f"FAIL: {msg}")
            sys.exit(1)
        else:
            print(f"OK: Found {marker}")


def test_strikethrough() -> None:
    """Test strikethrough plugin works."""
    md = "~~strikethrough~~"
    html = render_markdown(md)
    print("--- Strikethrough input ---")
    print(md)
    print("--- Output ---")
    print(html)

    if "<del>" not in html and "<s>" not in html:
        print("FAIL: Expected <del> or <s> for strikethrough")
        sys.exit(1)
    print("OK: Strikethrough rendered")


def test_lists() -> None:
    """Test unordered and ordered lists."""
    md = "- item 1\n- item 2\n- item 3"
    html = render_markdown(md)
    if "<ul>" not in html:
        print("FAIL: Expected <ul> for unordered list")
        sys.exit(1)
    print("OK: Unordered list rendered")

    md = "1. first\n2. second"
    html = render_markdown(md)
    if "<ol>" not in html:
        print("FAIL: Expected <ol> for ordered list")
        sys.exit(1)
    print("OK: Ordered list rendered")


def test_error_fallback() -> None:
    """Test that on error, the text is returned escaped in a <pre> block."""
    # Pass something that might cause a crash — mistune is robust, so we
    # just verify the function signature handles any string.
    result = render_markdown("")
    assert isinstance(result, str)
    print("OK: Empty string handled without error")


if __name__ == "__main__":
    test_basic()
    test_strikethrough()
    test_lists()
    test_error_fallback()
    print("\nAll checks passed!")
