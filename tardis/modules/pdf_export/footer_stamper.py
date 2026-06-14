"""
footer_stamper.py — Post-process PDFs to overlay centered page numbers in the footer.

Public function:
    stamp_page_numbers(input_path, output_path, brand_json, footer_data)

Each page of *input_path* receives a "Pagina X de Y" label stamped at the
bottom center via pikepdf + reportlab. The stamp PDF is generated in-memory
(no temp files) with a transparent background so only the page-number text
overlays the Chromium-printed content.
"""

import io
import logging

import pikepdf
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

logger = logging.getLogger("tardis")

# Muted gray from the reference CSS (--muted: #667085)
_PAGE_NUMBER_COLOR = (0.40, 0.47, 0.52)
_FONT_SIZE = 8.5  # points


def _make_stamp_bytes(
    page_w_pts: float,
    page_h_pts: float,
    page_num: int,
    total_pages: int,
) -> io.BytesIO:
    """Generate an in-memory stamp PDF with centered page-number text.

    The stamp canvas has a transparent background so only the text overlays
    the underlying page content.
    """
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_w_pts, page_h_pts))

    # Position: centered horizontally, 6 mm from the bottom edge.
    # 6 mm ≈ 17 pt (1 mm ≈ 2.83 pt; 6 × 2.83 ≈ 16.97)
    bottom_y = 6 * mm

    c.setFont("Helvetica", _FONT_SIZE)
    c.setFillColorRGB(*_PAGE_NUMBER_COLOR)
    c.drawCentredString(page_w_pts / 2, bottom_y, f"Página {page_num} de {total_pages}")
    c.showPage()
    c.save()

    buf.seek(0)
    return buf


def stamp_page_numbers(
    input_path: str,
    output_path: str,
    brand_json: dict | None = None,
    footer_data: dict | None = None,
) -> None:
    """Overlay ``Pagina {n} de {N}`` at the bottom centre of every page.

    Args:
        input_path: Path to the PDF produced by Chromium ``printToPdf``.
        output_path: Where to write the finished PDF.
        brand_json: Unused in Phase 4a — reserved for brand-specific
                    stamp styling (font, colour).
        footer_data: Unused in Phase 4a — reserved for custom footer text.

    Raises:
        Any exception is logged with full traceback and re-raised so the
        caller (``engine.py``) can convert it to ``NocoResult.fail``.
    """
    try:
        with pikepdf.open(input_path) as pdf:
            total_pages = len(pdf.pages)

            for i, page in enumerate(pdf.pages, start=1):
                # Read page dimensions from /MediaBox
                # MediaBox is a Rectangle [llx, lly, urx, ury]
                mb = page.MediaBox
                page_w = float(mb[2] - mb[0])
                page_h = float(mb[3] - mb[1])

                # Create stamp
                stamp_io = _make_stamp_bytes(page_w, page_h, i, total_pages)

                # Merge stamp onto the page
                with pikepdf.open(stamp_io) as stamp_pdf:
                    stamp_page = stamp_pdf.pages[0]
                    # add_overlay places stamp_page content as a Form XObject
                    # on top of the existing page content. push_stack=False
                    # avoids an extra q/Q pair; shrink/expand control fitting.
                    page.add_overlay(stamp_page, shrink=True, expand=True)

            pdf.save(output_path)
            logger.info(
                "Stamped page numbers on %d pages -> %s", total_pages, output_path
            )

    except Exception:
        logger.exception("Failed to stamp page numbers on %s", input_path)
        raise
