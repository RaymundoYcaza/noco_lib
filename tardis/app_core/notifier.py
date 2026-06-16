"""Notificador de bandeja de entrada para Tardis.

Monitorea las casillas configuradas en busca de nuevos correos no leídos
y muestra notificaciones (toast, sonido, destello de barra de tareas).
"""

import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Signal, QUrl, QSettings
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication

from app_core.concurrency import run_async
from modules.localmail import service

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient
    from app_core.config import TardisConfig

logger = logging.getLogger("tardis")


class InboxNotifier(QObject):
    """Monitorea la bandeja de entrada y emite señales cuando llegan nuevos correos.

    Parameters
    ----------
    client : NocoClient
        Cliente NocoDB para consultar la bandeja.
    config : TardisConfig
        Configuración de Tardis.
    main_window : MainWindow
        Ventana principal para mostrar notificaciones.
    parent : QObject | None
        Objeto padre Qt.
    """

    new_emails_arrived = Signal(int)  # Emite la cantidad de correos nuevos

    def __init__(
        self,
        client: "NocoClient",
        config: "TardisConfig",
        main_window: "MainWindow",
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._client = client
        self._config = config
        self._main_window = main_window
        self._last_count: int = 0

        # Timer de sondeo
        self._timer = QTimer(self)
        interval_ms = config.poll_interval_seconds * 1000
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

        # Sonido de notificación
        self._sound = QSoundEffect(self)
        sound_path = Path(__file__).resolve().parent.parent / "shared" / "sounds" / "notify.wav"
        if sound_path.exists():
            self._sound.setSource(QUrl.fromLocalFile(str(sound_path.resolve())))
            self._sound.setVolume(0.7)
        else:
            logger.warning("Archivo de sonido no encontrado: %s", sound_path)

        # Preferencia de sonido desde QSettings
        settings = QSettings("Tardis", "Tardis")
        self._sound_enabled = settings.value("notifications/sound_enabled", True, type=bool)

        # Conectar señal externamente (se espera que main.py haga la conexión)
        # self.new_emails_arrived.connect(self.notify)

    def start(self) -> None:
        """Inicia el sondeo periódico de la bandeja de entrada."""
        self._timer.start()
        # Primer sondeo después de 2 segundos (dar tiempo a que la app se inicialice)
        QTimer.singleShot(2000, self._poll)
        logger.info(
            "Notificador iniciado (intervalo: %ds, sonido: %s)",
            self._config.poll_interval_seconds,
            "sí" if self._sound_enabled else "no",
        )

    def stop(self) -> None:
        """Detiene el sondeo periódico."""
        self._timer.stop()
        logger.info("Notificador detenido.")

    def set_sound_enabled(self, enabled: bool) -> None:
        """Activa o desactiva el sonido de notificación.

        Parameters
        ----------
        enabled : bool
            True para activar el sonido, False para desactivarlo.
        """
        self._sound_enabled = enabled
        settings = QSettings("Tardis", "Tardis")
        settings.setValue("notifications/sound_enabled", enabled)
        logger.info("Sonido de notificación: %s", "activado" if enabled else "desactivado")

    # ── Internos ──────────────────────────────────────────────────────

    def _poll(self) -> None:
        """Ejecuta una consulta de correos no leídos."""
        if not self._config.mailboxes:
            logger.debug("Sondeo omitido: no hay casillas configuradas.")
            return

        logger.debug("Sondeando bandeja de entrada...")

        def on_success(result):
            current_count = result.affected_count if result.success else 0
            logger.debug(
                "Sondeo completado: %d no leídos (anterior: %d)",
                current_count,
                self._last_count,
            )
            if current_count > self._last_count:
                new_count = current_count - self._last_count
                logger.info("Nuevos correos detectados: %d", new_count)
                self.new_emails_arrived.emit(new_count)
            self._last_count = current_count

        def on_error(exc):
            logger.warning("Error en sondeo de bandeja: %s", exc)

        run_async(
            service.list_inbox,
            self._client,
            self._config.mailboxes,
            folder="inbox",
            only_unread=True,
            on_success=on_success,
            on_error=on_error,
        )

    def notify(self, new_count: int) -> None:
        """Maneja la llegada de nuevos correos: sonido, destello y toast.

        Este método se conecta a ``new_emails_arrived`` desde ``main.py``.
        
        Parameters
        ----------
        new_count : int
            Cantidad de correos nuevos detectados.
        """
        # Sonido
        if self._sound_enabled and self._sound.isLoaded():
            self._sound.play()

        # Destello en barra de tareas si la ventana no está enfocada
        if not self._main_window.isActiveWindow():
            QApplication.alert(self._main_window, 0)

        # Toast de notificación
        self._main_window.show_notification(
            f"📬 {new_count} mensaje(s) nuevo(s)",
            level="info",
            duration_ms=6000,
            action_label="Ver bandeja",
            action_callback=self._go_to_inbox,
        )

    def _go_to_inbox(self) -> None:
        """Navega a la bandeja de entrada de LocalMail."""
        try:
            # Activar módulo LocalMail
            self._main_window._activate_module("localmail")

            # Seleccionar nodo "All Mailboxes > Inbox"
            sv = getattr(self._main_window, "sidebar_view", None)
            if sv:
                sv.select_node_by_id("all:inbox")
        except Exception as e:
            logger.exception("Error al navegar a la bandeja de entrada: %s", e)
