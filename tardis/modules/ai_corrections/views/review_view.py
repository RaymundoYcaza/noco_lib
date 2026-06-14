"""ReviewView — comparison table for AI correction results.

Shows each AI-processed (record_id, field) pair as a table row
with the original value, the AI suggestion, and an accept checkbox.
The user can select rows to write back to NocoDB.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QMessageBox,
)
from PySide6.QtCore import Signal, Qt
from app_core.concurrency import run_async

import logging

logger = logging.getLogger("tardis")


class ReviewView(QWidget):
    """Comparison table for reviewing AI correction suggestions.

    Parameters
    ----------
    main_window : MainWindow
        For showing notifications and accessing app state.
    client : NocoClient
        For writing accepted changes back to NocoDB.
    results : list[dict]
        Per-field results from the AI processing pipeline. Each dict
        must contain ``record_id``, ``field``, ``original``,
        ``suggestion``, ``error``, and ``meta``.
    table_id : str
        The NocoDB table ID to write updates to.
    """

    back_requested = Signal()

    _HEADERS = ["Id", "Campo", "Valor original", "Sugerencia IA", "Aceptar"]

    def __init__(
        self,
        main_window: "MainWindow",
        client: "NocoClient",
        results: list[dict[str, Any]],
        table_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._client = client
        self._table_id = table_id

        # Index results and build mapping from row → result
        self._results = results
        self._checkboxes: dict[int, QCheckBox] = {}  # row → checkbox

        self._build_ui()
        self._populate_table()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 12, 16, 12)

        # ── Title ──
        title = QLabel("Revisión de sugerencias IA")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding-bottom: 4px;")
        layout.addWidget(title)

        # ── Summary label ──
        n_suggestions = sum(
            1 for r in self._results if r.get("error") is None
        )
        n_errors = sum(
            1 for r in self._results if r.get("error") is not None
        )
        self._summary_label = QLabel(
            f"{n_suggestions} sugerencias — {n_errors} errores"
        )
        self._summary_label.setStyleSheet("color: #a0a0a0; padding-bottom: 8px;")
        layout.addWidget(self._summary_label)

        # ── Top bar: back + bulk actions ──
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self._back_btn = QPushButton("← Volver")
        self._back_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #3a3a3a; "
            "border-radius: 4px; padding: 6px 14px; color: #e0e0e0; }"
            "QPushButton:hover { background: #2a2a2a; }"
        )
        top_bar.addWidget(self._back_btn)

        top_bar.addStretch()

        self._approve_all_btn = QPushButton("Aprobar todo")
        self._approve_all_btn.setStyleSheet(
            "QPushButton { background: #1a6b3c; color: #fff; border: none; "
            "border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background: #20854a; }"
        )
        top_bar.addWidget(self._approve_all_btn)

        self._reject_all_btn = QPushButton("Rechazar todo")
        self._reject_all_btn.setStyleSheet(
            "QPushButton { background: #6b1a1a; color: #fff; border: none; "
            "border-radius: 4px; padding: 6px 14px; }"
            "QPushButton:hover { background: #852020; }"
        )
        top_bar.addWidget(self._reject_all_btn)

        layout.addLayout(top_bar)

        # ── Table ──
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._HEADERS))
        self._table.setHorizontalHeaderLabels(self._HEADERS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            "QTableWidget { background: #1e1e1e; border: 1px solid #3a3a3a; "
            "border-radius: 4px; gridline-color: #2a2a2a; }"
            "QTableWidget::item { padding: 4px 8px; }"
            "QHeaderView::section { background: #2a2a2a; color: #c0c0c0; "
            "padding: 6px; border: none; border-bottom: 1px solid #3a3a3a; "
            "font-weight: bold; }"
            "QTableWidget::item:alternate { background: #252525; }"
        )

        # Stretch behaviour
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Id
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Campo
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # Original
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # Sugerencia
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Aceptar

        self._table.setMinimumHeight(200)
        layout.addWidget(self._table)

        # ── Apply button ──
        self._apply_btn = QPushButton("Aplicar cambios aprobados")
        self._apply_btn.setMinimumHeight(36)
        self._apply_btn.setStyleSheet(
            "QPushButton { background: #0a66c2; color: #fff; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background: #0b7ae0; }"
            "QPushButton:disabled { background: #3a3a3a; color: #6a6a6a; }"
        )
        layout.addWidget(self._apply_btn)

        # ── Signals ──
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._approve_all_btn.clicked.connect(self._approve_all)
        self._reject_all_btn.clicked.connect(self._reject_all)
        self._apply_btn.clicked.connect(self._on_apply)

    # ── Table population ─────────────────────────────────────────────

    def _populate_table(self) -> None:
        """Fill the QTableWidget with result rows."""
        self._table.setRowCount(len(self._results))
        self._checkboxes.clear()

        for row, result in enumerate(self._results):
            record_id = str(result.get("record_id", ""))
            field_name = str(result.get("field", ""))
            original = str(result.get("original", ""))
            suggestion = result.get("suggestion")
            error = result.get("error")

            # Id (col 0)
            id_item = QTableWidgetItem(record_id)
            id_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, id_item)

            # Campo (col 1)
            field_item = QTableWidgetItem(field_name)
            self._table.setItem(row, 1, field_item)

            # Valor original (col 2)
            orig_item = QTableWidgetItem(original)
            font = orig_item.font()
            font.setFamily("Consolas")
            orig_item.setFont(font)
            self._table.setItem(row, 2, orig_item)

            # Sugerencia IA (col 3)
            has_error = error is not None
            if has_error:
                sug_item = QTableWidgetItem(f"⚠ {error}")
                sug_item.setForeground(Qt.red)
            else:
                sug_item = QTableWidgetItem(suggestion if suggestion else "")
                # Muted style if suggestion == original (no change)
                if suggestion == original:
                    sug_item.setForeground(Qt.gray)

            sug_item.setFont(font)  # monospace for comparability
            self._table.setItem(row, 3, sug_item)

            # Aceptar checkbox (col 4)
            cb = QCheckBox()
            cb.setEnabled(not has_error)
            cb_container = QWidget()
            cb_layout = QHBoxLayout(cb_container)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.addWidget(cb)
            self._table.setCellWidget(row, 4, cb_container)
            self._checkboxes[row] = cb

        # Set row heights
        for row in range(self._table.rowCount()):
            self._table.setRowHeight(row, 32)

    # ── Bulk actions ─────────────────────────────────────────────────

    def _approve_all(self) -> None:
        """Check all enabled checkboxes."""
        for cb in self._checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(True)

    def _reject_all(self) -> None:
        """Uncheck all checkboxes."""
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    # ── Apply changes ────────────────────────────────────────────────

    def _on_apply(self) -> None:
        """Handle the 'Aplicar cambios aprobados' button."""
        # Collect accepted rows
        accepted_rows = [
            i for i, cb in self._checkboxes.items()
            if cb.isChecked()
        ]
        if not accepted_rows:
            self._main_window.show_notification(
                "No hay cambios seleccionados.", "info"
            )
            return

        accepted_results = [self._results[i] for i in accepted_rows]

        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirmar cambios",
            f"¿Aplicar {len(accepted_rows)} cambios a NocoDB?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._apply_btn.setEnabled(False)
        self._apply_changes(accepted_results)

    def _apply_changes(self, accepted: list[dict[str, Any]]) -> None:
        """Write accepted suggestions back to NocoDB.

        Groups results by ``record_id`` so each row update contains
        the changed fields for that record.
        """
        # Group by record_id
        updates_by_id: dict[str, dict[str, Any]] = {}
        for r in accepted:
            rid = str(r.get("record_id", ""))
            if rid not in updates_by_id:
                updates_by_id[rid] = {"Id": rid}
            updates_by_id[rid][str(r["field"])] = r["suggestion"]

        update_dicts = list(updates_by_id.values())

        logger.info(
            "Applying %d updates across %d records",
            len(accepted),
            len(update_dicts),
        )

        run_async(
            self._client.table(self._table_id).update,
            update_dicts,
            on_success=self._on_applied,
            on_error=self._on_apply_error,
        )

    def _on_applied(self, result) -> None:
        """Called on the main thread after a successful NocoDB update."""
        self._apply_btn.setEnabled(True)

        if result.success:
            count = getattr(result, "affected_count", 0)
            self._main_window.show_notification(
                f"✓ {count} registros actualizados", "info"
            )
        else:
            self._main_window.show_notification(
                f"Error al actualizar: {result.errors[0] if result.errors else 'unknown'}",
                "error",
            )

    def _on_apply_error(self, exc: Exception) -> None:
        """Called on the main thread when the NocoDB update raises."""
        self._apply_btn.setEnabled(True)
        self._main_window.show_notification(
            f"Error al aplicar cambios: {exc}", "error"
        )
        logger.exception("Error applying AI correction changes")
