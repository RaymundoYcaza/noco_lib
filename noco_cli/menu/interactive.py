"""
Menú interactivo de navegación. Envuelve las mismas funciones que el CLI
(no duplica lógica), pensado para usuarios que prefieren navegar en vez
de recordar comandos.

Uso:
    python -m noco_cli.menu.interactive
"""

from __future__ import annotations
import json
import os

import questionary

from noco_core import NocoClient


def _get_client() -> NocoClient:
    base_url = os.environ.get("NOCO_BASE_URL") or questionary.text("Base URL:").ask()
    token = os.environ.get("NOCO_TOKEN") or questionary.password("Token:").ask()
    base_id = os.environ.get("NOCO_BASE_ID") or questionary.text("Base ID (opcional):").ask()
    return NocoClient(base_url=base_url, token=token, base_id=base_id or None)


def _show(result):
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))


def main():
    client = _get_client()

    while True:
        choice = questionary.select(
            "¿Qué deseas hacer?",
            choices=[
                "Listar tablas (exportar esquema)",
                "Describir tabla",
                "Descubrir relaciones de una tabla",
                "Leer registros",
                "Renombrar campo",
                "Renombrar opción de select",
                "Salir",
            ],
        ).ask()

        if choice == "Salir" or choice is None:
            break

        if choice == "Listar tablas (exportar esquema)":
            from noco_ext import list_tables_to_file
            path = questionary.text("Ruta de salida (vacío = default):").ask() or None
            _show(list_tables_to_file(client, base_id=client.base_id, path=path))

        elif choice == "Describir tabla":
            name = questionary.text("Nombre de la tabla:").ask()
            _show(client.table(name).meta())

        elif choice == "Descubrir relaciones de una tabla":
            name = questionary.text("Nombre de la tabla:").ask()
            _show(client.table(name).discover(depth=1))

        elif choice == "Leer registros":
            name = questionary.text("Nombre de la tabla:").ask()
            where = questionary.text("Filtro 'where' (opcional, sintaxis NocoDB):").ask() or None
            _show(client.table(name).read(where=where, limit=20))

        elif choice == "Renombrar campo":
            from noco_ext import rename_field
            name = questionary.text("Nombre de la tabla:").ask()
            old = questionary.text("Nombre actual del campo:").ask()
            new = questionary.text("Nuevo nombre:").ask()
            table_id = client.table(name).table_id
            _show(rename_field(client, table_id, old, new))

        elif choice == "Renombrar opción de select":
            from noco_ext import rename_select_option
            name = questionary.text("Nombre de la tabla:").ask()
            field = questionary.text("Nombre del campo (select):").ask()
            old = questionary.text("Opción actual:").ask()
            new = questionary.text("Nueva opción:").ask()
            table_id = client.table(name).table_id
            _show(rename_select_option(client, table_id, field, old, new))

        print("\n" + "-" * 40 + "\n")


if __name__ == "__main__":
    main()
