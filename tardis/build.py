"""
Script de build para Tardis.
Empaqueta la aplicación en un ejecutable Windows (.exe) usando PyInstaller.

Uso:
    python build.py                  # Build estándar (--onedir, rápido)
    python build.py --portable       # Build en un solo .exe (--onefile, lento al inicio)
    python build.py --installer      # Build + generar installer Inno Setup

Nota:
    El modo por defecto es --onedir por velocidad de inicio.
    --portable (--onefile) solo para memorias USB o casos
    donde un solo archivo sea estrictamente necesario.

Variables de entorno:
    TARDIS_BUILD_VERSION: override de versión (opcional)

Nota sobre el icono (.ico):
    Para generar un logo.ico real a partir del SVG, instalar cairosvg:
        pip install cairosvg
        python -c "
    import cairosvg
    from pathlib import Path
    svg = Path('shared/brands/inorizonti/logo.svg').read_text()
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=256, output_height=256)
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(png))
    img.save('shared/brands/inorizonti/logo.ico', format='ICO', sizes=[(256, 256)])
        "
    Si no se instala cairosvg, se usará un placeholder rojo.
"""

import os
import sys
import subprocess
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ASSETS_DIR = ROOT / "shared"
ENV_EXAMPLE = ROOT / ".env.example"

# ── Versión ───────────────────────────────────────────────
sys.path.insert(0, str(ROOT))
from app_core.version import load_version  # type: ignore[import]

VERSION = os.environ.get("TARDIS_BUILD_VERSION") or load_version()


def _base_cmd() -> list[str]:
    """Construye la lista base de argumentos para PyInstaller."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--windowed",  # sin consola
        "--name", "Tardis",  # nombre neutral — la versión va en el instalador
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--add-data", f"{ASSETS_DIR}{os.pathsep}shared",
        "--add-data", f"{ROOT / 'noco_lib'}{os.pathsep}noco_lib",
        "--add-data", f"{ROOT / 'ai_lib'}{os.pathsep}ai_lib",
        # modules/ como datos garantiza que pkgutil.iter_modules() funcione
        "--add-data", f"{ROOT / 'modules'}{os.pathsep}modules",
        "--paths", str(ROOT),  # tardis/ — para que PyInstaller analice imports de modules/
        "--runtime-hook", str(ROOT / "scripts" / "rthook_noco_lib.py"),
        # Paquetes locales cargados dinámicamente (importlib / pkgutil)
        "--hidden-import", "modules.localmail",
        "--hidden-import", "modules.pdf_export",
        "--hidden-import", "modules.ai_corrections",
        # Dependencias de terceros usadas por noco_lib, ai_lib y módulos
        "--hidden-import", "requests",
        "--hidden-import", "jsonschema",
        "--hidden-import", "dotenv",
        "--hidden-import", "qtawesome",
        "--hidden-import", "markupsafe",
        # Paquetes pesados: collect-all recoge submodules, datos y binarios
        "--collect-all", "reportlab",
        "--collect-all", "mistune",
        "--collect-all", "pikepdf",
        "--collect-all", "jinja2",
        # Qt extras
        "--hidden-import", "PySide6.QtSvg",
        "--hidden-import", "PySide6.QtSvgWidgets",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "PySide6.QtWebEngineCore",
        "--hidden-import", "PySide6.QtMultimedia",
        "--hidden-import", "PySide6.QtPrintSupport",
        # Recolectar plugins Qt SVG para que QSvgRenderer funcione
        "--collect-binaries", "PySide6.QtSvg",
    ]
    # Icono
    ico = ROOT / "shared" / "brands" / "inorizonti" / "logo.ico"
    if ico.exists():
        cmd.extend(["--icon", str(ico)])
    # .env.example
    if ENV_EXAMPLE.exists():
        cmd.extend(["--add-data", f"{ENV_EXAMPLE}{os.pathsep}."])
    # VERSION (único punto de verdad para la versión)
    version_file = ROOT / "VERSION"
    if version_file.exists():
        cmd.extend(["--add-data", f"{version_file}{os.pathsep}."])
    return cmd


def build_dir() -> None:
    """Build en directorio (--onedir): rápido, para distribución estándar."""
    cmd = _base_cmd() + ["--onedir", str(ROOT / "app_core" / "main.py")]
    print(f"Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"[OK] Build completado: {DIST_DIR / 'Tardis'}")


def build_portable() -> None:
    """Build en un solo .exe (--onefile, portable).

    ADVERTENCIA: el inicio es más lento porque PyInstaller debe
    auto-extraer todo el bundle a %%TEMP%% antes de ejecutar la
    aplicación. Usar solo para USB o cuando un único archivo sea
    necesario.
    """
    cmd = _base_cmd() + ["--onefile", str(ROOT / "app_core" / "main.py")]
    print(f"Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"[OK] Build portable completado: {DIST_DIR / 'Tardis.exe'}")


def build_installer() -> None:
    """Build en directorio + genera instalador Inno Setup.

    Pasa la versión actual al script .iss mediante ``/d`` para que
    el instalador use el número de versión correcto sin hardcodearlo.
    """
    build_dir()
    iss_path = ROOT / "installer" / "tardis_setup.iss"
    if iss_path.exists():
        print("Generando instalador Inno Setup...")
        subprocess.run(
            ["iscc", f"/dMyAppVersion={VERSION}", str(iss_path)],
            check=True,
        )
        print("✅ Instalador generado.")
    else:
        print("⚠️  No se encontró installer/tardis_setup.iss — saltando instalador.")


if __name__ == "__main__":
    if "--portable" in sys.argv:
        build_portable()
    elif "--installer" in sys.argv:
        build_installer()
    else:
        build_dir()
