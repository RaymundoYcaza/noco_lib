# SPEC v2 — Proyecto "Tardis" (con plan de tareas checklist)

> Versión 2: incorpora decisiones cerradas de la sección 9 del spec
> anterior y el esquema REAL de la tabla `DIR_LOCAL-MAIL` ya existente en
> producción. Este documento es autocontenido — cualquier LLM puede
> retomarlo sin contexto previo.
>
> **Cómo usar la sección 8 (plan de tareas)**: es una checklist de
> Markdown (`- [ ]` / `- [x]`). La idea es avanzar **una tarea a la vez**:
> se le pide al LLM "ejecuta la tarea X.Y", al terminar se marca `[x]` en
> este documento y se continúa con la siguiente. Cada tarea indica
> archivo(s), entrada/salida esperada y dependencias.

---

## 0. Resumen ejecutivo

**Tardis** es una aplicación de escritorio modular tipo Outlook/Thunderbird,
construida en **Python + PySide6** (monorepo). Su corazón operativo es
**LocalMail**, que lee/escribe en la tabla **`DIR_LOCAL-MAIL`** (NocoDB,
ya existente en producción — esquema en sección 2). Sobre ese corazón se
agregan módulos (paneles/ventanas) auto-registrables.

---

## 1. Decisiones cerradas (sección 9 del spec anterior, resueltas)

| # | Pregunta | Decisión |
|---|---|---|
| 1 | Estructura de repos | **Monorepo**: `tardis/` contiene `app_core/`, `noco_lib/` (la librería ya construida, sin cambios funcionales), `ai_lib/` (futuro), `modules/`, `shared/`. |
| 2 | Identidad de usuario | **Login de Windows**. Tardis NO implementa pantalla de login propia. `TARDIS_USER_ID` se deriva automáticamente del usuario de sesión de Windows (`getpass.getuser()` / `os.getlogin()`), que ya está protegido por el PIN/contraseña de Windows a nivel de sistema operativo. Este valor se usa como `mailbox_owner`, `from` (al enviar) y para filtrar `to` (al leer bandeja). |
| 3 | Multidestinatario | **Fase 1: un solo destinatario** en el campo `to` (texto plano, un identificador). La estructura de la tabla ya tiene `to`, `cc`, `bcc`, `bco` como `SingleLineText` — fase 1 los trata como texto plano de un solo valor; fase posterior se define convención de separador (`;` o `,`) para múltiples valores sin cambiar el tipo de columna, evitando migraciones. |
| 4 | Tabla de emails | **Ya existe**: `DIR_LOCAL-MAIL` (`table.id = "me0rcf5a8bhhyc0"`). Esquema completo en sección 2. NO se crea tabla nueva. |
| 5 | Distribución | **PyInstaller modo one-folder**. |

### 1.1 Nota sobre "bco" vs "cc" vs "bcc"
La tabla tiene TRES campos similares: `bco`, `bcc`, `cc`. Se asume:
- `cc` = copia visible estándar.
- `bcc` = copia oculta estándar.
- `bco` = probablemente un campo legado o typo de `bcc`/`cc` del diseño
  original (sistema pensado para sync con email externo real, dado
  `message_source`, `external_message_id`, `sync_status`).

**Decisión para Fase 1**: LocalMail (interno) usa `to` y `cc` únicamente.
`bcc` y `bco` quedan reservados/sin usar por el módulo LocalMail interno,
pero NO se modifican ni eliminan de la tabla (podrían usarse por otro
proceso de sync externo). Esto se documenta como nota en `service.py`.

---

## 2. Esquema real de `DIR_LOCAL-MAIL` (fuente de verdad)

`table.id = "me0rcf5a8bhhyc0"`, `table.name = "DIR_LOCAL-MAIL"`.

