import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QSettings

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

class ComposerView(QWidget):
    def __init__(self, main_window, client: NocoClient, mailboxes: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self.mailboxes = mailboxes
        self._sent_successfully = False
        self._init_ui()

        # Restablecer geometría si existe
        settings = QSettings("Tardis", "Tardis")
        geom = settings.value("floating/Compose/geometry")
        if geom is not None:
            self.restoreGeometry(geom)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Style inputs and labels
        input_style = """
            QLineEdit, QTextEdit, QComboBox {
                background-color: #18181b;
                color: #e1e1e6;
                border: 1px solid #27272a;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #2563eb;
            }
        """
        label_style = "color: #a1a1aa; font-weight: bold;"

        # Title
        self.title_label = QLabel("Redactar Nuevo Correo")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(self.title_label)

        # Error label (hidden by default)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; font-weight: bold;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Desde (From)
        from_layout = QHBoxLayout()
        from_lbl = QLabel("Desde:")
        from_lbl.setFixedWidth(50)
        from_lbl.setStyleSheet(label_style)
        self.from_combo = QComboBox()
        self.from_combo.setStyleSheet(input_style)
        self.from_combo.addItems(self.mailboxes)
        from_layout.addWidget(from_lbl)
        from_layout.addWidget(self.from_combo)
        layout.addLayout(from_layout)

        # To:
        to_layout = QHBoxLayout()
        to_lbl = QLabel("Para:")
        to_lbl.setFixedWidth(50)
        to_lbl.setStyleSheet(label_style)
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("destinatario1; destinatario2")
        self.to_input.setStyleSheet(input_style)
        to_layout.addWidget(to_lbl)
        to_layout.addWidget(self.to_input)
        layout.addLayout(to_layout)

        # CC:
        cc_layout = QHBoxLayout()
        cc_lbl = QLabel("CC:")
        cc_lbl.setFixedWidth(50)
        cc_lbl.setStyleSheet(label_style)
        self.cc_input = QLineEdit()
        self.cc_input.setPlaceholderText("destinatario1; destinatario2")
        self.cc_input.setStyleSheet(input_style)
        cc_layout.addWidget(cc_lbl)
        cc_layout.addWidget(self.cc_input)
        layout.addLayout(cc_layout)

        # Subject:
        sub_layout = QHBoxLayout()
        sub_lbl = QLabel("Asunto:")
        sub_lbl.setFixedWidth(50)
        sub_lbl.setStyleSheet(label_style)
        self.subject_input = QLineEdit()
        self.subject_input.setStyleSheet(input_style)
        sub_layout.addWidget(sub_lbl)
        sub_layout.addWidget(self.subject_input)
        layout.addLayout(sub_layout)

        # Priority:
        prio_layout = QHBoxLayout()
        prio_lbl = QLabel("Prioridad:")
        prio_lbl.setFixedWidth(70)
        prio_lbl.setStyleSheet(label_style)
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Baja", "Media", "Alta"])
        self.priority_combo.setCurrentText("Media")
        self.priority_combo.setStyleSheet(input_style)
        prio_layout.addWidget(prio_lbl)
        prio_layout.addWidget(self.priority_combo)
        prio_layout.addStretch()
        layout.addLayout(prio_layout)

        # Body:
        body_lbl = QLabel("Mensaje:")
        body_lbl.setStyleSheet(label_style)
        self.body_input = QTextEdit()
        self.body_input.setStyleSheet(input_style)
        layout.addWidget(body_lbl)
        layout.addWidget(self.body_input)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_send = QPushButton("Enviar")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
            QPushButton:disabled {
                background-color: #1e293b;
                color: #64748b;
            }
        """)
        self.btn_send.clicked.connect(self._on_send_clicked)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_send)
        layout.addLayout(btn_layout)

        # Handle empty/single mailbox state
        if len(self.mailboxes) == 1:
            self.from_combo.setCurrentIndex(0)
            self.from_combo.setEnabled(False)
        elif len(self.mailboxes) == 0:
            self.from_combo.setEnabled(False)
            self.to_input.setEnabled(False)
            self.cc_input.setEnabled(False)
            self.subject_input.setEnabled(False)
            self.priority_combo.setEnabled(False)
            self.body_input.setEnabled(False)
            self.btn_send.setEnabled(False)
            
            # Show error/placeholder message
            self.error_label.setText("No hay casillas configuradas. Define TARDIS_MAILBOXES en tu archivo .env.")
            self.error_label.setVisible(True)

    def _on_send_clicked(self) -> None:
        try:
            from_val = self.from_combo.currentText().strip()
            to_val = self.to_input.text().strip()
            cc_val = self.cc_input.text().strip()
            subject_val = self.subject_input.text().strip()
            body_val = self.body_input.toPlainText()
            priority_val = self.priority_combo.currentText()

            # Parse comma/semicolon separated email addresses
            to_users = [s.strip() for s in to_val.split(";") if s.strip()]
            cc_users = [s.strip() for s in cc_val.split(";") if s.strip()] if cc_val else None

            # UI Validation
            if not from_val:
                self.error_label.setText("La casilla remitente (Desde) no puede estar vacía.")
                self.error_label.setVisible(True)
                return

            if not to_users:
                self.error_label.setText("El destinatario (Para) no puede estar vacío.")
                self.error_label.setVisible(True)
                return

            if not subject_val:
                self.error_label.setText("El asunto no puede estar vacío.")
                self.error_label.setVisible(True)
                return

            self.error_label.setVisible(False)
            self.btn_send.setEnabled(False)
            self.btn_send.setText("Enviando...")

            run_async(
                service.send_email,
                self.client,
                from_user=from_val,
                to_users=to_users,
                subject=subject_val,
                body=body_val,
                cc_users=cc_users,
                priority=priority_val,
                on_success=self._on_sent,
                on_error=self._on_error
            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ComposerView._on_send_clicked")

    def _on_sent(self, result) -> None:
        try:
            self.btn_send.setEnabled(True)
            self.btn_send.setText("Enviar")

            if not result.success:
                err_msg = ", ".join(result.errors) if result.errors else "Error desconocido al enviar el correo."
                self.error_label.setText(err_msg)
                self.error_label.setVisible(True)
                return

            self.error_label.setVisible(False)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification("Email sent", "success")

            self._sent_successfully = True

            # Clear the form
            self.to_input.clear()
            self.cc_input.clear()
            self.subject_input.clear()
            self.body_input.clear()
            self.priority_combo.setCurrentText("Media")

            # Close the widget itself
            self.close()

            # Find and close the parent CDockWidget (floating container) if applicable
            parent = self.parent()
            while parent:
                if parent.__class__.__name__ == "CDockWidget":
                    parent.close()
                    break
                parent = parent.parent()

            # Refresh list view if currently selected node is sent or inbox
            if hasattr(self.main_window, "sidebar_view") and self.main_window.sidebar_view:
                current_item = self.main_window.sidebar_view.currentItem()
                if current_item:
                    node = current_item.data(0, Qt.UserRole + 1)
                    if node and node.folder in ["sent", "inbox"]:
                        if hasattr(self.main_window, "email_list_view") and self.main_window.email_list_view:
                            self.main_window.email_list_view.load(
                                self.client,
                                node.mailboxes,
                                node.folder
                            )
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ComposerView._on_sent")

    def _on_error(self, exc: Exception) -> None:
        try:
            self.btn_send.setEnabled(True)
            self.btn_send.setText("Enviar")
            err_msg = f"Error inesperado: {exc}"
            self.error_label.setText(err_msg)
            self.error_label.setVisible(True)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err_msg, "error")
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ComposerView._on_error")

    def closeEvent(self, event) -> None:
        try:
            to_val = self.to_input.text().strip()
            subject_val = self.subject_input.text().strip()
            body_val = self.body_input.toPlainText().strip()

            if not self._sent_successfully and (to_val or subject_val or body_val):
                reply = QMessageBox.question(
                    self,
                    "Discard draft?",
                    "You have unsent content. Discard this email?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return

            settings = QSettings("Tardis", "Tardis")
            settings.setValue("floating/Compose/geometry", self.saveGeometry())
            event.accept()
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ComposerView.closeEvent")
            event.accept()
