"""Splash screen shown during Tardis application startup.

Muestra el logo de Inorizonti y el texto "LocalMail" mientras se
inicializan los componentes de la aplicación (config, cliente NocoDB,
descubrimiento de módulos, etc.).

Uso en main.py::

    from app_core.splash import SplashScreen

    app = QApplication(sys.argv)
    splash = SplashScreen(logo_svg_path)
    splash.show()
    app.processEvents()

    # ... inicialización ...

    splash.close()
    window.show()
"""

from pathlib import Path

from PySide6.QtWidgets import QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtSvg import QSvgRenderer


class SplashScreen(QSplashScreen):
    """Pantalla de inicio con el logo de Inorizonti y el texto 'LocalMail'.

    Parameters
    ----------
    logo_svg : str | Path
        Ruta al archivo SVG del logotipo de Inorizonti.
    width : int
        Ancho en píxeles de la ventana de splash (default 480).
    height : int
        Alto en píxeles de la ventana de splash (default 340).
    """

    # Colores del tema Inorizonti
    _COLOR_ACCENT = "#e9290c"
    _COLOR_TEXT_PRIMARY = "#1a1a18"
    _COLOR_TEXT_SECONDARY = "#5a5a56"
    _COLOR_BG = "#ffffff"

    def __init__(
        self,
        logo_svg: str | Path,
        width: int = 480,
        height: int = 340,
    ) -> None:
        self._logo_svg = str(logo_svg)
        self._w = width
        self._h = height

        pixmap = QPixmap(self._w, self._h)
        pixmap.fill(Qt.white)
        super().__init__(pixmap)

        self._render_pixmap()

    def _render_pixmap(self) -> None:
        """Pinta el contenido completo del splash sobre un QPixmap."""
        pixmap = QPixmap(self._w, self._h)
        pixmap.fill(Qt.white)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # ── Barra de acento en la parte inferior ──────────────────
        painter.setBrush(QColor(self._COLOR_ACCENT))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, self._h - 4, self._w, 4)

        # ── Logo SVG (proporcional, viewBox 1440×810 ≈ 16:9) ─────
        renderer = QSvgRenderer(self._logo_svg)
        logo_h = 160
        logo_w = int(logo_h * 1440 / 810)  # ≈ 284px manteniendo 16:9
        logo_x = (self._w - logo_w) // 2
        renderer.render(painter, QRectF(logo_x, 30, logo_w, logo_h))

        # ── Título "LocalMail" ───────────────────────────────────
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor(self._COLOR_TEXT_PRIMARY))
        painter.drawText(
            QRect(0, 200, self._w, 56),
            Qt.AlignCenter,
            "LocalMail",
        )

        # ── Subtítulo ────────────────────────────────────────────
        sub_font = QFont("Segoe UI", 13)
        painter.setFont(sub_font)
        painter.setPen(QColor(self._COLOR_TEXT_SECONDARY))
        painter.drawText(
            QRect(0, 256, self._w, 28),
            Qt.AlignCenter,
            "Cliente de correo corporativo",
        )

        painter.end()
        self.setPixmap(pixmap)

    def showEvent(self, event) -> None:
        """Centra el splash en la pantalla al mostrarse."""
        super().showEvent(event)
        screen = self.screen()
        if screen:
            screen_rect = screen.availableGeometry()
            x = (screen_rect.width() - self._w) // 2
            y = (screen_rect.height() - self._h) // 2
            self.move(x, y)
