"""SetupView — form for configuring and launching AI analysis.

Lets the user select a NocoDB table, fields, AI operation, and
additional context, then triggers the analysis pipeline.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from app_core.config import TardisConfig
    from noco_lib.noco_core.client import NocoClient
    from ai_lib.ai_client import AIClient

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QListWidget,
    QAbstractItemView,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Signal, Qt

from app_core.concurrency import run_async
from ai_lib.ai_service import (
    correct_value,
    classify_value,
    extract_value,
    summarize_value,
    estimate_time_seconds,
)

import logging

logger = logging.getLogger("tardis")

_SYSTEM_FIELDS = {"Id", "CreatedAt", "UpdatedAt", "nc_created_by", "nc_updated_by", "nc_order"}


class SetupView(QWidget):
    """Form for configuring an AI analysis run on NocoDB table data.

    Signals
    -------
    analysis_ready : Signal(object)
        Emitted with a dict containing ``records``, ``fields``,
        ``operation``, ``context``, ``table_id``, and ``field_meta``
        when the user confirms the analysis.
    """

    analysis_ready = Signal(object)

    _BATCH_SIZE = 20

    # Map operation keys to ai_service functions
    _OP_FN_MAP = {
        "correct": correct_value,
        "classify": classify_value,
        "extract": extract_value,
        "summarize": summarize_value,
    }

    def __init__(
        self,
        config: "TardisConfig",
        client: "NocoClient",
        ai_client: "AIClient",
        main_window: "MainWindow",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._client = client
        self._ai_client = ai_client
        self._main_window = main_window

        # Internal state
        self._table_id_map: dict[str, str] = {}  # display title → actual id
        self._table_titles: list[str] = []
        self._field_meta_cache: dict[str, dict] = {}  # field_name → meta dict

        # Processing state
        self._all_results: list[dict] = []
        self._completed_batches: int = 0
        self._total_batches: int = 0
        self._on_processing_complete: Callable[[list[dict]], None] | None = None

        self._build_ui()
        self._connect_signals()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 16, 24, 16)

        # Title
        title = QLabel("Correcciones con IA")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding-bottom: 8px;")
        layout.addWidget(title)

        # ── Table selector ──
        layout.addWidget(QLabel("Tabla:"))
        self._table_combo = QComboBox()
        self._table_combo.setMinimumWidth(300)
        layout.addWidget(self._table_combo)

        # ── Fields list ──
        layout.addWidget(QLabel("Campos a procesar:"))
        self._fields_list = QListWidget()
        self._fields_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._fields_list.setMinimumHeight(120)
        self._fields_list.setStyleSheet(
            "QListWidget { background: #2a2a2a; border: 1px solid #3a3a3a; "
            "border-radius: 4px; padding: 4px; }"
            "QListWidget::item { padding: 4px 8px; border-radius: 3px; }"
            "QListWidget::item:selected { background: #0a66c2; color: #fff; }"
        )
        layout.addWidget(self._fields_list)

        # ── Operation selector ──
        layout.addWidget(QLabel("Operación:"))
        self._operation_combo = QComboBox()
        self._operation_combo.addItems([
            "correct — Corrección ortográfica",
            "classify — Clasificar en opciones",
            "extract — Extraer campo de texto",
            "summarize — Resumir texto",
        ])
        self._operation_combo.setMinimumWidth(300)
        layout.addWidget(self._operation_combo)

        # ── Context input ──
        layout.addWidget(QLabel("Contexto adicional (opcional):"))
        self._context_input = QPlainTextEdit()
        self._context_input.setPlaceholderText(
            "Ejemplo: Los nombres deben estar en formato Title Case"
        )
        self._context_input.setMaximumBlockCount(3)
        self._context_input.setFixedHeight(70)
        self._context_input.setStyleSheet(
            "QPlainTextEdit { background: #2a2a2a; color: #e0e0e0; "
            "border: 1px solid #3a3a3a; border-radius: 4px; padding: 6px; }"
        )
        layout.addWidget(self._context_input)

        # ── Estimate label ──
        self._estimate_label = QLabel("")
        self._estimate_label.setStyleSheet("color: #a0a0a0; padding: 4px 0;")
        self._estimate_label.setVisible(False)
        layout.addWidget(self._estimate_label)

        # ── Progress bar (hidden until processing starts) ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMinimumHeight(24)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background: #2a2a2a; border: 1px solid #3a3a3a; "
            "border-radius: 4px; text-align: center; color: #e0e0e0; }"
            "QProgressBar::chunk { background: #0a66c2; border-radius: 3px; }"
        )
        layout.addWidget(self._progress_bar)

        # ── Analyze button ──
        self._analyze_btn = QPushButton("Analizar con IA")
        self._analyze_btn.setMinimumHeight(36)
        self._analyze_btn.setStyleSheet(
            "QPushButton { background: #0a66c2; color: #fff; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background: #0b7ae0; }"
            "QPushButton:disabled { background: #3a3a3a; color: #6a6a6a; }"
        )
        layout.addWidget(self._analyze_btn)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._table_combo.currentIndexChanged.connect(self._on_table_changed)
        self._fields_list.itemSelectionChanged.connect(self._update_estimate)
        self._operation_combo.currentIndexChanged.connect(self._update_estimate)
        self._analyze_btn.clicked.connect(self._on_analyze)

    # ── Show event: populate tables ──────────────────────────────────

    def showEvent(self, event) -> None:
        """Load table list when the widget becomes visible."""
        super().showEvent(event)
        if self._table_combo.count() == 0:
            run_async(
                self._client.list_tables,
                on_success=self._populate_tables,
                on_error=lambda exc: logger.error("Failed to list tables: %s", exc),
            )

    def _populate_tables(self, result) -> None:
        """Populate table combo from a successful list_tables result."""
        if not result.success:
            logger.warning("Failed to list tables: %s", result.errors)
            return

        self._table_combo.clear()
        self._table_id_map.clear()
        self._table_titles.clear()

        for t in result.data:
            title = t.get("title", "")
            tid = t.get("id", "")
            if title and tid:
                self._table_id_map[title] = tid
                self._table_titles.append(title)
                self._table_combo.addItem(title)

    # ── Table changed: populate fields ───────────────────────────────

    def _on_table_changed(self, index: int) -> None:
        """Load field metadata when the selected table changes."""
        self._fields_list.clear()
        self._estimate_label.setVisible(False)

        if index < 0 or index >= len(self._table_titles):
            return

        table_title = self._table_titles[index]
        table_id = self._table_id_map.get(table_title)
        if not table_id:
            return

        run_async(
            self._client.get_table_meta,
            table_id,
            on_success=self._populate_fields,
            on_error=lambda exc: logger.error("Failed to get table meta: %s", exc),
        )

    def _populate_fields(self, result) -> None:
        """Populate the fields list from a successful get_table_meta result."""
        if not result.success:
            logger.warning("Failed to get table meta: %s", result.errors)
            return

        columns = result.data.get("columns", []) if result.data else []
        self._fields_list.clear()
        self._field_meta_cache.clear()

        for col in columns:
            title = col.get("title", "")
            if title in _SYSTEM_FIELDS:
                continue
            self._fields_list.addItem(title)
            # Cache column metadata (options for SingleSelect etc.)
            col_options = col.get("colOptions", {})
            options_list = []
            if isinstance(col_options, dict):
                opts = col_options.get("options", [])
                if isinstance(opts, list):
                    options_list = [o.get("title", "") for o in opts if isinstance(o, dict)]
            self._field_meta_cache[title] = {"options": options_list}

        self._update_estimate()

    # ── Estimate ──────────────────────────────────────────────────────

    def _update_estimate(self) -> None:
        """Update the time estimate based on current selection."""
        selected_fields = self._selected_fields()
        if not selected_fields or not self._table_combo.currentText():
            self._estimate_label.setVisible(False)
            return

        table_title = self._table_combo.currentText()
        table_id = self._table_id_map.get(table_title)
        if not table_id:
            return

        # Fetch a small sample to estimate time
        run_async(
            self._client.table(table_id).read,
            limit=5,
            on_success=lambda r: self._show_estimate(r, selected_fields),
            on_error=lambda exc: logger.debug("Could not fetch sample for estimate: %s", exc),
        )

    def _show_estimate(self, result, selected_fields: list[str]) -> None:
        """Display time estimate from a sample read result."""
        if not result.success or not result.data:
            return

        records = result.data
        if not records:
            return

        est = estimate_time_seconds(records[:5], selected_fields)
        total_records = result.meta.get("totalRows", len(records))
        self._estimate_label.setText(
            f"~{est} segundos estimados para {total_records} registros"
        )
        self._estimate_label.setVisible(True)

    # ── Helpers ──────────────────────────────────────────────────────

    def _selected_fields(self) -> list[str]:
        """Return the list of currently selected field names."""
        return [item.text() for item in self._fields_list.selectedItems()]

    def _get_operation_key(self) -> str:
        """Extract the operation key from the combo text."""
        text = self._operation_combo.currentText()
        return text.split(" —")[0].strip()

    # ── Analyze handler ──────────────────────────────────────────────

    def _on_analyze(self) -> None:
        """Handle the 'Analizar con IA' button click."""
        # Validate
        selected_fields = self._selected_fields()
        if not selected_fields:
            self._main_window.show_notification(
                "Selecciona al menos un campo para procesar.", "error"
            )
            return

        table_title = self._table_combo.currentText()
        if not table_title:
            self._main_window.show_notification(
                "Selecciona una tabla.", "error"
            )
            return

        table_id = self._table_id_map.get(table_title)
        if not table_id:
            return

        self._analyze_btn.setEnabled(False)
        self._main_window.show_notification("Leyendo registros...", "info")

        # Read all records from the table
        run_async(
            self._client.table(table_id).read,
            limit=None,
            on_success=lambda r: self._on_records_loaded(
                r, selected_fields, table_id
            ),
            on_error=lambda exc: self._on_analyze_error(exc),
        )

    def _on_records_loaded(
        self, result, selected_fields: list[str], table_id: str
    ) -> None:
        """Handle the loaded records — show confirmation dialog."""
        self._analyze_btn.setEnabled(True)

        if not result.success:
            self._main_window.show_notification(
                f"Error al leer registros: {result.errors}", "error"
            )
            return

        records = result.data or []
        if not records:
            self._main_window.show_notification(
                "La tabla no contiene registros.", "error"
            )
            return

        operation = self._get_operation_key()
        context = self._context_input.toPlainText().strip()

        # Time estimate
        est = estimate_time_seconds(records, selected_fields)

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirmar análisis",
            f"Se procesarán {len(records)} registros en "
            f"{len(selected_fields)} campo(s).\n"
            f"Tiempo estimado: ~{est} segundos.\n\n"
            "¿Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # Build field_meta for the selected fields only
        field_meta = {
            fname: self._field_meta_cache.get(fname, {})
            for fname in selected_fields
        }

        self.analysis_ready.emit({
            "records": records,
            "fields": selected_fields,
            "operation": operation,
            "context": context,
            "table_id": table_id,
            "field_meta": field_meta,
        })

    def _on_analyze_error(self, exc: Exception) -> None:
        """Handle errors during record loading."""
        self._analyze_btn.setEnabled(True)
        self._main_window.show_notification(f"Error: {exc}", "error")
        logger.exception("Error loading records for analysis")

    # ── AI Processing Pipeline ───────────────────────────────────────

    def process_records(
        self,
        data: dict,
        on_complete: Callable[[list[dict]], None] | None = None,
    ) -> None:
        """Start the AI processing pipeline in batched background threads.

        Parameters
        ----------
        data : dict
            The dict emitted by ``analysis_ready`` signal – must contain
            ``records``, ``fields``, ``operation``, ``context``, ``field_meta``.
        on_complete : callable or None
            Invoked on the Qt main thread when *all* batches finish, with
            the full list of per-record result dicts.
        """
        records = data["records"]
        fields = data["fields"]
        operation = data["operation"]
        context = data["context"]
        field_meta = data["field_meta"]

        op_fn = self._OP_FN_MAP[operation]

        # Split records into fixed-size batches
        batches = [
            records[i : i + self._BATCH_SIZE]
            for i in range(0, len(records), self._BATCH_SIZE)
        ]
        self._total_batches = len(batches)
        self._completed_batches = 0
        self._all_results = []
        self._on_processing_complete = on_complete

        # Show progress bar, disable the analyze button
        self._progress_bar.setMaximum(self._total_batches)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._analyze_btn.setEnabled(False)
        self._main_window.show_notification(
            f"Procesando {len(records)} registros en {self._total_batches} lotes…",
            "info",
        )

        for batch in batches:
            run_async(
                self._process_batch,
                batch,
                fields,
                op_fn,
                operation,
                context,
                field_meta,
                on_success=self._batch_done,
                on_error=self._batch_error,
            )

    def _process_batch(
        self,
        batch: list[dict],
        fields: list[str],
        op_fn: Callable,
        operation: str,
        context: str,
        field_meta: dict[str, dict],
    ) -> list[dict]:
        """Process a single batch of records (runs in a worker thread).

        Returns a list of result dicts, one per (record, field) pair
        that had a non-empty value.
        """
        results: list[dict] = []
        for record in batch:
            for field in fields:
                value = str(record.get(field, ""))
                if not value.strip():
                    continue

                if operation == "classify":
                    options = field_meta.get(field, {}).get("options", [])
                    ai_result = op_fn(
                        self._ai_client, field, value, options, context
                    )
                else:
                    ai_result = op_fn(
                        self._ai_client, field, value, context
                    )

                results.append({
                    "record_id": record.get("Id", ""),
                    "field": field,
                    "original": value,
                    "suggestion": ai_result.data if ai_result.success else None,
                    "error": ai_result.errors[0] if not ai_result.success else None,
                    "meta": ai_result.meta,
                })

        return results

    def _batch_done(self, batch_results: list[dict]) -> None:
        """Callback invoked on the main thread when a batch completes."""
        self._all_results.extend(batch_results)
        self._completed_batches += 1
        self._progress_bar.setValue(self._completed_batches)

        if self._completed_batches >= self._total_batches:
            self._progress_bar.setVisible(False)
            self._analyze_btn.setEnabled(True)
            self._main_window.show_notification(
                f"✓ Procesamiento completado: {len(self._all_results)} sugerencias",
                "info",
            )
            if self._on_processing_complete is not None:
                self._on_processing_complete(self._all_results)

    def _batch_error(self, exc: Exception) -> None:
        """Callback invoked on the main thread when a batch fails."""
        logger.error("Batch processing error: %s", exc)
        self._main_window.show_notification(f"Error en lote: {exc}", "error")
        self._completed_batches += 1
        self._progress_bar.setValue(self._completed_batches)

        if self._completed_batches >= self._total_batches:
            self._progress_bar.setVisible(False)
            self._analyze_btn.setEnabled(True)
            self._main_window.show_notification(
                f"Procesamiento completado con errores: {len(self._all_results)} sugerencias",
                "warning",
            )
            if self._on_processing_complete is not None:
                self._on_processing_complete(self._all_results)
