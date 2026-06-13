"""
Módulo de configuración para cargar variables de entorno desde archivos .env
"""

import os
from pathlib import Path


def load_env(dotenv_path: str | None = None) -> None:
    """
    Carga variables desde un archivo .env hacia os.environ, si existe.
    
    Busca, en orden:
      1. dotenv_path explícito (si se pasa)
      2. .env en el directorio de trabajo actual (cwd)
      3. .env en la raíz del proyecto (subiendo desde este archivo
         hasta encontrar pyproject.toml, máx 3 niveles)
    
    No sobreescribe variables ya presentes en el entorno
    (override=False) — las variables de entorno reales del sistema
    tienen prioridad sobre el .env.
    
    Si python-dotenv no está instalado, falla silenciosamente
    (no debe romper la app si falta la dependencia opcional).
    """
    try:
        from dotenv import load_dotenv as _load_dotenv, find_dotenv
    except ImportError:
        # python-dotenv no está instalado, fallar silenciosamente
        return

    if dotenv_path is not None:
        # Ruta explícita proporcionada
        if os.path.exists(dotenv_path):
            _load_dotenv(dotenv_path=dotenv_path, override=False)
        return

    # Estrategia 1: Buscar en cwd
    cwd_env = os.path.join(os.getcwd(), ".env")
    if os.path.exists(cwd_env):
        _load_dotenv(dotenv_path=cwd_env, override=False)
        return

    # Estrategia 2: Usar find_dotenv de python-dotenv
    found = find_dotenv(usecwd=True)
    if found:
        _load_dotenv(dotenv_path=found, override=False)
        return

    # Estrategia 3: Buscar desde la ubicación de este módulo hacia arriba
    # hasta encontrar pyproject.toml (máx 3 niveles)
    current_dir = Path(__file__).parent
    for _ in range(3):
        current_dir = current_dir.parent
        pyproject = current_dir / "pyproject.toml"
        env_file = current_dir / ".env"
        if pyproject.exists() and env_file.exists():
            _load_dotenv(dotenv_path=str(env_file), override=False)
            return
        if not current_dir.parent.exists() or current_dir == current_dir.parent:
            break