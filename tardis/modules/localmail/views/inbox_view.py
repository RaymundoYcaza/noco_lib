import sys
import logging
from pathlib import Path
from typing import Literal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QLabel, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QPoint
from PySide6.QtGui import QFont, QColor, QAction

# Add paths to sys.path
tardis_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from app_core.concurrency import run_async
from modules.localmail import service
from noco_lib.noco_core.client import NocoClient

class InboxView(QWidget):
    email_selected = Signal(int)  # Emits the email ID when selected/opened

    def __init__(self, main_window: QWidget, client: NocoClient, mailboxes: list[str],
                 mode: Literal["inbox", "sent", "trash"] = "inbox", parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self.mailboxes = mailboxes
        self.mode = mode

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header / Action Bar
        action_layout = QHBoxLayout()
        mailboxes_str = ", ".join(self.mailboxes) if self.mailboxes else "Sin configurar"
        mode_titles = {
            "inbox": "Bandeja de Entrada",
            "sent": "Enviados",
            "trash": "Papelera"
        }
        title_prefix = mode_titles.get(self.mode, "Bandeja de Entrada")
        self.title_label = QLabel(f"{title_prefix} ({mailboxes_str})")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a1a18;")
        
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f5f3f0;
                color: #1a1a18;
                border: 1px solid #dddad6;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ede9e4;
            }
        """)
        self.btn_refresh.clicked.connect(self.load)

        self.btn_archive = QPushButton("Archivar")
        self.btn_archive.setEnabled(False)
        self.btn_archive.setCursor(Qt.PointingHandCursor)
        self.btn_archive.setStyleSheet("""
            QPushButton {
                background-color: #e9290c;
                color: #ffffff;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c5220a;
            }
            QPushButton:disabled {
                background-color: #f5f3f0;
                color: #a1a1aa;
                border: 1px solid #dddad6;
            }
        """)
        self.btn_archive.clicked.connect(self._on_archive)

        action_layout.addWidget(self.title_label)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_refresh)
        action_layout.addWidget(self.btn_archive)
        layout.addLayout(action_layout)

        # Table Setup
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        if self.mode == "sent":
            self.table.setHorizontalHeaderLabels(["Prioridad", "Para", "Asunto", "Fecha"])
        else:
            self.table.setHorizontalHeaderLabels(["Prioridad", "De", "Asunto", "Fecha"])
        
        # Grid and Selection Behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        
        # Stylesheet for premium feel
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: rgba(233, 41, 12, 0.03);
                color: #1a1a18;
                gridline-color: transparent;
                border: 1px solid #dddad6;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid rgba(233, 41, 12, 0.06);
            }
            QTableWidget::item:selected {
                background-color: rgba(233, 41, 12, 0.12);
                color: #1a1a18;
            }
            QHeaderView::section {
                background-color: #f5f3f0;
                color: #5a5a56;
                padding: 8px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #dddad6;
            }
        """)

        # Header resizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

        # Placeholder Label for empty mailboxes
        self.placeholder_label = QLabel("No hay casillas configuradas. Define TARDIS_MAILBOXES en tu archivo .env.")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #5a5a56; font-size: 14px;")
        self.placeholder_label.setVisible(False)
        layout.addWidget(self.placeholder_label)

    def load(self) -> None:
        """
        Carga los datos de la bandeja de entrada asíncronamente o muestra error si no hay casillas.
        """
        try:
            if not self.mailboxes:
                self.table.setVisible(False)
                self.placeholder_label.setVisible(True)
                self.btn_refresh.setEnabled(False)
                return
                
            self.table.setVisible(True)
            self.placeholder_label.setVisible(False)
            self.btn_refresh.setEnabled(False)
            self.btn_refresh.setText("Cargando...")
            
            if self.mode == "sent":
                service_func = service.list_sent
            elif self.mode == "trash":
                service_func = service.list_trash
            else:
                service_func = service.list_inbox

            run_async(
                service_func,
                self.client,
                self.mailboxes,
                on_success=self._populate,
                on_error=self._on_error
            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView.load")

    def _populate(self, result) -> None:
        try:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Actualizar")
            self.btn_archive.setEnabled(False)

            if not result.success:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(result.errors[0] if result.errors else "Error cargando bandeja", "error")
                return

            self.table.setRowCount(0)
            emails = result.data or []
            
            self.table.setRowCount(len(emails))
            for row, email in enumerate(emails):
                # Parse properties
                email_id = email.get("Id")
                priority = email.get("priority", "Media")
                from_user = email.get("to" if self.mode == "sent" else "from", "")
                title = email.get("title", "")
                created_at = email.get("CreatedAt", "")
                is_read = email.get("read")
                
                # Map Read status (NocoDB might return 1/0 or True/False)
                read_bool = is_read in [True, 1, "true"]
                
                # Format priority with styled indicators
                priority_indicator = "⚪ Media"
                if priority == "Alta":
                    priority_indicator = "🔴 Alta"
                elif priority == "Baja":
                    priority_indicator = "🟢 Baja"
                    
                # Date formatting (YYYY-MM-DD HH:MM)
                formatted_date = created_at[:16] if len(created_at) >= 16 else created_at

                # Create items
                item_priority = QTableWidgetItem(priority_indicator)
                item_priority.setData(Qt.UserRole, email_id)  # Save the email ID inside the first column item
                
                item_from = QTableWidgetItem(from_user)
                item_title = QTableWidgetItem(title)
                item_date = QTableWidgetItem(formatted_date)

                # Apply font weight based on read status (bold if unread)
                if not read_bool:
                    bold_font = QFont()
                    bold_font.setBold(True)
                    item_priority.setFont(bold_font)
                    item_from.setFont(bold_font)
                    item_title.setFont(bold_font)
                    item_date.setFont(bold_font)
                    
                    # Unread messages get a slightly brighter text
                    bright_color = QColor("#1a1a18")
                    item_priority.setForeground(bright_color)
                    item_from.setForeground(bright_color)
                    item_title.setForeground(bright_color)
                    item_date.setForeground(bright_color)
                else:
                    # Read messages get a slightly muted text
                    muted_color = QColor("#5a5a56")
                    item_priority.setForeground(muted_color)
                    item_from.setForeground(muted_color)
                    item_title.setForeground(muted_color)
                    item_date.setForeground(muted_color)

                self.table.setItem(row, 0, item_priority)
                self.table.setItem(row, 1, item_from)
                self.table.setItem(row, 2, item_title)
                self.table.setItem(row, 3, item_date)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._populate")

    def _on_error(self, exc: Exception) -> None:
        try:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Actualizar")
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(f"Error inesperado: {exc}", "error")
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._on_error")

    @Slot()
    def _on_selection_changed(self) -> None:
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            self.btn_archive.setEnabled(len(selected_rows) > 0)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._on_selection_changed")

    @Slot(QTableWidgetItem)
    def _on_double_click(self, item: QTableWidgetItem) -> None:
        try:
            row = item.row()
            first_item = self.table.item(row, 0)
            if first_item is None:
                return
                
            email_id = first_item.data(Qt.UserRole)
            if email_id is None:
                return

            # Mark as read in NocoDB asynchronously
            run_async(
                service.mark_as_read,
                self.client,
                email_id,
                on_success=lambda r: (self.load(), self.email_selected.emit(email_id)),
                on_error=self._on_error
            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._on_double_click")

    @Slot()
    def _on_archive(self) -> None:
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                return
                
            row = selected_rows[0].row()
            first_item = self.table.item(row, 0)
            if first_item is None:
                return
                
            email_id = first_item.data(Qt.UserRole)
            if email_id is None:
                return

            self._archive_by_id(email_id)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._on_archive")

    def _archive_by_id(self, email_id: int) -> None:
        try:
            self.btn_archive.setEnabled(False)
            run_async(
                service.archive_email,
                self.client,
                email_id,
                on_success=lambda r: self.load(),
                on_error=self._on_error
            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._archive_by_id")

    @Slot(QPoint)
    def _show_context_menu(self, pos: QPoint) -> None:
        try:
            item = self.table.itemAt(pos)
            if item is None:
                return

            row = item.row()
            first_item = self.table.item(row, 0)
            if first_item is None:
                return

            email_id = first_item.data(Qt.UserRole)
            if email_id is None:
                return

            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    color: #1a1a18;
                    border: 1px solid #dddad6;
                }
                QMenu::item:selected {
                    background-color: #ede9e4;
                }
            """)

            archive_action = QAction("Archivar", self)
            archive_action.triggered.connect(lambda: self._archive_by_id(email_id))
            menu.addAction(archive_action)

            menu.exec(self.table.viewport().mapToGlobal(pos))
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in InboxView._show_context_menu")
