import sys
from typing import Callable
from PySide6.QtWidgets import QMainWindow, QWidget, QMenuBar, QToolBar, QStatusBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

import PySide6QtAds as QtAds

# Add noco_lib search path to sys.path
from pathlib import Path
tardis_dir = Path(__file__).resolve().parent.parent
noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from noco_core.client import NocoClient
from app_core.config import TardisConfig

class MainWindow(QMainWindow):
    def __init__(self, client: NocoClient, config: TardisConfig | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.client = client
        self.config = config
        
        self.setWindowTitle("Tardis")
        self.resize(1024, 768)
        
        # Configure Premium Dark Theme stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121214;
                color: #e1e1e6;
            }
            QMenuBar {
                background-color: #18181b;
                color: #e1e1e6;
                border-bottom: 1px solid #27272a;
            }
            QMenuBar::item:selected {
                background-color: #27272a;
                border-radius: 4px;
            }
            QMenu {
                background-color: #18181b;
                color: #e1e1e6;
                border: 1px solid #27272a;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QToolBar {
                background-color: #18181b;
                border-bottom: 1px solid #27272a;
                spacing: 6px;
                padding: 4px;
            }
            QStatusBar {
                background-color: #18181b;
                color: #a1a1aa;
                border-top: 1px solid #27272a;
            }
        """)

        # Initialize Qt Advanced Docking System
        # CDockManager installs itself inside the main window
        self.dock_manager = QtAds.CDockManager(self)
        
        # Ensure status bar exists
        self.statusBar()

    def add_dock_panel(self, widget: QWidget, title: str, area: str = "left") -> QtAds.CDockWidget:
        """
        Crea un panel acoplable (CDockWidget) con el widget proporcionado y lo añade
        al CDockManager en la zona especificada.
        """
        # Map string area to QtAds DockWidgetArea enum
        area_map = {
            "left": QtAds.LeftDockWidgetArea,
            "right": QtAds.RightDockWidgetArea,
            "top": QtAds.TopDockWidgetArea,
            "bottom": QtAds.BottomDockWidgetArea,
            "center": QtAds.CenterDockWidgetArea
        }
        dock_area = area_map.get(area.lower(), QtAds.LeftDockWidgetArea)
        
        # Create CDockWidget using the modern, non-deprecated constructor
        dock_widget = QtAds.CDockWidget(self.dock_manager, title)
        dock_widget.setWidget(widget)
        
        self.dock_manager.addDockWidget(dock_area, dock_widget)
        return dock_widget

    def add_floating_window(self, widget: QWidget, title: str) -> QtAds.CDockWidget:
        """
        Crea un panel flotante independiente con el widget proporcionado.
        """
        dock_widget = QtAds.CDockWidget(self.dock_manager, title)
        dock_widget.setWidget(widget)
        
        self.dock_manager.addDockWidgetFloating(dock_widget)
        return dock_widget

    def add_menu_action(self, menu_path: str, label: str, callback: Callable) -> None:
        """
        Añade una opción de menú basada en una ruta anidada separada por '>' (ej. 'LocalMail > Bandeja de entrada').
        """
        menu_bar = self.menuBar()
        parts = [p.strip() for p in menu_path.split(">")]
        current_menu = None
        
        for part in parts:
            if not part:
                continue
            parent = current_menu if current_menu is not None else menu_bar
            found = False
            
            # Look for existing sub-menu
            for action in parent.actions():
                menu = action.menu()
                if menu and menu.title() == part:
                    current_menu = menu
                    found = True
                    break
            
            if not found:
                if current_menu is None:
                    current_menu = menu_bar.addMenu(part)
                else:
                    current_menu = current_menu.addMenu(part)
                    
        if current_menu is not None:
            action = current_menu.addAction(label)
            action.triggered.connect(callback)

    def add_toolbar_action(self, label: str, icon, callback: Callable) -> None:
        """
        Añade un botón de acción a la barra de herramientas principal.
        """
        if not hasattr(self, "main_toolbar"):
            self.main_toolbar = QToolBar("Main Toolbar", self)
            self.addToolBar(self.main_toolbar)
            
        if isinstance(icon, str):
            qicon = QIcon(icon)
        elif isinstance(icon, QIcon):
            qicon = icon
        else:
            qicon = QIcon()
            
        action = self.main_toolbar.addAction(qicon, label)
        action.triggered.connect(callback)

    def get_client(self) -> NocoClient:
        """
        Retorna la instancia del cliente NocoDB.
        """
        return self.client

    def show_notification(self, text: str, level: str = "info") -> None:
        """
        Muestra un mensaje en la barra de estado con un color distintivo según el nivel de alerta.
        """
        status_bar = self.statusBar()
        if level == "error":
            status_bar.setStyleSheet("QStatusBar { color: #f87171; font-weight: bold; background-color: #18181b; border-top: 1px solid #27272a; }")
        elif level == "warning":
            status_bar.setStyleSheet("QStatusBar { color: #fbbf24; font-weight: bold; background-color: #18181b; border-top: 1px solid #27272a; }")
        else:
            # Default / Info color
            status_bar.setStyleSheet("QStatusBar { color: #3b82f6; background-color: #18181b; border-top: 1px solid #27272a; }")
            
        status_bar.showMessage(text, 5000)
