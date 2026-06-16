"""
Script que incrementa el número de build en ``tardis/VERSION``.

Uso:
    python scripts/bump_version.py

Se ejecuta automáticamente en CI/CD (GitHub Actions) antes de cada
commit a la rama ``main``. Incrementa el último componente (build)
del formato ``x.y.z.build`` en 1.
"""

import sys
from pathlib import Path

# Agregar tardis/ al path para poder importar app_core.version
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_core.version import get_version_parts, set_build


def main() -> None:
    """Incrementa el build number y lo imprime en stdout."""
    _, _, _, build = get_version_parts()
    set_build(build + 1)
    print(f"Build incrementado a {build + 1}")


if __name__ == "__main__":
    main()
