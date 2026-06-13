"""
---
modulo: <nombre_descriptivo_snake_case>
tabla_principal: <Nombre tal como aparece en NocoDB>
operaciones: [read]            # subset de: read, create, update, delete
parametros_entrada: {}          # ej: {sku: str, nueva_cantidad: int}
retorna: NocoResult
descripcion: >
  <Descripción de una línea de qué hace este módulo y por qué existe.>
---

INSTRUCCIONES PARA GENERAR UN MÓDULO NUEVO (LLM):

1. Recibirás el JSON de discovery de la(s) tabla(s) involucradas
   (ver noco_discovery.discover_table). Úsalo para conocer nombres
   exactos de campos, tipos y relaciones — no inventes nombres.

2. La función pública principal debe:
   - Recibir `client: NocoClient` como primer argumento.
   - Recibir el resto de parámetros como kwargs simples (str, int, list, dict).
   - Devolver siempre un NocoResult (usar NocoResult.ok / NocoResult.fail).
   - No lanzar excepciones hacia afuera; capturarlas y convertirlas en
     NocoResult.fail(operation, str(exc)).

3. Si el módulo necesita exponerse por CLI, agregar al final un bloque
   `register_cli(app)` que registre un subcomando typer (ver ejemplo abajo).

4. Actualizar el front-matter YAML de arriba con los datos reales del módulo.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from noco_core.result import NocoResult

if TYPE_CHECKING:
    from noco_core.client import NocoClient


# ----------------------------------------------------------------------
# Función principal del módulo (ejemplo placeholder)
# ----------------------------------------------------------------------
def ejemplo_funcion(client: "NocoClient", **kwargs) -> NocoResult:
    """
    Reemplazar por la lógica real. Ejemplo mínimo:

        table = client.table("Clientes")
        return table.read(where=f"(Email,eq,{kwargs['email']})")
    """
    try:
        table = client.table(kwargs.get("tabla", "NombreTabla"))
        return table.read()
    except Exception as exc:  # noqa: BLE001
        return NocoResult.fail("read", str(exc))


# ----------------------------------------------------------------------
# Registro opcional como subcomando CLI (typer)
# ----------------------------------------------------------------------
def register_cli(app, get_client):
    """
    `app`: instancia typer.Typer del módulo / subapp.
    `get_client`: callable que devuelve un NocoClient ya configurado
                  (inyectado por noco_cli para no duplicar credenciales).
    """
    import typer

    @app.command("ejemplo")
    def _ejemplo(tabla: str = typer.Option(..., help="Nombre de la tabla")):
        client = get_client()
        result = ejemplo_funcion(client, tabla=tabla)
        typer.echo(result.to_dict())
