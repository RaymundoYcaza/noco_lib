from __future__ import annotations
from typing import TYPE_CHECKING
from app_core.concurrency import run_async
from modules.localmail import service as localmail_service

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

def register(app: MainWindow, client: NocoClient) -> None:
    """
    Registers the Dummy module in Tardis.
    """
    app.add_menu_action(
        "Dummy",
        "Enviar notificación de prueba",
        lambda: run_async(
            localmail_service.notify,
            client,
            to_users=app.config.mailboxes[:1],
            subject="Prueba",
            body="Notificación de prueba desde dummy",
            module_origin="dummy_notify_test",
            on_success=lambda r: app.show_notification(
                "Notify OK" if r.success else r.errors[0],
                "info" if r.success else "error"
            )
        )
    )
