# Changelog

## [0.2.0.2] — 2026-06-16

### Added

- **Pre-commit hook para auto-incrementar build number**
  - Se creó `tardis/scripts/pre-commit-bump.sh`: hook de git que ejecuta
    `bump_version.py` y staged `VERSION` automáticamente antes de cada commit.
  - Se creó `tardis/scripts/install_hooks.py`: script para copiar el hook a
    `.git/hooks/` y darle permisos de ejecución.
  - Instalación: `python tardis/scripts/install_hooks.py` (una vez por clon).
  - Ya no depende de GitHub Actions para incrementar el build number.

- **Backup automático del .env antes de actualizar**
  - `_backup_env()` en `updater.py`: respalda el `.env` en
    `%APPDATA%/Tardis/.env.<timestamp>.backup` antes de ejecutar el instalador.
  - No bloquea la actualización si el backup falla.

- **Notificación de variables faltantes en .env**
  - `_check_missing_env_vars()` en `config.py`: al iniciar la app, compara las
    variables del `.env` del usuario contra `.env.example` y loggea un warning
    si faltan variables nuevas.

### Changed

- **Splash screen: "LocalMail" → "Tardis"**
  - El título del splash cambió de "LocalMail" a "Tardis".
  - El subtítulo cambió de "Cliente de correo corporativo" a
    "Sistema de gestión documental y comunicaciones".

- **Nomenclatura neutral para build e instalador**
  - `build.py`: `--name` cambió de `"Tardis-v{VERSION}"` a `"Tardis"` (sin versión
    en la carpeta del .exe ni en el nombre del ejecutable).
  - `build.py`: `build_installer()` ahora pasa la versión a Inno Setup mediante
    `iscc /dMyAppVersion={VERSION}`, eliminando el hardcodeo en `.iss`.
  - `tardis_setup.iss`: `Source` path cambió de `..\dist\Tardis-v{#MyAppVersion}\*`
    a `..\dist\Tardis\*` (neutral). Los accesos directos nunca se rompen.
  - Los instaladores en el share de red (`Tardis-v{version}-Setup.exe`) siguen
    versionados — es correcto para artefactos de distribución.

### Fixed

- **CI: GitHub Actions fallaba con 403 al hacer git push**
  - El `bump-version` job del workflow no podía pushear porque el token por defecto
    (`GITHUB_TOKEN`) no tiene permisos de escritura.
  - Solución temporal: se implementó el hook pre-commit local.
  - Pendiente: configurar un PAT en Secrets del repo para reactivar el CI.

## [0.2.0.1] — 2026-06-16

### Fixed

- **PyInstaller packaging: módulos no aparecían en el .exe compilado**
  - El `build.py` original no incluía `--add-data` para el directorio `modules/`, por
    lo que `pkgutil.iter_modules()` no podía escanear los módulos en disco dentro del
    bundle de PyInstaller → la NavBar (barra lateral) aparecía vacía, mostrando solo
    el icono de Configuración.
  - Faltaban `--hidden-import` para `modules.localmail`, `modules.pdf_export` y
    `modules.ai_corrections` (importados dinámicamente vía `importlib.import_module`,
    no detectables por el análisis estático de PyInstaller).
  - Sin `--paths` apuntando a `tardis/`, PyInstaller no encontraba los paquetes
    locales (`noco_lib`, `ai_lib`, `modules`) durante la fase de análisis.
  - Sin `--collect-binaries PySide6.QtSvg`, el plugin SVG de Qt no se incluía en el
    bundle, impidiendo que `QSvgRenderer` mostrara el logo en el splash screen.
  - Reemplazadas ~20 líneas de `--hidden-import` para `reportlab`, `mistune`,
    `pikepdf` y `jinja2` con `--collect-all`, que es más limpio y captura todos
    los submodules automáticamente.

- **Versión mostraba `v0.0.0.0` en el .exe compilado**
  - El archivo `tardis/VERSION` (único punto de verdad) no se incluía en el bundle
    de PyInstaller. `version.py` lee `_internal/VERSION`, que no existía, cayendo
    en el `except FileNotFoundError` que retorna `"0.0.0.0"`.
  - Se agregó `--add-data "tardis/VERSION;."` para copiar el archivo al bundle.

- **Path resolution en frozen mode**
  - `main.py` y `module_registry.py` ahora detectan el modo frozen de PyInstaller
    (`sys.frozen` / `sys._MEIPASS`) para resolver rutas correctamente, en lugar de
    depender exclusivamente de `Path(__file__).resolve().parent.parent`.
  - El runtime hook (`scripts/rthook_noco_lib.py`) se mejoró para agregar todas las
    rutas de paquetes locales (`noco_lib`, `ai_lib`, `modules`, `app_core`, `shared`)
    a `sys.path` en el entorno empaquetado.

### Changed

- **`tardis/build.py`**: Se cambió `"pyinstaller"` por `sys.executable, "-m", "PyInstaller"`
  para evitar problemas cuando PyInstaller no está en el PATH del sistema.
- **`tardis/scripts/rthook_noco_lib.py`**: Reesrito completamente para soporte robusto
  de rutas en modo frozen, incluyendo debug tracing con `TARDIS_DEBUG=1`.
