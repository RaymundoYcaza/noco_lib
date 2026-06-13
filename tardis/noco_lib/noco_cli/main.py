"""
CLI principal de noco_lib.

Estructura:
- `noco core ...`      -> operaciones CRUD básicas (core)
- `noco discover ...`  -> introspección de tablas/relaciones
- `noco ext ...`       -> extensiones genéricas (selects, export, etc.)
- `noco modules ...`   -> módulos específicos auto-registrados desde noco_modules/

Configuración de credenciales: variables de entorno
    NOCO_BASE_URL, NOCO_TOKEN, NOCO_BASE_ID
o flags globales --base-url --token --base-id (tienen prioridad).
"""

from __future__ import annotations
import importlib
import json
import os
import pkgutil

import typer

from noco_core import NocoClient

from noco_core.config import load_env

load_env()

app = typer.Typer(help="Capa de abstracción CLI para NocoDB")
core_app = typer.Typer(help="Operaciones CRUD básicas")
discover_app = typer.Typer(help="Introspección de esquema y relaciones")
ext_app = typer.Typer(help="Extensiones genéricas")
modules_app = typer.Typer(help="Módulos específicos de negocio")

app.add_typer(core_app, name="core")
app.add_typer(discover_app, name="discover")
app.add_typer(ext_app, name="ext")
app.add_typer(modules_app, name="modules")


# ----------------------------------------------------------------------
# Configuración / cliente compartido
# ----------------------------------------------------------------------
_state: dict = {}


@app.callback()
def main(
    base_url: str = typer.Option(None, envvar="NOCO_BASE_URL"),
    token: str = typer.Option(None, envvar="NOCO_TOKEN"),
    base_id: str = typer.Option(None, envvar="NOCO_BASE_ID"),
):
    if not base_url or not token:
        typer.echo("Faltan NOCO_BASE_URL y/o NOCO_TOKEN (env o flags --base-url/--token).", err=True)
        raise typer.Exit(code=1)
    _state["base_url"] = base_url
    _state["token"] = token
    _state["base_id"] = base_id


def get_client() -> NocoClient:
    return NocoClient(base_url=_state["base_url"], token=_state["token"], base_id=_state.get("base_id"))


def _print(result) -> None:
    typer.echo(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))


# ----------------------------------------------------------------------
# core
# ----------------------------------------------------------------------
@core_app.command("read")
def core_read(table: str, where: str = None, limit: int = None):
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(table_obj.read(where=where, limit=limit))


@core_app.command("create")
def core_create(table: str, json_data: str):
    """json_data: JSON de un dict o lista de dicts."""
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(table_obj.create(json.loads(json_data)))


@core_app.command("update")
def core_update(table: str, json_data: str):
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(table_obj.update(json.loads(json_data)))


@core_app.command("delete")
def core_delete(table: str, ids: str):
    """ids: '1,2,3' o un solo id."""
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    id_list = [int(i) for i in ids.split(",")]
    target = id_list[0] if len(id_list) == 1 else id_list
    _print(table_obj.delete(target))


# ----------------------------------------------------------------------
# discover
# ----------------------------------------------------------------------
@discover_app.command("table")
def discover_table_cmd(table: str, depth: int = 1):
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(table_obj.discover(depth=depth))


@discover_app.command("overview")
def discover_overview_cmd():
    from noco_discovery import export_schema_overview
    _print(export_schema_overview(get_client(), base_id=_state.get("base_id")))


# ----------------------------------------------------------------------
# ext
# ----------------------------------------------------------------------
@ext_app.command("list-tables")
def ext_list_tables(path: str = None):
    from noco_ext import list_tables_to_file
    _print(list_tables_to_file(get_client(), base_id=_state.get("base_id"), path=path))


@ext_app.command("rename-field")
def ext_rename_field(table: str, old_name: str, new_name: str):
    from noco_ext import rename_field
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(rename_field(client, table_obj.table_id, old_name, new_name))


@ext_app.command("rename-select-option")
def ext_rename_select_option(table: str, field: str, old_option: str, new_option: str):
    from noco_ext import rename_select_option
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(rename_select_option(client, table_obj.table_id, field, old_option, new_option))


@ext_app.command("add-select-option")
def ext_add_select_option(table: str, field: str, option: str, color: str = None):
    from noco_ext import add_select_option
    client = get_client()
    table_obj = client.table(table)
    if table_obj.is_unresolved():
        _print(table_obj.meta())
        raise typer.Exit(1)
    _print(add_select_option(client, table_obj.table_id, field, option, color=color))


# ----------------------------------------------------------------------
# modules: auto-descubrimiento de noco_modules/*.py con register_cli()
# ----------------------------------------------------------------------
def _autoload_modules():
    import noco_modules
    for _, name, _ in pkgutil.iter_modules(noco_modules.__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"noco_modules.{name}")
        if hasattr(mod, "register_cli"):
            sub_app = typer.Typer(help=f"Módulo: {name}")
            mod.register_cli(sub_app, get_client)
            modules_app.add_typer(sub_app, name=name)


_autoload_modules()


if __name__ == "__main__":
    app()
