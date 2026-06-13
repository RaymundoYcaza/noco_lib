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

    # 2. Create views and save references on app
    app.inbox_view = InboxView(app, client, mailboxes)
    app.sent_view = InboxView(app, client, mailboxes, mode="sent")
    app.trash_view = InboxView(app, client, mailboxes, mode="trash")
    app.reader_view = ReaderView(app, client)

    # 3. Register dock panels in MainWindow using QtAds and save references
    app.inbox_dock = app.add_dock_panel(app.inbox_view, "LocalMail - Bandeja de entrada", area="left")
    app.sent_dock = app.add_dock_panel(app.sent_view, "LocalMail - Enviados", area="left")
    app.trash_dock = app.add_dock_panel(app.trash_view, "LocalMail - Papelera", area="left")
    app.reader_dock = app.add_dock_panel(app.reader_view, "LocalMail - Lector", area="center")

    # 4. Connect selection signals to the reader view
    app.inbox_view.email_selected.connect(app.reader_view.show_email)
    app.sent_view.email_selected.connect(app.reader_view.show_email)
    app.trash_view.email_selected.connect(app.reader_view.show_email)

    # 5. Load inbox data initially
    app.inbox_view.load()

    # 6. Add menu actions for reloading views and drafting a new mail
    app.add_menu_action("LocalMail", "Bandeja de entrada", lambda: app.inbox_view.load())
    app.add_menu_action("LocalMail", "Enviados", lambda: app.sent_view.load())
    app.add_menu_action("LocalMail", "Papelera", lambda: app.trash_view.load())

    def open_composer() -> None:
        composer = ComposerView(app, client, mailboxes)
        dock = app.add_floating_window(composer, "Redactar correo")
        if not hasattr(app, "_composer_windows"):
            app._composer_windows = []
        app._composer_windows.append((composer, dock))

    app.add_menu_action("LocalMail", "Redactar", open_composer)

