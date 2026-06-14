import sys
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QFrame,
    QTextBrowser, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

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

class ReaderView(QWidget):
    email_read = Signal(int)  # Emite el ID del correo cuando se marca como leído exitosamente

    def __init__(self, main_window, client: NocoClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self._current_email_id = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header/Title Label
        self.title_label = QLabel("Lector de Correo")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(self.title_label)

        # Action Buttons Row
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)

        self.btn_archive = QPushButton("Archive")
        self.btn_archive.setIcon(qta.icon("fa5s.archive", color="#e1e1e6"))
        self.btn_archive.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #e1e1e6;
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
                color: #52525b;
                border-color: #27272a;
            }
        """)

        self.btn_trash = QPushButton("Move to Trash")
        self.btn_trash.setIcon(qta.icon("fa5s.trash", color="#e1e1e6"))
        self.btn_trash.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #e1e1e6;
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
                color: #52525b;
                border-color: #27272a;
            }
        """)

        self.btn_archive.clicked.connect(self._on_archive_clicked)
        self.btn_trash.clicked.connect(self._on_trash_clicked)

        self.actions_layout.addWidget(self.btn_archive)
        self.actions_layout.addWidget(self.btn_trash)
        self.actions_layout.addStretch()
        layout.addLayout(self.actions_layout)

        # 1. Cabecera (Header block)
        self.header_widget = QWidget()
        self.header_layout = QVBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(8)

        # Asunto en negrita y más grande
        self.lbl_subject = QLabel()
        self.lbl_subject.setWordWrap(True)
        self.lbl_subject.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff; padding-bottom: 4px;")
        self.header_layout.addWidget(self.lbl_subject)

        # Layout del formulario para metadatos
        self.meta_layout = QFormLayout()
        self.meta_layout.setContentsMargins(0, 0, 0, 0)
        self.meta_layout.setSpacing(6)
        self.meta_layout.setLabelAlignment(Qt.AlignRight)

        label_style = "color: #a1a1aa; font-weight: bold; font-size: 13px;"
        value_style = "color: #e1e1e6; font-size: 13px;"

        self.lbl_from_hdr = QLabel("De:")
        self.lbl_from_hdr.setStyleSheet(label_style)
        self.lbl_from = QLabel()
        self.lbl_from.setStyleSheet(value_style)
        self.meta_layout.addRow(self.lbl_from_hdr, self.lbl_from)

        self.lbl_to_hdr = QLabel("Para:")
        self.lbl_to_hdr.setStyleSheet(label_style)
        self.lbl_to = QLabel()
        self.lbl_to.setStyleSheet(value_style)
        self.meta_layout.addRow(self.lbl_to_hdr, self.lbl_to)

        self.lbl_cc_hdr = QLabel("CC:")
        self.lbl_cc_hdr.setStyleSheet(label_style)
        self.lbl_cc = QLabel()
        self.lbl_cc.setStyleSheet(value_style)
        self.meta_layout.addRow(self.lbl_cc_hdr, self.lbl_cc)

        self.lbl_date_hdr = QLabel("Fecha:")
        self.lbl_date_hdr.setStyleSheet(label_style)
        self.lbl_date = QLabel()
        self.lbl_date.setStyleSheet(value_style)
        self.meta_layout.addRow(self.lbl_date_hdr, self.lbl_date)

        self.lbl_prio_hdr = QLabel("Prioridad:")
        self.lbl_prio_hdr.setStyleSheet(label_style)
        
        # Prioridad con icono y texto
        self.prio_container = QWidget()
        prio_layout = QHBoxLayout(self.prio_container)
        prio_layout.setContentsMargins(0, 0, 0, 0)
        prio_layout.setSpacing(6)
        
        self.lbl_prio_icon = QLabel()
        self.lbl_prio_text = QLabel()
        self.lbl_prio_text.setStyleSheet(value_style)
        prio_layout.addWidget(self.lbl_prio_icon)
        prio_layout.addWidget(self.lbl_prio_text)
        prio_layout.addStretch()
        
        self.meta_layout.addRow(self.lbl_prio_hdr, self.prio_container)

        self.header_layout.addLayout(self.meta_layout)
        layout.addWidget(self.header_widget)

        # 2. Separador visual
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setStyleSheet("background-color: #27272a; max-height: 1px; border: none; margin: 4px 0px;")
        layout.addWidget(self.separator)

        # 3. Cuerpo del mensaje
        self.browser = QTextBrowser()
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #18181b;
                color: #e1e1e6;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.browser)

        # Inicialmente ocultar cabecera y separador hasta que haya un correo cargado
        self.header_widget.setVisible(False)
        self.separator.setVisible(False)
        self.browser.setPlainText("Selecciona un correo para leerlo.")
        self._update_action_buttons()

    def show_email(self, email_id: int) -> None:
        """
        Loads and renders the email corresponding to the given email_id asynchronously.
        """
        try:
            if not isinstance(email_id, int) or email_id <= 0:
                self._current_email_id = None
                self.header_widget.setVisible(False)
                self.separator.setVisible(False)
                self.browser.setPlainText("ID de correo inválido.")
                self._update_action_buttons()
                return

            self._current_email_id = email_id
            self._update_action_buttons()
            self.header_widget.setVisible(False)
            self.separator.setVisible(False)
            self.browser.setPlainText("Cargando correo...")
            run_async(
                service.get_email,
                self.client,
                email_id,
                on_success=self._render,
                on_error=self._on_error
            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView.show_email")

    def _render(self, result) -> None:
        try:
            if not result.success:
                self._current_email_id = None
                self._update_action_buttons()
                err_msg = result.errors[0] if result.errors else "Error desconocido al cargar el correo."
                self.browser.setPlainText(f"Error: {err_msg}")
                self.header_widget.setVisible(False)
                self.separator.setVisible(False)
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err_msg, "error")
                return

            email = result.data
            if not email:
                self._current_email_id = None
                self._update_action_buttons()
                self.browser.setPlainText("Correo no encontrado.")
                self.header_widget.setVisible(False)
                self.separator.setVisible(False)
                return

            # Extraer campos
            from_user = email.get("from", "")
            to_user = email.get("to", "")
            cc = email.get("cc", "")
            created_at = email.get("CreatedAt", "")
            title = email.get("title", "")
            body = email.get("body", "")
            priority = email.get("priority", "Media")

            # Formatear fecha de forma legible
            formatted_date = created_at
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            # Rellenar widgets de cabecera
            self.lbl_subject.setText(title)
            self.lbl_from.setText(from_user)
            self.lbl_to.setText(to_user)
            
            if cc:
                self.lbl_cc.setText(cc)
                self.lbl_cc_hdr.setVisible(True)
                self.lbl_cc.setVisible(True)
            else:
                self.lbl_cc_hdr.setVisible(False)
                self.lbl_cc.setVisible(False)

            self.lbl_date.setText(formatted_date)

            # Icono y color de prioridad
            priority_colors = {
                "Alta": "#dc2626",   # Rojo
                "Media": "#eab308",  # Amarillo
                "Baja": "#16a34a"    # Verde
            }
            color_hex = priority_colors.get(priority, "#eab308")
            prio_icon = qta.icon("fa5s.circle", color=color_hex)
            self.lbl_prio_icon.setPixmap(prio_icon.pixmap(12, 12))
            self.lbl_prio_text.setText(priority)

            # Mostrar cabecera y separador, cargar cuerpo en el text browser
            self.header_widget.setVisible(True)
            self.separator.setVisible(True)
            self.browser.setPlainText(body)
            self._update_action_buttons()

            # Fire-and-forget: mark as read as a separate independent call
            email_id = email.get("Id")
            if email_id:
                run_async(
                    service.mark_as_read,
                    self.client,
                    email_id,
                    on_success=lambda r, eid=email_id: self._on_mark_as_read_success(eid, r),
                    on_error=lambda e: logging.getLogger("tardis").warning("Error al marcar como leído: %s", str(e))
                )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._render")

    def _on_mark_as_read_success(self, email_id: int, result) -> None:
        try:
            if result.success:
                self.email_read.emit(email_id)
            else:
                err = result.errors[0] if result.errors else "Error desconocido"
                logging.getLogger("tardis").warning("Fallo al marcar como leído en NocoDB: %s", err)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._on_mark_as_read_success")

    def _on_error(self, exc: Exception) -> None:
        try:
            self._current_email_id = None
            self._update_action_buttons()
            err_msg = f"Error inesperado: {exc}"
            self.browser.setPlainText(err_msg)
            self.header_widget.setVisible(False)
            self.separator.setVisible(False)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err_msg, "error")
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._on_error")

    def _get_current_folder(self) -> str | None:
        if hasattr(self.main_window, "sidebar_view") and self.main_window.sidebar_view:
            current_item = self.main_window.sidebar_view.currentItem()
            if current_item:
                node = current_item.data(0, Qt.UserRole + 1)
                if node:
                    return node.folder
        return None

    def _get_current_mailboxes(self) -> list[str]:
        if hasattr(self.main_window, "sidebar_view") and self.main_window.sidebar_view:
            current_item = self.main_window.sidebar_view.currentItem()
            if current_item:
                node = current_item.data(0, Qt.UserRole + 1)
                if node:
                    return node.mailboxes
        return []

    def _update_action_buttons(self) -> None:
        folder = self._get_current_folder()
        has_email = getattr(self, "_current_email_id", None) is not None
        self.btn_archive.setEnabled(has_email and folder != "archive")
        self.btn_trash.setEnabled(has_email and folder != "trash")

    def _on_archive_clicked(self) -> None:
        email_id = getattr(self, "_current_email_id", None)
        if not email_id:
            return
        self.btn_archive.setEnabled(False)
        self.btn_trash.setEnabled(False)
        run_async(
            service.archive_email,
            self.client,
            email_id,
            on_success=self._on_archive_success,
            on_error=self._on_action_error
        )

    def _on_trash_clicked(self) -> None:
        email_id = getattr(self, "_current_email_id", None)
        if not email_id:
            return
        self.btn_archive.setEnabled(False)
        self.btn_trash.setEnabled(False)
        run_async(
            service.move_to_trash,
            self.client,
            email_id,
            on_success=self._on_trash_success,
            on_error=self._on_action_error
        )

    def _on_archive_success(self, result) -> None:
        try:
            if result.success:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification("Email archived", "success")
                self._clear_reader_and_refresh()
            else:
                err = result.errors[0] if result.errors else "Error al archivar el correo"
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err, "error")
                self._update_action_buttons()
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._on_archive_success")
            self._update_action_buttons()

    def _on_trash_success(self, result) -> None:
        try:
            if result.success:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification("Moved to trash", "success")
                self._clear_reader_and_refresh()
            else:
                err = result.errors[0] if result.errors else "Error al mover a la papelera"
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err, "error")
                self._update_action_buttons()
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._on_trash_success")
            self._update_action_buttons()

    def _on_action_error(self, exc: Exception) -> None:
        try:
            err_msg = f"Error: {exc}"
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err_msg, "error")
            self._update_action_buttons()
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._on_action_error")

    def _clear_reader_and_refresh(self) -> None:
        self._current_email_id = None
        self.header_widget.setVisible(False)
        self.separator.setVisible(False)
        self.browser.setPlainText("Selecciona un correo para leerlo.")
        self._update_action_buttons()
        
        folder = self._get_current_folder()
        mailboxes = self._get_current_mailboxes()
        if folder and mailboxes and hasattr(self.main_window, "email_list_view") and self.main_window.email_list_view:
            self.main_window.email_list_view.load(self.client, mailboxes, folder)
