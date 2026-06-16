"""
Runtime hook — PyInstaller frozen-mode path bootstrap.

Ensures that the following paths are importable at runtime when the
application has been bundled with PyInstaller (``--onedir``):

  - ``sys._MEIPASS`` (the ``_internal/`` bundle root)
  - ``noco_lib``, ``ai_lib``, ``modules`` (local packages inside the bundle)
  - ``app_core``, ``shared`` (data & code directories)

This hook is a **safety net** for:
  1. ``pkgutil.iter_modules`` (filesystem scanning for dynamic module discovery)
  2. ``importlib.import_module`` (dynamic imports of modules.*.module)
  3. ``Path(__file__).resolve().parent.parent`` patterns (path resolution)
  4. Any ``sys.path``-based import that the static PyInstaller analyzer
     could not trace (e.g. dynamically constructed module names)

In non-frozen (source) mode this file is a no-op.
"""

import sys
import os
from pathlib import Path


def _bootstrap_frozen_paths() -> None:
    """Add all local package directories to ``sys.path``.

    Only runs when the process is a PyInstaller-frozen executable.
    """
    # Guard: only run inside a PyInstaller bundle
    if not getattr(sys, "frozen", False):
        return

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is None:
        # Unusual but possible if exe layout differs
        return

    base = Path(meipass).resolve()

    # The bundle root itself
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    # Local package directories inside the bundle
    local_packages = ["noco_lib", "ai_lib", "modules", "app_core", "shared"]
    for pkg in local_packages:
        pkg_path = base / pkg
        if pkg_path.is_dir() and str(pkg_path) not in sys.path:
            sys.path.insert(0, str(pkg_path))

    # pkgutil.iter_modules necesita el directorio modules/ en el filesystem
    # (ya está garantizado por --add-data en build.py)

    # Debug trace (visible with TARDIS_DEBUG=1)
    if os.environ.get("TARDIS_DEBUG", "").lower() in ("1", "true", "yes"):
        print(f"[rthook] sys._MEIPASS = {meipass}", file=sys.stderr)
        print(f"[rthook] sys.path = {sys.path[:8]}...", file=sys.stderr)


_bootstrap_frozen_paths()
