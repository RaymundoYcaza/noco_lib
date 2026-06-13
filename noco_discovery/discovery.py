"""
noco_discovery: construye el "diccionario de datos" de una tabla.

Función principal: discover_table(client, table_id, depth=1) -> NocoResult

El payload resultante (NocoResult.data) sigue siempre esta forma:

{
  "table": {"id": "...", "name": "..."},
  "fields": [
     {"name": str, "type": str, "required": bool, "options": [str, ...] | None}
  ],
  "relations": [
     {
       "field": str,                 # nombre del campo de relación en esta tabla
       "type": "hasMany" | "belongsTo" | "manyToMany" | "lookup" | "rollup",
       "related_table": {"id": str, "name": str},
       "related_fields": [str, ...]  # nombres de campos de la tabla relacionada (resumen)
     }
  ]
}

Este formato está diseñado para pegarse directo en un prompt: un LLM puede
leerlo y saber inmediatamente qué campos existen, cuáles son select (y sus
opciones), y cómo se conecta esta tabla con otras.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from noco_core.result import NocoResult

if TYPE_CHECKING:
    from noco_core.client import NocoClient


# Tipos de columna de NocoDB que representan relaciones / derivados
_RELATION_UIDTS = {
    "Links": "link",
    "LinkToAnotherRecord": "link",
    "Lookup": "lookup",
    "Rollup": "rollup",
}

_SELECT_UIDTS = {"SingleSelect", "MultiSelect"}


def _simplify_field(col: dict) -> dict:
    field = {
        "name": col.get("title"),
        "type": col.get("uidt"),
        "required": bool(col.get("rqd", False)),
    }
    if col.get("uidt") in _SELECT_UIDTS:
        opts = (col.get("colOptions") or {}).get("options", [])
        field["options"] = [o.get("title") for o in opts]
    return field


def discover_table(client: "NocoClient", table_id: str, depth: int = 1) -> NocoResult:
    meta_result = client.get_table_meta(table_id)
    if not meta_result.success:
        return meta_result

    table_meta = meta_result.data
    columns = table_meta.get("columns", [])

    fields = []
    relations = []

    for col in columns:
        uidt = col.get("uidt")
        if uidt in _RELATION_UIDTS:
            related = _describe_relation(client, col, depth=depth)
            if related:
                relations.append(related)
            # Las relaciones también se listan como fields informativos, sin 'options'
            fields.append({"name": col.get("title"), "type": uidt, "required": False})
        else:
            fields.append(_simplify_field(col))

    payload = {
        "table": {"id": table_meta.get("id"), "name": table_meta.get("title")},
        "fields": fields,
        "relations": relations,
    }
    return NocoResult.ok("schema", data=payload, table=table_meta.get("title"))


def _describe_relation(client: "NocoClient", col: dict, depth: int) -> dict | None:
    col_options = col.get("colOptions") or {}
    related_table_id = (
        col_options.get("fk_related_model_id")
        or col_options.get("fk_relation_table_id")
    )
    if not related_table_id:
        return None

    relation = {
        "field": col.get("title"),
        "type": _RELATION_UIDTS.get(col.get("uidt"), "unknown"),
        "related_table": {"id": related_table_id, "name": None},
        "related_fields": [],
    }

    if depth > 0:
        related_meta = client.get_table_meta(related_table_id)
        if related_meta.success:
            rel_data = related_meta.data
            relation["related_table"]["name"] = rel_data.get("title")
            relation["related_fields"] = [
                c.get("title") for c in rel_data.get("columns", [])
                if c.get("uidt") not in _RELATION_UIDTS
            ]

    return relation


def export_schema_overview(client: "NocoClient", base_id: str | None = None) -> NocoResult:
    """
    Recorre todas las tablas de la base y devuelve un resumen apto para
    documentación / contexto de LLM (sin profundizar relaciones, depth=0).
    """
    listing = client.list_tables(base_id=base_id)
    if not listing.success:
        return listing

    overview = []
    for t in listing.data:
        d = discover_table(client, t["id"], depth=0)
        if d.success:
            overview.append(d.data)
        else:
            overview.append({"table": {"id": t["id"], "name": t.get("title")}, "error": d.errors})

    return NocoResult.ok("schema", data=overview, meta={"table_count": len(overview)})
