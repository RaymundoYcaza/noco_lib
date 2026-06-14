"""
chromium_printer.py — QtWebEngine printToPdf wrapper for the PDF Export engine.

Usage (from the Qt main thread)::

    printer = ChromiumPrinter()
    printer.set_view(view)   # shared QWebEngineView created at startup

    # Connect to the signal
    printer.print_finished.connect(on_done)

    # Start async print
    printer.print_to_pdf(html_string, "/tmp/output.pdf", orientation="portrait")

The ``print_finished`` signal fires with ``(success: bool, path: str)``
when QtWebEngine finishes writing the PDF.

For synchronous-style usage (e.g. from ``generate_pdf``), drive the call
with a ``QEventLoop``::

    loop = QEventLoop()
    result_holder = {}

    def on_done(success, path):
        result_holder["success"] = success
        loop.quit()

    printer.print_finished.connect(on_done)
    printer.print_to_pdf(html, tmp_path)
    loop.exec()
    printer.print_finished.disconnect(on_done)
"""

import logging
import pathlib

from PySide6.QtCore import QMarginsF, QObject, QUrl, Signal
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger("tardis")

# Default page margins matching ``print.css`` ``@page`` rules
_MARGIN_TOP_MM = 12.0
_MARGIN_BOTTOM_MM = 18.0
_MARGIN_LEFT_MM = 0.0
_MARGIN_RIGHT_MM = 0.0


class ChromiumPrinter(QObject):
    """Async wrapper around ``QWebEngineView.page().printToPdf()``.

    Signals:
        print_finished(success: bool, output_path: str):
            Emitted when the PDF has been written or on failure.
    """

    print_finished = Signal(bool, str)  # success, output_path

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._view: QWebEngineView | None = None
        self._pending_output_path: str = ""
        self._orientation: str = "portrait"

    # ── View management ────────────────────────────────────────────

    def set_view(self, view: QWebEngineView) -> None:
        """Set the shared ``QWebEngineView`` used for PDF rendering.

        This view should be created on the main thread (typically by
        ``MainWindow`` at startup) and kept as a single shared instance
        — not created per call.
        """
        self._view = view

    # ── Public API ─────────────────────────────────────────────────

    def print_to_pdf(
        self,
        html: str,
        output_path: str,
        orientation: str = "portrait",
    ) -> None:
        """Render *html* to a PDF via QtWebEngine.

        **Must be called from the Qt main thread.**

        The result is delivered via the ``print_finished`` signal.

        Args:
            html: The full HTML document string (with inline CSS).
            output_path: Filesystem path where the PDF will be saved.
            orientation: ``\"portrait\"`` (default) or ``\"landscape\"``.
        """
        if self._view is None:
            raise RuntimeError(
                "ChromiumPrinter: no QWebEngineView set. "
                "Call set_view(view) before print_to_pdf()."
            )

        self._pending_output_path = output_path
        self._orientation = orientation

        # Disconnect any previous loadFinished connection to avoid
        # stale callbacks piling up across multiple calls.
        try:
            self._view.loadFinished.disconnect(self._on_load_finished)
        except (TypeError, RuntimeError):
            pass  # Was not connected

        self._view.loadFinished.connect(self._on_load_finished)

        # Load the HTML with a safe base URL so relative resources
        # (SVG, etc.) are resolved against a neutral origin.
        self._view.setHtml(html, QUrl("about:blank"))

    # ── Internal slots ─────────────────────────────────────────────

    def _on_load_finished(self, ok: bool) -> None:
        """Called when QtWebEngine finishes loading the HTML page."""
        # Disconnect immediately — we only need this once per call.
        try:
            self._view.loadFinished.disconnect(self._on_load_finished)
        except (TypeError, RuntimeError):
            pass

        if not ok:
            logger.error(
                "ChromiumPrinter: page load failed for %s",
                self._pending_output_path,
            )
            self.print_finished.emit(False, self._pending_output_path)
            return

        # Build page layout matching print.css @page margins
        if self._orientation == "landscape":
            page_size = QPageSize(QPageSize.A4)
            orientation_enum = QPageLayout.Landscape
        else:
            page_size = QPageSize(QPageSize.A4)
            orientation_enum = QPageLayout.Portrait

        margins = QMarginsF(
            _MARGIN_LEFT_MM,
            _MARGIN_TOP_MM,
            _MARGIN_RIGHT_MM,
            _MARGIN_BOTTOM_MM,
        )
        layout = QPageLayout(page_size, orientation_enum, margins, QPageLayout.Millimeter)

        # Connect the PDF-finished signal
        try:
            self._view.page().pdfPrintingFinished.disconnect(self._on_pdf_done)
        except (TypeError, RuntimeError):
            pass

        self._view.page().pdfPrintingFinished.connect(self._on_pdf_done)

        # Start the async PDF generation
        self._view.page().printToPdf(self._pending_output_path, layout)

    def _on_pdf_done(self, path: str, success: bool) -> None:
        """Called when ``printToPdf`` has finished writing the file."""
        try:
            self._view.page().pdfPrintingFinished.disconnect(self._on_pdf_done)
        except (TypeError, RuntimeError):
            pass

        if success:
            file_size = pathlib.Path(path).stat().st_size
            logger.info("ChromiumPrinter: PDF written to %s (%d bytes)", path, file_size)
        else:
            logger.error("ChromiumPrinter: printToPdf failed for %s", path)

        self.print_finished.emit(success, path)
