import sys
import logging
from typing import Callable

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMenuBar,
    QToolBar,
    QStatusBar,
    QStackedWidget,
)
from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QIcon

# Add noco_lib search path to sys.path
tardis_dir = Path(__file__).resolve().parent.parent
noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from noco_core.client import NocoClient
from app_core.config import TardisConfig
from app_core.widgets.toast import Toast
from app_core.widgets.nav_bar import NavBar
from app_core.widgets.nav_button import NavButton
from app_core.sidebar.tree_model import SidebarNode

logger = logging.getLogger("tardis")


# ── Floating window (replaces QtAds FloatingDockWidget) ─────────────


class FloatingWindow(QWidget):
    """Standalone floating window that wraps a child widget.

    Replaces the former ``QtAds.CDockWidget``-based floating windows.
    Saves and restores geometry via ``QSettings`` automatically.
    """

    def __init__(
        self,
        child: QWidget,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(title)
        self._child_widget = child
        self._title_str = title

        # Wrap the child in a simple layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(child)

        # Restore geometry if previously saved
        self._restore_geometry()

    # ── Geometry persistence ─────────────────────────────────────

    def _restore_geometry(self) -> None:
        try:
            settings = QSettings("Tardis", "Tardis")
            key = "floating/Compose/geometry" if self._title_str == "Redactar correo" else f"floating/{self._title_str}/geometry"
            geom = settings.value(key)
            if geom is not None:
                self.restoreGeometry(geom)
        except Exception:
            logger.exception("Failed to restore floating window geometry")

    def _save_geometry(self) -> None:
        try:
            settings = QSettings("Tardis", "Tardis")
            key = "floating/Compose/geometry" if self._title_str == "Redactar correo" else f"floating/{self._title_str}/geometry"
            settings.setValue(key, self.saveGeometry())
        except Exception:
            logger.exception("Failed to save floating window geometry")

    # ── Close handling ───────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Save geometry and propagate close to the child widget."""
        self._save_geometry()
        if self._child_widget and not self._child_widget.close():
            event.ignore()
            return
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════
#  MainWindow
# ═══════════════════════════════════════════════════════════════════


class MainWindow(QMainWindow):
    """Tardis main application window.

    Layout after Phase 4b refactor (no dock system)::

        ┌──────┬──────────────────────────────────────┐
        │      │                                      │
        │ Nav  │  QStackedWidget                      │
        │ Bar  │  (module screens)                    │
        │ 52px │                                      │
        │      │                                      │
        └──────┴──────────────────────────────────────┘

    Extension points (unchanged from Phase 3):
      - ``add_floating_window``
      - ``add_menu_action``
      - ``add_toolbar_action``
      - ``show_notification``
      - ``add_sidebar_node``

    NEW extension points (Phase 4b):
      - ``register_nav_item`` — replaces ``add_dock_panel``
    """

    def __init__(
        self,
        client: NocoClient,
        config: TardisConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self.config = config

        self.setWindowTitle("Tardis")
        self.resize(1024, 768)

        # ── Central content: QHBoxLayout with NavBar + Stack ─────
        self._content_widget = QWidget(self)
        self._content_layout = QHBoxLayout(self._content_widget)
        self._content_layout.setSpacing(0)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        # Left: App Switcher bar (52px fixed)
        self._nav_bar = NavBar(self._content_widget)
        self._content_layout.addWidget(self._nav_bar)

        # Right: Stacked widget for module screens
        self._stack = QStackedWidget(self._content_widget)
        self._content_layout.addWidget(self._stack, stretch=1)

        # Install as the main window's central widget
        super().setCentralWidget(self._content_widget)

        # Ensure status bar exists
        self.statusBar()

        # ── Internal state ───────────────────────────────────────
        self._nav_bar.module_activated.connect(self._on_nav_activated)
        self._module_screens: dict[str, QWidget] = {}
        self._module_toolbars: dict[str, QWidget | None] = {}
        self._extra_sidebar_nodes: list[SidebarNode] = []
        self._central_widget_ref: QWidget | None = None  # for backward compat

    # ── New: navigation item registration ──────────────────────────

    def register_nav_item(
        self,
        module_id: str,
        icon: str,
        label: str,
        widget: QWidget,
        toolbar: QWidget | None = None,
        position: str = "middle",
    ) -> None:
        """Register a module screen in the App Switcher bar.

        Parameters
        ----------
        module_id : str
            Unique key, e.g. ``\"localmail\"``, ``\"pdf_export\"``.
        icon : str
            qtawesome icon name, e.g. ``\"fa5s.envelope\"``.
        label : str
            Tooltip and human-readable name.
        widget : QWidget
            The module's main screen widget (added to the stack).
        toolbar : QWidget | None, optional
            Reserved for Phase 6 — stored but not displayed.
        position : str, optional
            ``\"top\"`` (fixed above scroll), ``\"middle\"`` (scrollable),
            or ``\"bottom\"`` (fixed below spacer, above Settings).
        """
        if module_id in self._module_screens:
            logger.warning(
                "register_nav_item: module_id '%s' already registered — skipping",
                module_id,
            )
            return

        # Create nav button and add to the bar
        btn = NavButton(icon_name=icon, label=label, module_id=module_id)
        self._nav_bar.add_button(btn, position)

        # Add widget to the stack
        self._stack.addWidget(widget)
        self._module_screens[module_id] = widget
        self._module_toolbars[module_id] = toolbar

        logger.info(
            "Nav item registered: %s (icon=%s, position=%s)",
            module_id,
            icon,
            position,
        )

    def _activate_module(self, module_id: str) -> None:
        """Switch to the given module screen and persist the choice."""
        widget = self._module_screens.get(module_id)
        if widget is None:
            logger.warning("_activate_module: unknown module '%s'", module_id)
            return

        self._stack.setCurrentWidget(widget)
        self._nav_bar.set_active(module_id)

        # Persist last active module
        try:
            settings = QSettings("Tardis", "Tardis")
            settings.setValue("nav/last_active_module", module_id)
        except Exception:
            logger.exception("Failed to persist last active module")

        self._central_widget_ref = widget

    def _on_nav_activated(self, module_id: str) -> None:
        """Handle NavBar's ``module_activated`` signal."""
        self._activate_module(module_id)

    def _restore_last_module(self) -> None:
        """Restore the last active module from QSettings on startup."""
        try:
            settings = QSettings("Tardis", "Tardis")
            last = settings.value("nav/last_active_module", "localmail")
            if last and last in self._module_screens:
                self._activate_module(last)
            elif self._module_screens:
                # Fallback to first registered module
                first = next(iter(self._module_screens))
                self._activate_module(first)
        except Exception:
            logger.exception("Failed to restore last active module")
            # Fallback: activate first if any
            if self._module_screens:
                first = next(iter(self._module_screens))
                self._activate_module(first)

    # ── Backward compat: setCentralWidget / centralWidget ──────────

    def setCentralWidget(self, widget: QWidget) -> None:
        """Override: add *widget* to the module stack (backward compat).

        Modules that still use ``setCentralWidget`` (e.g. LocalMail)
        work by adding the widget to the stack. New modules should use
        ``register_nav_item`` instead.
        """
        self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)
        self._central_widget_ref = widget

    def centralWidget(self) -> QWidget | None:
        """Return the current central widget (backward compat)."""
        return self._central_widget_ref

    # ── add_dock_panel — REMOVED ──────────────────────────────────

    def add_dock_panel(self, widget: QWidget, title: str, area: str = "left") -> None:
        """REMOVED. Use ``register_nav_item`` instead."""
        raise NotImplementedError(
            "add_dock_panel is removed in Phase 4b. "
            "Use register_nav_item(module_id, icon, label, widget, position) instead."
        )

    # ── add_floating_window (reimplemented, no QtAds) ─────────────

    def add_floating_window(self, widget: QWidget, title: str) -> "FloatingWindow":
        """Create an independent floating window.

        Saves and restores geometry via ``QSettings``.
        Returns the ``FloatingWindow`` wrapper.
        """
        floating = FloatingWindow(child=widget, title=title, parent=self)
        floating.resize(800, 600)
        floating.show()
        floating.raise_()
        return floating

    # ── Menu actions ──────────────────────────────────────────────

    def add_menu_action(self, menu_path: str, label: str, callback: Callable) -> None:
        """Add a menu action under a nested path.

        Paths use ``>`` as separator, e.g. ``\"LocalMail > Redactar\"``.
        """
        menu_bar = self.menuBar()
        parts = [p.strip() for p in menu_path.split(">")]
        current_menu = None

        for part in parts:
            if not part:
                continue
            parent = current_menu if current_menu is not None else menu_bar
            found = False

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

    # ── Toolbar actions ───────────────────────────────────────────

    def add_toolbar_action(self, label: str, icon, callback: Callable) -> None:
        """Add a button to the main toolbar."""
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
        """Return the NocoDB client instance."""
        return self.client

    # ── Notifications ─────────────────────────────────────────────

    def show_notification(
        self,
        text: str,
        level: str = "info",
        duration_ms: int = 4000,
        action_label: str | None = None,
        action_callback: Callable | None = None,
    ) -> None:
        """
        Muestra una notificación tipo Toast en la esquina inferior derecha.

        Parameters
        ----------
        text : str
            Texto del mensaje.
        level : str
            Nivel: "info", "success", "warning", "error".
        duration_ms : int
            Duración en milisegundos.
        action_label : str | None
            Texto opcional para el botón de acción.
        action_callback : Callable | None
            Función a ejecutar al hacer clic en el botón de acción.
        """
        status_bar = self.statusBar()
        status_bar.setStyleSheet("")
        status_bar.setObjectName(f"status-{level}")
        status_bar.style().unpolish(status_bar)
        status_bar.style().polish(status_bar)
        status_bar.showMessage(text, min(duration_ms, 5000))

        try:
            Toast(self, text, level, duration_ms, action_label, action_callback)
        except Exception:
            logger.exception("Error al mostrar notificación Toast")

    # ── Sidebar nodes ─────────────────────────────────────────────

    def add_sidebar_node(self, node: SidebarNode) -> None:
        """Register an extra sidebar node contributed by a module."""
        self._extra_sidebar_nodes.append(node)

    # ── Close event ───────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Save splitter state before closing."""
        try:
            if hasattr(self, "three_pane_splitter") and self.three_pane_splitter:
                settings = QSettings("Tardis", "Tardis")
                settings.setValue(
                    "three_pane/splitter_sizes",
                    self.three_pane_splitter.saveState(),
                )
        except Exception:
            logger.exception("Exception in MainWindow.closeEvent while saving splitter state")
        super().closeEvent(event)
