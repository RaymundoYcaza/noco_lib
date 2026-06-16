"""Utilidades compartidas para el ecosistema Tardis.

Funciones de uso general que pueden ser empleadas desde cualquier
módulo de la aplicación.
"""


def human_readable_size(size_bytes: int) -> str:
    """Convierte un tamaño en bytes a formato legible para humanos.

    Parameters
    ----------
    size_bytes : int
        Tamaño en bytes.

    Returns
    -------
    str
        Representación legible, e.g. ``\"1.2 KB\"``, ``\"3.4 MB\"``,
        ``\"500 B\"``.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