| Campo | Tipo | Uso en LocalMail Fase 1 |
|---|---|---|
| `Id` | ID | PK, usado en update/delete |
| `CreatedAt` | CreatedTime | automático, mostrar como fecha de envío si `client_updated_at` vacío |
| `UpdatedAt` | LastModifiedTime | automático, no usado directamente |
| `nc_created_by`, `nc_updated_by`, `nc_order` | metadatos NocoDB | ignorados |
| `title` | SingleLineText | **Asunto** |
| `body` | LongText | **Cuerpo** (texto plano en Fase 1; HTML básico fase posterior) |
| `from` | SingleLineText | usuario remitente (Windows username) |
| `to` | SingleLineText | destinatario único (Fase 1) |
| `cc` | SingleLineText | copia (opcional, Fase 1 soporta un valor) |
| `bcc` | SingleLineText | **reservado, no usado por LocalMail Fase 1** |
| `bco` | SingleLineText | **reservado, no usado, posible legado** |
| `priority` | SingleSelect: Baja/Media/Alta | mostrar como columna/ícono en bandeja; default `Media` al enviar |
| `labels` | SingleSelect: flw/qn/follow | NO usado en Fase 1 (queda para clasificación futura) |
| `read` | Checkbox | estado leído/no leído — reemplaza el campo `Estado` que se había propuesto en spec v1 |
| `read_date` | DateTime | timestamp al marcar como leído |
| `message_source` | SingleLineText | Fase 1: usar valor fijo `"tardis"` al crear desde LocalMail |
| `synced`, `synced_date`, `sync_status`, `external_message_id` | sync con email externo | **NO tocados por Fase 1** (quedan en su default/null) |
| `Attachment` | Attachment | NO usado en Fase 1 (fase posterior: adjuntos) |
| `message_uuid` | SingleLineText | generar UUID4 al crear cada mensaje (identificador propio, independiente del `Id` de NocoDB) |
| `thread_uuid` | SingleLineText | Fase 1: igual a `message_uuid` si es mensaje nuevo (no hay hilos todavía); fase posterior: agrupar respuestas |
| `reply_to_uuid` | SingleLineText | Fase 1: vacío (no hay "responder" todavía) |
| `mailbox_owner` | SingleLineText | **clave de bandeja**: igual al `to` para mensajes recibidos por ese usuario. Define de quién es la "carpeta". Fase 1: al enviar, se crea UN registro con `mailbox_owner = to` (la bandeja del destinatario) — ver decisión 2.2 abajo. |
| `folder` | SingleSelect: inbox/sent/drafts/archive/trash | Fase 1 usa `inbox`, `sent`, `archive`. `drafts`/`trash` quedan modeladas pero sin UI todavía. |
| `schema_version` | SingleLineText | Fase 1: escribir `"1"` al crear desde Tardis |
| `notify_enabled`, `notify_remind_after` | recordatorios | NO usados en Fase 1 |
| `client_updated_at` | DateTime | Fase 1: setear al momento de creación desde Tardis (timestamp del cliente, distinto de `CreatedAt` que es de NocoDB) |

### 2.1 Pregunta resuelta: ¿uno o dos registros por correo enviado?

Dado que NO existe relación N:N de destinatarios (Fase 1 = un destinatario
en `to` como texto), y existe `folder` con valores `inbox`/`sent`, hay dos
estrategias:

- **(A) Un registro por correo**, con `from`, `to`, `folder` fijo en
  `inbox`, y la bandeja de cada usuario se calcula con `where
  (mailbox_owner,eq,<usuario>)`. El "enviado" se ve filtrando
  `(from,eq,<usuario>)` sin necesidad de un segundo registro.
- **(B) Dos registros por correo** (uno `folder=sent` con
  `mailbox_owner=remitente`, otro `folder=inbox` con
  `mailbox_owner=destinatario`), como hacen los clientes de correo reales.

**Decisión Fase 1: opción (A)** — un solo registro por correo, con
`mailbox_owner = to` y `folder = inbox`. La "Bandeja de enviados" del
remitente se implementa como una vista filtrada (`from = usuario_actual`),
NO como un registro físico adicional. Esto evita duplicación y es
suficiente para Fase 1; la opción (B) queda documentada como alternativa
si se requiere que el remitente pueda "archivar su copia" de forma
independiente del destinatario (fase posterior).

### 2.2 Mapeo de acciones a campos

