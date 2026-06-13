# SPEC — Tardis Fase 2 v2 (consolidada, lista para ejecución tarea por tarea)

> Reemplaza completamente a `tardis_spec_fase2.md` y su addendum — este es
> el documento único a usar. Continuación de `tardis_spec_v2.md` (Fase 1
> completada: la app abre, muestra paneles "LocalMail - Bandeja de
> entrada" y "LocalMail - Lector", pero la bandeja aparece vacía).
> Documento autocontenido: cualquier LLM puede retomarlo sin contexto
> previo.
>
> **Modo de uso**: ejecutar **una tarea a la vez, en el orden listado**.
> Cada tarea tiene Entrada / Salida / Verificación / Depende de. Marcar
> `[x]` solo cuando la Verificación se cumple. No saltar tareas.

---

## 0. Contexto mínimo (recordatorio, no rediseñar)

- **`noco_lib`**: capa de abstracción sobre NocoDB v2. Contrato universal
  `NocoResult(success, operation, table, data, affected_count, errors, meta)`.
  `client.table("DIR_LOCAL-MAIL")` nunca lanza excepción; si no resuelve,
  cualquier método devuelve `NocoResult.fail(...)`.
- **Tabla `DIR_LOCAL-MAIL`** (`table.id = "me0rcf5a8bhhyc0"`, 329 filas en
  producción), campos relevantes: `title, body, from, to, cc, bcc, bco,
  priority (Baja/Media/Alta), labels, read (Checkbox), read_date,
  message_source, synced (Checkbox), synced_date, Attachment,
  message_uuid, thread_uuid, reply_to_uuid, mailbox_owner, folder
  (inbox/sent/drafts/archive/trash), schema_version, notify_enabled
  (Checkbox), notify_remind_after, client_updated_at, sync_status,
  external_message_id, CreatedAt, UpdatedAt`.
- **Regla de oro**: ninguna llamada a `noco_lib` fuera de `run_async()`.

---

## 1. Causa confirmada de la bandeja vacía (no requiere exploración a ciegas)

Datos reales de `DIR_LOCAL-MAIL` muestran `mailbox_owner` con formato de
**email** (ej. `alicia.gentil@inorizonti.com`, `dev@bisstox.com`,
`ventas@plyson.com`), mientras que Fase 1 usa
`TardisConfig.user_id = getpass.getuser()`, que devuelve un **username
local de Windows** (ej. `"raymundo"`, visible en el título "Bandeja de
Entrada (raymundo)" de la captura). Estos valores nunca coinciden — la
query es válida, simplemente no hay filas donde `mailbox_owner =
"raymundo"`.

Además, **una persona tiene asignadas varias casillas** (varios valores
de `mailbox_owner`), por lo que el filtro debe ser `mailbox_owner IN
(<lista de casillas del usuario>)`, no un valor único.

**Conclusión**: el fix es reemplazar la identidad de filtrado por una
lista configurable de casillas (`TARDIS_MAILBOXES`), confirmar
empíricamente la sintaxis de filtro `where` que soporta NocoDB v2 para
"IN"/"OR", y propagar ese cambio por `service.py` → vistas → composer.

---

## 2. Decisiones de diseño Fase 2 (versión final)

### 2.1 Identidad: `TARDIS_MAILBOXES` (lista de casillas)

- Nueva variable de entorno **`TARDIS_MAILBOXES`**, lista separada por
  `;`. Ejemplo:
  ```
  TARDIS_MAILBOXES=alicia.gentil@inorizonti.com;dev@bisstox.com
  ```
- `TardisConfig.mailboxes: list[str]` — parseo de `TARDIS_MAILBOXES`,
  `strip()` por elemento, descartando vacíos. Si queda `[]`, NO es un
  error de Tardis: es config faltante, y se debe comunicar explícitamente
  en la UI (sección 2.2).
- `user_id` (de `getpass.getuser()`) se conserva solo para logs/futuro,
  **no se usa para filtrar `DIR_LOCAL-MAIL`**.
- No existe `TARDIS_MAILBOX_OVERRIDE` (descartado, reemplazado desde el
  inicio por la lista).

### 2.2 Validación de "sin casillas configuradas"

Si `config.mailboxes == []`, `InboxView`/`SentView`/`TrashView`, ANTES de
llamar `run_async`, muestran un mensaje fijo en el panel: *"No hay
casillas configuradas. Define TARDIS_MAILBOXES en tu archivo .env."* — sin
tocar la red.

### 2.3 Sintaxis de filtro multi-casilla (a confirmar empíricamente)

Dos candidatos a probar contra la API real, en este orden:

1. Operador `in`: `(mailbox_owner,in,a@x.com,b@y.com)`
2. Agrupación `~or`: `((mailbox_owner,eq,a@x.com)~or(mailbox_owner,eq,b@y.com))`

El que funcione se usa, combinado con `~and(folder,eq,<folder>)` para el
resto del filtro. Documentar en código (comentario) cuál se eligió y por
qué.

### 2.4 Checkboxes (`read`, `synced`, `notify_enabled`)

Lectura: llegan como enteros `0`/`1` (confirmado en datos reales: `"read": 1`).
Escritura: probar primero `True`/`False` (Python bool → JSON `true`/`false`);
si la API lo rechaza, usar `1`/`0`. Documentar el resultado en
`service.py`.

### 2.5 Valores fijos al escribir desde Tardis

- `schema_version = "1.0.0"` (semver, confirmado por datos reales — NO
  `"1"`).
- `message_source = "tardis"` (la tabla es compartida con un sistema
  externo que escribe `"automation"` — Tardis nunca filtra por este
  campo al leer, solo lo escribe).

### 2.6 Multidestinatario — convención de separador

- `to` y `cc` aceptan múltiples valores separados por `; ` (punto y coma
  + espacio al unir; al parsear, split por `;` y `strip()`).
- `send_email(client, from_user: str, to_users: list[str], subject: str,
  body: str, cc_users: list[str] | None = None, priority: str = "Media")`.
- Genera `message_uuid = str(uuid4())` UNA vez. Crea **un registro por
  cada destinatario** en `to_users + (cc_users or [])`, cada uno con
  `mailbox_owner = <ese destinatario>`, mismo `message_uuid` y
  `thread_uuid`, `to = "; ".join(to_users)`, `cc = "; ".join(cc_users or [])`
  (igual en todos los registros, para que el lector muestre la lista
  completa).
- Comportamiento best-effort: si una creación individual falla, las
  demás continúan; `meta["partial_errors"]` acumula fallos;
  `success = (al menos 1 creación exitosa)`; `affected_count` = creaciones
  exitosas.

### 2.7 Composer: selector "Desde"

`ComposerView` agrega `QComboBox "Desde"` poblado con
`config.mailboxes`. Si `len(mailboxes) == 1`, combo deshabilitado con esa
única opción preseleccionada. El valor elegido es `from_user`.

### 2.8 Carpetas "Enviados" y "Papelera"

- `list_sent(client, mailboxes, limit=50)`: `where: from IN mailboxes`
  (misma sintaxis confirmada en 2.3), deduplicado por `message_uuid` en
  Python (conservar el primero por `CreatedAt` descendente).
- `list_trash(client, mailboxes, limit=50)`: igual a `list_inbox` con
  `folder="trash"`.
- `InboxView` se generaliza con parámetro `mode: Literal["inbox","sent","trash"]`,
  reutilizable para los 3 paneles.

### 2.9 `notify()` desde módulo dummy

`modules/dummy_notify_test/module.py`, menú "Dummy > Enviar notificación
de prueba", llama
`run_async(localmail_service.notify, client, to_users=config.mailboxes[:1], subject="Prueba", body="...", module_origin="dummy_notify_test", ...)`.
Sirve de ejemplo vivo para módulos futuros y prueba del bus de
notificaciones.

### 2.10 Administrador de módulos

Vive en `app_core/views/module_admin_view.py` (parte del core, no un
módulo — necesita el `dict[str, ModuleInfo]` de `module_registry`).
Tabla con columnas Nombre/Estado/Error. Registrado desde `main.py` como
dock panel "Administrador de módulos" (`area="bottom"`).

### 2.11 Theming

`app_core/styles/dark.qss` + `app_core/theming.apply_theme(app, "dark")`,
llamado en `main.py` antes de `window.show()`. Paleta basada en la
captura existente (fondo `#1e1e1e`-ish, acento azul, texto gris claro).

### 2.12 Ventanas flotantes avanzadas

- Persistencia de geometría con `QSettings("Tardis", "Tardis")`, clave
  `floating/<title>/geometry`, guardada en `closeEvent` y restaurada al
  crear.
- `ComposerView.closeEvent`: si hay contenido sin enviar
  (`to`/`title`/`body` no vacíos), confirmar descarte con `QMessageBox`.

### 2.13 Nota sobre layout "Three-Pane" (informativa, NO implementar en Fase 2)

Diseño objetivo futuro:

```
┌─────────┬─────────────┬─────────────────┐
│ Menú    │ Lista       │ Detalle         │
│ lateral │ Emails      │ Contenido       │
└─────────┴─────────────┴─────────────────┘
```

El panel "Menú lateral" futuro será un árbol `Casilla > Carpeta` (un nodo
= una casilla + una carpeta = una llamada a `service.list_inbox(client,
mailboxes=[esa_casilla], folder=esa_carpeta)`). El trabajo de Fase 2 en
`service.py` (parámetro `mailboxes: list[str]`) se reutiliza sin cambios
en Fase 3 — solo cambia cómo se invoca desde la UI (tabs → árbol). No se
requiere ninguna tarea adicional ahora; se deja como nota en
`modules/localmail/README.md` (tarea 8.7.2).

### 2.14 Recomendación futura (no bloqueante, no es tarea de Fase 2)

Crear tabla `DIR_USERS` (usuario de Windows → lista de casillas
asignadas) para reemplazar `TARDIS_MAILBOXES` por configuración
centralizada en NocoDB. Anotado en `modules/localmail/README.md`
(tarea 8.7.2).

---

## 3. PLAN DE TAREAS (checklist — ejecutar en orden)

### 8.0 — Fix de identidad y filtro multi-casilla (PRIORITARIO)

- [x] **8.0.1** Crear `scripts/diag_inbox.py` (carpeta `scripts/` nueva en
      la raíz). El script debe:
      1. Cargar config con `load_tardis_config()`.
      2. Imprimir `config.user_id` (de `getpass.getuser()`).
      3. Llamar `client.table("DIR_LOCAL-MAIL").read(limit=10)` (sin
         filtro) e imprimir `result.success`, `result.errors`, y para
         cada registro: `Id, from, to, mailbox_owner, folder, read`.
      Entrada: `.env` real. Salida: listado en consola de hasta 10
      registros con esos campos.
      Verificación: el script corre sin excepción y muestra al menos 1
      registro con `mailbox_owner` en formato email.
      Depende de: ninguna.

- [x] **8.0.2** Agregar a `.env.example`:
      ```
      # Lista de casillas (mailbox_owner) asignadas a este usuario,
      # separadas por ';'. Ejemplo:
      # TARDIS_MAILBOXES=alicia.gentil@inorizonti.com;dev@bisstox.com
      TARDIS_MAILBOXES=
      ```
      Implementar `TardisConfig.mailboxes: list[str]` en
      `app_core/config.py` según sección 2.1 (parseo por `;`, `strip()`,
      descartar vacíos). Si en Fase 1 existe `user_id` usado para filtrar
      LocalMail, dejarlo solo como atributo informativo, sin uso en
      `service.py` a partir de aquí.
      Entrada: ninguna. Salida: `TardisConfig` con campo nuevo
      `mailboxes: list[str]`.
      Verificación: script de prueba que imprima
      `load_tardis_config().mailboxes` con `TARDIS_MAILBOXES` vacío →
      devuelve `[]`; con `TARDIS_MAILBOXES="a@x.com;b@y.com"` → devuelve
      `["a@x.com", "b@y.com"]`.
      Depende de: 8.0.1.

- [x] **8.0.3** En `scripts/diag_inbox.py`, agregar una sección que, con
      `TARDIS_MAILBOXES` configurado a UN valor real tomado de 8.0.1 (ej.
      `alicia.gentil@inorizonti.com`), pruebe la sintaxis #1 de sección
      2.3:
      ```python
      where = f"(mailbox_owner,in,{mb})"
      result = client.table("DIR_LOCAL-MAIL").read(where=where, sort="-CreatedAt")
      ```
      e imprima `result.success`, `result.errors`, `len(result.data)`.
      Verificación: el resultado es impreso (éxito o fallo, ambos son
      información útil).
      Depende de: 8.0.2.

- [x] **8.0.4** En el mismo script, probar la sintaxis #2 de sección 2.3
      con el mismo valor:
      ```python
      where = f"((mailbox_owner,eq,{mb}))"  # caso de 1 sola casilla
      ```
      e imprimir igual que 8.0.3.
      Verificación: ambos resultados (8.0.3 y 8.0.4) impresos para
      comparar.
      Depende de: 8.0.3.

- [x] **8.0.5** Repetir 8.0.3 y 8.0.4 con DOS valores reales separados por
      `;` (ej. `"alicia.gentil@inorizonti.com;dev@bisstox.com"`),
      construyendo:
      - Sintaxis `in`: `(mailbox_owner,in,a@x.com,b@y.com)`
      - Sintaxis `~or`: `((mailbox_owner,eq,a@x.com)~or(mailbox_owner,eq,b@y.com))`
      Imprimir resultados de ambas.
      Verificación: al menos UNA de las dos sintaxis devuelve
      `success=True` y filas que incluyen registros de ambas casillas (se
      puede confirmar revisando `mailbox_owner` de las filas devueltas).
      Depende de: 8.0.4.

- [x] **8.0.6** También en el script, probar el filtro combinado completo
      que usará `list_inbox`, con la sintaxis ganadora de 8.0.5 + `~and`:
      ```python
      where = f"{filtro_multicasilla}~and(folder,eq,inbox)~and(read,eq,0)"
      ```
      Probar con `read,eq,0` y, si falla, con `read,eq,false`. Documentar
      cuál funciona (comentario en el script).
      Verificación: `result.success=True` con al menos una variante de
      `read`.
      Depende de: 8.0.5.

- [x] **8.0.7** Implementar `service.list_inbox(client, mailboxes:
      list[str], folder: str = "inbox", only_unread: bool = False, limit:
      int = 50) -> NocoResult` usando la sintaxis confirmada en 8.0.5/8.0.6:
      - Si `mailboxes == []`: `NocoResult.fail("read", "No hay casillas
        configuradas (TARDIS_MAILBOXES vacío).", table="DIR_LOCAL-MAIL")`
        sin llamar a la API.
      - Construir `where` con la sintaxis ganadora + `~and(folder,eq,<folder>)`
        + (si `only_unread`) `~and(read,eq,<valor confirmado>)`.
      - `sort="-CreatedAt"`.
      - `NocoResult.ok("read", data=result.data, table="DIR_LOCAL-MAIL",
        affected_count=len(result.data))`.
      Verificación: llamar la función desde un script con
      `mailboxes=["alicia.gentil@inorizonti.com"]`, `folder="sent"` (que
      sí tiene datos según 8.0.1) y confirmar `success=True` y
      `affected_count > 0`.
      Depende de: 8.0.6.

- [x] **8.0.8** Actualizar `modules/localmail/views/inbox_view.py`
      (`InboxView`):
      - Constructor recibe `mailboxes: list[str]` (no `user_id`/`mailbox_id`).
      - En `load()`: si `mailboxes == []`, mostrar directamente el mensaje
        de sección 2.2 (sin `run_async`). Si no, llamar
        `run_async(service.list_inbox, client, mailboxes, on_success=self._populate)`.
      - `_populate`: si `result.success` False, mostrar
        `result.errors[0]` vía `main_window.show_notification(..., "error")`
        con duración mínima 5s (`showMessage(text, 5000)`); si True,
        poblar tabla con `result.data`.
      Verificación: con `config.mailboxes = []`, el panel muestra el
      mensaje de "sin casillas" sin hacer requests (verificable agregando
      un `print` temporal antes de `run_async` and confirmando que no se
      imprime).
      Depende de: 8.0.7.

- [x] **8.0.9** Actualizar `modules/localmail/module.py`: pasar
      `config.mailboxes` (en vez de `user_id`) al construir `InboxView`.
      Verificar que `MainWindow` expone `config: TardisConfig` — si no,
      agregarlo ahora (atributo simple asignado en `__init__` desde lo
      que recibe `main.py`).
      Verificación: revisar que no quede ninguna referencia a
      `user_id`/`mailbox_id` en `inbox_view.py`/`module.py` relacionada
      con el filtro de LocalMail (`grep -r "mailbox_id"` no debe encontrar
      coincidencias activas en `modules/localmail/`).
      Depende de: 8.0.8.

- [x] **8.0.10** **CHECKPOINT 1**: configurar `TARDIS_MAILBOXES` en `.env`
      real con 1-2 casillas reales que tengan registros con
      `folder="inbox"`. Si de los registros vistos en 8.0.1 ninguno tiene
      `folder="inbox"` (en los 5 de ejemplo son `sent`/`archive`), hacer
      una de estas dos cosas:
      (a) consultar más filas (`limit=50` o más) en
      `scripts/diag_inbox.py` hasta encontrar alguna con `folder="inbox"`
      y usar esa `mailbox_owner`, o
      (b) crear un registro de prueba manualmente (vía NocoDB UI o
      `client.table("DIR_LOCAL-MAIL").create(...)` desde un script) con
      `folder="inbox"` y `mailbox_owner` = una casilla de
      `TARDIS_MAILBOXES`.
      Ejecutar Tardis y confirmar que la bandeja muestra ese/esos
      registro(s).
      Verificación: la UI de Tardis muestra al menos 1 fila real en
      "Bandeja de entrada", sin tracebacks en consola.
      Depende de: 8.0.9.

### 8.1 — Multidestinatario (sección 2.6, 2.7)

- [x] **8.1.1** Agregar `QComboBox "Desde"` a `ComposerView` poblado con
      `config.mailboxes` (sección 2.7). Si `len(mailboxes) == 1`, combo
      deshabilitado con esa opción preseleccionada. Si `len(mailboxes) ==
      0`, deshabilitar todo el formulario y mostrar el mensaje de sección
      2.2 también aquí (no se puede enviar sin casilla "Desde").
      Verificación: con 2 casillas en `TARDIS_MAILBOXES`, el combo
      muestra ambas y permite elegir; con 1, aparece deshabilitado pero
      visible con el valor correcto.
      Depende de: 8.0.10.

- [x] **8.1.2** Modificar `service.send_email` a la firma de sección 2.6:
      `send_email(client, from_user: str, to_users: list[str], subject:
      str, body: str, cc_users: list[str] | None = None, priority: str =
      "Media") -> NocoResult`. Validaciones (sin llamar API si fallan):
      `to_users` no vacío tras filtrar strings no vacías tras `.strip()`;
      `subject.strip()` no vacío; `from_user.strip()` no vacío. Si alguna
      falla: `NocoResult.fail("create", [<mensaje específico>], table="DIR_LOCAL-MAIL")`.
      Verificación: llamar con `to_users=[]` → `success=False` y mensaje
      claro; llamar con `to_users=["  "]` (solo espacios) → también
      `success=False`.
      Depende de: 8.1.1.

- [x] **8.1.3** Implementar el cuerpo de `send_email` según sección 2.6:
      `message_uuid = str(uuid4())`, `thread_uuid = message_uuid`,
      `reply_to_uuid = ""`, `to = "; ".join(to_users_validos)`,
      `cc = "; ".join(cc_users_validos or [])`, `folder="inbox"`,
      `read=False` (o `0` según 2.4 — usar lo confirmado),
      `message_source="tardis"`, `schema_version="1.0.0"`,
      `client_updated_at=<iso now con timezone, ej. datetime.now(timezone.utc).isoformat()>`.
      Loop sobre `to_users_validos + (cc_users_validos or [])`: por cada
      `destinatario`, `create({..., "mailbox_owner": destinatario, "from":
      from_user, "title": subject, "body": body, "priority": priority if
      priority in ["Baja","Media","Alta"] else "Media"})`. Acumular
      resultados; `meta["partial_errors"]` para fallos individuales;
      `success = any(ok)`; `affected_count = count(ok)`;
      `data = [registros creados exitosos]`.
      Verificación: con `to_users=["<casilla_propia_de_prueba>"]`, llamar
      la función desde un script y confirmar `success=True`,
      `affected_count==1`, y que el registro creado es visible luego con
      `list_inbox` filtrando esa casilla.
      Depende de: 8.1.2.

- [x] **8.1.4** Actualizar `ComposerView`: campos `to`/`cc` como texto
      libre con `;` (placeholder `"destinatario1; destinatario2"`).
      Parsing antes de llamar `send_email`:
      `[s.strip() for s in texto.split(";") if s.strip()]`. Botón
      "Enviar" → `run_async(service.send_email, client,
      from_user=<combo seleccionado>, to_users=<parsed>, subject=...,
      body=..., cc_users=<parsed o None>, priority=<combo prioridad>,
      on_success=self._on_sent)`.
      `_on_sent`: si `result.success`, notificación "Correo enviado" +
      limpiar formulario (o cerrar ventana); si no, mostrar
      `result.errors` en el formulario sin cerrar.
      Verificación: enviar a 2 destinatarios separados por `;` desde la
      UI, confirmar `NocoResult.success=True`.
      Depende de: 8.1.3.

- [x] **8.1.5** **CHECKPOINT 2**: con dos casillas reales como
      destinatarios (`destA; destB`, donde idealmente `destA` y `destB`
      están ambas en `TARDIS_MAILBOXES` para poder verificar desde la
      misma sesión, o usar `scripts/diag_inbox.py` para verificar la
      segunda), confirmar que AMBAS reciben un registro con el mismo
      `message_uuid` y `folder="inbox"`.
      Depende de: 8.1.4.

### 8.2 — Vistas "Enviados" y "Papelera" (sección 2.8)

- [x] **8.2.1** Implementar `service.list_sent(client, mailboxes:
      list[str], limit: int = 50) -> NocoResult`: mismo filtro
      multi-casilla de 8.0.7 pero sobre el campo `from` en vez de
      `mailbox_owner`, `sort="-CreatedAt"`. Tras obtener `result.data`,
      deduplicar en Python por `message_uuid` (conservar el primero en el
      orden recibido, ya viene ordenado por `-CreatedAt`).
      Verificación: con `mailboxes=["alicia.gentil@inorizonti.com"]`
      (que en los datos de ejemplo tiene `folder="sent"`), `success=True`
      y `affected_count > 0`, sin `message_uuid` duplicados en `data`.
      Depende de: 8.1.5.

- [ ] **8.2.2** Implementar `service.list_trash(client, mailboxes:
      list[str], limit: int = 50) -> NocoResult`: idéntico a
      `list_inbox` con `folder="trash"`.
      Verificación: `success=True` (puede devolver `affected_count==0` si
      no hay registros en trash, eso es válido).
      Depende de: 8.2.1.

- [ ] **8.2.3** Refactorizar `InboxView` para aceptar
      `mode: Literal["inbox","sent","trash"] = "inbox"` en el
      constructor. En `load()`, según `mode`, llamar
      `service.list_inbox` / `service.list_sent` / `service.list_trash`
      respectivamente (todas reciben `client, mailboxes` igual). Mantener
      `email_selected: Signal(int)`.
      Verificación: instanciar la vista 3 veces con cada `mode` (script
      de prueba o temporalmente en `module.py`) y confirmar que cada una
      llama al `service.*` correcto (verificable con `print` temporal o
      revisando el `where` resultante).
      Depende de: 8.2.2.

- [ ] **8.2.4** Actualizar `modules/localmail/module.py`:
      - Crear `sent_view = InboxView(app, client, config.mailboxes, mode="sent")`
        y `trash_view = InboxView(app, client, config.mailboxes, mode="trash")`.
      - Registrar ambos como dock panels junto al de "Bandeja de
        entrada" (mismo `area="left"`, verificar si Qt Advanced Docking
        los agrupa como tabs automáticamente; si no, ajustar `area` para
        lograr agrupación en tabs).
      - Agregar `app.add_menu_action("LocalMail", "Enviados", lambda:
        sent_view.load())` y `app.add_menu_action("LocalMail", "Papelera",
        lambda: trash_view.load())`.
      - Conectar `email_selected` de ambas nuevas vistas al mismo
        `reader`.
      Verificación: visualmente aparecen 3 pestañas/paneles (Bandeja,
      Enviados, Papelera) en el área izquierda, cada uno cargable desde su
      entrada de menú.
      Depende de: 8.2.3.

- [ ] **8.2.5** **CHECKPOINT 3**: con los datos creados en 8.1.5
      (`destA`/`destB` en `TARDIS_MAILBOXES`), confirmar:
      - "Enviados" del remitente original muestra el correo enviado (1
        fila, no duplicada por `message_uuid`).
      - "Bandeja de entrada" de `destA` y `destB` muestran el correo
        recibido.
      - "Papelera" aparece vacía (o con datos si existieran de antes) sin
        error.
      Depende de: 8.2.4.

### 8.3 — `notify()` desde módulo dummy (sección 2.9)

- [ ] **8.3.1** Implementar `service.notify(client, to_users: list[str],
      subject: str, body: str, module_origin: str) -> NocoResult`: atajo
      que llama `send_email(client, from_user=f"sistema:{module_origin}",
      to_users=to_users, subject=subject, body=body, priority="Media")`.
      Verificación: llamar desde script con
      `to_users=["<una casilla de TARDIS_MAILBOXES>"]`, confirmar
      `success=True` y que el registro creado tiene
      `from="sistema:test"`.
      Depende de: 8.2.5.

- [ ] **8.3.2** Crear `modules/dummy_notify_test/module.py` con
      `register(app, client)`:
      - `app.add_menu_action("Dummy", "Enviar notificación de prueba",
        lambda: run_async(localmail_service.notify, client,
        to_users=app.config.mailboxes[:1], subject="Prueba",
        body="Notificación de prueba desde dummy",
        module_origin="dummy_notify_test", on_success=lambda r:
        app.show_notification("Notify OK" if r.success else
        r.errors[0], "info" if r.success else "error")))`.
      - Import cruzado explícito: `from modules.localmail import service
        as localmail_service`.
      Verificación: aparece menú "Dummy" con la opción; si
      `config.mailboxes` está vacío, `to_users=[]` debe producir el
      `NocoResult.fail` de validación de `send_email` (8.1.2), mostrado
      vía `show_notification` con `level="error"` (probar este caso
      temporalmente vaciando `TARDIS_MAILBOXES` y restaurando después).
      Depende de: 8.3.1.

- [ ] **8.3.3** **CHECKPOINT 4**: con `TARDIS_MAILBOXES` configurado
      normalmente, ejecutar "Dummy > Enviar notificación de prueba",
      confirmar `success=True`, y verificar (refrescando manualmente
      "Bandeja de entrada") que el mensaje aparece con
      `from="sistema:dummy_notify_test"`.
      Depende de: 8.3.2.

### 8.4 — Administrador de módulos (sección 2.10)

- [ ] **8.4.1** Revisar/ajustar `app_core/module_registry.py`: confirmar
      que `discover_and_register` devuelve `dict[str, ModuleInfo]` donde
      `ModuleInfo` tiene al menos `name: str, loaded: bool, error: str |
      None`. Ajustar si el shape real difiere.
      Verificación: imprimir el dict resultante en `main.py`
      temporalmente y confirmar que incluye `localmail` y
      `dummy_notify_test` con `loaded=True, error=None`.
      Depende de: 8.3.3.

- [ ] **8.4.2** Crear `app_core/views/module_admin_view.py` con
      `ModuleAdminView(QWidget)`: constructor recibe `module_info:
      dict[str, ModuleInfo]`, muestra `QTableWidget` con columnas
      Nombre/Estado/Error, una fila por entrada del dict.
      Verificación: instanciar con un dict de prueba
      (`{"foo": ModuleInfo(name="foo", loaded=True, error=None), "bar":
      ModuleInfo(name="bar", loaded=False, error="ImportError: x")}`) y
      confirmar 2 filas visibles con los valores correctos.
      Depende de: 8.4.1.

- [ ] **8.4.3** En `main.py`, tras
      `module_info = discover_and_register(window, client)`, instanciar
      `ModuleAdminView(module_info)` y
      `window.add_dock_panel(admin_view, "Administrador de módulos", area="bottom")`.
      Verificación: panel visible al arrancar Tardis, mostrando
      `localmail` y `dummy_notify_test` como "Cargado".
      Depende de: 8.4.2.

- [ ] **8.4.4** **CHECKPOINT 5**: introducir temporalmente un error de
      sintaxis en `modules/dummy_notify_test/module.py` (ej. una variable
      no definida dentro de `register`), reiniciar Tardis, confirmar que:
      (a) Tardis arranca sin tumbarse, (b) el panel "Administrador de
      módulos" muestra `dummy_notify_test` como "Error" con el mensaje de
      excepción. Revertir el error.
      Depende de: 8.4.3.

### 8.5 — Theming (sección 2.11)

- [ ] **8.5.1** Crear `app_core/styles/dark.qss` con variables
      documentadas en comentarios (fondo principal ~`#1e1e1e`, fondo
      secundario ~`#2a2a2a`, texto ~`#e0e0e0`, acento ~`#0a66c2`,
      error ~`#d9534f`, warning ~`#f0ad4e`), aplicando estos colores a
      `QMainWindow`, `QTableWidget`/`QTableView`, `QPushButton`,
      `QLineEdit`/`QTextEdit`, `QComboBox`, `QMenuBar`/`QMenu`,
      `QStatusBar`.
      Verificación: archivo `.qss` válido (sin errores de sintaxis QSS al
      cargarlo).
      Depende de: 8.4.4.

- [ ] **8.5.2** Implementar `app_core/theming.py`:
      `apply_theme(app: QApplication, theme: str = "dark") -> None` que
      lee `app_core/styles/<theme>.qss` y hace
      `app.setStyleSheet(contenido)`. Manejar `FileNotFoundError` con
      fallback a sin estilo (no romper si falta el archivo).
      Verificación: llamar `apply_theme(app, "dark")` y confirmar que
      `app.styleSheet()` no está vacío.
      Depende de: 8.5.1.

- [ ] **8.5.3** Llamar `apply_theme(app, "dark")` en `main.py` antes de
      `window.show()`. Ajustar `MainWindow.show_notification` y cualquier
      color hardcodeado de error/éxito para usar `setObjectName(...)`
      compatible con selectores del `.qss` (ej.
      `self.statusBar().setObjectName("status-error")` al mostrar error).
      Verificación visual: todos los paneles (Bandeja, Enviados, Papelera,
      Lector, Administrador de módulos, Composer) se ven con la nueva
      paleta, sin texto invisible por contraste.
      Depende de: 8.5.2.

### 8.6 — Ventanas flotantes avanzadas (sección 2.12)

- [ ] **8.6.1** En `MainWindow.add_floating_window`: usar
      `QSettings("Tardis", "Tardis")`. Al crear la ventana, si existe
      `floating/<title>/geometry`, `restoreGeometry(...)`. En
      `closeEvent` de la ventana flotante, `saveGeometry()` →
      `settings.setValue("floating/<title>/geometry", ...)`.
      Verificación: abrir "Redactar", mover/redimensionar, cerrar, volver
      a abrir → posición/tamaño se mantienen.
      Depende de: 8.5.3.

- [ ] **8.6.2** En `ComposerView.closeEvent`: si `to`/`title`/`body` (tras
      `strip()`) tienen contenido no vacío, mostrar
      `QMessageBox.question("¿Descartar borrador?", ...)`. Si el usuario
      elige "No"/cancelar, `event.ignore()`.
      Verificación: escribir algo en "Asunto", intentar cerrar → aparece
      el diálogo; elegir cancelar → la ventana NO se cierra; elegir
      confirmar → se cierra.
      Depende de: 8.1.4, 8.6.1.

- [ ] **8.6.3** **CHECKPOINT 6**: recorrido combinado — abrir "Redactar",
      mover ventana, escribir asunto, intentar cerrar (confirmar diálogo),
      cancelar, completar y enviar correo, reabrir "Redactar" y confirmar
      que recuerda posición/tamaño de la vez anterior (sin contenido,
      formulario limpio).
      Depende de: 8.6.2.

### 8.7 — Cierre de Fase 2

- [ ] **8.7.1** **CHECKPOINT FINAL**: recorrido completo end-to-end:
      bandeja con datos reales (8.0.10), envío multidestinatario
      (8.1.5), Enviados/Papelera correctos (8.2.5), notify dummy (8.3.3),
      administrador de módulos refleja estado real (8.4.4), tema oscuro
      aplicado (8.5.3), ventanas flotantes con persistencia y confirmación
      de descarte (8.6.3).
      Depende de: 8.6.3.

- [ ] **8.7.2** Crear/actualizar `modules/localmail/README.md` con dos
      notas para fases futuras:
      (a) Sección 2.13 de este documento (reuso de `service.py` con
      `mailboxes=[una_sola_casilla]` para el árbol Casilla>Carpeta del
      layout three-pane en Fase 3).
      (b) Sección 2.14 (tabla `DIR_USERS` como reemplazo futuro de
      `TARDIS_MAILBOXES`).
      Depende de: 8.7.1.

---

## 4. Próximas fases (referencia, sin detallar aún)

- **Fase 3**: layout three-pane (menú lateral por casilla/carpeta, lista,
  detalle); `pdf_export` (QtWebEngine + overlay de footer con pikepdf).
- **Fase 4**: `ai_lib` + `ai_corrections`.