"""
NocoTable: wrapper delgado alrededor de NocoClient + table_id.

Esto es lo que hace posible:

    client = NocoClient(base_url=..., token=...)
    table = client.table("Clientes")
    result = table.read(where="(Estado,eq,Activo)")

Cada método delega 1:1 en NocoClient, simplemente fijando table_id.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from .result import NocoResult

if TYPE_CHECKING:
    from .client import NocoClient


class NocoTable:
    def __init__(self, client: "NocoClient", table_id: str, name: str):
        self.client = client
        self.table_id = table_id
        self.name = name

    def __repr__(self) -> str:
        return f"<NocoTable name={self.name!r} id={self.table_id!r}>"

    # ---- lectura ----
    def read(self, where: Optional[str] = None, limit: Optional[int] = None,
             offset: int = 0, fields: Optional[list[str]] = None,
             sort: Optional[str] = None) -> NocoResult:
        return self.client.get_records(
            self.table_id, where=where, limit=limit, offset=offset,
            fields=fields, sort=sort,
        )

    # ---- escritura ----
    def create(self, records: dict | list[dict]) -> NocoResult:
        return self.client.create_records(self.table_id, records)

    def update(self, records: dict | list[dict]) -> NocoResult:
        return self.client.update_records(self.table_id, records)

    def delete(self, record_ids: int | list[int]) -> NocoResult:
        return self.client.delete_records(self.table_id, record_ids)

    # ---- esquema ----
    def meta(self) -> NocoResult:
        return self.client.get_table_meta(self.table_id)

    def add_column(self, column_def: dict) -> NocoResult:
        return self.client.create_column(self.table_id, column_def)

    # ---- discovery (delegado, ver noco_discovery) ----
    def discover(self, depth: int = 1) -> NocoResult:
        from noco_discovery.discovery import discover_table
        return discover_table(self.client, self.table_id, depth=depth)
