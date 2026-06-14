import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QPushButton,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from app_core.concurrency import run_async
from app_core.views.module_admin_view import ModuleAdminView
from modules.localmail import service as localmail_service

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from app_core.config import TardisConfig
    from noco_lib.noco_core.client import NocoClient

logger = logging.getLogger("tardis")


class SettingsView(QWidget):
    """Settings screen with three tabs: Modules, Connection, Diagnostics.

    Replaces the former Module Admin bottom dock panel and provides
    a home for diagnostics that were previously in the Dummy module.
    """

    def __init__(
        self,
        config: "TardisConfig",
        module_info: dict,
        client: "NocoClient",
        main_window: "MainWindow",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._module_info = module_info
        self._client = client
        self._main_window = main_window

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Title
        title = QLabel("Configuración")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding-bottom: 8px;")
        layout.addWidget(title)

        # Tab widget
        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_modules_tab(), "Módulos")
        self._tabs.addTab(self._build_connection_tab(), "Conexión")
        self._tabs.addTab(self._build_diagnostics_tab(), "Diagnóstico")

        layout.addWidget(self._tabs, stretch=1)

    # ── Modules tab ───────────────────────────────────────────────────

    def _build_modules_tab(self) -> QWidget:
        """Tab showing the module admin table (Name / Status / Error)."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        info_label = QLabel(
            "Módulos registrados en Tardis. Si un módulo muestra 'Error', "
            "revise el mensaje y corrija la configuración o el código."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #a0a0a0; padding-bottom: 4px;")
        layout.addWidget(info_label)

        # Embed the existing ModuleAdminView
        self._modules_view = ModuleAdminView(self._module_info)
        layout.addWidget(self._modules_view, stretch=1)

        return tab

    # ── Connection tab ────────────────────────────────────────────────

    def _build_connection_tab(self) -> QWidget:
        """Tab showing read-only connection details."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── NocoDB group ──
        noco_group = QGroupBox("NocoDB")
        noco_form = QFormLayout(noco_group)
        noco_form.setSpacing(8)

        noco_form.addRow("URL:", self._readonly_label(self._config.noco_base_url or "(no configurado)"))
        noco_form.addRow("Base ID:", self._readonly_label(self._config.noco_base_id or "(no configurado)"))
        noco_form.addRow("Token:", self._readonly_label(self._mask_token(self._config.noco_token)))

        layout.addWidget(noco_group)

        # ── AI group ──
        ai_group = QGroupBox("Inteligencia Artificial")
        ai_form = QFormLayout(ai_group)
        ai_form.setSpacing(8)

        ai_provider = os.environ.get("TARDIS_AI_PROVIDER", "ollama")
        ai_model = os.environ.get("TARDIS_AI_MODEL", "gemma3:27b")
        ai_base_url = os.environ.get("TARDIS_AI_BASE_URL", "http://localhost:11434")

        ai_form.addRow("Proveedor:", self._readonly_label(ai_provider))
        ai_form.addRow("Modelo:", self._readonly_label(ai_model))
        ai_form.addRow("URL base:", self._readonly_label(ai_base_url))

        layout.addWidget(ai_group)

        # ── LocalMail group ──
        lm_group = QGroupBox("LocalMail")
        lm_form = QFormLayout(lm_group)
        lm_form.setSpacing(8)

        lm_form.addRow("Tabla:", self._readonly_label(self._config.localmail_table))
        lm_form.addRow("Casillas:", self._readonly_label("; ".join(self._config.mailboxes) if self._config.mailboxes else "(ninguna)"))
        lm_form.addRow("Usuario:", self._readonly_label(self._config.user_id))

        layout.addWidget(lm_group)

        layout.addStretch()
        return tab

    @staticmethod
    def _mask_token(token: str) -> str:
        """Show first 4 chars + \"****\", or placeholder if empty."""
        if not token:
            return "(no configurado)"
        if len(token) <= 4:
            return token + "****"
        return token[:4] + "****"

    @staticmethod
    def _readonly_label(text: str) -> QLabel:
        """Create a styled read-only QLabel for connection details."""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        label.setStyleSheet(
            "color: #e0e0e0; background: #2a2a2a; padding: 4px 8px; "
            "border-radius: 4px; font-family: monospace;"
        )
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        return label

    # ── Diagnostics tab ───────────────────────────────────────────────

    def _build_diagnostics_tab(self) -> QWidget:
        """Tab with test notification and log file buttons."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # ── Test notification ──
        notify_group = QGroupBox("Notificaciones")
        notify_layout = QVBoxLayout(notify_group)

        notify_desc = QLabel(
            "Envía un mensaje de prueba a la bandeja de entrada de la "
            "primera casilla configurada."
        )
        notify_desc.setWordWrap(True)
        notify_desc.setStyleSheet("color: #a0a0a0;")
        notify_layout.addWidget(notify_desc)

        self._notify_btn = QPushButton("Enviar notificación de prueba")
        self._notify_btn.clicked.connect(self._on_send_test_notification)
        notify_layout.addWidget(self._notify_btn)

        layout.addWidget(notify_group)

        # ── Log file ──
        log_group = QGroupBox("Registros (logs)")
        log_layout = QVBoxLayout(log_group)

        log_desc = QLabel(
            "Abre el archivo de registro de Tardis en el visor predeterminado "
            "del sistema."
        )
        log_desc.setWordWrap(True)
        log_desc.setStyleSheet("color: #a0a0a0;")
        log_layout.addWidget(log_desc)

        self._log_btn = QPushButton("Abrir archivo de registro")
        self._log_btn.clicked.connect(self._on_open_log_file)
        log_layout.addWidget(self._log_btn)

        layout.addWidget(log_group)

        # ── Last action result ──
        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet(
            "padding: 8px; border-radius: 4px; font-weight: bold;"
        )
        self._result_label.hide()
        layout.addWidget(self._result_label)

        layout.addStretch()
        return tab

    # ── Diagnostics: test notification ────────────────────────────────

    def _on_send_test_notification(self) -> None:
        """Send a test notification via LocalMail's notify API."""
        self._notify_btn.setEnabled(False)
        self._set_result("Enviando notificación de prueba...", "info")

        mailboxes = self._config.mailboxes[:1] if self._config.mailboxes else []
        if not mailboxes:
            self._set_result(
                "No hay casillas configuradas (TARDIS_MAILBOXES vacío).",
                "error",
            )
            self._notify_btn.setEnabled(True)
            return

        def on_notify_result(result):
            self._notify_btn.setEnabled(True)
            if result.success:
                self._set_result(
                    f"✓ Notificación enviada correctamente a {mailboxes[0]}.",
                    "success",
                )
                self._main_window.show_notification(
                    "Notificación de prueba enviada.", "success"
                )
            else:
                err = "; ".join(result.errors) if result.errors else "Error desconocido"
                self._set_result(f"✗ Error al enviar notificación: {err}", "error")

        def on_notify_error(exc):
            self._notify_btn.setEnabled(True)
            self._set_result(f"✗ Error: {exc}", "error")

        run_async(
            localmail_service.notify,
            self._client,
            to_users=mailboxes,
            subject="Prueba de diagnóstico",
            body="Notificación de prueba desde Configuración > Diagnóstico de Tardis.",
            module_origin="diagnostics",
            on_success=on_notify_result,
            on_error=on_notify_error,
        )

    # ── Diagnostics: open log file ────────────────────────────────────

    def _on_open_log_file(self) -> None:
        """Open the Tardis log file with the system default viewer."""
        log_path = self._get_log_path()
        if not log_path or not log_path.exists():
            self._set_result(
                f"Archivo de registro no encontrado: {log_path}", "error"
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(str(log_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(log_path)])
            else:
                subprocess.Popen(["xdg-open", str(log_path)])
            self._set_result(
                f"Abriendo: {log_path}", "success"
            )
        except Exception as exc:
            logger.exception("Failed to open log file")
            self._set_result(f"Error al abrir archivo: {exc}", "error")

    @staticmethod
    def _get_log_path() -> Path | None:
        """Resolve the ``logs/tardis.log`` path relative to the project root."""
        try:
            # SettingsView lives at tardis/app_core/views/settings_view.py
            # Project root is parents[3] (tardis → app_core → views → settings_view.py)
            root = Path(__file__).resolve().parents[3]
            return root / "logs" / "tardis.log"
        except Exception:
            # Fallback: cwd/logs/tardis.log
            return Path.cwd() / "logs" / "tardis.log"

    # ── Result label helper ────────────────────────────────────────────

    def _set_result(self, text: str, level: str = "info") -> None:
        """Update the result label with style based on level."""
        colors = {
            "info": "color: #0a66c2; background: rgba(10, 102, 194, 0.1);",
            "success": "color: #5cb85c; background: rgba(92, 184, 92, 0.1);",
            "error": "color: #d9534f; background: rgba(217, 83, 79, 0.1);",
        }
        style = colors.get(level, colors["info"])
        self._result_label.setStyleSheet(f"padding: 8px; border-radius: 4px; font-weight: bold; {style}")
        self._result_label.setText(text)
        self._result_label.show()
