import sys
from typing import Callable
from PySide6.QtWidgets import QMainWindow, QWidget, QMenuBar, QToolBar, QStatusBar
from PySide6.QtCore import Qt, QSettings
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
from app_core.widgets.toast import Toast
from app_core.sidebar.tree_model import SidebarNode



class FloatingDockWidget(QtAds.CDockWidget):
    def __init__(self, dock_manager, title: str, parent: QWidget | None = None):
        super().__init__(dock_manager, title, parent)
        self.title_str = title

    def closeEvent(self, event):
        # Propagate close to the child widget first, so its closeEvent is called.
        # If the child widget ignores/rejects the close, we ignore this event.
        if self.widget():
            if not self.widget().close():
                event.ignore()
                return
                
        settings = QSettings("Tardis", "Tardis")
        container = self.floatingDockContainer()
        if container:
            settings.setValue(f"floating/{self.title_str}/geometry", container.saveGeometry())
        else:
            settings.setValue(f"floating/{self.title_str}/geometry", self.saveGeometry())
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, client: NocoClient, config: TardisConfig | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.client = client
        self.config = config
        
        self.setWindowTitle("Tardis")
        self.resize(1024, 768)
        
        # QSS stylesheet is loaded and applied globally in main.py using apply_theme

        # Initialize Qt Advanced Docking System
        # CDockManager installs itself inside the main window
        self.dock_manager = QtAds.CDockManager(self)
        
        # Ensure status bar exists
        self.statusBar()
        
        self._extra_sidebar_nodes = []

    def setCentralWidget(self, widget: QWidget) -> None:
        """
        Overrides setCentralWidget to integrate the widget into the QtAds CDockManager
        instead of replacing it, preserving the docking system and other dock panels.
        """
        # Set config flag to hide title bar for the central widget
        self.dock_manager.setConfigFlag(QtAds.CDockManager.HideSingleCentralWidgetTitleBar, True)

        # Create a non-closable, non-movable, non-floatable CDockWidget for the center
        dock_widget = QtAds.CDockWidget(self.dock_manager, "CentralView")
        dock_widget.setWidget(widget)
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetClosable, False)
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetMovable, False)
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetFloatable, False)
        dock_widget.setFeature(QtAds.CDockWidget.NoTab, True)
        
        # Set as central widget of CDockManager
        self.dock_manager.setCentralWidget(dock_widget)
        
        # Keep references to prevent garbage collection and allow retrieval
        self._central_dock_widget = dock_widget
        self._central_widget_ref = widget

    def centralWidget(self) -> QWidget | None:
        return getattr(self, "_central_widget_ref", None)

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
        dock_widget = FloatingDockWidget(self.dock_manager, title)
        dock_widget.setWidget(widget)
        
        self.dock_manager.addDockWidgetFloating(dock_widget)
        
        # Restore geometry if it exists
        settings = QSettings("Tardis", "Tardis")
        geom = settings.value(f"floating/{title}/geometry")
        if geom is not None:
            container = dock_widget.floatingDockContainer()
            if container:
                container.restoreGeometry(geom)
            else:
                dock_widget.restoreGeometry(geom)
                
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
        También instancia y muestra un Toast flotante.
        """
        # 1. Update status bar (fallback)
        status_bar = self.statusBar()
        status_bar.setStyleSheet("")
        status_bar.setObjectName(f"status-{level}")
        status_bar.style().unpolish(status_bar)
        status_bar.style().polish(status_bar)
        status_bar.showMessage(text, 5000)

        # 2. Instantiate and show floating Toast notification
        try:
            Toast(self, text, level)
        except Exception as e:
            import logging
            logging.getLogger("tardis").exception("Exception displaying Toast notification")

    def add_sidebar_node(self, node: SidebarNode) -> None:
        """
        Registers an additional top-level node in the sidebar
        tree, contributed by a module. Must be called during
        module registration (register(app, client)), before the
        sidebar widget is built/shown.
        """
        self._extra_sidebar_nodes.append(node)

    def closeEvent(self, event) -> None:
        try:
            # Guardar el estado/proporciones del splitter de 3 paneles
            if hasattr(self, "three_pane_splitter") and self.three_pane_splitter:
                settings = QSettings("Tardis", "Tardis")
                settings.setValue("three_pane/splitter_sizes", self.three_pane_splitter.saveState())
        except Exception as e:
            import logging
            logging.getLogger("tardis").exception("Exception in MainWindow.closeEvent while saving splitter state")
        super().closeEvent(event)