| Acción de usuario | Campos que cambian |
|---|---|
| Enviar correo | INSERT: `title, body, from, to, cc, priority, folder='inbox', mailbox_owner=to, read=false, message_uuid=<uuid4>, thread_uuid=<mismo uuid4>, reply_to_uuid='', message_source='tardis', schema_version='1', client_updated_at=<now>` |
| Abrir correo (marcar leído) | UPDATE: `read=true, read_date=<now>` |
| Archivar correo | UPDATE: `folder='archive'` |
| Mover a papelera | UPDATE: `folder='trash'` (Fase 1: acción disponible pero sin vista de "Papelera" todavía — opcional, ver tarea 8.4.6) |

---

## 3. Recordatorio: `noco_lib` (sin cambios, ver spec v1 para detalle completo)

```python
from noco_core import NocoClient

client = NocoClient(base_url=..., token=..., base_id=...)
table = client.table("DIR_LOCAL-MAIL")   # o por table_id "me0rcf5a8bhhyc0"
result = table.read(where="(mailbox_owner,eq,rycaza)~and(folder,eq,inbox)")
# result: NocoResult(success, operation, table, data, affected_count, errors, meta)
```

`client.table(...)` nunca lanza excepción; si no resuelve, `table_id is
None` y cualquier método devuelve `NocoResult.fail(...)`.

Sintaxis `where`: `"(Campo,eq,Valor)"`, combinable con `~and`/`~or`.
Operadores: `eq, neq, gt, lt, gte, lte, like, in, isblank, notblank`.

---

## 4. Arquitectura de carpetas (monorepo)

```
tardis/
├── app_core/
│   ├── main.py
│   ├── main_window.py
│   ├── module_registry.py
│   ├── concurrency.py
│   └── config.py
├── noco_lib/                  # existente, sin cambios
│   ├── noco_core/
│   ├── noco_discovery/
│   ├── noco_ext/
│   ├── noco_modules/
│   └── noco_cli/
├── modules/
│   ├── localmail/
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── service.py
│   │   └── views/
│   │       ├── inbox_view.py
│   │       ├── reader_view.py
│   │       └── composer_view.py
│   └── _template_module/
├── shared/
│   ├── widgets/
│   └── templates/
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 5. `app_core` — contratos exactos (referencia para implementación)

### 5.1 `concurrency.run_async`

```python
def run_async(fn: Callable, *args,
               on_success: Callable[[Any], None] | None = None,
               on_error: Callable[[Exception], None] | None = None,
               **kwargs) -> None:
    """
    Ejecuta fn(*args, **kwargs) en QThreadPool.globalInstance().
    - on_success(result) se invoca en el hilo de UI con lo que retorne fn
      (típicamente un NocoResult, incluso si .success es False).
    - on_error(exc) se invoca en el hilo de UI si fn lanza una excepción
      NO controlada.
    REGLA DE ORO: cualquier llamada a noco_lib desde un módulo DEBE pasar
    por run_async. Nunca llamar a client.table(...).read()/create()/etc.
    directamente desde un slot de UI.
    """
```

### 5.2 `main_window.MainWindow`

```python
class MainWindow(QMainWindow):
    def add_dock_panel(self, widget: QWidget, title: str,
                        area: str = "left") -> "DockWidget": ...
    def add_floating_window(self, widget: QWidget, title: str) -> "DockWidget": ...
    def add_menu_action(self, menu_path: str, label: str, callback: Callable) -> None: ...
    def add_toolbar_action(self, label: str, icon, callback: Callable) -> None: ...
    def get_client(self) -> NocoClient: ...
    def show_notification(self, text: str, level: str = "info") -> None: ...
```

### 5.3 `module_registry`

```python
def discover_and_register(main_window: MainWindow, client: NocoClient) -> dict[str, ModuleInfo]:
    """
    Itera carpetas en modules/ (excluye prefijo '_'), importa module.py,
    llama register(app=main_window, client=client) si existe.
    Captura excepciones por módulo; un módulo roto no detiene Tardis.
    Devuelve {nombre_modulo: ModuleInfo(loaded: bool, error: str | None)}.
    """
