from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QLabel
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor
import qtawesome as qta
from noco_lib.noco_core.client import NocoClient
from app_core.concurrency import run_async
from modules.localmail import service
import logging

class EmailListView(QWidget):
    email_selected = Signal(int)  # Emite el ID del correo cuando se hace un clic simple

    def __init__(self, main_window: QWidget, client: NocoClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        
        self._current_mailboxes = []
        self._current_folder = None
        self._all_rows = []
        self._current_search_text = ""
        self._current_priority = "All"
        
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Barra de acciones con el botón Actualizar
        action_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #ffffff;
                border: 1px solid #3f3f46;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
            QPushButton:disabled {
                background-color: #18181b;
                color: #71717a;
                border-color: #27272a;
            }
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        
        action_layout.addWidget(self.btn_refresh)
        action_layout.addStretch()
        layout.addLayout(action_layout)
        
        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Prioridad", "De", "Asunto", "Fecha"])
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #18181b;
                alternate-background-color: #202024;
                color: #e1e1e6;
                gridline-color: transparent;
                border: 1px solid #27272a;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #27272a;
            }
            QTableWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #27272a;
                color: #a1a1aa;
                padding: 8px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #3f3f46;
            }
        """)
        
        # Resizing de columnas de la cabecera
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        # Conexión del clic simple
        self.table.itemClicked.connect(self._on_item_clicked)
        
        layout.addWidget(self.table)
        
        # Label de placeholder
        self.placeholder_label = QLabel("No hay casillas configuradas.")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        self.placeholder_label.setVisible(False)
        layout.addWidget(self.placeholder_label)

    def _on_item_clicked(self, item: QTableWidgetItem) -> None:
        try:
            row = item.row()
            first_item = self.table.item(row, 0)
            if first_item is None:
                return
            email_id = first_item.data(Qt.UserRole)
            if email_id is not None:
                try:
                    email_id = int(email_id)
                    self.email_selected.emit(email_id)
                except (ValueError, TypeError):
                    logging.getLogger("tardis").error("ID de correo inválido: %s", type(email_id))
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in EmailListView._on_item_clicked")

    def load(self, client: NocoClient, mailboxes: list[str], folder: str | None) -> None:
        """
        Carga los correos asíncronamente según las casillas y la carpeta especificadas.
        """
        try:
            self._current_mailboxes = mailboxes
            self._current_folder = folder
            
            if not mailboxes:
                self.table.setVisible(False)
                self.placeholder_label.setText("No hay casillas configuradas. Define TARDIS_MAILBOXES en tu archivo .env.")
                self.placeholder_label.setVisible(True)
                self.btn_refresh.setEnabled(False)
                return
                
            if folder is None:
                logging.getLogger("tardis").error("EmailListView.load llamada con folder=None")
                return

            self.table.setVisible(True)
            self.placeholder_label.setVisible(False)
            self.btn_refresh.setEnabled(False)
            self.btn_refresh.setText("Cargando...")
            
            # Mapear carpeta al servicio correspondiente
            if folder == "sent":
                service_func = service.list_sent
                service_args = (client, mailboxes)
                self.table.setHorizontalHeaderItem(1, QTableWidgetItem("Para"))
            elif folder == "trash":
                service_func = service.list_trash
                service_args = (client, mailboxes)
                self.table.setHorizontalHeaderItem(1, QTableWidgetItem("De"))
            else:
                service_func = service.list_inbox
                service_args = (client, mailboxes, folder)
                self.table.setHorizontalHeaderItem(1, QTableWidgetItem("De"))
                
            run_async(
                service_func,
                *service_args,
                on_success=self._populate,
                on_error=self._on_error
            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in EmailListView.load")

    @Slot()
    def refresh(self) -> None:
        self.load(self.client, self._current_mailboxes, self._current_folder)

    def _populate(self, result) -> None:
        try:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Actualizar")
            
            if not result.success:
                err_msg = result.errors[0] if result.errors else "Error cargando correos"
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err_msg, "error")
                self.table.setRowCount(0)
                self._all_rows = []
                return
                
            self._all_rows = result.data or []
            self._repopulate_table()
                
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in EmailListView._populate")

    def apply_filter(self, search_text: str, priority: str) -> None:
        self._current_search_text = search_text
        self._current_priority = priority
        self._repopulate_table()

    def _repopulate_table(self) -> None:
        try:
            self.table.setRowCount(0)
            
            # Filter the rows client-side
            filtered_emails = []
            search_lower = self._current_search_text.lower()
            
            for email in self._all_rows:
                priority = email.get("priority", "Media")
                
                # Filter by priority
                if self._current_priority != "All" and priority != self._current_priority:
                    continue
                
                title = email.get("title", "") or ""
                
                if self._current_folder == "sent":
                    from_user = email.get("to", "") or ""
                else:
                    from_user = email.get("from", "") or ""
                
                # Filter by search text (subject or sender/recipient)
                if search_lower:
                    if search_lower not in title.lower() and search_lower not in from_user.lower():
                        continue
                        
                filtered_emails.append(email)
                
            self.table.setRowCount(len(filtered_emails))
            for row, email in enumerate(filtered_emails):
                email_id = email.get("Id")
                priority = email.get("priority", "Media")
                
                if self._current_folder == "sent":
                    from_user = email.get("to", "") or ""
                else:
                    from_user = email.get("from", "") or ""
                    
                title = email.get("title", "") or ""
                created_at = email.get("CreatedAt", "") or ""
                is_read = email.get("read")
                
                # Mapear estado de lectura
                read_bool = is_read in [True, 1, "true"]
                
                # Formatear el indicador de prioridad usando qtawesome
                priority_colors = {
                    "Alta": "#dc2626",   # Rojo
                    "Media": "#eab308",  # Amarillo
                    "Baja": "#16a34a"    # Verde
                }
                color_hex = priority_colors.get(priority, "#eab308")
                prio_icon = qta.icon("fa5s.circle", color=color_hex)
                
                item_priority = QTableWidgetItem()
                item_priority.setIcon(prio_icon)
                item_priority.setToolTip(f"Prioridad: {priority}")
                item_priority.setData(Qt.UserRole, email_id)
                
                formatted_date = created_at[:16] if len(created_at) >= 16 else created_at
                
                item_from = QTableWidgetItem(from_user)
                item_title = QTableWidgetItem(title)
                item_date = QTableWidgetItem(formatted_date)
                
                # Aplicar peso y color de la fuente según si está leído o no
                if not read_bool:
                    bold_font = QFont()
                    bold_font.setBold(True)
                    item_priority.setFont(bold_font)
                    item_from.setFont(bold_font)
                    item_title.setFont(bold_font)
                    item_date.setFont(bold_font)
                    
                    bright_color = QColor("#ffffff")
                    item_from.setForeground(bright_color)
                    item_title.setForeground(bright_color)
                    item_date.setForeground(bright_color)
                else:
                    muted_color = QColor("#a1a1aa")
                    item_from.setForeground(muted_color)
                    item_title.setForeground(muted_color)
                    item_date.setForeground(muted_color)
                    
                self.table.setItem(row, 0, item_priority)
                self.table.setItem(row, 1, item_from)
                self.table.setItem(row, 2, item_title)
                self.table.setItem(row, 3, item_date)
                
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in EmailListView._repopulate_table")

    def _on_error(self, exc: Exception) -> None:
        try:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Actualizar")
            err_msg = f"Error inesperado: {exc}"
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err_msg, "error")
            self.table.setRowCount(0)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in EmailListView._on_error")
