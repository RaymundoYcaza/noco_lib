import logging
from PySide6.QtWidgets import QApplication

from app_core.themes.theme_engine import apply_theme as _engine_apply_theme

logger = logging.getLogger(__name__)

def apply_theme(app: QApplication, theme: str = "inorizonti") -> None:
    """
    Aplica un tema a la aplicación Tardis.
    
    Delega en ``theme_engine.apply_theme`` que carga tokens desde
    ``app_core/themes/<theme>.json`` y genera QSS dinámicamente.
    
    Parameters
    ----------
    app : QApplication
        Instancia de la aplicación Qt.
    theme : str, optional
        Nombre del tema (sin extensión), por defecto "inorizonti".
    """
    _engine_apply_theme(app, theme_name=theme)
