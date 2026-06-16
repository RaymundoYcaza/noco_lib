# SPEC — Tardis Phase 6: Empaquetado, Versionado y Actualización Automática

> Self-contained document. Any LLM can pick it up without prior context.
> **Execution rule**: complete tasks **one at a time, in listed order**.
> Each task has Context / Steps / Verification / Depends on.
> **After finishing a task, the LLM MUST mark it `[x]` before proceeding.**
> Do not skip a task whose dependency is not yet `[x]`.
>
> **Language rule**: all code comments, docstrings, README files, inline
> documentation, and user-facing strings written or updated during this
> phase MUST be in Spanish. Task descriptions in this spec are in Spanish
> (for clarity), and every artifact produced must be documented in Spanish.

---

## 0. Context recap (do not redesign)

- **Tardis** is a PySide6 desktop app. Modules in `modules/<name>/`,
  each exposes `register(app: MainWindow, client: NocoClient) -> None`.
- **Current state** (Phases 1–5 complete): three-pane LocalMail (sidebar
  tree + email list + reader), App Switcher nav bar (52px left column),
  PDF Export screen, AI Corrections screen, Settings screen (Modules,
  Connection, Diagnostics, Apariencia, Firmas tabs). Theme Inorizonti
  (light with red accent). InboxNotifier with polling, sound, taskbar
  alerts. Email signatures. Attachments upload/download via NocoDB local
  storage (`signedPath`).
- **`noco_lib`** / **`NocoResult`**: abstraction over NocoDB v2.
- **`ai_lib`** / **`AIResult`**: abstraction over Ollama.
- **`pdf_export`**: `generate_pdf` / `generate_html`.
- **Golden rule**: I/O calls run inside `run_async()`, never in the Qt
  main thread. Exception: `generate_pdf` (drives own QEventLoop).
- **Logging**: `logging.getLogger("tardis")`. All log messages in Spanish.
- **Extension points**: `register_nav_item`, `add_floating_window`,
  `add_menu_action`, `show_notification`.
- **Version actual**: `0.1.0` (en `pyproject.toml`). Tag `v0.1.0-beta`.

---

## 1. Confirmed design decisions

### 1.1 Menu superior → botón hamburguesa (ROADMAP)

