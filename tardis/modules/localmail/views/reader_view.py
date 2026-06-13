import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLabel
from PySide6.QtCore import Qt

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
    def __init__(self, main_window, client: NocoClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header/Title Label
        self.title_label = QLabel("Lector de Correo")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(self.title_label)

        # Text Browser for rendering email plain text
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

        # Initial instruction
        self.browser.setPlainText("Selecciona un correo para leerlo.")

    def show_email(self, email_id: int) -> None:
        """
        Loads and renders the email corresponding to the given email_id asynchronously.
        """
        try:
            if not isinstance(email_id, int) or email_id <= 0:
                self.browser.setPlainText("ID de correo inválido.")
                return

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
                err_msg = result.errors[0] if result.errors else "Error desconocido al cargar el correo."
                self.browser.setPlainText(f"Error: {err_msg}")
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err_msg, "error")
                return

            email = result.data
            if not email:
                self.browser.setPlainText("Correo no encontrado.")
                return

            # Extract values safely
            from_user = email.get("from", "")
            to_user = email.get("to", "")
            cc = email.get("cc", "")
            created_at = email.get("CreatedAt", "")
            title = email.get("title", "")
            body = email.get("body", "")

            # Format details
            lines = [
                f"De:      {from_user}",
                f"Para:    {to_user}",
            ]
            if cc:
                lines.append(f"CC:      {cc}")
            lines.extend([
                f"Fecha:   {created_at}",
                f"Asunto:  {title}",
                "-" * 60,
                "",
                body
            ])

            rendered_text = "\n".join(lines)
            self.browser.setPlainText(rendered_text)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._render")

    def _on_error(self, exc: Exception) -> None:
        try:
            err_msg = f"Error inesperado: {exc}"
            self.browser.setPlainText(err_msg)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err_msg, "error")
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in ReaderView._on_error")
