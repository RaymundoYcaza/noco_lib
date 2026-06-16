from typing import Callable
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Slot, QEvent
import logging


class Toast(QWidget):
    """Notificación tipo Toast con soporte opcional de botón de acción.

    Parámetros
    ----------
    parent : QWidget
        Widget padre (normalmente MainWindow).
    text : str
        Texto del mensaje.
    level : str
        Nivel: "info", "success", "warning", "error".
    duration_ms : int
        Duración en milisegundos antes de cerrarse.
    action_label : str | None
        Texto del botón de acción (None = sin botón).
    action_callback : Callable | None
        Función a ejecutar al hacer clic en el botón de acción.
    """

    _active_toasts = []

    def __init__(
        self,
        parent: QWidget,
        text: str,
        level: str = "info",
        duration_ms: int = 4000,
        action_label: str | None = None,
        action_callback: Callable | None = None,
    ):
        super().__init__(parent)
        self.text = text
        self.level = level.lower()
        self.duration_ms = duration_ms
        self._action_label = action_label
        self._action_callback = action_callback

        self.init_ui()
        self.adjust_size_and_position()

        Toast._active_toasts.append(self)
        Toast.reposition_all()

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.show()
        self.raise_()
        self.fade_in()

        QTimer.singleShot(self.duration_ms, self.fade_out)

        if parent:
            parent.installEventFilter(self)

    def init_ui(self):
        self.setObjectName("ToastWidget")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Texto
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.label, stretch=1)

        # Botón de acción (opcional)
        self._action_btn: QPushButton | None = None
        if self._action_label and self._action_callback:
            self._action_btn = QPushButton(self._action_label)
            self._action_btn.setCursor(Qt.PointingHandCursor)
            self._action_btn.setStyleSheet("""
                QPushButton {
                    color: #ffffff; background: transparent;
                    border: none; font-weight: bold; font-size: 12px;
                    text-decoration: underline; padding: 4px 8px;
                }
                QPushButton:hover {
                    background: rgba(255,255,255,0.15);
                    border-radius: 3px;
                }
            """)
            self._action_btn.clicked.connect(self._on_action_clicked)
            layout.addWidget(self._action_btn)

        # Colores según nivel
        bg_colors = {
            "info": "rgba(21, 101, 192, 0.95)",     # Azul info
            "success": "rgba(46, 125, 50, 0.95)",   # Verde éxito
            "warning": "rgba(245, 124, 0, 0.95)",   # Naranja advertencia
            "error": "rgba(198, 40, 40, 0.95)",     # Rojo error
        }
        border_colors = {
            "info": "#1565c0",
            "success": "#2e7d32",
            "warning": "#f57c00",
            "error": "#c62828",
        }
        bg = bg_colors.get(self.level, bg_colors["info"])
        border = border_colors.get(self.level, border_colors["info"])

        self.setStyleSheet(f"""
            QWidget#ToastWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
        """)

    def _on_action_clicked(self) -> None:
        """Ejecuta el callback de acción y cierra el toast."""
        try:
            if self._action_callback:
                self._action_callback()
        except Exception as e:
            logging.getLogger("tardis").exception("Error en callback de acción del toast: %s", e)
        finally:
            self.close_and_remove()

    def mousePressEvent(self, event):
        """Cierra el toast al hacer clic en cualquier parte del cuerpo.

        Nota: Los clics en el botón de acción son manejados por el propio
        botón (QPushButton.clicked), no por este evento.
        """
        self.close_and_remove()
        super().mousePressEvent(event)

    def adjust_size_and_position(self):
        self.setMaximumWidth(350)
        self.setMinimumWidth(200)
        self.adjustSize()

    @classmethod
    def reposition_all(cls):
        for i, toast in enumerate(cls._active_toasts):
            parent = toast.parentWidget()
            if not parent:
                continue
            parent_w = parent.width()
            parent_h = parent.height()
            y_offset = 16
            for prev_toast in cls._active_toasts[:i]:
                y_offset += prev_toast.height() + 8
            x = parent_w - 16 - toast.width()
            y = parent_h - 16 - toast.height() - (y_offset - 16)
            toast.move(x, y)

    def fade_in(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    @Slot()
    def fade_out(self):
        try:
            self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.anim.setDuration(250)
            self.anim.setStartValue(1.0)
            self.anim.setEndValue(0.0)
            self.anim.setEasingCurve(QEasingCurve.InCubic)
            self.anim.finished.connect(self.close_and_remove)
            self.anim.start()
        except Exception:
            self.close_and_remove()

    def close_and_remove(self):
        try:
            self.close()
            if self in Toast._active_toasts:
                Toast._active_toasts.remove(self)
            Toast.reposition_all()
            self.deleteLater()
        except Exception:
            logging.getLogger("tardis").exception("Error en Toast.close_and_remove")

    def closeEvent(self, event):
        try:
            if self in Toast._active_toasts:
                Toast._active_toasts.remove(self)
            Toast.reposition_all()
        except Exception:
            pass
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        try:
            if watched == self.parentWidget() and event.type() == QEvent.Resize:
                Toast.reposition_all()
        except Exception:
            pass
        return super().eventFilter(watched, event)