El menú superior (`QMenuBar`) actual se utiliza marginalmente (solo para
"LocalMail > Redactar", que ya fue reemplazado por el botón "+ Nuevo
mensaje" en la sidebar). Se eliminará por completo en esta fase.

A futuro (Phase 7+), se implementará un botón de menú tipo "hamburguesa"
(☰) en la esquina superior izquierda de la ventana, cuyo menú contendrá:
- Acciones globales (Configuración, Acerca de, Salir)
- Navegación rápida a módulos
- Ayuda / Documentación
- Versión de la aplicación

Este botón tendrá su propia spec dedicada cuando se implemente.

### 1.2 Formato de versión: `x.y.z.build`

Se adopta el formato **`x.y.z.build`** donde:
- `x` = Major (cambios incompatibles)
- `y` = Minor (nuevas funcionalidades)
- `z` = Patch (bugfixes)
- `build` = Número de compilación auto-incrementado en cada commit a `main`

El archivo fuente de la versión es `tardis/VERSION` (único punto de verdad).

### 1.3 Badge de versión

Se mostrará un badge con la versión en el panel de Configuración > Conexión
(esquina inferior del tab), visible siempre y con formato legible.

### 1.4 Distribución mediante PyInstaller

Se usará **PyInstaller** para empaquetar Tardis en un directorio
`.exe` + DLLs para Windows.

**Decisión de diseño: `--onedir` por defecto (NO `--onefile`).**

| Modo | Flag | Uso | Inicio |
|---|---|---|---|
| `--onedir` | _(por defecto)_ | Distribución estándar + installer | Rápido (sin extracción) |
| `--onefile` | `--portable` | USB / usuarios que prefieran 1 solo archivo | Lento (+3-10s extracción a `%TEMP%`) |

Razones:
- PySide6 pesa ~80-120MB; `--onefile` descomprime todo a `%TEMP%` cada
  vez que arrancas, añadiendo segundos al inicio.
- `--onedir` permite que `.env` esté junto al `.exe` de forma natural.
- Para actualización por ruta de red, reemplazar el `.exe` dentro de la
  carpeta es trivial sin tocar DLLs.
- Los antivirus generan menos falsos positivos con estructuras de
  directorio que con ejecutables autoextraíbles.

El script de build empaquetará:
- El código fuente compilado
- Los assets (temas, sonidos, fuentes, logos)
- `.env.example` (el usuario copia a `.env`)
- Un instalador opcional (Inno Setup)

### 1.5 Actualización automática desde ruta de red

Mecanismo de actualización por detección en ruta de red (drive virtual):

1. Al iniciar la app, se consulta una ruta configurable (por defecto
   `X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis`) buscando un archivo
   `VERSION` remoto.
2. Se compara la versión remota con la versión local.
3. Si la remota es mayor, se muestra un diálogo:
   > "Hay una nueva versión disponible: v{remota} (actual: v{local}).
   >   ¿Deseas descargar e instalar la actualización?"
4. Si el usuario acepta:
   - Se descarga el instalador `.exe` desde la ruta de red.
   - Se ejecuta el instalador en modo silencioso.
   - Tardis se cierra para permitir la instalación.
5. La ruta es configurable via variable de entorno
   `TARDIS_UPDATE_PATH` y también desde Settings > Apariencia (futuro).

**Informe de complejidad**: ver sección 5.

---

## 2. Nuevas dependencias

```toml
# Para compilación (dev only, no se incluye en distribución):
# pyinstaller>=6.0
# 
# Para actualización automática:
# requests>=2.31 (ya incluido)
# 
# No se requieren nuevas dependencias en runtime.
```

---

## 3. Nuevos / modificados archivos

```
tardis/
  VERSION                              # NEW: archivo de versión (único punto de verdad)
  build.py                             # NEW: script de build con PyInstaller
  installer/
    tardis_setup.iss                   # NEW: script Inno Setup (opcional)

app_core/
  version.py                           # NEW: utilidad de carga/versión
  updater.py                           # NEW: comprobación de actualización automática
  main.py                              # MODIFIED: eliminar menuBar(), agregar badge versión
  main_window.py                       # MODIFIED: eliminar menuBar() y add_menu_action()
  views/
    settings_view.py                   # MODIFIED: agregar badge de versión en Conexión

.github/
  workflows/
    build.yml                          # NEW: GitHub Action para build automático

scripts/
  bump_version.py                      # NEW: script para auto-incrementar build number
  test_update_path.py                  # NEW: script de prueba de ruta de actualización

pyproject.toml                         # MODIFIED: sync version con VERSION file
```

---

## 4. PLAN DE TAREAS (checklist — ejecutar en orden, marcar `[x]` al terminar)

### 13.0 — Sistema de versionado

- [x] **13.0.1** Crear `tardis/VERSION` como archivo de versión único.

      Context:
      Necesitamos un único punto de verdad para la versión de la aplicación.
      El archivo `VERSION` en la raíz de `tardis/` contendrá una línea con
      el formato `x.y.z.build`.

      Steps:
      1. Crear `tardis/VERSION` con contenido:
         ```
         0.1.0.1
         ```
      2. Crear `tardis/app_core/version.py` con:
         ```python
         from pathlib import Path

         _version_file = Path(__file__).resolve().parent.parent / "VERSION"

         def load_version() -> str:
             \"\"\"Lee y retorna el string de versión desde VERSION.\"\"\"
             try:
                 return _version_file.read_text(encoding="utf-8").strip()
             except FileNotFoundError:
                 return "0.0.0.0"

         def get_version_parts() -> tuple[int, int, int, int]:
             \"\"\"Retorna (major, minor, patch, build).\"\"\"
             parts = load_version().split(".")
             if len(parts) != 4:
                 return (0, 0, 0, 0)
             try:
                 return tuple(int(p) for p in parts)  # type: ignore[return-value]
             except ValueError:
                 return (0, 0, 0, 0)

         def set_build(build: int) -> None:
             \"\"\"Actualiza solo el número de build en VERSION.\"\"\"
             major, minor, patch, _ = get_version_parts()
             _version_file.write_text(f"{major}.{minor}.{patch}.{build}\n", encoding="utf-8")
         ```
      3. Crear `scripts/bump_version.py`:
         ```python
         \"\"\"
         Script que incrementa el número de build en tardis/VERSION.
         Uso: python scripts/bump_version.py
         Se ejecuta automáticamente en CI/CD antes de cada commit a main.
         \"\"\"
         import sys
         from pathlib import Path
         sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tardis"))
         from app_core.version import get_version_parts, set_build

         def main():
             _, _, _, build = get_version_parts()
             set_build(build + 1)
             print(f"Build incrementado a {build + 1}")

         if __name__ == "__main__":
             main()
         ```
      4. Sincronizar `pyproject.toml`: leer `VERSION` y usar ese valor
         para `project.version`. Se puede hacer manualmente o mediante
         un script de pre-build.

      Verification:
      ```bash
      cd tardis && python -c "from app_core.version import load_version; print(load_version())"
      ```
      Debe imprimir `0.1.0.1`.
      Ejecutar `python scripts/bump_version.py` y verificar que `VERSION`
      ahora contiene `0.1.0.2`.
      Depends on: none.

- [x] **13.0.2** Configurar GitHub Action para auto-incrementar build en
      cada push a `main`.

      Context:
      Cada vez que se haga push a la rama `main`, el CI debe:
      1. Ejecutar `scripts/bump_version.py`.
      2. Hacer commit del archivo `VERSION` actualizado.
      3. Crear una tag `v{major}.{minor}.{patch}.{build}`.
      4. Disparar el build de distribución (tarea 13.2.x).

      Steps:
      1. Crear `.github/workflows/build.yml`:
         ```yaml
         name: Build Tardis

         on:
           push:
             branches: [ main ]

         jobs:
           bump-version:
             runs-on: windows-latest
             steps:
               - uses: actions/checkout@v4
               - name: Set up Python
                 uses: actions/setup-python@v5
                 with:
                   python-version: '3.13'
               - name: Increment build number
                 run: python scripts/bump_version.py
               - name: Commit VERSION bump
                 run: |
                   git config user.name "Tardis CI"
                   git config user.email "ci@tardis.app"
                   git add tardis/VERSION
                   git commit -m "chore: bump build number [skip ci]" || echo "No changes to commit"
                   git push
               - name: Create tag
                 run: |
                   $version = Get-Content tardis/VERSION -Raw
                   git tag "v$version"
                   git push origin "v$version"
           build:
             needs: bump-version
             runs-on: windows-latest
             steps:
               - uses: actions/checkout@v4
                 with:
                   ref: main
               - name: Build with PyInstaller
                 run: python build.py
               - name: Upload artifact
                 uses: actions/upload-artifact@v4
                 with:
                   name: Tardis-${{ github.ref_name }}
                   path: dist/
         ```
      2. No implementar aún — esbozar el workflow. La implementación
         detallada se hará en tarea 13.2.x junto con el script de build.

      Verification: el workflow YAML existe en `.github/workflows/build.yml`.
      Depends on: 13.0.1.

### 13.1 — Eliminación del menú superior + badge de versión

- [x] **13.1.1** Eliminar `QMenuBar` de `MainWindow`.

      Context:
      El menú superior (`QMenuBar`) ya no se usa. No hay acciones de menú
      registradas actualmente (la única era "LocalMail > Redactar" que fue
      reemplazada por el botón "+ Nuevo mensaje" en la sidebar).
      Se elimina el `menuBar()` y el método `add_menu_action`.

      Steps:
      1. En `app_core/main_window.py`:
         - Eliminar `QMenuBar` de los imports.
         - Eliminar el método `add_menu_action(self, menu_path, label, callback)`.
         - NO eliminar `add_toolbar_action` (puede usarse en el futuro).
         - Si `menuBar()` se llama en algún lugar (por ejemplo para ocultarlo),
           reemplazar con `self.menuBar().hide()` o eliminar la llamada.
      2. Buscar referencias a `add_menu_action` en todo el proyecto:
         ```bash
         grep -r "add_menu_action" --include="*.py"
         ```
         Si hay alguna referencia (ej. en `modules/localmail/module.py`),
         eliminarla o comentarla.
      3. Agregar un comentario en el código (`_init_ui` o similar):
         ```python
         # NOTA: El menú superior fue eliminado en Phase 6.
         # Roadmap: en Phase 7+ se implementará un botón hamburguesa (☰)
         # con su propia spec dedicada.
         ```
      4. Agregar entrada en el roadmap de `EXTENSION_POINTS.md` (sección 6)
         indicando que el menú superior fue eliminado y será reemplazado
         por un botón hamburguesa en una fase futura.

      Verification:
      Ejecutar Tardis — no debe haber barra de menú en la parte superior
      de la ventana. `add_menu_action` ya no existe como método de
      `MainWindow`. `grep -r "add_menu_action" --include="*.py"` retorna 0.
      Depends on: none.

- [x] **13.1.2** Agregar badge de versión en Configuración > Conexión.

      Context:
      El usuario debe poder ver la versión de la aplicación fácilmente.
      El lugar más apropiado es el tab "Conexión" de Configuración, donde
      ya se muestran datos de configuración de solo lectura.

      Steps:
      1. En `app_core/views/settings_view.py`, en `_build_connection_tab`:
         - Al final del layout (después de todos los grupos, antes de
           `layout.addStretch()`), agregar un `QGroupBox("Acerca de")`.
         - Dentro del grupo:
           ```python
           version_group = QGroupBox("Acerca de")
           version_layout = QVBoxLayout(version_group)
           badge = QLabel(f"🛸 Tardis v{load_version()}")
           badge.setStyleSheet("""
               font-size: 20px; font-weight: bold;
               color: #e9290c; padding: 16px;
               background: #f5f3f0; border-radius: 8px;
           """)
           badge.setAlignment(Qt.AlignCenter)
           version_layout.addWidget(badge)
           ```
         - Importar `load_version` desde `app_core.version`.
         - Opcional: agregar tooltip con los números de versión
           desglosados (Major.Minor.Patch.Build).

      Verification:
      Abrir Tardis > Configuración > Conexión — debe verse un badge
      rojo con "🛸 Tardis v0.1.0.1" al final del tab.
      Depends on: 13.0.1, 13.1.1.

- [x] **13.1.3** **CHECKPOINT — Versionado y badge**: verificar:
      1. `VERSION` file existe y es legible.
      2. `load_version()` funciona desde cualquier punto del proyecto.
      3. Badge visible en Configuración > Conexión con formato correcto.
      4. No hay `menuBar()` visible en la ventana principal.
      5. `add_menu_action` eliminado de `MainWindow`.
      Depends on: 13.1.2.

### 13.2 — Script de compilación (PyInstaller)

- [x] **13.2.1** Crear `tardis/build.py` para empaquetar con PyInstaller.

      Context:
      Necesitamos un script reproducible que empaquete Tardis en un
      ejecutable único para distribución a usuarios Windows.
      PyInstaller es la herramienta estándar para aplicaciones PySide6.

      Steps:
      1. Instalar PyInstaller (solo dev):
         ```bash
         pip install pyinstaller
         ```
      2. Crear `tardis/build.py`:
         ```python
         \"\"\"
         Script de build para Tardis.
         Empaqueta la aplicación en un ejecutable Windows (.exe)
         usando PyInstaller.

         Uso:
             python build.py                  # Build estándar (--onedir, fast)
             python build.py --portable       # Build en un solo .exe (--onefile, lento al inicio)
             python build.py --installer      # Build + generar installer Inno Setup

         Nota:
             El modo por defecto es --onedir por velocidad de inicio.
             --portable (--onefile) solo para memorias USB o casos
             donde un solo archivo sea estrictamente necesario.

         Variables de entorno:
             TARDIS_BUILD_VERSION: override de versión (opcional)
         \"\"\"
         import os
         import sys
         import subprocess
         import shutil
         from pathlib import Path

         # ── Rutas ─────────────────────────────────────────────────
         ROOT = Path(__file__).resolve().parent
         DIST_DIR = ROOT / "dist"
         BUILD_DIR = ROOT / "build"
         ASSETS_DIR = ROOT / "shared"

         # ── Versión ───────────────────────────────────────────────
         sys.path.insert(0, str(ROOT))
         from app_core.version import load_version

         VERSION = os.environ.get("TARDIS_BUILD_VERSION") or load_version()

         # ── PyInstaller args ──────────────────────────────────────
         def build_portable():
             \"\"\"Build en un solo .exe (portable).\"\"\"
             cmd = [
                 "pyinstaller",
                 "--onefile",
                 "--windowed",  # sin consola
                 "--name", f"Tardis-v{VERSION}",
                 "--distpath", str(DIST_DIR),
                 "--workpath", str(BUILD_DIR),
                 "--specpath", str(BUILD_DIR),
                 "--add-data", f"{ASSETS_DIR}{os.pathsep}shared",
                 "--icon", str(ROOT / "shared" / "brands" / "inorizonti" / "logo.ico"),
                 "--hidden-import", "PySide6.QtSvg",
                 "--hidden-import", "PySide6.QtWebEngineWidgets",
                 "--hidden-import", "qtawesome",
                 str(ROOT / "app_core" / "main.py"),
             ]
             print(f"Ejecutando: {' '.join(cmd)}")
             subprocess.run(cmd, check=True)

         def build_dir():
             \"\"\"Build en directorio (más rápido para debug).\"\"\"
             cmd = [
                 "pyinstaller",
                 "--onedir",
                 "--windowed",
                 "--name", f"Tardis-v{VERSION}",
                 "--distpath", str(DIST_DIR),
                 "--workpath", str(BUILD_DIR),
                 "--specpath", str(BUILD_DIR),
                 "--add-data", f"{ASSETS_DIR}{os.pathsep}shared",
                 "--icon", str(ROOT / "shared" / "brands" / "inorizonti" / "logo.ico"),
                 "--hidden-import", "PySide6.QtSvg",
                 "--hidden-import", "PySide6.QtWebEngineWidgets",
                 "--hidden-import", "qtawesome",
                 str(ROOT / "app_core" / "main.py"),
             ]
             print(f"Ejecutando: {' '.join(cmd)}")
             subprocess.run(cmd, check=True)

         def build_installer():
             \"\"\"Genera también el instalador Inno Setup.\"\"\"
             build_dir()
             # Generar .iss y compilar
             iss_path = ROOT / "installer" / "tardis_setup.iss"
             if iss_path.exists():
                 subprocess.run(["iscc", str(iss_path)], check=True)
             else:
                 print("Advertencia: no se encontró installer/tardis_setup.iss")

         if __name__ == "__main__":
             if "--portable" in sys.argv:
                 build_portable()
             elif "--installer" in sys.argv:
                 build_installer()
             else:
                 build_dir()
         ```
      3. Crear `tardis/installer/tardis_setup.iss` (opcional):
         ```
         ; Script Inno Setup para Tardis
         ; Requiere Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

         [Setup]
         AppName=Tardis
         AppVersion={#VERSION}
         DefaultDirName={autopf}\Tardis
         DefaultGroupName=Tardis
         UninstallDisplayIcon={app}\Tardis.exe
         Compression=lzma2
         SolidCompression=yes
         OutputDir=..\dist\installer
         OutputBaseFilename=Tardis-v{#VERSION}-Setup

         [Files]
         Source: "..\dist\Tardis-v{#VERSION}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

         [Icons]
         Name: "{group}\Tardis"; Filename: "{app}\Tardis-v{#VERSION}.exe"
         Name: "{group}\Uninstall Tardis"; Filename: "{uninstallexe}"
         ```
      4. Agregar `build/`, `dist/`, `*.spec` al `.gitignore`.
      5. Probar el build localmente:
         ```bash
         cd tardis && pip install pyinstaller && python build.py
         ```

      Verification:
      `python build.py` genera un ejecutable funcional en `tardis/dist/`.
      El ejecutable inicia Tardis correctamente (ventana se abre, splash
      se muestra, módulos cargan). No aparecen ventanas de consola.
      Depends on: 13.0.1.

- [x] **13.2.2** Preparar assets para distribución: logo.ico y .env.example.

      Context:
      Para el build necesitamos:
      - Un archivo `.ico` del logo (para el icono del .exe).
      - Un `.env.example` que el usuario copia a `.env`.

      Steps:
      1. Convertir `shared/brands/inorizonti/logo.svg` a `logo.ico`
         (herramienta online o script Python con `cairosvg` + `pillow`).
         Guardar en `shared/brands/inorizonti/logo.ico`.
      2. Crear `tardis/.env.example`:
         ```env
         # ── NocoDB ─────────────────────────────────────────
         NOCO_BASE_URL=https://tu-servidor.nocodb.com
         NOCO_TOKEN=tu-token-de-api
         NOCO_BASE_ID=id-de-tu-base

         # ── LocalMail ───────────────────────────────────────
         TARDIS_MAILBOXES=usuario1@empresa.com;usuario2@empresa.com
         TARDIS_LOCALMAIL_TABLE=DIR_LOCAL-MAIL

         # ── Notificaciones ──────────────────────────────────
         TARDIS_POLL_INTERVAL_SECONDS=60

         # ── Adjuntos ────────────────────────────────────────
         TARDIS_MAX_ATTACHMENT_MB=10

         # ── IA (opcional) ───────────────────────────────────
         TARDIS_AI_PROVIDER=ollama
         TARDIS_AI_MODEL=gemma3:27b
         TARDIS_AI_BASE_URL=http://localhost:11434

         # ── Actualizaciones (Phase 6+) ──────────────────────
         TARDIS_UPDATE_PATH=X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis
         ```
      3. En `build.py`, incluir `.env.example` en el bundle:
         Agregar `--add-data` para incluir `.env.example` en la raíz
         del ejecutable.
      4. En `app_core/config.py`, modificar `load_tardis_config` para
         que cuando `sys.frozen` es True (ejecutable compilado), busque
         `.env` en el directorio del ejecutable (ya implementado — ver
         línea `if getattr(sys, 'frozen', False):`).

      Verification:
      El build incluye `.env.example`. Al ejecutar el .exe compilado,
      si no hay `.env` junto al .exe, la app muestra error de conexión
      (esperado). El usuario copia `.env.example` a `.env`, configura
      sus credenciales, y Tardis funciona.
      Depends on: 13.2.1.

- [x] **13.2.3** **CHECKPOINT — Build**: verificar:
      1. `python build.py` genera ejecutable funcional (carpeta).
      2. `python build.py --portable` genera un único .exe portable
         (inicio más lento, para USB).
      3. El .exe no muestra consola (ventana oculta).
      4. Al copiar `.env.example` a `.env` y configurar credenciales,
         Tardis inicia y se conecta a NocoDB correctamente.
      5. Los assets compartidos (sonidos, temas, logos, templates) se
         cargan correctamente desde dentro del bundle.
      Depends on: 13.2.2.

### 13.3 — Actualización automática desde ruta de red

- [ ] **13.3.1** Crear `app_core/updater.py`.

      Context:
      Mecanismo de detección de nuevas versiones consultando un archivo
      `VERSION` en una ruta de red configurable.

      Steps:
      1. Crear `app_core/updater.py`:
         ```python
         \"\"\"
         Módulo de actualización automática de Tardis.

         Consulta una ruta de red (o local) configurable en busca de
         nuevas versiones. Si la versión remota es mayor, solicita
         confirmación al usuario para descargar e instalar.

         Variables de entorno:
             TARDIS_UPDATE_PATH (default: X:\\B02_SOFTWARE-LIBRARY\\00-INTERNOS\\Tardis)
         \"\"\"
         import os
         import sys
         import logging
         import subprocess
         from pathlib import Path

         from app_core.version import load_version, get_version_parts

         logger = logging.getLogger("tardis")

         def get_update_path() -> Path:
             \"\"\"Retorna la ruta configurada para buscar actualizaciones.\"\"\"
             raw = os.environ.get(
                 "TARDIS_UPDATE_PATH",
                 r"X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis",
             )
             return Path(raw)

         def check_for_updates() -> str | None:
             \"\"\"
             Compara la versión local con la remota.

             Returns
             -------
             str | None
                 La versión remota (string) si hay una actualización
                 disponible, o None si ya estamos en la última versión
                 o si no se pudo contactar la ruta de red.
             \"\"\"
             update_dir = get_update_path()
             remote_version_file = update_dir / "VERSION"

             if not remote_version_file.exists():
                 logger.debug(
                     "Ruta de actualización no disponible: %s",
                     remote_version_file,
                 )
                 return None

             try:
                 remote_version = remote_version_file.read_text(
                     encoding="utf-8"
                 ).strip()
             except Exception as exc:
                 logger.warning("Error al leer VERSION remoto: %s", exc)
                 return None

             if not remote_version:
                 return None

             # Comparar versiones
             local = get_version_parts()
             try:
                 remote_parts = tuple(int(p) for p in remote_version.split("."))
             except (ValueError, AttributeError):
                 logger.warning("Formato de versión remota inválido: %s", remote_version)
                 return None

             # Normalizar a 4 partes
             while len(remote_parts) < 4:
                 remote_parts = (*remote_parts, 0)

             if remote_parts > local:
                 logger.info(
                     "Nueva versión disponible: %s (local: %s)",
                     remote_version,
                     load_version(),
                 )
                 return remote_version

             logger.debug("Ya estamos en la última versión.")
             return None

         def download_and_install(remote_version: str) -> bool:
             \"\"\"
             Descarga e instala la nueva versión desde la ruta de red.

             Returns
             -------
             bool
                 True si se inició la instalación correctamente.
             \"\"\"
             update_dir = get_update_path()
             installer_name = f"Tardis-v{remote_version}-Setup.exe"
             installer_path = update_dir / installer_name

             if not installer_path.exists():
                 # Fallback: buscar el .exe portable
                 portable_name = f"Tardis-v{remote_version}.exe"
                 installer_path = update_dir / portable_name
                 if not installer_path.exists():
                     logger.error(
                         "Instalador no encontrado: %s ni %s",
                         update_dir / installer_name,
                         update_dir / portable_name,
                     )
                     return False

             try:
                 logger.info("Ejecutando instalador: %s", installer_path)
                 if sys.platform == "win32":
                     subprocess.Popen(
                         [str(installer_path), "/SILENT", f"/D={Path(sys.executable).parent}"],
                         shell=True,
                     )
                 else:
                     subprocess.Popen(["xdg-open", str(installer_path)])
                 return True
             except Exception as exc:
                 logger.exception("Error al ejecutar instalador: %s", exc)
                 return False
         ```

      Verification:
      ```python
      python -c "from app_core.updater import check_for_updates; print(check_for_updates())"
      ```
      Si la ruta de red no existe, retorna `None`.
      Si existe un `VERSION` remoto con versión mayor, retorna el string.
      Depends on: 13.0.1.

- [ ] **13.3.2** Integrar el updater en `main.py` con diálogo de confirmación.

      Context:
      Al iniciar Tardis, después de cargar todos los módulos y mostrar
      la ventana, se debe consultar si hay actualizaciones. Si las hay,
      se muestra un `QMessageBox` con opciones "Sí" / "No".

      Steps:
      1. En `app_core/main.py`, al final de `main()` (después de
         `window.showMaximized()` y antes del event loop), agregar:
         ```python
         # ── 12. Verificar actualizaciones (Phase 6) ────────────
         from app_core.updater import check_for_updates, download_and_install
         try:
             remote_ver = check_for_updates()
             if remote_ver:
                 local_ver = load_version()
                 reply = QMessageBox.question(
                     window,
                     "Actualización disponible",
                     f"Hay una nueva versión de Tardis disponible:\n\n"
                     f"  Actual:  v{local_ver}\n"
                     f"  Nueva:    v{remote_ver}\n\n"
                     "¿Deseas descargar e instalar la actualización?",
                     QMessageBox.Yes | QMessageBox.No,
                     QMessageBox.Yes,
                 )
                 if reply == QMessageBox.Yes:
                     download_and_install(remote_ver)
                     sys.exit(0)  # Cerrar Tardis para permitir instalación
         except Exception as exc:
             logger.warning("Error al verificar actualizaciones: %s", exc)
         ```
      2. Agregar imports necesarios:
         ```python
         from PySide6.QtWidgets import QMessageBox
         from app_core.version import load_version
         ```
      3. El chequeo debe ejecutarse con un `QTimer.singleShot(3000, ...)`
         para no retrasar la apertura de la ventana:
         ```python
         QTimer.singleShot(3000, lambda: _check_updates(window))
         ```
         Crear una función auxiliar `_check_updates(window)` con la
         lógica anterior.

      Verification:
      - Configurar `TARDIS_UPDATE_PATH` apuntando a un directorio local
        de prueba.
      - Crear un `VERSION` remoto con `9.9.9.999`.
      - Iniciar Tardis → después de 3 segundos, aparece diálogo:
        "Hay una nueva versión disponible: v9.9.9.999 (actual: v0.1.0.1)".
      - Hacer clic en "Sí" → Tardis se cierra.
      - Hacer clic en "No" → el diálogo se cierra y Tardis continúa.
      - Sin `TARDIS_UPDATE_PATH` configurado → no hay diálogo, no hay error.
      Depends on: 13.3.1.

- [ ] **13.3.3** Agregar configuración de ruta de actualización en Settings.

      Context:
      El usuario debe poder ver y cambiar la ruta de actualización desde
      la UI (Settings > Apariencia o una nueva sección).

      Steps:
      1. En `app_core/views/settings_view.py`, en `_build_appearance_tab`,
         después del grupo de "Notificaciones", agregar:
         ```python
         # ── Actualizaciones ──
         update_group = QGroupBox("Actualizaciones")
         update_layout = QVBoxLayout(update_group)

         update_desc = QLabel(
             "Ruta donde Tardis busca nuevas versiones.\n"
             "Puede ser una unidad de red (X:), local (C:) o disco externo."
         )
         update_desc.setWordWrap(True)
         update_desc.setStyleSheet("color: #5a5a56;")
         update_layout.addWidget(update_desc)

         path_row = QHBoxLayout()
         self._update_path = QLineEdit()
         self._update_path.setText(
             os.environ.get(
                 "TARDIS_UPDATE_PATH",
                 r"X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis",
             )
         )
         path_row.addWidget(self._update_path, stretch=1)

         self._update_path_save = QPushButton("Guardar ruta")
         self._update_path_save.clicked.connect(self._on_save_update_path)
         path_row.addWidget(self._update_path_save)
         update_layout.addLayout(path_row)

         # Botón "Buscar actualizaciones ahora"
         self._check_updates_btn = QPushButton("Buscar actualizaciones ahora")
         self._check_updates_btn.clicked.connect(self._on_check_updates_now)
         update_layout.addWidget(self._check_updates_btn)

         # Label de resultado
         self._update_result = QLabel("")
         self._update_result.setWordWrap(True)
         update_layout.addWidget(self._update_result)

         layout.addWidget(update_group)
         ```
      2. Implementar `_on_save_update_path`:
         ```python
         def _on_save_update_path(self) -> None:
             \"\"\"Guarda la ruta de actualización en variables de entorno y QSettings.\"\"\"
             path = self._update_path.text().strip()
             if not path:
                 QMessageBox.warning(self, "Validación", "La ruta no puede estar vacía.")
                 return
             # Persistir en QSettings para el próximo inicio
             from PySide6.QtCore import QSettings
             settings = QSettings("Tardis", "Tardis")
             settings.setValue("updates/update_path", path)
             # También establecer en entorno para la sesión actual
             os.environ["TARDIS_UPDATE_PATH"] = path
             self._main_window.show_notification(
                 "Ruta de actualización guardada. Se usará en el próximo inicio.",
                 "success",
             )
         ```
      3. En `app_core/updater.py`, modificar `get_update_path()` para
         leer primero de `QSettings` y luego de variable de entorno:
         ```python
         def get_update_path() -> Path:
             \"\"\"Retorna la ruta configurada.\"\"\"
             # 1. QSettings (configurado por el usuario en Settings)
             from PySide6.QtCore import QSettings
             settings = QSettings("Tardis", "Tardis")
             qs_path = settings.value("updates/update_path")
             if qs_path:
                 return Path(qs_path)
             # 2. Variable de entorno
             raw = os.environ.get(
                 "TARDIS_UPDATE_PATH",
                 r"X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis",
             )
             return Path(raw)
         ```
      4. Implementar `_on_check_updates_now`:
         ```python
         def _on_check_updates_now(self) -> None:
             \"\"\"Busca actualizaciones ahora y muestra el resultado.\"\"\"
             from app_core.updater import check_for_updates, download_and_install
             from app_core.version import load_version

             def _do_check():
                 remote = check_for_updates()
                 if remote:
                     reply = QMessageBox.question(
                         self,
                         "Actualización disponible",
                         f"Hay una nueva versión: v{remote}\n"
                         f"(actual: v{load_version()})\n\n"
                         "¿Descargar e instalar ahora?",
                         QMessageBox.Yes | QMessageBox.No,
                     )
                     if reply == QMessageBox.Yes:
                         if download_and_install(remote):
                             self._main_window.show_notification(
                                 "Instalando actualización...", "info"
                             )
                             # Cerrar Tardis
                             self._main_window.close()
                         else:
                             self._set_update_result(
                                 "Error al descargar la actualización.", "error"
                             )
                     else:
                         self._set_update_result(
                             "Actualización cancelada por el usuario.", "info"
                         )
                 else:
                     self._set_update_result(
                         f"Ya tienes la última versión (v{load_version()}).", "success"
                     )

             run_async(_do_check)
         ```

      Verification:
      Abrir Settings > Apariencia → sección "Actualizaciones" visible.
      La ruta por defecto aparece en el campo de texto. Cambiar la ruta
      y hacer clic en "Guardar ruta" → toast de confirmación.
      Cerrar y reabrir Tardis → la ruta guardada persiste.
      Hacer clic en "Buscar actualizaciones ahora" → mensaje de resultado.
      Depends on: 13.3.2.

- [ ] **13.3.4** **CHECKPOINT — Actualizaciones**: verificar:
      1. Sin ruta configurada: Tardis inicia sin diálogo, sin errores.
      2. Con ruta configurada y VERSION remoto con versión superior:
         diálogo aparece después de 3 segundos.
      3. "Sí" → Tardis se cierra.
      4. "No" → Tardis continúa normalmente.
      5. "Buscar actualizaciones ahora" en Settings funciona
         independientemente de la comprobación automática.
      6. La ruta es persistente entre reinicios.
      Depends on: 13.3.3.

### 13.4 — Roadmap y documentación

- [ ] **13.4.1** Actualizar `EXTENSION_POINTS.md` con los cambios de Phase 6.

      Steps:
      1. En la sección de Roadmap (al final del documento), agregar:
         ```markdown
         ### Phase 6 — Empaquetado, versionado y actualización automática (completada)
         - Menú superior eliminado.
         - Sistema de versionado `x.y.z.build` con auto-incremento en CI.
         - Badge de versión en Configuración > Conexión.
         - Script de build con PyInstaller (`build.py`).
         - Actualización automática desde ruta de red configurable.
         - Spec: `specs/1781569500000_tardis-spec-phase6/README.md`.

         ### Phase 7 — Botón de menú hamburguesa (☰) (pendiente de spec)
         - Reemplazar el menú superior eliminado en Phase 6.
         - Menú desplegable desde esquina superior izquierda.
         - Acceso rápido a módulos, Configuración, Acerca de, Salir.
         - Spec dedicada en desarrollo.
         ```
      2. En la sección de `MainWindow.add_menu_action`, marcar como
         `ELIMINADO en Phase 6`.

      Verification:
      `EXTENSION_POINTS.md` refleja el nuevo estado del proyecto y el
      roadmap a futuro.
      Depends on: 13.3.4.

- [ ] **13.4.2** Actualizar `README.md` principal con instrucciones de
      instalación y actualización.

      Steps:
      1. Agregar sección "Instalación" al `README.md`:
         - Descargar el instalador desde la ruta de red.
         - Ejecutar `Tardis-vX.X.X.X-Setup.exe`.
         - Copiar `.env.example` a `.env` y configurar.
         - Ejecutar Tardis.
      2. Agregar sección "Actualización":
         - Tardis busca actualizaciones automáticamente al iniciar.
         - Configurar `TARDIS_UPDATE_PATH` en `.env` o desde Settings.
         - Aceptar el diálogo de actualización cuando aparezca.
      3. Agregar sección "Compilación desde código fuente":
         ```bash
         git clone <repo>
         cd tardis
         pip install -r requirements.txt
         pip install pyinstaller
         python build.py
         ```

      Verification:
      `README.md` contiene instrucciones claras para instalación,
      actualización y compilación.
      Depends on: 13.4.1.

---

## 5. Informe de complejidad — Actualización automática desde ruta de red

### Evaluación

| Aspecto | Complejidad | Justificación |
|---|---|---|
| **Lectura de VERSION remoto** | 🟢 Baja | `Path.read_text()` sobre ruta UNC/letra de unidad. Misma API que archivo local. |
| **Comparación de versiones** | 🟢 Baja | Tupla de enteros, comparación directa. |
| **Diálogo de confirmación** | 🟢 Baja | `QMessageBox.question()` estándar. |
| **Ejecución del instalador** | 🟡 Media | `subprocess.Popen` con `/SILENT` en Windows. Requiere que el instalador soporte modo silencioso (Inno Setup lo soporta nativamente con `/SILENT` y `/VERYSILENT`). |
| **Persistencia de ruta** | 🟢 Baja | `QSettings` + variable de entorno. Ya implementado en otras partes del código. |
| **Manejo de errores** | 🟢 Baja | `try/except` en cada operación de red. El fallo no debe impedir que Tardis inicie. |
| **Ruta de red no disponible** | 🟢 Baja | `Path.exists()` retorna `False` si la unidad no está montada. Se maneja con `logger.debug` y retorno `None`. |
| **Instalador no encontrado** | 🟢 Baja | Verificar existencia antes de ejecutar. Mostrar error en log. |
| **CI/CD integration** | 🟡 Media | GitHub Action necesita Windows runner para build. El bump de versión es trivial. |
| **Seguridad** | 🟡 Media | El instalador se ejecuta desde una ruta de red. En entornos corporativos, la ruta `X:\` suele ser segura (admin gestiona). Se podría agregar verificación de hash SHA256 en el futuro. |

### Veredicto

**Complejidad general: BAJA-MEDIA.** El mecanismo es simple porque:

1. No requiere servidor web, API REST, ni backend de actualizaciones.
2. Usa solo el sistema de archivos local/de red (`Path.read_text`, `Path.exists`).
3. No requiere autenticación (la ruta de red ya está asegurada por el
   administrador del sistema).
4. PyInstaller + Inno Setup son herramientas maduras y bien documentadas.
5. El auto-incremento de build en CI/CD es un script Python de 10 líneas.

**Recomendación: IMPLEMENTAR.** El valor para el usuario es alto
(actualización con un clic, sin búsqueda manual) y el costo de
implementación es bajo (~1 día de trabajo para todos los componentes).

### Riesgos identificados

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| La unidad X: no está montada al iniciar Tardis | Alta | El chequeo falla silenciosamente (`logger.debug`). No hay bloqueo ni error visible. |
| El instalador requiere permisos de administrador | Media | Inno Setup puede configurarse para instalar por usuario (`privilegesRequired=lowest`). Evaluar en Phase 6b. |
| El usuario cambia la unidad de red | Baja | La ruta es configurable desde Settings. |
| El archivo VERSION remoto tiene formato inválido | Baja | `try/except` con `logger.warning`. Retorno `None` seguro. |

---

## 6. ROADMAP (futuro, no implementado aquí)

### Phase 6b — Mejoras al sistema de actualización (spec pendiente)
- Verificación de integridad: hash SHA256 del instalador.
- Descarga parcial o reanudable (si el instalador es grande).
- Canales de actualización: stable / beta / nightly.
- Rollback a versión anterior.

### Phase 7 — Botón de menú hamburguesa (spec pendiente)
- Reemplazar el menú superior eliminado en Phase 6.
- Menú desplegable con acceso a módulos, Configuración, Acerca de, Salir.
- Versión de la app en el menú.
- Atajos de teclado (Ctrl+Q para salir, etc.).
- Spec dedicada en desarrollo.

### Phase 8 — Temas múltiples y selector (spec pendiente)
- Selector de tema en Settings > Apariencia.
- Temas adicionales (oscuro, alto contraste).
- Live theme switching sin reinicio.
- Editor de temas (colores personalizados).
