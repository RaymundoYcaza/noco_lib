#!/usr/bin/env python3
"""
Instala los hooks de git locales para Tardis.

Uso:
    python scripts/install_hooks.py

Esto copia los hooks desde ``scripts/git_hooks/`` (o desde el propio
directorio de scripts) a ``.git/hooks/`` y les da permisos de ejecucion.

Hooks instalados:
  - pre-commit -> incrementa el build number en tardis/VERSION
                  antes de cada commit local.
"""

import shutil
import stat
import sys
from pathlib import Path


def _get_repo_root() -> Path:
    """Retorna la raiz del repositorio git."""
    marker = Path(__file__).resolve()
    for parent in marker.parents:
        if (parent / ".git").exists():
            return parent
    print("[ERROR] no se encontro .git/")
    sys.exit(1)


def install_hook(name: str, source: Path, hooks_dir: Path) -> None:
    """Instala un hook copiandolo a .git/hooks/ con permisos de ejecucion."""
    dest = hooks_dir / name
    shutil.copy2(str(source), str(dest))
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  [OK] Hook '{name}' instalado en {dest}")


def main() -> None:
    repo_root = _get_repo_root()
    hooks_dir = repo_root / ".git" / "hooks"

    if not hooks_dir.exists():
        print(f"[ERROR] No existe {hooks_dir}")
        sys.exit(1)

    print(f"Instalando hooks en: {hooks_dir}")
    print()

    precommit_src = repo_root / "tardis" / "scripts" / "pre-commit-bump.sh"
    if precommit_src.exists():
        install_hook("pre-commit", precommit_src, hooks_dir)
    else:
        print(f"[WARNING] No se encontro el hook fuente: {precommit_src}")
        print("         Nada que instalar.")

    print()
    print("[OK] Hooks instalados correctamente.")
    print("    El build number se incrementara automaticamente en cada commit local.")


if __name__ == "__main__":
    main()
