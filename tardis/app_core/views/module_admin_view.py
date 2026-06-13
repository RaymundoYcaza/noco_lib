from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
)
from PySide6.QtGui import QColor

if TYPE_CHECKING:
    from app_core.module_registry import ModuleInfo

class ModuleAdminView(QWidget):
    """
    Vista de administración de módulos que muestra una tabla con la información
    de cada módulo cargado o fallido.
    """
    def __init__(self, module_info: dict[str, ModuleInfo], parent: QWidget | None = None):
        super().__init__(parent)
        self.module_info = module_info
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Estado", "Error"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Configurar modo de redimensionado de cabeceras
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.populate_table()

        layout.addWidget(self.table)
        self.setLayout(layout)

    def populate_table(self) -> None:
        self.table.setRowCount(len(self.module_info))
        for row_idx, (mod_name, info) in enumerate(self.module_info.items()):
            # Nombre
            name_item = QTableWidgetItem(info.name)
            self.table.setItem(row_idx, 0, name_item)

            # Estado
            estado_str = "Cargado" if info.loaded else "Error"
            state_item = QTableWidgetItem(estado_str)
            if not info.loaded:
                state_item.setForeground(QColor("red"))
            else:
                state_item.setForeground(QColor("green"))
            self.table.setItem(row_idx, 1, state_item)

            # Error
            error_item = QTableWidgetItem(info.error or "")
            self.table.setItem(row_idx, 2, error_item)
