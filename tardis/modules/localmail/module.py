from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Qt, QSettings
from modules.localmail.views.sidebar_view import SidebarTreeView
from modules.localmail.views.reader_view import ReaderView
from modules.localmail.views.composer_view import ComposerView

def register(app: MainWindow, client: NocoClient) -> None:
    """
    Registers the LocalMail module components inside the Tardis main window using a three-pane layout.
    """
    # 1. Obtain user identity from configuration
    user_id = app.config.user_id if getattr(app, "config", None) else "unknown"
    mailboxes = app.config.mailboxes if getattr(app, "config", None) else []

    # 2. Create the left Sidebar view and save reference
    app.sidebar_view = SidebarTreeView(app, client, mailboxes)

    # 3. Create the center layout (filter bar placeholder + email list placeholder)
    center_widget = QWidget()
    center_layout = QVBoxLayout(center_widget)
    center_layout.setContentsMargins(0, 0, 0, 0)
    center_layout.setSpacing(8)

    app.filter_placeholder = QLabel("Filtros (Placeholder)")
    app.filter_placeholder.setStyleSheet("background-color: #27272a; color: #a1a1aa; padding: 10px; border-radius: 4px;")
    
    app.list_placeholder = QLabel("Lista de Correos (Placeholder)")
    app.list_placeholder.setStyleSheet("background-color: #18181b; color: #e1e1e6; padding: 20px; border: 1px solid #27272a; border-radius: 6px;")
    
    center_layout.addWidget(app.filter_placeholder)
    center_layout.addWidget(app.list_placeholder)

    # 4. Create the right Reader view
    app.reader_view = ReaderView(app, client)

    # 5. Create horizontal QSplitter to hold Left, Center, and Right panes
    splitter = QSplitter(Qt.Horizontal)
    splitter.addWidget(app.sidebar_view)
    splitter.addWidget(center_widget)
    splitter.addWidget(app.reader_view)
    
    app.three_pane_splitter = splitter

    # Restore splitter sizes/state if saved
    settings = QSettings("Tardis", "Tardis")
    state = settings.value("three_pane/splitter_sizes")
    if state is not None:
        splitter.restoreState(state)
    else:
        # Initial proportions roughly [1, 2, 2]
        splitter.setSizes([200, 412, 412])

    # 6. Register three-pane widget as central widget of MainWindow
    app.setCentralWidget(splitter)

    # 7. Add menu action for composing a new mail (floating window)
    def open_composer() -> None:
        composer = ComposerView(app, client, mailboxes)
        dock = app.add_floating_window(composer, "Redactar correo")
        if not hasattr(app, "_composer_windows"):
            app._composer_windows = []
        app._composer_windows.append((composer, dock))

    app.add_menu_action("LocalMail", "Redactar", open_composer)