```

### 5.4 `config.load_tardis_config`

```python
@dataclass
class TardisConfig:
    noco_base_url: str
    noco_token: str
    noco_base_id: str
    localmail_table: str   # default "DIR_LOCAL-MAIL"
    user_id: str           # derivado de getpass.getuser(), NO de .env

def load_tardis_config() -> TardisConfig:
    """
    1. noco_core.config.load_env() -> carga .env (NOCO_*).
    2. user_id = getpass.getuser() (usuario de sesión Windows).
    3. localmail_table = os.environ.get("TARDIS_LOCALMAIL_TABLE", "DIR_LOCAL-MAIL").
    4. Construye y devuelve TardisConfig. No requiere diálogo de primer
       arranque (a diferencia del spec v1) porque user_id es automático.
    """
```

---

## 6. `modules/localmail/service.py` — contratos exactos

Todas las funciones: primer parámetro `client: NocoClient`, retorno
`NocoResult`. Usar `client.table("DIR_LOCAL-MAIL")` internamente (no
hardcodear el `table_id`, usar el nombre para legibilidad — `noco_lib` ya
resuelve por nombre eficientemente).

```python
def list_inbox(client, user_id: str, folder: str = "inbox",
                only_unread: bool = False, limit: int = 50) -> NocoResult:
    """
    where = (mailbox_owner,eq,<user_id>)~and(folder,eq,<folder>)
    si only_unread: ~and(read,eq,false)
    sort = "-CreatedAt" (más recientes primero)
    NocoResult.ok("read", data=[...registros...], table="DIR_LOCAL-MAIL",
                   affected_count=len(...))
    """

def list_sent(client, user_id: str, limit: int = 50) -> NocoResult:
    """where = (from,eq,<user_id>), sort = "-CreatedAt" """

def get_email(client, email_id: int) -> NocoResult:
    """read(where=f"(Id,eq,{email_id})"), data = registro único o None"""

def mark_as_read(client, email_id: int) -> NocoResult:
    """update [{"Id": email_id, "read": True, "read_date": <iso now>}]"""

def archive_email(client, email_id: int) -> NocoResult:
    """update [{"Id": email_id, "folder": "archive"}]"""

def move_to_trash(client, email_id: int) -> NocoResult:
    """update [{"Id": email_id, "folder": "trash"}]"""

def send_email(client, from_user: str, to_user: str, subject: str, body: str,
               cc: str | None = None, priority: str = "Media") -> NocoResult:
    """
    Genera message_uuid = str(uuid4()).
    create({
        "title": subject, "body": body, "from": from_user, "to": to_user,
        "cc": cc or "", "priority": priority, "folder": "inbox",
        "mailbox_owner": to_user, "read": False,
        "message_uuid": <uuid>, "thread_uuid": <mismo uuid>,
        "reply_to_uuid": "", "message_source": "tardis",
        "schema_version": "1", "client_updated_at": <iso now>,
    })
    Validar ANTES de crear: to_user no vacío, subject no vacío.
    Si validación falla: NocoResult.fail("create", [...], table="DIR_LOCAL-MAIL")
    sin llamar a la API.
    """

def notify(client, to_user: str, subject: str, body: str, module_origin: str) -> NocoResult:
    """
    Atajo para otros módulos. Igual que send_email pero:
    from_user = f"sistema:{module_origin}"
    priority = "Media" (o parametrizable en fase posterior)
    """
