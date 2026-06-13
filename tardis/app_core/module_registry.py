import pkgutil
import importlib
import sys
from pathlib import Path
from dataclasses import dataclass

# Path helpers
tardis_dir = Path(__file__).resolve().parent.parent
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

# Add noco_lib search path to sys.path
noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from noco_core.client import NocoClient
from app_core.main_window import MainWindow

@dataclass
class ModuleInfo:
    name: str
    loaded: bool
    error: str | None = None

def discover_and_register(main_window: MainWindow, client: NocoClient) -> dict[str, ModuleInfo]:
    """
    Itera carpetas en modules/ (excluye prefijo '_'), importa module.py,
    llama register(app=main_window, client=client) si existe.
    Captura excepciones por módulo; un módulo roto no detiene Tardis.
    Devuelve {nombre_modulo: ModuleInfo(name: str, loaded: bool, error: str | None)}.
    """
    modules_dir = tardis_dir / "modules"
    results = {}

    if not modules_dir.exists():
        print(f"[Tardis] Directorio de módulos no existe en {modules_dir}")
        return results

    # Iterate over modules inside the modules/ folder
    for _, module_name, ispkg in pkgutil.iter_modules([str(modules_dir)]):
        # Exclude modules with leading underscores (like _template_module)
        if module_name.startswith('_'):
            continue

        try:
            # Import modules.<module_name>.module
            module_path = f"modules.{module_name}.module"
            mod = importlib.import_module(module_path)
            
            if hasattr(mod, "register"):
                mod.register(main_window, client)
                print(f"[Tardis] Módulo '{module_name}' cargado")
                results[module_name] = ModuleInfo(name=module_name, loaded=True)
            else:
                err_msg = "Función 'register' no encontrada en module.py"
                print(f"[Tardis] ERROR cargando '{module_name}': {err_msg}")
                results[module_name] = ModuleInfo(name=module_name, loaded=False, error=err_msg)
                
        except Exception as exc:
            import traceback
            traceback.print_exc()
            err_msg = str(exc)
            print(f"[Tardis] ERROR cargando '{module_name}': {err_msg}")
            results[module_name] = ModuleInfo(name=module_name, loaded=False, error=err_msg)

    return results
