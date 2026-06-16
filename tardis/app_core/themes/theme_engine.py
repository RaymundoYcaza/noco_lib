"""Motor de temas para Tardis.

Carga archivos de tokens JSON (e.g. inorizonti.json) y genera
QSS dinámico aplicable a la aplicación. Todos los colores se
derivan de los tokens, evitando valores hex hardcodeados en el QSS.
"""

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

logger = logging.getLogger("tardis")


def load_theme(theme_path: str) -> dict[str, str]:
    """Carga un archivo de tema JSON y retorna sus tokens (sin la clave 'meta').

    Parameters
    ----------
    theme_path : str
        Ruta al archivo JSON del tema.

    Returns
    -------
    dict
        Diccionario token → valor hex. Vacío si hay error (degradación suave).
    """
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error("El archivo de tema %s no contiene un objeto JSON válido.", theme_path)
            return {}
        # Remover la clave 'meta' si existe; retornar solo tokens de color
        tokens = {k: v for k, v in data.items() if k != "meta"}
        logger.info("Tema cargado: %s (%d tokens)", theme_path, len(tokens))
        return tokens
    except FileNotFoundError:
        logger.error("Archivo de tema no encontrado: %s. Usando valores por defecto de Qt.", theme_path)
        return {}
    except json.JSONDecodeError as e:
        logger.error("Error parseando JSON del tema %s: %s. Usando valores por defecto.", theme_path, e)
        return {}