```

### 6.1 Validaciones comunes
- `priority` debe ser uno de `["Baja", "Media", "Alta"]`; si no, usar
  `"Media"` y registrar advertencia en `meta["warnings"]` del
  `NocoResult.ok(...)` (no fallar por esto).
- `email_id` debe ser `int > 0`; si no, `NocoResult.fail("update"/"read",
  "email_id inválido")` sin llamar a la API.

---

## 7. `modules/localmail/views/` — contratos de UI

### 7.1 `inbox_view.InboxView(QWidget)`
- `QTableView` (o `QTreeWidget`) con columnas: `priority` (ícono/color),
  `from`, `title`, `CreatedAt`, `read` (negrita si `False`).
- Constructor: `InboxView(main_window: MainWindow, client: NocoClient, user_id: str)`.
- Método `load()`: llama
  `run_async(service.list_inbox, client, user_id, on_success=self._populate)`.
- `_populate(result: NocoResult)`: si `result.success`, llena la tabla
  con `result.data`; si no, `main_window.show_notification(result.errors[0], "error")`.
- Doble click en fila → `run_async(service.mark_as_read, client, email_id,
  on_success=lambda r: (self.load(), self.email_selected.emit(email_id)))`.
  `email_selected` es una `Signal(int)` que `module.py` conecta para
  abrir/actualizar el `ReaderView`.
- Botón/menú contextual "Archivar" → `run_async(service.archive_email, ...)`
  seguido de `self.load()`.

### 7.2 `reader_view.ReaderView(QWidget)`
- `QTextBrowser` (texto plano en Fase 1, `setPlainText`).
- Método `show_email(email_id: int)`:
  `run_async(service.get_email, client, email_id, on_success=self._render)`.
- `_render(result)`: si `success` y `data` no vacío, mostrar
  `title`, `from`, `to`, `cc`, `CreatedAt`, `body`. Si vacío o error,
  mostrar mensaje "Correo no encontrado" / error.

### 7.3 `composer_view.ComposerView(QWidget)`
- Formulario: `QLineEdit` para `to`, `cc`; `QLineEdit` para `title`;
  `QTextEdit` para `body`; `QComboBox` para `priority`
  (`["Baja", "Media", "Alta"]`, default `"Media"`).
- Botón "Enviar" → valida campos no vacíos en UI (feedback inmediato,
  sin red) → `run_async(service.send_email, client, from_user=user_id,
  to_user=..., subject=..., body=..., cc=..., priority=...,
  on_success=self._on_sent)`.
- `_on_sent(result)`: si `success`,
  `main_window.show_notification("Correo enviado", "info")` y cerrar
  ventana/limpiar formulario; si no, mostrar `result.errors` en la UI
  (no cerrar, permitir reintentar).

---

## 8. PLAN DE TAREAS (checklist — avanzar una a la vez)

> Convención: cada tarea tiene **Entrada**, **Salida**, **Depende de**,
> **Archivo(s)**. Marcar `[x]` al completar. No saltar tareas: si una
> depende de otra no marcada, resolver la dependencia primero.

### 8.1 Preparación del monorepo

- [x] **8.1.1** Crear estructura de carpetas vacía según sección 4
      (incluyendo `__init__.py` donde aplique).
      Archivo(s): estructura completa de `tardis/`.
      Entrada: ninguna. Salida: árbol de carpetas creado.
      Depende de: ninguna.

- [x] **8.1.2** Mover/copiar el código existente de `noco_lib`
      (`noco_core`, `noco_discovery`, `noco_ext`, `noco_modules`,
      `noco_cli`) dentro de `tardis/noco_lib/`, sin modificar su
      contenido.
      Entrada: repo `noco_lib` actual. Salida: `tardis/noco_lib/*` idéntico
      funcionalmente, importable como `from noco_lib.noco_core import NocoClient`
      O ajustar imports si se decide aplanar (documentar la decisión
      tomada en un comentario en `tardis/README.md`).
      Depende de: 8.1.1.

- [x] **8.1.3** Crear `tardis/pyproject.toml` con dependencias:
      `PySide6>=6.7`, `PySide6-QtAds`, `python-dotenv>=1.0`, `requests>=2.31`
      (heredada de noco_lib), `typer>=0.12`, `questionary>=2.0` (si se
      conserva `noco_cli`).
      Entrada: lista de dependencias de sección "Dependencias" (spec v1
      sección 8, ajustada — sin Jinja2/pikepdf todavía, eso es Fase 3).
      Salida: `pyproject.toml` instalable con `pip install -e .`.
      Depende de: 8.1.1.

- [x] **8.1.4** Crear `tardis/.env.example`:
      ```
      NOCO_BASE_URL=https://app.nocodb.com
      NOCO_TOKEN=tu_token_aqui
      NOCO_BASE_ID=pxxxxxxxx
      TARDIS_LOCALMAIL_TABLE=DIR_LOCAL-MAIL
      ```
      y agregar `.env` a `.gitignore`.
      Depende de: 8.1.1.

- [x] **8.1.5** Verificación: ejecutar un script temporal que haga
      `from noco_lib.noco_core import NocoClient` (o la ruta de import que
      se haya decidido en 8.1.2) y llame
      `client.table("DIR_LOCAL-MAIL").meta()`, confirmando
      `success=True` y `data["id"] == "me0rcf5a8bhhyc0"`.
      Entrada: `.env` real (no versionado) con credenciales válidas.
      Salida: confirmación impresa en consola.
      Depende de: 8.1.2, 8.1.3, 8.1.4.

### 8.2 `app_core` — núcleo de la aplicación

- [x] **8.2.1** Implementar `app_core/config.py` con `TardisConfig` y
      `load_tardis_config()` exactamente según sección 5.4.
      Entrada: `.env` cargado vía `noco_core.config.load_env()`,
      `getpass.getuser()`.
      Salida: instancia `TardisConfig` con los 5 campos poblados.
      Depende de: 8.1.5.

- [x] **8.2.2** Implementar `app_core/concurrency.py` con `run_async()`
      según contrato de sección 5.1, basado en `QThreadPool` + `QRunnable`
      + `Signal`.
      Entrada: ninguna (módulo independiente).
      Salida: función `run_async` importable y testeable con una función
      dummy (`lambda: NocoResult.ok("read", data=[1,2,3])`).
      Depende de: 8.1.3 (PySide6 instalado).

- [x] **8.2.3** Implementar `app_core/main_window.py`:
      - Clase `MainWindow(QMainWindow)`.
      - Integrar Qt Advanced Docking System (`PySide6-QtAds`):
        `self.dock_manager = QtAds.CDockManager(self)`.
      - Implementar `add_dock_panel`, `add_floating_window`,
        `add_menu_action`, `add_toolbar_action`, `get_client`,
        `show_notification` según firmas de sección 5.2.
      - `show_notification`: implementación mínima Fase 1 puede ser un
        `QStatusBar.showMessage(text, timeout)` con color según `level`
        (info/error) — no requiere sistema de toasts elaborado todavía.
      Entrada: instancia de `NocoClient` (recibida en constructor).
      Salida: ventana que abre vacía (sin módulos) sin errores.
      Depende de: 8.2.2.

- [x] **8.2.4** Implementar `app_core/module_registry.py`:
      `discover_and_register(main_window, client)` según contrato de
      sección 5.3. Usar `pkgutil.iter_modules` sobre `modules/`,
      `importlib.import_module`, `try/except` por módulo, log a stdout
      con `print(f"[Tardis] Módulo '{name}' cargado")` /
      `print(f"[Tardis] ERROR cargando '{name}': {exc}")`.
      Entrada: carpeta `modules/` (puede estar vacía o con módulos
      placeholder en este punto).
      Salida: `dict[str, ModuleInfo]`, sin excepciones no controladas
      aunque `modules/` esté vacía.
      Depende de: 8.2.3.

- [x] **8.2.5** Implementar `app_core/main.py`:
      1. `config = load_tardis_config()`.
      2. `client = NocoClient(base_url=config.noco_base_url, token=config.noco_token, base_id=config.noco_base_id)`.
      3. `app = QApplication(sys.argv)`.
      4. `window = MainWindow(client)`.
      5. `discover_and_register(window, client)`.
      6. `window.show()`.
      7. `sys.exit(app.exec())`.
      Entrada: nada (lee `.env` automáticamente).
      Salida: la aplicación abre una ventana vacía sin errores ni
      bloqueos.
      Depende de: 8.2.1, 8.2.4.

- [x] **8.2.6** **Checkpoint manual**: ejecutar `python -m app_core.main`
      (o `python app_core/main.py`, según se resuelva el entrypoint) y
      confirmar visualmente que la ventana abre, no hay tracebacks en
      consola, y `print` de `module_registry` no reporta errores (aunque
      `modules/` esté vacía).
      Depende de: 8.2.5.

### 8.3 Plantilla de módulo

- [x] **8.3.1** Crear `modules/_template_module/module.py` con:
      ```python
      def register(app: "MainWindow", client: "NocoClient") -> None:
          """
          Punto de entrada del módulo. Aquí se crean widgets/vistas y se
          registran con app.add_dock_panel / add_floating_window /
          add_menu_action. NUNCA llamar a client.table(...).read()/etc.
          directamente aquí de forma síncrona si el resultado depende de
          red — usar run_async desde dentro de las vistas.
          """
          pass
      ```
      y `modules/_template_module/README.md` con front-matter YAML
      (mismo espíritu que `noco_modules/_template_module.py`, adaptado a
      "módulo de Tardis": `nombre`, `paneles`, `ventanas_flotantes`,
      `tablas_noco_usadas`, `descripcion`).
      Entrada: ninguna. Salida: plantilla copiable para módulos futuros.
      Depende de: 8.2.6.

### 8.4 Módulo `localmail`

- [x] **8.4.1** Implementar `modules/localmail/service.py` con las 7
      funciones de sección 6 (`list_inbox`, `list_sent`, `get_email`,
      `mark_as_read`, `archive_email`, `move_to_trash`, `send_email`,
      `notify`) — son 8 funciones en total, contar `notify`.
      Cada función usa `client.table("DIR_LOCAL-MAIL")` y devuelve
      `NocoResult` según especificación exacta de sección 6.
      Entrada: `client: NocoClient` real (de 8.1.5).
      Salida: cada función probada manualmente (script suelto) contra la
      tabla real, confirmando `NocoResult.success=True` para casos válidos
      y `False` con mensaje claro para `email_id` inválido.
      Depende de: 8.1.5, 8.2.2 (aunque `service.py` no usa `run_async`
      directamente — eso es responsabilidad de las vistas — sí depende
      conceptualmente de que `NocoResult` esté disponible vía `noco_lib`).

- [x] **8.4.2** Implementar `modules/localmail/views/inbox_view.py`
      (`InboxView`) según sección 7.1, incluyendo la `Signal(int)
      email_selected`.
      Entrada: `main_window`, `client`, `user_id`.
      Salida: widget que, al instanciarse y llamar `.load()`, muestra
      filas reales de la tabla `DIR_LOCAL-MAIL` filtradas por
      `mailbox_owner = user_id` (puede no haber filas si el usuario actual
      no tiene correos — probar también con un `user_id` que sí tenga
      datos, vía override manual para pruebas).
      Depende de: 8.4.1, 8.2.3.

- [x] **8.4.3** Implementar `modules/localmail/views/reader_view.py`
      (`ReaderView`) según sección 7.2.
      Entrada: `main_window`, `client`.
      Salida: widget que, al llamar `.show_email(email_id)` con un id
      real, muestra `title`/`from`/`to`/`cc`/`CreatedAt`/`body`.
      Depende de: 8.4.1, 8.2.3.

- [x] **8.4.4** Implementar `modules/localmail/views/composer_view.py`
      (`ComposerView`) según sección 7.3.
      Entrada: `main_window`, `client`, `user_id` (para `from_user`).
      Salida: formulario funcional que, al enviar con datos válidos hacia
      un `to_user` de prueba, crea un registro real en `DIR_LOCAL-MAIL`
      verificable luego con `InboxView` de ese destinatario.
      Depende de: 8.4.1, 8.2.3.

- [x] **8.4.5** Implementar `modules/localmail/module.py` con
      `register(app, client)`:
      - `user_id = app.get_client()` → NO, `user_id` viene de
        `TardisConfig` (pasar `config.user_id` al `register`, o exponer
        `app.config` en `MainWindow` — **decisión a tomar en esta tarea**:
        agregar atributo `MainWindow.config: TardisConfig` en 8.2.3 si no
        se hizo, y usarlo aquí).
      - Crear `inbox = InboxView(app, client, user_id)`,
        `reader = ReaderView(app, client)`.
      - `app.add_dock_panel(inbox, "LocalMail - Bandeja de entrada", area="left")`.
      - `app.add_dock_panel(reader, "LocalMail - Lector", area="center")`.
      - Conectar `inbox.email_selected.connect(reader.show_email)`.
      - `inbox.load()` al final de `register`.
      - `app.add_menu_action("LocalMail", "Bandeja de entrada", lambda: inbox.load())`.
      - `app.add_menu_action("LocalMail", "Redactar", lambda: <abrir composer>)`:
        crear `composer = ComposerView(app, client, user_id)` y
        `app.add_floating_window(composer, "Redactar correo")`. Definir si
        se crea una sola instancia reutilizada o una nueva cada vez
        (recomendado Fase 1: una nueva ventana flotante cada vez que se
        hace click en "Redactar", simple y sin estado compartido).
      Entrada: `app: MainWindow`, `client: NocoClient`.
      Salida: al arrancar Tardis, aparece el panel de bandeja con datos
      reales del usuario actual; doble click abre el lector; menú
      "LocalMail > Redactar" abre ventana flotante funcional.
      Depende de: 8.4.2, 8.4.3, 8.4.4, 8.2.4.

- [x] **8.4.6** (Opcional, Fase 1 extendida) Agregar acción "Archivar" en
      menú contextual de `InboxView` (click derecho sobre fila) que llame
      `run_async(service.archive_email, client, email_id, on_success=...)`
      y refresque la lista. Documentar en `modules/localmail/README.md`
      que "Papelera" (`move_to_trash`) está implementado en `service.py`
      pero sin entrada de UI todavía (queda para Fase 2).
      Depende de: 8.4.5.

- [x] **8.4.7** **Checkpoint manual de Fase 1**: con dos usuarios de
      prueba (ej. ejecutar Tardis en dos sesiones/configuraciones de
      `.env` distintas, o simular cambiando `TARDIS_LOCALMAIL_TABLE`/
      `user_id` manualmente para pruebas), confirmar el flujo completo:
      Usuario A redacta y envía un correo a Usuario B → Usuario B lo ve en
      su bandeja → Usuario B hace doble click → se marca como leído y se
      muestra en el lector → (opcional) Usuario B lo archiva y desaparece
      de `folder=inbox`.
      Depende de: 8.4.5, 8.4.6 (si se implementó).

### 8.5 Empaquetado

- [x] **8.5.1** Crear configuración de PyInstaller modo **one-folder**
      (`tardis.spec` o comando documentado en `README.md`):
      `pyinstaller --name Tardis --onedir app_core/main.py` (ajustar
      `--add-data` para incluir `.env.example`, plantillas futuras, y
      verificar que `PySide6-QtAds` y plugins de Qt se incluyan
      correctamente — puede requerir hooks adicionales, documentar
      cualquier flag extra necesario).
      Entrada: app funcional de 8.4.7.
      Salida: carpeta `dist/Tardis/` con `Tardis.exe` que arranca
      correctamente en una máquina limpia (sin Python instalado) y se
      conecta a NocoDB usando un `.env` colocado junto al ejecutable.
      Depende de: 8.4.7.

- [x] **8.5.2** Documentar en `README.md` el proceso de build y
      distribución (qué archivos copiar a compañeros, dónde colocar
      `.env`, cómo actualizar cuando haya nueva versión).
      Depende de: 8.5.1.

---

## 9. Próximas fases (referencia, no detalladas aún)

- **Fase 2**: ventanas flotantes avanzadas, pantalla "Administrador de
  módulos", theming, `notify()` probado desde un módulo dummy, vista de
  "Papelera" y "Enviados" explícitas, soporte multidestinatario real
  (convención de separador en `to`/`cc`).
- **Fase 3**: `pdf_export` (QtWebEngine + overlay de footer con pikepdf).
- **Fase 4**: `ai_lib` + `ai_corrections`.

Estas fases se detallarán con el mismo formato de checklist cuando se
complete la sección 8.

---