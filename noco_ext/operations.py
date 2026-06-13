"""
noco_ext: extensiones genéricas reutilizables para cualquier tabla/base.

No son CRUD puro (eso es noco_core) ni introspección (eso es noco_discovery),
son operaciones de "ayuda" comunes a cualquier proyecto: exportar esquemas,
gestionar opciones de selects, renombrar campos, etc.

Convención: toda función recibe `client: NocoClient` como primer argumento
y devuelve NocoResult.
"""

from __future__ import annotations
import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from noco_core.result import NocoResult
from noco_discovery.discovery import export_schema_overview

if TYPE_CHECKING:
    from noco_core.client import NocoClient


DEFAULT_EXPORT_DIR = os.path.expanduser("~/noco_exports")


# ----------------------------------------------------------------------
# Listado / exportación de tablas
# ----------------------------------------------------------------------
def list_tables_to_file(client: "NocoClient", base_id: Optional[str] = None,
                         path: Optional[str] = None) -> NocoResult:
    """
    Lista todas las tablas de la base y exporta el resumen de esquema
    (vía discovery, depth=0) a un archivo JSON.

    - path: ruta completa de archivo destino. Si no se provee, se usa
      DEFAULT_EXPORT_DIR/<base_id o 'base'>_schema_<timestamp>.json
    """
    overview = export_schema_overview(client, base_id=base_id)
    if not overview.success:
        return overview

    if path is None:
        os.makedirs(DEFAULT_EXPORT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bid = base_id or client.base_id or "base"
        path = os.path.join(DEFAULT_EXPORT_DIR, f"{bid}_schema_{ts}.json")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(overview.data, f, ensure_ascii=False, indent=2)

    return NocoResult.ok(
        "schema",
        data={"path": path, "table_count": len(overview.data)},
        meta={"exported_to": path},
    )


# ----------------------------------------------------------------------
# Gestión de columnas tipo select
# ----------------------------------------------------------------------
def _find_column(client: "NocoClient", table_id: str, column_title: str) -> dict | None:
    meta = client.get_table_meta(table_id)
    if not meta.success:
        return None
    for col in meta.data.get("columns", []):
        if col.get("title") == column_title:
            return col
    return None


def rename_field(client: "NocoClient", table_id: str, old_name: str, new_name: str) -> NocoResult:
    """
    Renombra cualquier campo (no solo selects). Ej:
        rename_field(client, table_id, "Ctegoria", "Categoria")
    """
    col = _find_column(client, table_id, old_name)
    if col is None:
        return NocoResult.fail("update", f"Campo '{old_name}' no encontrado en tabla {table_id}.", table=table_id)

    return client.update_column(col["id"], {"title": new_name})


def add_select_option(client: "NocoClient", table_id: str, field_name: str,
                       new_option: str, color: Optional[str] = None) -> NocoResult:
    """
    Agrega una opción nueva a un campo SingleSelect/MultiSelect, preservando
    las opciones existentes.
    """
    col = _find_column(client, table_id, field_name)
    if col is None:
        return NocoResult.fail("update", f"Campo '{field_name}' no encontrado.", table=table_id)
    if col.get("uidt") not in ("SingleSelect", "MultiSelect"):
        return NocoResult.fail("update", f"El campo '{field_name}' no es un select.", table=table_id)

    existing = (col.get("colOptions") or {}).get("options", [])
    existing_titles = {o.get("title") for o in existing}
    if new_option in existing_titles:
        return NocoResult.ok("update", data=col, table=table_id, affected_count=0,
                              meta={"note": "La opción ya existía, no se hizo nada."})

    new_opt = {"title": new_option}
    if color:
        new_opt["color"] = color

    updated_options = existing + [new_opt]
    return client.update_column(col["id"], {"colOptions": {"options": updated_options}})


def rename_select_option(client: "NocoClient", table_id: str, field_name: str,
                          old_option: str, new_option: str) -> NocoResult:
    """
    Renombra una opción dentro de un SingleSelect/MultiSelect sin afectar las demás.
    Ej: en el campo "Categoria", cambiar la opción "Ctegoria" -> "Categoria".
    """
    col = _find_column(client, table_id, field_name)
    if col is None:
        return NocoResult.fail("update", f"Campo '{field_name}' no encontrado.", table=table_id)
    if col.get("uidt") not in ("SingleSelect", "MultiSelect"):
        return NocoResult.fail("update", f"El campo '{field_name}' no es un select.", table=table_id)

    options = (col.get("colOptions") or {}).get("options", [])
    found = False
    for o in options:
        if o.get("title") == old_option:
            o["title"] = new_option
            found = True
            break

    if not found:
        return NocoResult.fail("update", f"La opción '{old_option}' no existe en '{field_name}'.", table=table_id)

    return client.update_column(col["id"], {"colOptions": {"options": options}})


# ----------------------------------------------------------------------
# Operaciones masivas con validación previa
# ----------------------------------------------------------------------
def bulk_update_with_validation(client: "NocoClient", table_id: str,
                                 records: list[dict], required_keys: Optional[list[str]] = None) -> NocoResult:
    """
    Valida que cada registro tenga 'Id' y (opcionalmente) los campos requeridos
    antes de enviar el update masivo. Evita mandar requests parciales inválidos.
    """
    required_keys = required_keys or []
    errors = []
    for i, rec in enumerate(records):
        if "Id" not in rec:
            errors.append(f"Registro #{i} no tiene 'Id'.")
            continue
        for key in required_keys:
            if key not in rec:
                errors.append(f"Registro #{i} (Id={rec['Id']}) le falta el campo requerido '{key}'.")

    if errors:
        return NocoResult.fail("update", errors, table=table_id)

    return client.update_records(table_id, records)
