"""Visor de correo electrónico con barra de acciones y sección de adjuntos.

Incluye botones para: Responder, Reenviar, Archivar, Eliminar, Restaurar
y Más (menú con \"Ver encabezados técnicos\").
"""

import sys
import os
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QFrame,
    QTextBrowser, QLabel, QPushButton, QMenu, QDialog,
    QPlainTextEdit, QFileDialog, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont
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
from noco_lib.noco_core.result import NocoResult
from shared.utils import human_readable_size as _human_readable_size


class ReaderView(QWidget):
    """Panel de lectura de correos con barra de acciones y soporte de adjuntos."""

    email_read = Signal(int)  # Emite el ID del correo cuando se marca como leído

    def __init__(self, main_window, client: NocoClient, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self._current_email_id: int | None = None
        self._current_email: dict | None = None
        self._init_ui()

    # ── Helper para crear botones de acción ────────────────────────────

    def _make_action_btn(self, icon_name: str, label: str) -> QPushButton:
        """Crea un botón de acción compacto con icono qtawesome + texto."""
        btn = QPushButton()
        h_layout = QHBoxLayout(btn)
        h_layout.setContentsMargins(8, 2, 8, 2)
        h_layout.setSpacing(4)
        icon_label = QLabel()
        try:
            icon_label.setPixmap(qta.icon(icon_name, color="#5a5a56").pixmap(16, 16))
        except Exception:
            pass
        icon_label.setFixedSize(16, 16)
        text_label = QLabel(label)
        text_label.setStyleSheet("color: #1a1a18; font-size: 12px; font-weight: 600;")
        h_layout.addWidget(icon_label)
        h_layout.addWidget(text_label)
        h_layout.addStretch()
        btn.setFixedHeight(28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background: #ede9e4;
            }
            QPushButton:disabled {
                opacity: 0.4;
            }
        """)
        return btn

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Barra de acciones (siempre visible arriba) ──────────────
        self._action_bar = QWidget()
        self._action_bar.setObjectName("readerActionBar")
        self._action_bar.setStyleSheet("""
            QWidget#readerActionBar {
                background: #f5f3f0;
                border-bottom: 1px solid #dddad6;
            }
        """)
        action_layout = QHBoxLayout(self._action_bar)
        action_layout.setContentsMargins(8, 4, 8, 4)
        action_layout.setSpacing(4)

        self._btn_reply = self._make_action_btn("fa5s.reply", "Responder")
        self._btn_forward = self._make_action_btn("fa5s.share", "Reenviar")
        self._btn_archive = self._make_action_btn("fa5s.archive", "Archivar")
        self._btn_trash = self._make_action_btn("fa5s.trash", "Eliminar")
        self._btn_restore = self._make_action_btn("fa5s.undo-alt", "Restaurar")
        self._btn_more = self._make_action_btn("fa5s.ellipsis-h", "Más")

        # Menú "Más"
        self._more_menu = QMenu(self)
        self._more_menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                color: #1a1a18;
                border: 1px solid #dddad6;
            }
            QMenu::item:selected {
                background: #ede9e4;
            }
        """)
        self._action_ver_headers = self._more_menu.addAction("Ver encabezados técnicos")
        self._action_ver_headers.triggered.connect(self._on_show_technical_headers)
        self._btn_more.setMenu(self._more_menu)

        action_layout.addWidget(self._btn_reply)
        action_layout.addWidget(self._btn_forward)
        action_layout.addWidget(self._btn_archive)
        action_layout.addWidget(self._btn_trash)
        action_layout.addWidget(self._btn_restore)
        action_layout.addWidget(self._btn_more)
        action_layout.addStretch()

        layout.addWidget(self._action_bar)

        # ── Contenido del lector (scrollable) ──────────────────────
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        # 1. Cabecera (header block)
        self.header_widget = QWidget()
        header_inner = QVBoxLayout(self.header_widget)
        header_inner.setContentsMargins(0, 0, 0, 0)
        header_inner.setSpacing(8)

        self.lbl_subject = QLabel()
        self.lbl_subject.setWordWrap(True)
        self.lbl_subject.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a1a18; padding-bottom: 4px;")
        header_inner.addWidget(self.lbl_subject)

        self.meta_layout = QFormLayout()
        self.meta_layout.setContentsMargins(0, 0, 0, 0)
        self.meta_layout.setSpacing(6)
        self.meta_layout.setLabelAlignment(Qt.AlignRight)

        lbl_style = "color: #5a5a56; font-weight: bold; font-size: 13px;"
        val_style = "color: #1a1a18; font-size: 13px;"

        self.lbl_from_hdr = QLabel("De:")
        self.lbl_from_hdr.setStyleSheet(lbl_style)
        self.lbl_from = QLabel()
        self.lbl_from.setStyleSheet(val_style)
        self.meta_layout.addRow(self.lbl_from_hdr, self.lbl_from)

        self.lbl_to_hdr = QLabel("Para:")
        self.lbl_to_hdr.setStyleSheet(lbl_style)
        self.lbl_to = QLabel()
        self.lbl_to.setStyleSheet(val_style)
        self.meta_layout.addRow(self.lbl_to_hdr, self.lbl_to)

        self.lbl_cc_hdr = QLabel("CC:")
        self.lbl_cc_hdr.setStyleSheet(lbl_style)
        self.lbl_cc = QLabel()
        self.lbl_cc.setStyleSheet(val_style)
        self.meta_layout.addRow(self.lbl_cc_hdr, self.lbl_cc)

        self.lbl_date_hdr = QLabel("Fecha:")
        self.lbl_date_hdr.setStyleSheet(lbl_style)
        self.lbl_date = QLabel()
        self.lbl_date.setStyleSheet(val_style)
        self.meta_layout.addRow(self.lbl_date_hdr, self.lbl_date)

        self.lbl_prio_hdr = QLabel("Prioridad:")
        self.lbl_prio_hdr.setStyleSheet(lbl_style)
        self.prio_container = QWidget()
        prio_row = QHBoxLayout(self.prio_container)
        prio_row.setContentsMargins(0, 0, 0, 0)
        prio_row.setSpacing(6)
        self.lbl_prio_icon = QLabel()
        self.lbl_prio_text = QLabel()
        self.lbl_prio_text.setStyleSheet(val_style)
        prio_row.addWidget(self.lbl_prio_icon)
        prio_row.addWidget(self.lbl_prio_text)
        prio_row.addStretch()
        self.meta_layout.addRow(self.lbl_prio_hdr, self.prio_container)

        header_inner.addLayout(self.meta_layout)
        content_layout.addWidget(self.header_widget)

        # 2. Separador
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setStyleSheet("background: #dddad6; max-height: 1px; border: none; margin: 4px 0;")
        content_layout.addWidget(self.separator)

        # 3. Cuerpo del mensaje
        self.browser = QTextBrowser()
        self.browser.setStyleSheet("""
            QTextBrowser {
                background: #ffffff;
                color: #1a1a18;
                border: 1px solid #dddad6;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        content_layout.addWidget(self.browser, stretch=1)

        # 4. Sección de adjuntos (oculta inicialmente)
        self._attachments_section = QWidget()
        self._attachments_section.setVisible(False)
        att_layout = QVBoxLayout(self._attachments_section)
        att_layout.setContentsMargins(0, 4, 0, 0)
        att_layout.setSpacing(4)

        self._attachments_header = QLabel()
        self._attachments_header.setStyleSheet("font-weight: bold; color: #1a1a18; font-size: 13px;")
        att_layout.addWidget(self._attachments_header)

        self._attachments_list = QWidget()
        self._attachments_list_layout = QVBoxLayout(self._attachments_list)
        self._attachments_list_layout.setContentsMargins(0, 0, 0, 0)
        self._attachments_list_layout.setSpacing(4)
        att_layout.addWidget(self._attachments_list)

        content_layout.addWidget(self._attachments_section)

        layout.addWidget(self._content, stretch=1)

        # ── Estado inicial ──────────────────────────────────────────
        self.header_widget.setVisible(False)
        self.separator.setVisible(False)
        self._attachments_section.setVisible(False)
        self.browser.setPlainText("Selecciona un correo para leerlo.")
        self._update_action_bar_state(None)

        # ── Señales ─────────────────────────────────────────────────
        self._btn_reply.clicked.connect(self._on_reply)
        self._btn_forward.clicked.connect(self._on_forward)
        self._btn_archive.clicked.connect(self._on_archive_clicked)
        self._btn_trash.clicked.connect(self._on_trash_clicked)
        self._btn_restore.clicked.connect(self._on_restore_clicked)

    # ── Gestión de estado de la barra de acciones ─────────────────────

    def _update_action_bar_state(self, email: dict | None) -> None:
        """Habilita/deshabilita botones según si hay un correo cargado y su carpeta."""
        self._btn_reply.setEnabled(email is not None)
        self._btn_forward.setEnabled(email is not None)
        self._btn_archive.setEnabled(email is not None)
        self._btn_trash.setEnabled(email is not None)
        self._btn_more.setEnabled(email is not None)

        # Restaurar visible solo si la carpeta es archive o trash
        if email and email.get("folder") in ("archive", "trash"):
            self._btn_restore.setVisible(True)
            self._btn_restore.setEnabled(True)
        else:
            self._btn_restore.setVisible(False)

    # ── Métodos públicos ──────────────────────────────────────────────

    def show_email(self, email_id: int) -> None:
        """Carga y muestra un correo por su ID de forma asíncrona."""
        try:
            if not isinstance(email_id, int) or email_id <= 0:
                self._current_email_id = None
                self._current_email = None
                self.header_widget.setVisible(False)
                self.separator.setVisible(False)
                self._attachments_section.setVisible(False)
                self.browser.setPlainText("ID de correo inválido.")
                self._update_action_bar_state(None)
                return

            self._current_email_id = email_id
            self._update_action_bar_state(None)
            self.header_widget.setVisible(False)
            self.separator.setVisible(False)
            self._attachments_section.setVisible(False)
            self.browser.setPlainText("Cargando correo...")

            run_async(
                service.get_email,
                self.client,
                email_id,
                on_success=self._render,
                on_error=self._on_error,
            )
        except Exception:
            logging.getLogger("tardis").exception("Error en ReaderView.show_email")

    def _render(self, result) -> None:
        """Renderiza el correo cargado en la UI."""
        try:
            if not result.success:
                self._current_email_id = None
                self._current_email = None
                self._update_action_bar_state(None)
                err = result.errors[0] if result.errors else "Error al cargar el correo."
                self.browser.setPlainText(f"Error: {err}")
                self.header_widget.setVisible(False)
                self.separator.setVisible(False)
                self._attachments_section.setVisible(False)
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err, "error")
                return

            email = result.data
            if not email:
                self._current_email_id = None
                self._current_email = None
                self._update_action_bar_state(None)
                self.browser.setPlainText("Correo no encontrado.")
                self.header_widget.setVisible(False)
                self.separator.setVisible(False)
                self._attachments_section.setVisible(False)
                return

            self._current_email = email
            email_id = email.get("Id")

            # Extraer campos
            from_user = email.get("from", "")
            to_user = email.get("to", "")
            cc = email.get("cc", "")
            created_at = email.get("CreatedAt", "")
            title = email.get("title", "")
            body = email.get("body", "")
            priority = email.get("priority", "Media")
            attachments = email.get("Attachment")

            # Formatear fecha
            formatted_date = created_at
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            # Rellenar widgets
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

            # Prioridad
            prio_colors = {"Alta": "#e9290c", "Media": "#f57c00", "Baja": "#2e7d32"}
            color_hex = prio_colors.get(priority, "#f57c00")
            try:
                icon_pix = qta.icon("fa5s.circle", color=color_hex).pixmap(12, 12)
                self.lbl_prio_icon.setPixmap(icon_pix)
            except Exception:
                self.lbl_prio_icon.setText("●")
                self.lbl_prio_icon.setStyleSheet(f"color: {color_hex}; font-size: 14px;")
            self.lbl_prio_text.setText(priority)

            # Mostrar cabecera y cuerpo
            self.header_widget.setVisible(True)
            self.separator.setVisible(True)
            self.browser.setPlainText(body)
            self._update_action_bar_state(email)

            # Sección de adjuntos
            self._render_attachments(attachments)

            # Marcar como leído (fire-and-forget)
            if email_id:
                run_async(
                    service.mark_as_read,
                    self.client,
                    email_id,
                    on_success=lambda r, eid=email_id: self._on_mark_as_read_success(eid, r),
                    on_error=lambda e: logging.getLogger("tardis").warning(
                        "Error al marcar como leído: %s", str(e)
                    ),
                )
        except Exception:
            logging.getLogger("tardis").exception("Error en ReaderView._render")

    def _render_attachments(self, attachments) -> None:
        """Renderiza la sección de adjuntos si hay archivos adjuntos."""
        # Limpiar adjuntos anteriores
        for i in reversed(range(self._attachments_list_layout.count())):
            w = self._attachments_list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if not attachments:
            self._attachments_section.setVisible(False)
            return

        # Parsear adjuntos: NocoDB puede devolverlos como:
        # - lista de dicts
        # - lista de strings JSON
        # - string JSON directamente en el campo Attachment
        parsed = []
        if isinstance(attachments, list):
            for item in attachments:
                if isinstance(item, dict):
                    parsed.append(item)
                elif isinstance(item, str):
                    try:
                        parsed_item = json.loads(item)
                        if isinstance(parsed_item, dict):
                            parsed.append(parsed_item)
                        elif isinstance(parsed_item, list):
                            parsed.extend(parsed_item)
                    except (json.JSONDecodeError, ValueError):
                        logging.getLogger("tardis").warning(
                            "No se pudo parsear adjunto: %s", item[:80]
                        )
                        continue
        elif isinstance(attachments, str):
            try:
                parsed_data = json.loads(attachments)
                if isinstance(parsed_data, list):
                    parsed = parsed_data
                elif isinstance(parsed_data, dict):
                    parsed = [parsed_data]
            except (json.JSONDecodeError, ValueError):
                logging.getLogger("tardis").warning(
                    "No se pudo parsear campo Attachment (string): %s", attachments[:80]
                )

        if not parsed:
            self._attachments_section.setVisible(False)
            return

        self._attachments_header.setText(f"📎 Adjuntos ({len(parsed)})")
        self._attachments_section.setVisible(True)

        for att in parsed:
            title = att.get("title", "Archivo")
            size = att.get("size", 0)
            url = (att.get("signedUrl") or att.get("signedPath") or att.get("url") or att.get("path", ""))

            # Fila con borde visible, hover y cursor pointer
            row = QWidget()
            row.setObjectName("attachmentRow")
            row.setCursor(Qt.PointingHandCursor)
            row.setStyleSheet("""
                QWidget#attachmentRow {
                    background: #ffffff;
                    border: 1px solid #dddad6;
                    border-radius: 4px;
                }
                QWidget#attachmentRow:hover {
                    background: #f5f3f0;
                    border-color: #e9290c;
                }
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(8)

            if url:
                # Nombre del archivo como enlace clicable
                btn_filename = QPushButton(f"{title}  ·  {_human_readable_size(size)}")
                btn_filename.setFlat(True)
                btn_filename.setCursor(Qt.PointingHandCursor)
                btn_filename.setStyleSheet("""
                    QPushButton {
                        color: #e9290c; background: transparent;
                        border: none; text-align: left;
                        padding: 2px 0; font-size: 12px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        color: #c5220a;
                    }
                """)
                full_url = url
                btn_filename.clicked.connect(
                    lambda checked, u=full_url: self._on_open_attachment(u)
                )
                row_layout.addWidget(btn_filename)
                row_layout.addStretch()

                # Botón Abrir (acento rojo)
                btn_abrir = QPushButton("Abrir")
                btn_abrir.setFixedHeight(26)
                btn_abrir.setCursor(Qt.PointingHandCursor)
                btn_abrir.setStyleSheet("""
                    QPushButton {
                        background: #e9290c; color: #ffffff;
                        border: none; border-radius: 4px;
                        padding: 2px 14px; font-size: 12px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background: #c5220a;
                    }
                """)
                btn_abrir.clicked.connect(
                    lambda checked, u=full_url: self._on_open_attachment(u)
                )
                row_layout.addWidget(btn_abrir)

                # Botón Descargar
                btn_descargar = QPushButton("Descargar")
                btn_descargar.setFixedHeight(26)
                btn_descargar.setCursor(Qt.PointingHandCursor)
                btn_descargar.setStyleSheet("""
                    QPushButton {
                        background: #f5f3f0; color: #1a1a18;
                        border: 1px solid #dddad6; border-radius: 4px;
                        padding: 2px 10px; font-size: 12px;
                    }
                    QPushButton:hover {
                        background: #ede9e4;
                        border-color: #e9290c;
                        color: #e9290c;
                    }
                """)
                btn_descargar.clicked.connect(
                    lambda checked, u=full_url, t=title: self._on_download_attachment(u, t)
                )
                row_layout.addWidget(btn_descargar)
            else:
                # Sin URL: cursor normal, solo texto informativo
                row.setCursor(Qt.ArrowCursor)
                info_lbl = QLabel(f"{title}  ·  {_human_readable_size(size)}")
                info_lbl.setStyleSheet("color: #5a5a56; font-size: 12px; border: none;")
                row_layout.addWidget(info_lbl)
                row_layout.addStretch()

            self._attachments_list_layout.addWidget(row)

    # ── Utilidades para adjuntos ──────────────────────────────────────

    def _resolve_attachment_url(self, url: str) -> str:
        """Convierte una URL relativa de NocoDB a absoluta.

        NocoDB devuelve rutas como ``download/d1/storage/...``
        que deben prefijarse con ``base_url``.
        """
        if url.startswith("http://") or url.startswith("https://"):
            return url
        base = self.client.base_url.rstrip("/")
        if url.startswith("/"):
            return f"{base}{url}"
        return f"{base}/{url}"

    def _download_attachment_file_sync(self, url: str, save_path: str) -> NocoResult:
        """Descarga un adjunto de forma síncrona usando la sesión autenticada.

        Crea su propia sesión para evitar problemas de concurrencia con
        la sesión principal del cliente.
        """
        import requests as req_lib
        try:
            full_url = self._resolve_attachment_url(url)
            logging.getLogger("tardis").info(
                "Descargando adjunto desde: %s", full_url
            )

            # Crear sesión propia con el token de autenticación
            download_session = req_lib.Session()
            download_session.headers.update({
                "xc-token": self.client.token,
            })
            resp = download_session.get(full_url, stream=True, timeout=60)
            resp.raise_for_status()

            total_bytes = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)

            logging.getLogger("tardis").info(
                "Adjunto descargado: %s (%d bytes)", save_path, total_bytes
            )
            return NocoResult.ok(
                "read", data={"path": save_path}, affected_count=1
            )
        except Exception as exc:
            logging.getLogger("tardis").error(
                "Error al descargar adjunto desde %s: %s",
                url, exc
            )
            return NocoResult.fail("read", f"Error al descargar archivo: {exc}")

    def _on_open_attachment(self, url: str) -> None:
        """Descarga el adjunto a un archivo temporal y lo abre."""
        try:
            ext = Path(url.split("?")[0].split("#")[0]).suffix or ".tmp"

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp_path = tmp.name

            # Notificar inicio de descarga
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(
                    "Descargando adjunto…", "info", duration_ms=1500
                )

            def _on_done(result):
                if result.success:
                    logging.getLogger("tardis").info(
                        "Abriendo adjunto: %s", tmp_path
                    )
                    try:
                        if sys.platform == "win32":
                            os.startfile(tmp_path)
                        elif sys.platform == "darwin":
                            subprocess.Popen(["open", tmp_path])
                        else:
                            subprocess.Popen(["xdg-open", tmp_path])
                    except Exception as e:
                        if hasattr(self.main_window, "show_notification"):
                            self.main_window.show_notification(
                                f"No se pudo abrir el archivo: {e}", "error"
                            )
                else:
                    err = result.errors[0] if result.errors else "Error al descargar"
                    if hasattr(self.main_window, "show_notification"):
                        self.main_window.show_notification(err, "error")
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

            run_async(
                self._download_attachment_file_sync,
                url,
                tmp_path,
                on_success=_on_done,
                on_error=lambda e: (
                    self.main_window.show_notification(
                        f"Error al descargar: {e}", "error"
                    )
                    if hasattr(self.main_window, "show_notification")
                    else None
                ),
            )
        except Exception as exc:
            logging.getLogger("tardis").exception("Error en _on_open_attachment")
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(
                    f"Error al abrir: {exc}", "error"
                )

    def _on_download_attachment(self, url: str, default_name: str) -> None:
        """Descarga un adjunto a una ubicación elegida por el usuario."""
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar archivo", default_name, "Todos los archivos (*.*)"
        )
        if not save_path:
            return

        if hasattr(self.main_window, "show_notification"):
            self.main_window.show_notification(
                "Descargando…", "info", duration_ms=2000
            )

        def _on_done(result):
            if hasattr(self.main_window, "show_notification"):
                if result.success:
                    self.main_window.show_notification(
                        f"Archivo descargado: {Path(save_path).name}", "success"
                    )
                else:
                    err = result.errors[0] if result.errors else "Error al descargar"
                    self.main_window.show_notification(err, "error")

        run_async(
            self._download_attachment_file_sync,
            url,
            save_path,
            on_success=_on_done,
            on_error=lambda e: (
                self.main_window.show_notification(
                    f"Error al descargar: {e}", "error"
                )
                if hasattr(self.main_window, "show_notification")
                else None
            ),
        )

    def _on_show_technical_headers(self) -> None:
        """Muestra un diálogo con todos los campos del correo como JSON formateado."""
        if not self._current_email:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Encabezados técnicos")
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(json.dumps(self._current_email, indent=2, ensure_ascii=False))
        text_edit.setStyleSheet("""
            QPlainTextEdit {
                background: #ffffff; color: #1a1a18;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(text_edit)
        dialog.exec()

    def _on_mark_as_read_success(self, email_id: int, result) -> None:
        """Callback al marcar como leído."""
        try:
            if result.success:
                self.email_read.emit(email_id)
            else:
                err = result.errors[0] if result.errors else "Error desconocido"
                logging.getLogger("tardis").warning("Fallo al marcar como leído: %s", err)
        except Exception:
            logging.getLogger("tardis").exception("Error en _on_mark_as_read_success")

    def _on_error(self, exc: Exception) -> None:
        """Maneja errores de carga asíncrona."""
        try:
            self._current_email_id = None
            self._current_email = None
            self._update_action_bar_state(None)
            err = f"Error inesperado: {exc}"
            self.browser.setPlainText(err)
            self.header_widget.setVisible(False)
            self.separator.setVisible(False)
            self._attachments_section.setVisible(False)
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err, "error")
        except Exception:
            logging.getLogger("tardis").exception("Error en _on_error")

    # ── Acciones de la barra ──────────────────────────────────────────

    def _get_current_folder(self) -> str | None:
        """Obtiene la carpeta del correo actual desde el sidebar."""
        sv = getattr(self.main_window, "sidebar_view", None)
        if sv:
            item = sv.currentItem()
            if item:
                node = item.data(0, Qt.UserRole + 1)
                if node:
                    return node.folder
        return None

    def _get_current_mailboxes(self) -> list[str]:
        """Obtiene las casillas del nodo actual del sidebar."""
        sv = getattr(self.main_window, "sidebar_view", None)
        if sv:
            item = sv.currentItem()
            if item:
                node = item.data(0, Qt.UserRole + 1)
                if node:
                    return node.mailboxes
        return []

    def _on_reply(self) -> None:
        """Abre el compositor prellenado para responder al correo actual."""
        if not self._current_email:
            return
        from modules.localmail.views.composer_view import ComposerView
        composer = ComposerView.for_reply(
            self._current_email, self.client,
            getattr(self.main_window, "config", None),
            self.main_window
        )
        self.main_window.add_floating_window(composer, "Responder")

    def _on_forward(self) -> None:
        """Abre el compositor prellenado para reenviar el correo actual."""
        if not self._current_email:
            return
        from modules.localmail.views.composer_view import ComposerView
        composer = ComposerView.for_forward(
            self._current_email, self.client,
            getattr(self.main_window, "config", None),
            self.main_window
        )
        self.main_window.add_floating_window(composer, "Reenviar")

    def _on_archive_clicked(self) -> None:
        """Archiva el correo actual."""
        email_id = self._current_email_id
        if not email_id:
            return
        self._update_action_bar_state(None)
        run_async(
            service.archive_email,
            self.client,
            email_id,
            on_success=self._on_archive_success,
            on_error=self._on_action_error,
        )

    def _on_trash_clicked(self) -> None:
        """Mueve el correo actual a la papelera."""
        email_id = self._current_email_id
        if not email_id:
            return
        self._update_action_bar_state(None)
        run_async(
            service.move_to_trash,
            self.client,
            email_id,
            on_success=self._on_trash_success,
            on_error=self._on_action_error,
        )

    def _on_restore_clicked(self) -> None:
        """Restaura el correo actual a la bandeja de entrada."""
        email_id = self._current_email_id
        if not email_id:
            return
        mailboxes = self._get_current_mailboxes()
        if not mailboxes:
            return
        self._update_action_bar_state(None)
        run_async(
            service.restore_email,
            self.client,
            email_id,
            mailboxes[0],
            on_success=self._on_restore_success,
            on_error=self._on_action_error,
        )

    def _on_archive_success(self, result) -> None:
        """Callback tras archivar exitosamente."""
        try:
            if result.success:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification("Correo archivado", "success")
                self._clear_reader_and_refresh()
            else:
                err = result.errors[0] if result.errors else "Error al archivar"
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err, "error")
                self._update_action_bar_state(self._current_email)
        except Exception:
            logging.getLogger("tardis").exception("Error en _on_archive_success")

    def _on_trash_success(self, result) -> None:
        """Callback tras mover a la papelera exitosamente."""
        try:
            if result.success:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification("Correo movido a papelera", "success")
                self._clear_reader_and_refresh()
            else:
                err = result.errors[0] if result.errors else "Error al mover a papelera"
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err, "error")
                self._update_action_bar_state(self._current_email)
        except Exception:
            logging.getLogger("tardis").exception("Error en _on_trash_success")

    def _on_restore_success(self, result) -> None:
        """Callback tras restaurar exitosamente."""
        try:
            if result.success:
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(
                        "Correo restaurado a bandeja de entrada", "success"
                    )
                self._clear_reader_and_refresh()
            else:
                err = result.errors[0] if result.errors else "Error al restaurar"
                if hasattr(self.main_window, "show_notification"):
                    self.main_window.show_notification(err, "error")
                self._update_action_bar_state(self._current_email)
        except Exception:
            logging.getLogger("tardis").exception("Error en _on_restore_success")

    def _on_action_error(self, exc: Exception) -> None:
        """Maneja errores de las acciones de la barra."""
        try:
            err = f"Error: {exc}"
            if hasattr(self.main_window, "show_notification"):
                self.main_window.show_notification(err, "error")
            self._update_action_bar_state(self._current_email)
        except Exception:
            logging.getLogger("tardis").exception("Error en _on_action_error")

    def _clear_reader_and_refresh(self) -> None:
        """Limpia el lector y recarga la lista de correos."""
        self._current_email_id = None
        self._current_email = None
        self.header_widget.setVisible(False)
        self.separator.setVisible(False)
        self._attachments_section.setVisible(False)
        self.browser.setPlainText("Selecciona un correo para leerlo.")
        self._update_action_bar_state(None)

        folder = self._get_current_folder()
        mailboxes = self._get_current_mailboxes()
        ev = getattr(self.main_window, "email_list_view", None)
        if folder and mailboxes and ev:
            ev.load(self.client, mailboxes, folder)