def generate_qss(tokens: dict[str, str]) -> str:
    """Genera una hoja de estilo QSS completa a partir de los tokens del tema.

    Parameters
    ----------
    tokens : dict
        Diccionario con token → valor hex. Los tokens deben incluir al menos
        las claves definidas en la especificación de Inorizonti.

    Returns
    -------
    str
        String QSS listo para aplicar via app.setStyleSheet().
    """
    # Valores por defecto razonables si algún token falta
    def t(key: str, fallback: str = "#000000") -> str:
        return tokens.get(key, fallback)

    qss = f"""
    /*** Tardis — Tema generado dinámicamente ***/

    /* ── Contenedores principales ────────────────────────────── */
    QMainWindow {{
        background-color: {t("color.bg.primary", "#ffffff")};
    }}
    QWidget {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
    }}
    QScrollArea {{
        background-color: {t("color.bg.primary", "#ffffff")};
        border: none;
    }}
    QSplitter::handle {{
        background-color: {t("color.border.primary", "#dddad6")};
        width: 1px;
        height: 1px;
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    QSplitter::handle:vertical {{
        height: 1px;
    }}

    /* ── TreeWidget (Sidebar) ────────────────────────────────── */
    QTreeWidget {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.primary", "#1a1a18")};
        border: none;
        border-radius: 0px;
        padding: 4px;
        outline: none;
    }}
    QTreeWidget::item {{
        padding: 6px 8px;
        border-radius: 4px;
        color: {t("color.text.primary", "#1a1a18")};
    }}
    QTreeWidget::item:hover {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}
    QTreeWidget::item:selected {{
        background-color: {t("color.bg.accent", "#e9290c")};
        color: {t("color.text.on.accent", "#ffffff")};
    }}
    QTreeWidget::branch:has-children:!has-siblings:closed,
    QTreeWidget::branch:closed:has-children:has-siblings {{
        border-image: none;
    }}
    QTreeWidget::branch:open:has-children:!has-siblings,
    QTreeWidget::branch:open:has-children:has-siblings {{
        border-image: none;
    }}

    /* ── TableWidget (Email list) ─────────────────────────────── */
    QTableWidget {{
        background-color: {t("color.bg.primary", "#ffffff")};
        alternate-background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.primary", "#1a1a18")};
        gridline-color: transparent;
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 6px;
        selection-background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}
    QTableWidget::item {{
        padding: 8px 10px;
        border-bottom: 1px solid {t("color.border.primary", "#dddad6")};
    }}
    QTableWidget::item:selected {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
        color: {t("color.text.primary", "#1a1a18")};
    }}
    QHeaderView::section {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.secondary", "#5a5a56")};
        padding: 6px 8px;
        font-weight: bold;
        border: none;
        border-bottom: 1px solid {t("color.border.primary", "#dddad6")};
    }}

    /* ── Botones ─────────────────────────────────────────────── */
    QPushButton {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        padding: 6px 14px;
        border-radius: 4px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}
    QPushButton:pressed {{
        background-color: {t("color.border.primary", "#dddad6")};
    }}
    QPushButton:disabled {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.secondary", "#5a5a56")};
        border-color: {t("color.border.primary", "#dddad6")};
    }}

    /* Botón de acento rojo (ej: "+ Nuevo mensaje") */
    QPushButton#accentButton {{
        background: {t("color.bg.accent", "#e9290c")};
        color: {t("color.text.on.accent", "#ffffff")};
        border: none;
        border-radius: 4px;
        font-weight: bold;
        padding: 6px 14px;
    }}
    QPushButton#accentButton:hover {{
        background: {t("color.bg.accent.hover", "#c5220a")};
    }}
    QPushButton#accentButton:pressed {{
        background: {t("color.bg.accent.hover", "#c5220a")};
    }}
    QPushButton#accentButton:disabled {{
        background: {t("color.border.primary", "#dddad6")};
        color: {t("color.text.secondary", "#5a5a56")};
    }}

    /* ── Inputs ──────────────────────────────────────────────── */
    QLineEdit {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 4px;
        padding: 6px 10px;
    }}
    QLineEdit:focus {{
        border-color: {t("color.border.accent", "#e9290c")};
    }}
    QLineEdit:disabled {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.secondary", "#5a5a56")};
    }}

    QTextEdit, QPlainTextEdit {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 4px;
        padding: 6px;
    }}
    QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {t("color.border.accent", "#e9290c")};
    }}

    /* ── ComboBox ────────────────────────────────────────────── */
    QComboBox {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 4px;
        padding: 6px 10px;
        min-width: 100px;
    }}
    QComboBox:focus {{
        border-color: {t("color.border.accent", "#e9290c")};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        selection-background-color: {t("color.bg.tertiary", "#ede9e4")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
    }}

    /* ── Labels ──────────────────────────────────────────────── */
    QLabel {{
        color: {t("color.text.primary", "#1a1a18")};
        background: transparent;
    }}

    /* ── Menus ───────────────────────────────────────────────── */
    QMenuBar {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border-bottom: 1px solid {t("color.border.primary", "#dddad6")};
    }}
    QMenuBar::item:selected {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}
    QMenu {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
    }}
    QMenu::item:selected {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}
    QMenu::separator {{
        height: 1px;
        background: {t("color.border.primary", "#dddad6")};
        margin: 4px 8px;
    }}

    /* ── StatusBar ───────────────────────────────────────────── */
    QStatusBar {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.secondary", "#5a5a56")};
        border-top: 1px solid {t("color.border.primary", "#dddad6")};
    }}

    /* ── Tabs ────────────────────────────────────────────────── */
    QTabWidget::pane {{
        background-color: {t("color.bg.primary", "#ffffff")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-top: none;
    }}
    QTabBar::tab {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.secondary", "#5a5a56")};
        padding: 8px 16px;
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border-bottom: 2px solid {t("color.border.accent", "#e9290c")};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}

    /* ── ListWidget ──────────────────────────────────────────── */
    QListWidget {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 4px;
    }}
    QListWidget::item:selected {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
        color: {t("color.text.primary", "#1a1a18")};
    }}
    QListWidget::item:hover {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
    }}

    /* ── ScrollBar ───────────────────────────────────────────── */
    QScrollBar:vertical {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        width: 8px;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {t("color.border.primary", "#dddad6")};
        min-height: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {t("color.text.secondary", "#5a5a56")};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        height: 8px;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {t("color.border.primary", "#dddad6")};
        min-width: 30px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {t("color.text.secondary", "#5a5a56")};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ── ProgressBar ─────────────────────────────────────────── */
    QProgressBar {{
        background-color: {t("color.bg.secondary", "#f5f3f0")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {t("color.bg.accent", "#e9290c")};
        border-radius: 3px;
    }}

    /* ── CheckBox ────────────────────────────────────────────── */
    QCheckBox {{
        color: {t("color.text.primary", "#1a1a18")};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 3px;
        background-color: {t("color.bg.primary", "#ffffff")};
    }}
    QCheckBox::indicator:checked {{
        background-color: {t("color.bg.accent", "#e9290c")};
        border-color: {t("color.bg.accent", "#e9290c")};
    }}

    /* ── ToolTip ─────────────────────────────────────────────── */
    QToolTip {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        padding: 4px 8px;
        border-radius: 4px;
    }}

    /* ── NavButton (App Switcher) ────────────────────────────── */
    /* Nota: El color del icono del NavButton se establece desde Python
       (qtawesome), no desde QSS. El QSS aquí solo controla el fondo y
       bordes. El color del borde izquierdo activo usa border.accent. */
    NavButton {{
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0px;
    }}
    NavButton:hover {{
        background-color: {t("color.bg.tertiary", "#ede9e4")};
    }}
    /* NavButton:checked se refiere al botón activo. El borde izquierdo
       usa el color de acento. El color del icono se maneja en Python. */
    NavButton:checked {{
        background-color: {t("color.bg.primary", "#ffffff")};
        border-left: 3px solid {t("color.border.accent", "#e9290c")};
    }}

    /* ── TextBrowser (Reader) ────────────────────────────────── */
    QTextBrowser {{
        background-color: {t("color.bg.primary", "#ffffff")};
        color: {t("color.text.primary", "#1a1a18")};
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 6px;
        padding: 12px;
    }}

    /* ── GroupBox ────────────────────────────────────────────── */
    QGroupBox {{
        color: {t("color.text.primary", "#1a1a18")};
        font-weight: bold;
        border: 1px solid {t("color.border.primary", "#dddad6")};
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 16px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        padding: 0 8px;
        color: {t("color.text.primary", "#1a1a18")};
    }}
    """
    return qss


def apply_theme(app: QApplication, theme_name: str = "inorizonti") -> None:
    """Carga un archivo de tema y lo aplica a la aplicación QApplication.

    Parameters
    ----------
    app : QApplication
        Instancia de la aplicación Qt.
    theme_name : str, optional
        Nombre del tema (sin extensión .json), por defecto "inorizonti".
    """
    theme_dir = Path(__file__).resolve().parent
    theme_path = str(theme_dir / f"{theme_name}.json")

    tokens = load_theme(theme_path)
    if not tokens:
        logger.warning("No se pudieron cargar los tokens del tema '%s'. "
                       "La aplicación usará los valores por defecto de Qt.", theme_name)
        return

    qss = generate_qss(tokens)
    app.setStyleSheet(qss)
    logger.info("Tema '%s' aplicado correctamente (%d reglas QSS generadas).",
                theme_name, qss.count("{"))
