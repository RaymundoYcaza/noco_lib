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
        table_id: str | None,
        name: str,
        resolution_error: str | None = None,
    ):
        self.client = client
        self.table_id = table_id
        self.name = name
        self.resolution_error = resolution_error

    def __repr__(self) -> str:
        if self.table_id is None:
            return f"<NocoTable name={self.name!r} UNRESOLVED: {self.resolution_error!r}>"
        return f"<NocoTable name={self.name!r} id={self.table_id!r}>"

    def is_unresolved(self) -> bool:
        """Verifica si la tabla está en estado no resuelto (table_id es None)"""
        return self.table_id is None

    def _check_resolved(self, operation: str) -> NocoResult | None:
        """Verifica si la tabla está resuelta. Si no, devuelve un NocoResult.fail."""
        if self.table_id is None:
            return NocoResult.fail(
                operation,
                f"No se pudo resolver la tabla '{self.name}': {self.resolution_error}",
                table=self.name,
            )
        return None

    # ---- lectura ----
    def read(self, where: Optional[str] = None, limit: Optional[int] = None,
             offset: int = 0, fields: Optional[list[str]] = None,
             sort: Optional[str] = None) -> NocoResult:
        error_result = self._check_resolved("read")
        if error_result is not None:
            return error_result
        return self.client.get_records(
            self.table_id, where=where, limit=limit, offset=offset,
            fields=fields, sort=sort,
        )

    # ---- escritura ----
    def create(self, records: dict | list[dict]) -> NocoResult:
        error_result = self._check_resolved("create")
        if error_result is not None:
            return error_result
        return self.client.create_records(self.table_id, records)

    def update(self, records: dict | list[dict]) -> NocoResult:
        error_result = self._check_resolved("update")
        if error_result is not None:
            return error_result
        return self.client.update_records(self.table_id, records)

    def delete(self, record_ids: int | list[int]) -> NocoResult:
        error_result = self._check_resolved("delete")
        if error_result is not None:
            return error_result
        return self.client.delete_records(self.table_id, record_ids)

    # ---- esquema ----
    def meta(self) -> NocoResult:
        error_result = self._check_resolved("meta")
        if error_result is not None:
            return error_result
        return self.client.get_table_meta(self.table_id)

    def add_column(self, column_def: dict) -> NocoResult:
        error_result = self._check_resolved("update")
        if error_result is not None:
            return error_result
        return self.client.create_column(self.table_id, column_def)

    # ---- discovery (delegado, ver noco_discovery) ----
    def discover(self, depth: int = 1) -> NocoResult:
        error_result = self._check_resolved("schema")
        if error_result is not None:
            return error_result
        from noco_discovery.discovery import discover_table
        return discover_table(self.client, self.table_id, depth=depth)
