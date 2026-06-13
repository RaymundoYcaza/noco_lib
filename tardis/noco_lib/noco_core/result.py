"""
Contrato universal de retorno (NocoResult).

Toda función pública del ecosistema (core, discovery, extensiones, módulos)
DEBE devolver una instancia de NocoResult. Esto permite que:
- El CLI sepa cómo imprimir el resultado.
- El menú interactivo sepa cómo mostrarlo.
- Scripts externos sepan cómo consumirlo sin leer la implementación.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class NocoResult:
    success: bool
    operation: str                     # "read" | "create" | "update" | "delete" | "schema" | "meta"
    table: Optional[str] = None
    data: Any = None                   # list[dict] | dict | None
    affected_count: int = 0
    errors: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def ok(cls, operation: str, data: Any = None, table: str = None,
           affected_count: int = 0, meta: dict = None) -> "NocoResult":
        return cls(
            success=True,
            operation=operation,
            table=table,
            data=data,
            affected_count=affected_count,
            errors=[],
            meta=meta or {},
        )

    @classmethod
    def fail(cls, operation: str, errors: list[str] | str, table: str = None,
             meta: dict = None) -> "NocoResult":
        if isinstance(errors, str):
            errors = [errors]
        return cls(
            success=False,
            operation=operation,
            table=table,
            data=None,
            affected_count=0,
            errors=errors,
            meta=meta or {},
        )
