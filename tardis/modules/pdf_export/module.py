"""
module.py — PDF Export UI panel for Tardis.

Provides a dock panel with:
- Brand selector (bisstox / plyson / inorizonti)
- Doc type selector (all 10 types from document_presentation.json)
- JSON editor for the document payload
- "Vista previa HTML" button → renders HTML in a floating QWebEngineView
- "Generar PDF" button → runs the full pipeline, opens the result
- Status line showing last operation result
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

import json
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger("tardis")

# ── Module-level paths ─────────────────────────────────────────────
_MODULE_DIR = Path(__file__).resolve().parent
_TARDIS_DIR = _MODULE_DIR.parents[1]
_SHARED_DIR = _TARDIS_DIR / "shared"
_SCHEMAS_DIR = _SHARED_DIR / "schemas"
_DOC_PRESENTATION_PATH = _SCHEMAS_DIR / "document_presentation.json"


def _load_doc_types() -> list[str]:
    """Load doc type slugs from document_presentation.json."""
    try:
        with _DOC_PRESENTATION_PATH.open("r", encoding="utf-8") as f:
            pres = json.load(f)
        return list(pres.keys())
    except Exception:
        logger.exception("Failed to load document_presentation.json")
        return [
            "report", "technical_report", "support_ticket", "delivery_act",
            "letter", "communication", "minutes", "quote", "manual", "checklist",
        ]


_BRANDS = ["bisstox", "plyson", "inorizonti"]
_DOC_TYPES = _load_doc_types()


class PdfExportPanel(QWidget):
    """Dock panel for interactive PDF generation."""

    def __init__(
        self,
        app: MainWindow,
        client: NocoClient,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._app = app
        self._client = client

        # Lazy-created hidden QWebEngineView shared by ChromiumPrinter
        self._printer_view: QWebEngineView | None = None

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Brand selector ──
        layout.addWidget(QLabel("Marca:"))
        self._brand_combo = QComboBox()
        self._brand_combo.addItems(_BRANDS)
        self._brand_combo.setCurrentIndex(0)
        layout.addWidget(self._brand_combo)

        # ── Doc type selector ──
        layout.addWidget(QLabel("Tipo de documento:"))
        self._doc_type_combo = QComboBox()
        self._doc_type_combo.addItems(_DOC_TYPES)
        self._doc_type_combo.setCurrentIndex(
            _DOC_TYPES.index("letter") if "letter" in _DOC_TYPES else 0
        )
        layout.addWidget(self._doc_type_combo)

        # ── Audience selector ──
        layout.addWidget(QLabel("Audiencia:"))
        self._audience_combo = QComboBox()
        self._audience_combo.addItems(["external", "internal", "confidential", "draft"])
        self._audience_combo.setCurrentIndex(0)
        layout.addWidget(self._audience_combo)

        # ── Options row ──
        options_layout = QHBoxLayout()
        self._cover_check = QCheckBox("Portada")
        self._cover_check.setChecked(False)
        options_layout.addWidget(self._cover_check)
        self._compact_check = QCheckBox("Compacto")
        self._compact_check.setChecked(False)
        options_layout.addWidget(self._compact_check)
        layout.addLayout(options_layout)

        # ── JSON editor ──
        layout.addWidget(QLabel("JSON del documento:"))
        self._json_editor = QPlainTextEdit()
        self._json_editor.setPlaceholderText(
            '{\n  "title": "Ejemplo",\n  "din": "DIN-001",\n  "contact": {\n    "name": "Cliente"\n  },\n  "sections": []\n}'
        )
        self._json_editor.setMinimumHeight(180)
        self._json_editor.setStyleSheet("font-family: 'Courier New', monospace; font-size: 11px;")
        layout.addWidget(self._json_editor)

        # ── Fill with example JSON ──
        self._load_example_json()

        # ── Buttons ──
        btn_layout = QHBoxLayout()

        self._preview_btn = QPushButton("Vista previa HTML")
        self._preview_btn.clicked.connect(self._on_preview_html)
        btn_layout.addWidget(self._preview_btn)

        self._generate_btn = QPushButton("Generar PDF")
        self._generate_btn.clicked.connect(self._on_generate_pdf)
        btn_layout.addWidget(self._generate_btn)

        layout.addLayout(btn_layout)

        # ── Status line ──
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("padding: 4px; border-top: 1px solid #ccc;")
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _load_example_json(self) -> None:
        """Populate the JSON editor with a minimal working example."""
        example = {
            "title": "Documento de prueba",
            "din": "DIN-EJEMPLO-001",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "contact": {"name": "Cliente de prueba"},
            "status": "final",
            "sections": [
                {
                    "type": "text",
                    "content": "Este es un documento de prueba generado desde el panel PDF Export.",
                },
            ],
        }
        self._json_editor.setPlainText(json.dumps(example, indent=2, ensure_ascii=False))

    # ── Helpers ────────────────────────────────────────────────────

    def _get_printer_view(self) -> QWebEngineView:
        """Return (creating if needed) the hidden QWebEngineView shared by ChromiumPrinter."""
        if self._printer_view is None:
            self._printer_view = QWebEngineView(self)
            self._printer_view.setFixedSize(1, 1)
        return self._printer_view

    def _build_data_dict(self) -> dict | None:
        """Parse the JSON editor contents and build a full data dict.

        Returns None and shows an error toast if parsing fails.
        """
        raw = self._json_editor.toPlainText().strip()
        if not raw:
            self._app.show_notification("El JSON del documento está vacío.", "error")
            return None

        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._app.show_notification(f"JSON inválido: {exc}", "error")
            self._status_label.setText(f"Error JSON: {exc}")
            return None

        # Validate that document sub-dict has the required fields
        if not isinstance(document, dict):
            self._app.show_notification("El JSON debe ser un objeto (dict).", "error")
            return None

        data = {
            "brand": self._brand_combo.currentText(),
            "doc_type": self._doc_type_combo.currentText(),
            "audience": self._audience_combo.currentText(),
            "has_cover": self._cover_check.isChecked(),
            "compact_header": self._compact_check.isChecked(),
            "document": document,
        }
        return data

    def _show_preview_window(self, html: str, title: str) -> None:
        """Open a floating window with a QWebEngineView showing the rendered HTML."""
        preview_view = QWebEngineView()
        preview_view.setHtml(html)
        preview_view.setMinimumSize(600, 400)
        self._app.add_floating_window(preview_view, title)

    # ── Button handlers ────────────────────────────────────────────

    def _on_preview_html(self) -> None:
        """Handle 'Vista previa HTML' button click."""
        self._status_label.setText("Generando vista previa HTML...")

        data = self._build_data_dict()
        if data is None:
            return

        # Import here to avoid circular imports at module level
        from .engine import generate_html

        result = generate_html(data, data["brand"])

        if result.success:
            html = result.data["html"]
            din = data["document"].get("din", "documento")
            self._show_preview_window(html, f"Vista previa: {din}")
            self._status_label.setText(f"OK: Vista previa generada ({len(html)} chars)")
            self._app.show_notification("Vista previa HTML generada.", "success")
        else:
            msg = "; ".join(result.errors) if result.errors else "Error desconocido"
            self._status_label.setText(f"Error: {msg}")
            self._app.show_notification(f"Error al generar vista previa: {msg}", "error")

    def _on_generate_pdf(self) -> None:
        """Handle 'Generar PDF' button click."""
        self._status_label.setText("Generando PDF...")

        data = self._build_data_dict()
        if data is None:
            return

        # Build output path: ~/Downloads/<din>_<timestamp>.pdf
        din = data["document"].get("din", "documento")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{din}_{timestamp}.pdf"
        downloads = Path.home() / "Downloads"
        output_path = str(downloads / filename)

        # Ensure downloads directory exists
        downloads.mkdir(parents=True, exist_ok=True)

        # Set up ChromiumPrinter with a hidden view
        from .chromium_printer import ChromiumPrinter

        printer = ChromiumPrinter()
        printer.set_view(self._get_printer_view())

        from .engine import generate_pdf

        # Run the full pipeline (synchronous on main thread, drives internal QEventLoop).
        # generate_pdf calls generate_html -> validate_document internally.
        result = generate_pdf(data, data["brand"], output_path, printer, open_after=True)

        if result.success:
            pages = result.data.get("pages", 0)
            self._status_label.setText(
                f"OK: PDF generado ({pages} página(s)) → {output_path}"
            )
            self._app.show_notification(
                f"PDF generado: {pages} página(s). Abriendo...", "success"
            )
        else:
            msg = "; ".join(result.errors) if result.errors else "Error desconocido"
            self._status_label.setText(f"Error: {msg}")
            self._app.show_notification(f"Error al generar PDF: {msg}", "error")


# ═══════════════════════════════════════════════════════════════════
#  Module entry point (called by module_registry during app startup)
# ═══════════════════════════════════════════════════════════════════

def register(app: MainWindow, client: NocoClient) -> None:
    """Register the PDF Export panel as a dock widget and menu action.

    Args:
        app: The Tardis ``MainWindow`` instance.
        client: The ``NocoClient`` instance (unused by this module but
                required by the module contract).
    """
    panel = PdfExportPanel(app, client)

    # Register as a dock panel on the right side
    app.add_dock_panel(panel, "PDF Export", area="right")

    # Register a menu action under Herramientas
    app.add_menu_action("Herramientas", "PDF Export", lambda: panel.show())

    logger.info("PDF Export module registered")
