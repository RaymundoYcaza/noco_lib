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
    def __init__(
        self,
        client: "NocoClient",
        table_id: str,
        name: Optional[str] = None,
        resolution_error: Optional[str] = None,
    ):
        self._client = client
        self._table_id = table_id
        self._name = name or table_id
        self._resolution_error = resolution_error

    def __repr__(self) -> str:
        if self.is_unresolved():
            error_msg = self._resolution_error or "Error desconocido"
            return f"<NocoTable name='{self._name}' UNRESOLVED: {error_msg}>"
        return f"<NocoTable name='{self._name}' id='{self._table_id}'>"

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

    def is_unresolved(self) -> bool:
        """Verifica si la tabla está en estado no resuelto (table_id es None)"""
        return self._table_id is None
