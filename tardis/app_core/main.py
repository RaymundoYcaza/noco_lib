import sys
import logging
from pathlib import Path

# Add paths to sys.path
tardis_dir = Path(__file__).resolve().parent.parent
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
from noco_lib.noco_core import NocoClient
from app_core.concurrency import run_async

logger = logging.getLogger("tardis")
from app_core.config import load_tardis_config
from app_core.logging_setup import setup_logging
from app_core.main_window import MainWindow
from app_core.module_registry import discover_and_register
from app_core.theming import apply_theme
from app_core.views.settings_view import SettingsView
from app_core.splash import SplashScreen

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

    # 4. Mostrar splash screen mientras se inicializa el resto
    logo_path = tardis_dir / "shared" / "brands" / "inorizonti" / "logo.svg"
    splash = SplashScreen(logo_path)
    splash.show()
    app.processEvents()
    
    # 5. Crear la ventana principal de la aplicación
    window = MainWindow(client=client, config=config)
    
    # 6. Descubrir y registrar módulos modularmente
    module_info = discover_and_register(window, client)
    
    # 7. Crear y registrar la pantalla de Configuración
    settings_view = SettingsView(config, module_info, client, window)
    window.register_nav_item(
        module_id="settings",
        icon="fa5s.cog",
        label="Configuración",
        widget=settings_view,
        position="bottom",
    )
    
    # 8. Aplicar tema Inorizonti (claro con acento rojo) antes de mostrar la ventana
    apply_theme(app, "inorizonti")
    
    # 9. Restore last active module after all modules are registered
    window._restore_last_module()

    # 10. Iniciar notificador de bandeja de entrada
    from app_core.notifier import InboxNotifier
    notifier = InboxNotifier(client, config, window)
    notifier.new_emails_arrived.connect(notifier.notify)
    notifier.start()
    window._notifier = notifier  # Mantener referencia para evitar recolección de basura
    settings_view.set_notifier(notifier)  # Pasar al panel de Configuración

    # 11. Cerrar splash y mostrar la ventana principal maximizada
    splash.close()
    window.showMaximized()

    # ── 12. Verificar actualizaciones (Phase 6) ────────────────
    # (Ejecutado 3s después del inicio en un hilo secundario)
    def _update_check_done(win: MainWindow, remote_ver: str | None) -> None:
        """Callback en el hilo de UI con el resultado de la verificación."""
        if remote_ver is None:
            return
        from app_core.updater import download_and_install
        from app_core.version import load_version
        local_ver = load_version()
        reply = QMessageBox.question(
            win,
            "Actualización disponible",
            f"Hay una nueva versión de Tardis disponible:\n\n"
            f"  Actual:  v{local_ver}\n"
            f"  Nueva:   v{remote_ver}\n\n"
            "¿Deseas descargar e instalar la actualización?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            download_and_install(remote_ver)
            sys.exit(0)

    def _run_update_check(win: MainWindow) -> None:
        """Lanza la verificación en hilo secundario para no bloquear la UI."""
        from app_core.updater import check_for_updates
        run_async(
            check_for_updates,
            on_success=lambda r: _update_check_done(win, r),
            on_error=lambda e: logger.warning(
                "Error al verificar actualizaciones: %s", e
            ),
        )

    QTimer.singleShot(3000, lambda: _run_update_check(window))

    # 13. Iniciar el bucle de eventos de la aplicación
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
