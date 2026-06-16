"""Visor de redacción de correo con soporte para responder, reenviar, adjuntos y firmas."""

import sys
import os
import uuid
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QMessageBox, QFileDialog,
    QSizePolicy,
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
from modules.localmail.signatures import (
    get_signatures_for_mailbox,
    get_default_signature,
    build_signature_html,
)
from noco_lib.noco_core.client import NocoClient
from shared.utils import human_readable_size as _human_readable_size


class ComposerView(QWidget):
    """Widget de redacción de correo electrónico.

    Puede crearse de forma estándar, o mediante los métodos de clase
    ``for_reply()`` y ``for_forward()`` para prellenar el formulario
    al responder o reenviar un correo.
    """

    def __init__(
        self,
        main_window,
        client: NocoClient,
        mailboxes: list[str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self.mailboxes = mailboxes
        self._sent_successfully = False
        self._reply_to_uuid: str = ""
        self._thread_uuid_override: str | None = None
        self._attachment_paths: list[str] = []
        self._signature_start_pos: int | None = None

        self._init_ui()
        self._load_signatures_for_mailbox(
            mailboxes[0] if mailboxes else ""
        )

        # Restaurar geometría
        settings = QSettings("Tardis", "Tardis")
        geom = settings.value("floating/Compose/geometry")
        if geom is not None:
            self.restoreGeometry(geom)

    # ── Métodos de clase para Reply/Forward ────────────────────────────

    @classmethod
    def for_reply(
        cls,
        original_email: dict,
        client: NocoClient,
        config,
        main_window,
    ) -> "ComposerView":
        """Crea un ComposerView prellenado para responder un correo."""
        mailboxes = list(config.mailboxes) if config and hasattr(config, "mailboxes") else []
        composer = cls(main_window, client, mailboxes)
        composer.setWindowTitle("Responder")

        # Destinatario = remitente original
        composer.to_input.setText(original_email.get("from", ""))

        # Asunto: prefijo "Re: " si no existe ya
        orig_subject = original_email.get("title", "")
        if orig_subject.lower().startswith("re: "):
            composer.subject_input.setText(orig_subject)
        else:
            composer.subject_input.setText(f"Re: {orig_subject}")

        # Cuerpo: cita con "> " por línea
        orig_body = original_email.get("body", "")
        quoted = "\n".join(f"> {line}" for line in orig_body.splitlines())
        composer.body_input.setText(f"\n\n---\n{quoted}")

        # Metadata de respuesta
        composer._reply_to_uuid = original_email.get("message_uuid", "")
        composer._thread_uuid_override = original_email.get("thread_uuid", None)

        return composer

    @classmethod
    def for_forward(
        cls,
        original_email: dict,
        client: NocoClient,
        config,
        main_window,
    ) -> "ComposerView":
        """Crea un ComposerView prellenado para reenviar un correo."""
        mailboxes = list(config.mailboxes) if config and hasattr(config, "mailboxes") else []
        composer = cls(main_window, client, mailboxes)
        composer.setWindowTitle("Reenviar")

        # Destinatario: vacío (el usuario lo completa)
        composer.to_input.setText("")

        # Asunto: prefijo "Fwd: "
        orig_subject = original_email.get("title", "")
        if orig_subject.lower().startswith("fwd: "):
            composer.subject_input.setText(orig_subject)
        else:
            composer.subject_input.setText(f"Fwd: {orig_subject}")

        # Cuerpo: mensaje reenviado completo (sin citación por línea)
        orig_body = original_email.get("body", "")
        composer.body_input.setText(f"\n\n--- Mensaje reenviado ---\n{orig_body}")

        # Nuevo hilo de conversación
        composer._reply_to_uuid = ""
        composer._thread_uuid_override = None  # se genera nuevo uuid4 en send_email

        return composer

    # ── UI ─────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Título
        self.title_label = QLabel("Redactar Nuevo Correo")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a1a18;")
        layout.addWidget(self.title_label)

        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #c62828; font-weight: bold;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        # Desde
        from_row = QHBoxLayout()
        from_lbl = QLabel("Desde:")
        from_lbl.setFixedWidth(50)
        from_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.from_combo = QComboBox()
        self.from_combo.addItems(self.mailboxes)
        from_row.addWidget(from_lbl)
        from_row.addWidget(self.from_combo)
        layout.addLayout(from_row)

        # Para
        to_row = QHBoxLayout()
        to_lbl = QLabel("Para:")
        to_lbl.setFixedWidth(50)
        to_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("destinatario1; destinatario2")
        to_row.addWidget(to_lbl)
        to_row.addWidget(self.to_input)
        layout.addLayout(to_row)

        # CC
        cc_row = QHBoxLayout()
        cc_lbl = QLabel("CC:")
        cc_lbl.setFixedWidth(50)
        cc_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.cc_input = QLineEdit()
        self.cc_input.setPlaceholderText("destinatario1; destinatario2")
        cc_row.addWidget(cc_lbl)
        cc_row.addWidget(self.cc_input)
        layout.addLayout(cc_row)

        # Asunto
        sub_row = QHBoxLayout()
        sub_lbl = QLabel("Asunto:")
        sub_lbl.setFixedWidth(50)
        sub_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.subject_input = QLineEdit()
        sub_row.addWidget(sub_lbl)
        sub_row.addWidget(self.subject_input)
        layout.addLayout(sub_row)

        # Prioridad
        prio_row = QHBoxLayout()
        prio_lbl = QLabel("Prioridad:")
        prio_lbl.setFixedWidth(70)
        prio_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Baja", "Media", "Alta"])
        self.priority_combo.setCurrentText("Media")
        prio_row.addWidget(prio_lbl)
        prio_row.addWidget(self.priority_combo)
        prio_row.addStretch()
        layout.addLayout(prio_row)

        # Cuerpo del mensaje
        body_lbl = QLabel("Mensaje:")
        body_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.body_input = QTextEdit()
        self.body_input.setMinimumHeight(150)
        layout.addWidget(body_lbl)
        layout.addWidget(self.body_input, stretch=1)

        # ── Selector de firma ──────────────────────────────────────────
        sig_row = QHBoxLayout()
        sig_lbl = QLabel("Firma:")
        sig_lbl.setStyleSheet("font-weight: bold; color: #5a5a56;")
        self.sig_combo = QComboBox()
        self.sig_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sig_row.addWidget(sig_lbl)
        sig_row.addWidget(self.sig_combo, stretch=1)
        layout.addLayout(sig_row)

        # ── Sección de adjuntos ────────────────────────────────────────
        att_label = QLabel("Adjuntos:")
        att_label.setStyleSheet("font-weight: bold; color: #5a5a56;")
        layout.addWidget(att_label)

        attach_row = QHBoxLayout()
        self.btn_attach = QPushButton("📎 Adjuntar archivo")
        self.btn_attach.setCursor(Qt.PointingHandCursor)
        self.btn_attach.setStyleSheet("""
            QPushButton {
                background: #f5f3f0; color: #1a1a18;
                border: 1px solid #dddad6; border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover { background: #ede9e4; }
        """)
        self.btn_attach.clicked.connect(self._on_attach_clicked)
        attach_row.addWidget(self.btn_attach)
        attach_row.addStretch()
        layout.addLayout(attach_row)

        self._attachments_container = QWidget()
        self._attachments_container.setVisible(False)
        self._attachments_layout = QVBoxLayout(self._attachments_container)
        self._attachments_layout.setContentsMargins(0, 0, 0, 0)
        self._attachments_layout.setSpacing(4)
        layout.addWidget(self._attachments_container)

        # ── Botón de envío ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_send = QPushButton("Enviar")
        self.btn_send.setObjectName("accentButton")
        self.btn_send.setFixedHeight(36)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: #e9290c; color: #ffffff; border: none;
                border-radius: 4px; padding: 8px 24px; font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background: #c5220a; }
            QPushButton:disabled { background: #dddad6; color: #5a5a56; }
        """)
        self.btn_send.clicked.connect(self._on_send_clicked)
        btn_row.addWidget(self.btn_send)
        layout.addLayout(btn_row)

        # Conectar señal de cambio de "Desde" para recargar firmas
        self.from_combo.currentTextChanged.connect(self._on_from_changed)
        self.sig_combo.currentIndexChanged.connect(self._on_sig_changed)

        # Estado inicial
        if len(self.mailboxes) == 1:
            self.from_combo.setCurrentIndex(0)
            self.from_combo.setEnabled(False)
        elif len(self.mailboxes) == 0:
            self._disable_all()

    def _disable_all(self) -> None:
        """Deshabilita todos los campos si no hay casillas configuradas."""
        for w in [self.from_combo, self.to_input, self.cc_input,
                  self.subject_input, self.priority_combo, self.body_input,
                  self.btn_send, self.btn_attach, self.sig_combo]:
            w.setEnabled(False)
        self.error_label.setText(
            "No hay casillas configuradas. Define TARDIS_MAILBOXES en tu .env."
        )
        self.error_label.setVisible(True)

    # ── Manejo de firmas ──────────────────────────────────────────────

    def _on_from_changed(self, mailbox: str) -> None:
        """Recarga las firmas al cambiar la casilla remitente."""
        self._load_signatures_for_mailbox(mailbox)

    def _on_sig_changed(self, index: int) -> None:
        """Aplica la firma seleccionada al cuerpo del mensaje."""
        sig = self.sig_combo.itemData(index)
        self._apply_signature(sig)

    def _load_signatures_for_mailbox(self, mailbox: str) -> None:
        """Pobla el combo de firmas con las firmas de la casilla seleccionada."""
        self.sig_combo.blockSignals(True)
        self.sig_combo.clear()
        self.sig_combo.addItem("(Sin firma)", userData=None)

        if mailbox:
            sigs = get_signatures_for_mailbox(mailbox)
            for sig in sigs:
                display = sig.get("name", "Firma")
                if sig.get("is_default"):
                    display += " (predeterminada)"
                self.sig_combo.addItem(display, userData=sig)

            # Seleccionar firma predeterminada
            default = get_default_signature(mailbox)
            if default:
                for i in range(self.sig_combo.count()):
                    data = self.sig_combo.itemData(i)
                    if data and data.get("id") == default.get("id"):
                        self.sig_combo.setCurrentIndex(i)
                        self._apply_signature(default)
                        break
            else:
                self._apply_signature(None)

        self.sig_combo.blockSignals(False)

    def _apply_signature(self, sig: dict | None) -> None:
        """Inserta o remueve la firma del cuerpo del mensaje."""
        body = self.body_input.toPlainText()

        if sig is None:
            # Remover firma insertada previamente
            if self._signature_start_pos is not None:
                body = body[:self._signature_start_pos].rstrip()
                self.body_input.setPlainText(body)
                self._signature_start_pos = None
            return

        # Remover firma anterior si existe
        if self._signature_start_pos is not None:
            body = body[:self._signature_start_pos].rstrip()

        # Insertar nueva firma
        sig_html = build_signature_html(sig)
        # Convertir HTML a texto plano aproximado (para el QTextEdit en modo plano)
        import re
        sig_text = re.sub(r"<[^>]+>", "", sig_html)
        sig_text = sig_text.replace("&nbsp;", " ").replace("&amp;", "&")
        # Colapsar múltiples líneas vacías
        sig_text = re.sub(r"\n{3,}", "\n\n", sig_text).strip()

        new_body = f"{body}\n\n---\n{sig_text}" if body.strip() else sig_text
        self._signature_start_pos = len(body) if body.strip() else 0
        self.body_input.setPlainText(new_body)

    # ── Manejo de adjuntos ────────────────────────────────────────────

    def _on_attach_clicked(self) -> None:
        """Abre el diálogo de selección de archivos para adjuntar."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar archivos", "", "Todos los archivos (*.*)"
        )
        max_mb = int(os.environ.get("TARDIS_MAX_ATTACHMENT_MB", "10"))
        max_bytes = max_mb * 1024 * 1024

        for fpath in files:
            if fpath in self._attachment_paths:
                continue
            try:
                fsize = Path(fpath).stat().st_size
                if fsize > max_bytes:
                    if hasattr(self.main_window, "show_notification"):
                        self.main_window.show_notification(
                            f"El archivo {Path(fpath).name} supera el límite de {max_mb}MB",
                            "error",
                        )
                    continue
                self._add_attachment_chip(fpath)
            except Exception as e:
                logging.getLogger("tardis").warning("Error al adjuntar %s: %s", fpath, e)

    def _add_attachment_chip(self, fpath: str) -> None:
        """Agrega un chip visual para un archivo adjunto."""
        self._attachment_paths.append(fpath)
        path_obj = Path(fpath)
        fsize = path_obj.stat().st_size
        fsize_str = _human_readable_size(fsize)

        chip = QWidget()
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(4, 2, 4, 2)
        chip_layout.setSpacing(8)

        name_label = QLabel(f"{path_obj.name} ({fsize_str})")
        name_label.setStyleSheet("color: #1a1a18; font-size: 12px;")
        chip_layout.addWidget(name_label)
        chip_layout.addStretch()

        btn_remove = QPushButton("×")
        btn_remove.setFixedSize(20, 20)
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.setStyleSheet("""
            QPushButton {
                background: transparent; color: #5a5a56;
                border: none; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { color: #e9290c; }
        """)
        btn_remove.clicked.connect(lambda checked, p=fpath: self._remove_attachment(p))
        chip_layout.addWidget(btn_remove)

        self._attachments_layout.addWidget(chip)
        self._attachments_container.setVisible(True)

    def _remove_attachment(self, fpath: str) -> None:
        """Remueve un archivo adjunto de la lista."""
        if fpath in self._attachment_paths:
            self._attachment_paths.remove(fpath)

        # Remover el chip visual: buscar el widget cuyo label contiene el nombre
        for i in range(self._attachments_layout.count()):
            w = self._attachments_layout.itemAt(i).widget()
            if w:
                labels = w.findChildren(QLabel)
                for lbl in labels:
                    if Path(fpath).name in lbl.text():
                        w.setParent(None)
                        w.deleteLater()
                        break

        if not self._attachment_paths:
            self._attachments_container.setVisible(False)

    # ── Envío ──────────────────────────────────────────────────────────

    def _on_send_clicked(self) -> None:
        """Valida y envía el correo."""
        try:
            from_val = self.from_combo.currentText().strip()
            to_val = self.to_input.text().strip()
            cc_val = self.cc_input.text().strip()
            subject_val = self.subject_input.text().strip()
            body_val = self.body_input.toPlainText()
            priority_val = self.priority_combo.currentText()

            to_users = [s.strip() for s in to_val.split(";") if s.strip()]
            cc_users = [s.strip() for s in cc_val.split(";") if s.strip()] if cc_val else None

            if not from_val:
                self.error_label.setText("La casilla remitente no puede estar vacía.")
                self.error_label.setVisible(True)
                return
            if not to_users:
                self.error_label.setText("El destinatario no puede estar vacío.")
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
                reply_to_uuid=self._reply_to_uuid,
                thread_uuid_override=self._thread_uuid_override,
                attachments=self._attachment_paths if self._attachment_paths else None,
                on_success=self._on_sent,
                on_error=self._on_error,
            )
        except Exception:
            logging.getLogger("tardis").exception("Error en ComposerView._on_send_clicked")

    def _on_sent(self, result) -> None:
        """Callback tras el envío."""
        try:
            self.btn_send.setEnabled(True)
            self.btn_send.setText("Enviar")

            if not result.success:
                err = "; ".join(result.errors) if result.errors else "Error al enviar."
                self.error_label.setText(err)
                self.error_label.setVisible(True)
                return

            # Mostrar advertencias de adjuntos si las hay
            att_errors = result.meta.get("attachment_errors", [])
            if att_errors:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(
                        f"Correo enviado, pero {len(att_errors)} adjunto(s) fallaron",
                        "warning",
                    )

            self.error_label.setVisible(False)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification("Correo enviado correctamente", "success")
            self._sent_successfully = True

            # Cerrar y refrescar
            self.close()
            parent = self.parent()
            while parent:
                if parent.__class__.__name__ == "FloatingWindow":
                    parent.close()
                    break
                parent = parent.parent()

            # Refrescar lista
            sv = getattr(self.main_window, "sidebar_view", None)
            if sv:
                item = sv.currentItem()
                if item:
                    node = item.data(0, Qt.UserRole + 1)
                    if node and node.folder in ("sent", "inbox"):
                        ev = getattr(self.main_window, "email_list_view", None)
                        if ev:
                            ev.load(self.client, node.mailboxes, node.folder)
        except Exception:
            logging.getLogger("tardis").exception("Error en ComposerView._on_sent")

    def _on_error(self, exc: Exception) -> None:
        """Maneja errores del envío asíncrono."""
        try:
            self.btn_send.setEnabled(True)
            self.btn_send.setText("Enviar")
            err = f"Error inesperado: {exc}"
            self.error_label.setText(err)
            self.error_label.setVisible(True)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err, "error")
        except Exception:
            logging.getLogger("tardis").exception("Error en ComposerView._on_error")

    def closeEvent(self, event) -> None:
        """Pregunta antes de descartar un borrador no enviado."""
        try:
            to_val = self.to_input.text().strip()
            subject_val = self.subject_input.text().strip()
            body_val = self.body_input.toPlainText().strip()

            if not self._sent_successfully and (to_val or subject_val or body_val):
                reply = QMessageBox.question(
                    self,
                    "Descartar borrador",
                    "Tienes contenido sin enviar. ¿Descartar este correo?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return

            settings = QSettings("Tardis", "Tardis")
            settings.setValue("floating/Compose/geometry", self.saveGeometry())
            event.accept()
        except Exception:
            logging.getLogger("tardis").exception("Error en ComposerView.closeEvent")
            event.accept()
