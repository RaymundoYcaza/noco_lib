from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Qt, QSettings
from modules.localmail.views.sidebar_view import SidebarTreeView
from modules.localmail.views.email_list_view import EmailListView
from modules.localmail.views.filter_bar import FilterBarView
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

    # 3. Create the center layout (filter bar + email list view)
    center_widget = QWidget()
    center_layout = QVBoxLayout(center_widget)
    center_layout.setContentsMargins(0, 0, 0, 0)
    center_layout.setSpacing(8)

    app.filter_bar_view = FilterBarView(app)
    app.email_list_view = EmailListView(app, client)
    
    # Wire filter bar changes to email list filtering
    app.filter_bar_view.filter_changed.connect(app.email_list_view.apply_filter)
    
    center_layout.addWidget(app.filter_bar_view)
    center_layout.addWidget(app.email_list_view)

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

    # 7. Wire sidebar -> list
    def on_node_selected(node) -> None:
        if node.folder is None:
            return
        app.email_list_view.load(client, node.mailboxes, node.folder)
        # Store last selected node ID in QSettings
        local_settings = QSettings("Tardis", "Tardis")
        local_settings.setValue("three_pane/last_selected_node", node.id)

    app.sidebar_view.node_selected.connect(on_node_selected)

    # Wire list -> reader (single click selection)
    app.email_list_view.email_selected.connect(app.reader_view.show_email)

    # Wire reader -> list (mark as read update in-place)
    app.reader_view.email_read.connect(app.email_list_view.mark_row_as_read)

    # 8. Restore last selected node, default to All Mailboxes > Inbox (all:inbox)
    last_selected_node_id = settings.value("three_pane/last_selected_node")
    node_restored = False
    if last_selected_node_id:
        node_restored = app.sidebar_view.select_node_by_id(last_selected_node_id)
    if not node_restored:
        app.sidebar_view.select_node_by_id("all:inbox")

    # 9. Add menu action for composing a new mail (floating window)
    def open_composer() -> None:
        composer = ComposerView(app, client, mailboxes)
        dock = app.add_floating_window(composer, "Redactar correo")
        if not hasattr(app, "_composer_windows"):
            app._composer_windows = []
        app._composer_windows.append((composer, dock))

    app.add_menu_action("LocalMail", "Redactar", open_composer)
