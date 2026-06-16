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
        "pyinstaller",
        "--windowed",  # sin consola
        "--name", f"Tardis-v{VERSION}",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        "--add-data", f"{ASSETS_DIR}{os.pathsep}shared",
        "--hidden-import", "PySide6.QtSvg",
        "--hidden-import", "PySide6.QtWebEngineWidgets",
        "--hidden-import", "qtawesome",
    ]
    # Icono
    ico = ROOT / "shared" / "brands" / "inorizonti" / "logo.ico"
    if ico.exists():
        cmd.extend(["--icon", str(ico)])
    # .env.example
    if ENV_EXAMPLE.exists():
        cmd.extend(["--add-data", f"{ENV_EXAMPLE}{os.pathsep}."])
    return cmd


def build_dir() -> None:
    """Build en directorio (--onedir): rápido, para distribución estándar."""
    cmd = _base_cmd() + ["--onedir", str(ROOT / "app_core" / "main.py")]
    print(f"Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"✅ Build completado: {DIST_DIR / f'Tardis-v{VERSION}'}")


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
    print(f"✅ Build portable completado: {DIST_DIR / f'Tardis-v{VERSION}.exe'}")


def build_installer() -> None:
    """Build en directorio + genera instalador Inno Setup."""
    build_dir()
    iss_path = ROOT / "installer" / "tardis_setup.iss"
    if iss_path.exists():
        print("Generando instalador Inno Setup...")
        subprocess.run(["iscc", str(iss_path)], check=True)
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
