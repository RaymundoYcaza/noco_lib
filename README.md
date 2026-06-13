# noco_lib

Capa de abstracción sobre la API v2 de NocoDB. Diseñada para usarse en
~3 líneas de código, exponer un esquema de "discovery" legible por LLMs,
y permitir que tanto humanos (CLI / menú) como otros scripts consuman
sus funciones con un contrato de retorno único.

## Instalación

```bash
pip install -e .
```

Configurar credenciales (env vars o flags `--base-url --token --base-id`):

```bash
export NOCO_BASE_URL="https://app.nocodb.com"
export NOCO_TOKEN="xxxxx"
export NOCO_BASE_ID="pxxxxxxxx"   # opcional, requerido para listar tablas por nombre
```

### Configuración con variables de entorno

Puedes configurar las credenciales de NocoDB de tres formas (en orden de prioridad):

#### 1. Variables de entorno del shell (mayor prioridad)
```bash
export NOCO_BASE_URL="https://tu-nocodb.com"
export NOCO_TOKEN="tu_token"
export NOCO_BASE_ID="pxxxxxxxx"

## Uso en 3 líneas

```python
from noco_core import NocoClient

client = NocoClient(base_url="https://app.nocodb.com", token="xxxxx", base_id="pxxxxxxxx")
table = client.table("Clientes")
result = table.read(where="(Estado,eq,Activo)")
```

## Estructura del repo

```
noco_core/        Cliente HTTP + CRUD básico + NocoResult (el contrato)
noco_discovery/    Introspección de esquema y relaciones, formato para LLMs
noco_ext/          Extensiones genéricas (selects, renombrar campos, exportar esquema)
noco_modules/      Módulos de negocio específicos (uno por archivo)
noco_cli/          CLI (typer) + menú interactivo (questionary)
docs/              Documentación adicional / contratos
```

## El contrato: `NocoResult`

Toda función pública (en cualquier capa) devuelve `NocoResult`:

```python
@dataclass
class NocoResult:
    success: bool
    operation: str          # "read" | "create" | "update" | "delete" | "schema" | "meta"
    table: str | None
    data: Any                # list[dict] | dict | None
    affected_count: int
    errors: list[str]
    meta: dict
```

Esto permite que un script externo haga:

```python
result = table.update([{"Id": 5, "Categoria": "Premium"}])
if result.success:
    print(f"Actualizados: {result.affected_count}")
else:
    print("Error:", result.errors)
```

## Discovery: el "diccionario de datos" para LLMs

```python
result = client.table("Clientes").discover(depth=1)
print(result.data)
```

Devuelve:

```json
{
  "table": {"id": "tbl_xxx", "name": "Clientes"},
  "fields": [
    {"name": "Email", "type": "Email", "required": true},
    {"name": "Categoria", "type": "SingleSelect", "options": ["A", "B", "C"]}
  ],
  "relations": [
    {
      "field": "Pedidos",
      "type": "hasMany",
      "related_table": {"id": "tbl_yyy", "name": "Pedidos"},
      "related_fields": ["Fecha", "Total", "Estado"]
    }
  ]
}
```

Pega este JSON directamente en un prompt junto con un requisito en
lenguaje natural para que un LLM genere un nuevo módulo (ver
`noco_modules/_template_module.py`).

## Generar un módulo nuevo con un LLM

1. Ejecuta `noco discover table "NombreTabla" --depth 1` y copia el JSON.
2. Pega el JSON + el contenido de `noco_modules/_template_module.py` +
   tu requisito en un prompt.
3. Pide al LLM que devuelva un archivo `.py` siguiendo exactamente esa
   plantilla (front-matter YAML, función principal con `NocoResult`,
   `register_cli` opcional).
4. Guarda el archivo en `noco_modules/`. La CLI lo auto-registra en el
   próximo arranque (`noco modules <nombre_modulo> --help`).

## CLI

```bash
noco discover table "Clientes" --depth 1
noco discover overview
noco core read "Clientes" --where "(Estado,eq,Activo)"
noco ext list-tables --path /ruta/salida.json
noco ext rename-field "Productos" "Ctegoria" "Categoria"
noco ext rename-select-option "Productos" "Categoria" "Ctegoria" "Categoria"
noco modules <nombre_modulo> ejemplo --tabla "Clientes"
```

## Menú interactivo

```bash
python -m noco_cli.menu.interactive
```

## Convenciones

- `snake_case` para funciones y archivos, `PascalCase` para clases.
- Ninguna función pública lanza excepciones hacia el caller final;
  todo error se devuelve en `NocoResult.fail(...)`.
- Toda función de gestión recibe `client: NocoClient` como primer argumento.
- Los módulos de `noco_modules/` siguen `_template_module.py` al pie de la letra.
