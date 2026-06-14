import sys
from pathlib import Path

# Add paths to sys.path
tardis_dir = Path(__file__).resolve().parent.parent
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from PySide6.QtWidgets import QApplication
from noco_lib.noco_core import NocoClient
from app_core.config import load_tardis_config
from app_core.logging_setup import setup_logging
from app_core.main_window import MainWindow
from app_core.module_registry import discover_and_register
from app_core.theming import apply_theme
from app_core.views.settings_view import SettingsView

def main() -> None:
    # Initialize logging first
    setup_logging()
    
    # 1. Cargar la configuración de Tardis (.env y Windows user identity)
    config = load_tardis_config()
    
    # 2. Inicializar el cliente NocoDB
    client = NocoClient(
        base_url=config.noco_base_url,
        token=config.noco_token,
        base_id=config.noco_base_id
    )
    
    # 3. Inicializar QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Tardis")
    
    # 4. Crear la ventana principal de la aplicación
    window = MainWindow(client=client, config=config)
    
    # 5. Descubrir y registrar módulos modularmente
    module_info = discover_and_register(window, client)
    
    # 6. Crear y registrar la pantalla de Configuración
    settings_view = SettingsView(config, module_info, client, window)
    window.register_nav_item(
        module_id="settings",
        icon="fa5s.cog",
        label="Configuración",
        widget=settings_view,
        position="bottom",
    )
    
    # 7. Aplicar tema antes de mostrar la ventana
    apply_theme(app, "dark")
    
    # 8. Restore last active module after all modules are registered
    window._restore_last_module()
    
    # 9. Mostrar la ventana principal
    window.show()
    
    # 10. Iniciar el bucle de eventos de la aplicación
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
