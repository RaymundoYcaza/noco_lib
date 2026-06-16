"""Utilidades para la gestión de firmas de correo electrónico.

Las firmas se almacenan en un archivo JSON en la raíz del proyecto
(tardis_signatures.json) con la siguiente estructura:

.. code-block:: json

    [
      {
        "id": "<uuid4>",
        "name": "Firma oficial Inorizonti",
        "mailbox": "alicia.gentil@inorizonti.com",
        "html": "<p>Alicia Gentil<br>...</p>",
        "include_logo": true,
        "logo_brand": "inorizonti",
        "is_default": true
      }
    ]
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("tardis")

# Archivo de firmas en la raíz del proyecto (junto a tardis/ o en el directorio actual)
SIGNATURES_FILE = Path(__file__).resolve().parent.parent.parent / "tardis_signatures.json"


def load_signatures() -> list[dict[str, Any]]:
    """Carga la lista de firmas desde el archivo JSON.

    Returns
    -------
    list[dict]
        Lista de firmas. Vacía si el archivo no existe o hay error.
    """
    if not SIGNATURES_FILE.exists():
        return []
    try:
        with open(SIGNATURES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("El archivo de firmas no contiene una lista JSON válida.")
            return []
        return data
    except json.JSONDecodeError as e:
        logger.warning("Error al parsear el archivo de firmas: %s", e)
        return []
    except Exception as e:
        logger.warning("Error al cargar firmas: %s", e)
        return []


def save_signatures(signatures: list[dict[str, Any]]) -> None:
    """Guarda la lista de firmas en el archivo JSON.

    Parameters
    ----------
    signatures : list[dict]
        Lista de firmas a guardar.

    Raises
    ------
    IOError
        Si no se puede escribir el archivo.
    """
    try:
        with open(SIGNATURES_FILE, "w", encoding="utf-8") as f:
            json.dump(signatures, f, indent=2, ensure_ascii=False)
        logger.info("Firmas guardadas correctamente (%d firmas).", len(signatures))
    except Exception as e:
        logger.error("Error al guardar firmas: %s", e)
        raise


def get_default_signature(mailbox: str) -> dict[str, Any] | None:
    """Retorna la firma predeterminada para una casilla dada.

    Parameters
    ----------
    mailbox : str
        Dirección de correo de la casilla.

    Returns
    -------
    dict | None
        La firma predeterminada, o None si no hay ninguna.
    """
    sigs = load_signatures()
    for sig in sigs:
        if sig.get("mailbox") == mailbox and sig.get("is_default"):
            return sig
    return None


def get_signatures_for_mailbox(mailbox: str) -> list[dict[str, Any]]:
    """Retorna todas las firmas configuradas para una casilla.

    Parameters
    ----------
    mailbox : str
        Dirección de correo de la casilla.

    Returns
    -------
    list[dict]
        Firmas para la casilla (vacío si no hay).
    """
    sigs = load_signatures()
    return [s for s in sigs if s.get("mailbox") == mailbox]


def build_signature_html(sig: dict[str, Any]) -> str:
    """Construye el HTML completo de una firma, incluyendo el logo si está configurado.

    Parameters
    ----------
    sig : dict
        Diccionario de la firma con claves ``html``, ``include_logo``, ``logo_brand``.

    Returns
    -------
    str
        HTML completo de la firma.
    """
    parts = []

    # Logo de marca (inline SVG)
    if sig.get("include_logo") and sig.get("logo_brand"):
        brand = sig["logo_brand"]
        logo_path = Path(__file__).resolve().parent.parent.parent / "shared" / "brands" / brand / "logo.svg"
        if logo_path.exists():
            try:
                svg_content = logo_path.read_text(encoding="utf-8")
                parts.append(f'<div class="firma-logo" style="margin-bottom: 8px;">{svg_content}</div>\n')
            except Exception as e:
                logger.warning("Error al leer logo %s: %s", logo_path, e)

    # Cuerpo HTML de la firma
    html_body = sig.get("html", "")
    if html_body:
        parts.append(html_body)

    return "\n".join(parts)
