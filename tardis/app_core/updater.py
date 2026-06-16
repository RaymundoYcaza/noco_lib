"""
Módulo de actualización automática de Tardis.

Consulta una ruta de red (o local) configurable en busca de nuevas
versiones. Si la versión remota es mayor, solicita confirmación al
usuario para descargar e instalar.

La ruta se configura mediante:
1. QSettings (Settings > Apariencia > Actualizaciones)
2. Variable de entorno ``TARDIS_UPDATE_PATH``
3. Valor por defecto: ``X:\\B02_SOFTWARE-LIBRARY\\00-INTERNOS\\Tardis``

Uso:
    from app_core.updater import check_for_updates, download_and_install

    remote = check_for_updates()
    if remote:
        download_and_install(remote)
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

from app_core.version import load_version, get_version_parts

logger = logging.getLogger("tardis")


def get_update_path() -> Path:
    """Retorna la ruta configurada para buscar actualizaciones.

    El orden de precedencia es:
    1. QSettings (configurado por el usuario en Settings > Apariencia)
    2. Variable de entorno ``TARDIS_UPDATE_PATH``
    3. Valor por defecto ``X:\\B02_SOFTWARE-LIBRARY\\00-INTERNOS\\Tardis``
    """
    # 1. QSettings
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings("Tardis", "Tardis")
        qs_path = settings.value("updates/update_path")
        if qs_path:
            return Path(qs_path)
    except Exception:
        logger.debug("No se pudo leer QSettings para update_path")

    # 2. Variable de entorno
    raw = os.environ.get(
        "TARDIS_UPDATE_PATH",
        r"X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis",
    )
    return Path(raw)


def check_for_updates() -> str | None:
    """Compara la versión local con la remota.

    Lee el archivo ``VERSION`` desde la ruta de actualización
    configurada. Si la versión remota es mayor que la local,
    retorna el string de la versión remota.

    Returns
    -------
    str | None
        La versión remota si hay una actualización disponible,
        o ``None`` si ya estamos en la última versión o si no
        se pudo contactar la ruta de red.
    """
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
        logger.warning(
            "Formato de versión remota inválido: %s", remote_version
        )
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
    """Descarga e instala la nueva versión desde la ruta de red.

    Busca primero un instalador Inno Setup (``Tardis-v{version}-Setup.exe``)
    y luego un ejecutable portable (``Tardis-v{version}.exe``).

    Parameters
    ----------
    remote_version : str
        Versión remota a instalar (formato ``x.y.z.build``).

    Returns
    -------
    bool
        ``True`` si se inició la instalación correctamente.
    """
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
                [
                    str(installer_path),
                    "/SILENT",
                    f"/D={Path(sys.executable).parent}",
                ],
                shell=True,
            )
        else:
            subprocess.Popen(["xdg-open", str(installer_path)])
        return True
    except Exception as exc:
        logger.exception("Error al ejecutar instalador: %s", exc)
        return False
