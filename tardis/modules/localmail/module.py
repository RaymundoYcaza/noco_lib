from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

from modules.localmail.views.inbox_view import InboxView
from modules.localmail.views.reader_view import ReaderView
from modules.localmail.views.composer_view import ComposerView

def register(app: MainWindow, client: NocoClient) -> None:
    """
    Registers the LocalMail module components inside the Tardis main window.
    """
    # 1. Obtain user identity from configuration
    user_id = app.config.user_id if getattr(app, "config", None) else "unknown"
    mailboxes = app.config.mailboxes if getattr(app, "config", None) else []

    # 2. Create views
    inbox = InboxView(app, client, mailboxes)
    reader = ReaderView(app, client)

    # 3. Register dock panels in MainWindow using QtAds
    app.add_dock_panel(inbox, "LocalMail - Bandeja de entrada", area="left")
    app.add_dock_panel(reader, "LocalMail - Lector", area="center")

    # 4. Connect inbox selection signal to the reader view
    inbox.email_selected.connect(reader.show_email)

    # 5. Load inbox data initially
    inbox.load()

    # 6. Add menu actions for reloading inbox and drafting a new mail
    app.add_menu_action("LocalMail", "Bandeja de entrada", lambda: inbox.load())

    def open_composer() -> None:
        composer = ComposerView(app, client, mailboxes)
        app.add_floating_window(composer, "Redactar correo")

    app.add_menu_action("LocalMail", "Redactar", open_composer)
