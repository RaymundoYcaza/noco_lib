import os
import sys
import getpass
import logging
from dataclasses import dataclass
from pathlib import Path

# Add noco_lib search path to sys.path
tardis_dir = Path(__file__).resolve().parent.parent
noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from noco_core.config import load_env

logger = logging.getLogger("tardis")

@dataclass
class TardisConfig:
    noco_base_url: str
    noco_token: str
    noco_base_id: str
    localmail_table: str   # default "DIR_LOCAL-MAIL"
    user_id: str           # derivado de getpass.getuser(), NO de .env
    mailboxes: list[str]   # parsed from TARDIS_MAILBOXES
    ai_provider: str       # default "ollama"
    ai_model: str          # default "gemma3:27b"
    ai_base_url: str       # default "http://localhost:11434"
    poll_interval_seconds: int = 60  # intervalo de sondeo de bandeja de entrada

def _check_missing_env_vars() -> None:
    """Compara las variables del ``.env`` del usuario contra el archivo
    ``.env.example`` empaquetado y loguea un warning si faltan variables
    nuevas que deberían configurarse.

    Busca el ``.env.example`` junto al ejecutable (frozen) o en la raíz
    del proyecto (desarrollo), extrae los nombres de variable, y los
    compara con ``os.environ`` actual.
    """
    # Determinar ruta del .env.example
    if getattr(sys, "frozen", False):
        # En frozen: --add-data lo coloca junto al .exe
        example_path = Path(sys.executable).parent / ".env.example"
    else:
        example_path = tardis_dir / ".env.example"

    if not example_path.exists():
        logger.debug("No se encontró .env.example en: %s", example_path)
        return

    try:
        lines = example_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        logger.warning("Error al leer .env.example: %s", exc)
        return

    # Extraer nombres de variable (líneas con KEY=algo, ignorando comentarios)
    example_vars: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        # Tomar todo antes del primer =
        var_name = stripped.split("=", 1)[0].strip()
        # Si la línea comienza con "export ", quitarlo
        if var_name.startswith("export "):
            var_name = var_name[7:].strip()
        if var_name and not var_name.startswith("#"):
            example_vars.append(var_name)

    if not example_vars:
        return

    # Comparar con las variables actuales en el entorno
    missing = [v for v in example_vars if v not in os.environ]

    if missing:
        logger.warning(
            "Variables de entorno no configuradas en tu .env "
            "(revisa .env.example para los valores recomendados):\n  %s",
            "\n  ".join(missing),
        )


def load_tardis_config() -> TardisConfig:
    """
    1. noco_core.config.load_env() -> carga .env (NOCO_*).
    2. user_id = getpass.getuser() (usuario de sesión Windows).
    3. localmail_table = os.environ.get("TARDIS_LOCALMAIL_TABLE", "DIR_LOCAL-MAIL").
    4. Construye y devuelve TardisConfig.
    """
    # 1. Cargar .env desde el directorio junto al ejecutable si está congelado, o de tardis_dir
    if getattr(sys, 'frozen', False):
        tardis_env = Path(sys.executable).parent / ".env"
    else:
        tardis_env = tardis_dir / ".env"

    if tardis_env.exists():
        load_env(str(tardis_env))
    else:
        load_env()

    # 2. Obtener credenciales de NocoDB
    noco_base_url = os.environ.get("NOCO_BASE_URL", "")
    noco_token = os.environ.get("NOCO_TOKEN", "")
    noco_base_id = os.environ.get("NOCO_BASE_ID", "")
    
    # 3. Obtener nombre de la tabla de correos locales
    localmail_table = os.environ.get("TARDIS_LOCALMAIL_TABLE", "DIR_LOCAL-MAIL")

    # 4. Derivar identidad de usuario basada en el inicio de sesión de Windows
    try:
        user_id = getpass.getuser()
    except Exception:
        user_id = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))

    # 5. Parsear la lista de casillas (TARDIS_MAILBOXES)
    mailboxes_raw = os.environ.get("TARDIS_MAILBOXES", "")
    mailboxes = [m.strip() for m in mailboxes_raw.split(";") if m.strip()]

    # 6. AI configuration
    ai_provider = os.environ.get("TARDIS_AI_PROVIDER", "ollama")
    ai_model = os.environ.get("TARDIS_AI_MODEL", "gemma3:27b")
    ai_base_url = os.environ.get("TARDIS_AI_BASE_URL", "http://localhost:11434")

    # 7. Intervalo de sondeo de notificaciones
    try:
        poll_interval_seconds = int(os.environ.get("TARDIS_POLL_INTERVAL_SECONDS", "60"))
    except (ValueError, TypeError):
        poll_interval_seconds = 60

    # 8. Verificar si faltan variables nuevas respecto a .env.example
    _check_missing_env_vars()

    return TardisConfig(
        noco_base_url=noco_base_url,
        noco_token=noco_token,
        noco_base_id=noco_base_id,
        localmail_table=localmail_table,
        user_id=user_id,
        mailboxes=mailboxes,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_base_url=ai_base_url,
        poll_interval_seconds=poll_interval_seconds,
    )

