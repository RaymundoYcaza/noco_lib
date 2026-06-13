import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

def apply_theme(app: QApplication, theme: str = "dark") -> None:
    """
    Lee app_core/styles/<theme>.qss y lo aplica a la aplicación.
    Maneja FileNotFoundError con fallback a sin estilo.
    """
    style_dir = Path(__file__).resolve().parent / "styles"
    qss_path = style_dir / f"{theme}.qss"
    
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            qss_content = f.read()
        app.setStyleSheet(qss_content)
    except FileNotFoundError:
        logger.warning(f"Archivo de tema no encontrado: {qss_path}. Continuando sin estilo.")
    except Exception as e:
        logger.error(f"Error al aplicar el tema {theme}: {e}. Continuando sin estilo.")
