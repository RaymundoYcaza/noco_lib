from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

def register(app: "MainWindow", client: "NocoClient") -> None:
    """
    Punto de entrada del módulo. Aquí se crean widgets/vistas y se
    registran con app.add_dock_panel / add_floating_window /
    add_menu_action. NUNCA llamar a client.table(...).read()/etc.
    directamente aquí de forma síncrona si el resultado depende de
    red — usar run_async desde dentro de las vistas.
    """
    pass
