"""
Utilidad de versionado de Tardis.

Punto de verdad único: el archivo ``VERSION`` en la raíz del proyecto.
Formato: ``x.y.z.build`` donde ``build`` se incrementa automáticamente
en cada commit a la rama ``main`` mediante CI/CD.

Uso:
    from app_core.version import load_version, get_version_parts, set_build

    version_str = load_version()           # "0.1.0.42"
    major, minor, patch, build = get_version_parts()  # (0, 1, 0, 42)
    set_build(43)                          # actualiza VERSION
"""

from pathlib import Path

_version_file = Path(__file__).resolve().parent.parent / "VERSION"


def load_version() -> str:
    """Lee y retorna el string de versión desde ``VERSION``.

    Returns
    -------
    str
        Versión en formato ``x.y.z.build``, o ``"0.0.0.0"`` si el
        archivo no existe o no puede leerse.
    """
    try:
        return _version_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "0.0.0.0"


def get_version_parts() -> tuple[int, int, int, int]:
    """Retorna los componentes numéricos de la versión.

    Returns
    -------
    tuple[int, int, int, int]
        ``(major, minor, patch, build)``. Si el formato es inválido
        retorna ``(0, 0, 0, 0)``.
    """
    parts = load_version().split(".")
    if len(parts) != 4:
        return (0, 0, 0, 0)
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0, 0)


def set_build(build: int) -> None:
    """Actualiza solo el número de build en el archivo ``VERSION``.

    Parameters
    ----------
    build : int
        Nuevo número de compilación (se incrementa automáticamente
        en CI/CD, no debe modificarse manualmente).
    """
    major, minor, patch, _ = get_version_parts()
    _version_file.write_text(f"{major}.{minor}.{patch}.{build}\n", encoding="utf-8")
