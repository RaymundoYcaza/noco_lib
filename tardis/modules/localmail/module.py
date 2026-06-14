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

import logging

logger = logging.getLogger("tardis")


class LocalMailScreen(QWidget):
    """Full-screen widget for the LocalMail module.

    Contains the three-pane layout: folder sidebar (left), email list
    + filter bar (center), and reader (right), arranged in a horizontal
    ``QSplitter``.

    This widget is registered via ``register_nav_item`` and replaces
    the former ``setCentralWidget`` pattern.
    """

    def __init__(
        self,
        app: MainWindow,
        client: NocoClient,
        mailboxes: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app = app
        self._client = client
        self._mailboxes = mailboxes

        self._build_ui()
        self._wire_signals()
        self._restore_last_node()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 1. Sidebar
        self._sidebar_view = SidebarTreeView(self._app, self._client, self._mailboxes)
        self._app.sidebar_view = self._sidebar_view  # keep for backward compat

        # 2. Center: filter bar + email list
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        self._filter_bar = FilterBarView(self._app)
        self._app.filter_bar_view = self._filter_bar

        self._email_list = EmailListView(self._app, self._client)
        self._app.email_list_view = self._email_list

        center_layout.addWidget(self._filter_bar)
        center_layout.addWidget(self._email_list)

        # 3. Reader
        self._reader = ReaderView(self._app, self._client)
        self._app.reader_view = self._reader

        # 4. Horizontal splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self._sidebar_view)
        self._splitter.addWidget(center_widget)
        self._splitter.addWidget(self._reader)
        self._app.three_pane_splitter = self._splitter

        # Restore splitter sizes
        settings = QSettings("Tardis", "Tardis")
        state = settings.value("three_pane/splitter_sizes")
        if state is not None:
            self._splitter.restoreState(state)
        else:
            self._splitter.setSizes([200, 412, 412])

        # Main layout for this screen
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._splitter)

    # ── Signal wiring ────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        # Filter bar → email list
        self._filter_bar.filter_changed.connect(self._email_list.apply_filter)

        # Sidebar node selected → load folder
        self._sidebar_view.node_selected.connect(self._on_node_selected)

        # Email selected → show in reader
        self._email_list.email_selected.connect(self._reader.show_email)

        # Reader marks email as read → update list row
        self._reader.email_read.connect(self._email_list.mark_row_as_read)

    def _on_node_selected(self, node) -> None:
        if node.folder is None:
            return
        self._email_list.load(self._client, node.mailboxes, node.folder)
        # Persist selection
        settings = QSettings("Tardis", "Tardis")
        settings.setValue("three_pane/last_selected_node", node.id)

    def _restore_last_node(self) -> None:
        settings = QSettings("Tardis", "Tardis")
        last_id = settings.value("three_pane/last_selected_node")
        restored = False
        if last_id:
            restored = self._sidebar_view.select_node_by_id(last_id)
        if not restored:
            self._sidebar_view.select_node_by_id("all:inbox")


# ═══════════════════════════════════════════════════════════════════════
#  Module entry point
# ═══════════════════════════════════════════════════════════════════════


def register(app: MainWindow, client: NocoClient) -> None:
    """Register the LocalMail module as a navigation item.

    Creates the three-pane screen and registers it with the App Switcher
    bar at the ``"top"`` position. All menu actions are preserved.
    """
    mailboxes = app.config.mailboxes if getattr(app, "config", None) else []

    # 1. Build the full-screen LocalMail widget
    screen = LocalMailScreen(app, client, mailboxes)

    # 2. Register as a nav item (always first, top position)
    app.register_nav_item(
        module_id="localmail",
        icon="fa5s.envelope",
        label="LocalMail",
        widget=screen,
        toolbar=None,       # Phase 6: will be the QToolBar
        position="top",     # Always visible at the top of the nav bar
    )

    # 3. Menu actions (unchanged)
    def open_composer() -> None:
        composer = ComposerView(app, client, mailboxes)
        dock = app.add_floating_window(composer, "Redactar correo")
        if not hasattr(app, "_composer_windows"):
            app._composer_windows = []
        app._composer_windows.append((composer, dock))

    app.add_menu_action("LocalMail", "Redactar", open_composer)

    logger.info("LocalMail module registered (nav item)")
