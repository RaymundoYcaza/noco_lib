# BUGFIX SPEC — Adjuntos no se preservan al enviar correos en LocalMail

> Self-contained document. Any LLM can pick it up without prior context.
> **Execution rule**: complete tasks **one at a time, in listed order**.
> Each task has Context / Steps / Verification / Depends on.
> **After finishing a task, the LLM MUST mark it `[x]` before proceeding.**
> Do not skip a task whose dependency is not yet `[x]`.
>
> **Language rule**: all code comments, docstrings, README files, inline
> documentation, and user-facing strings written or updated during this
> session MUST be in Spanish.

---

## 0. Síntoma reportado

Al crear un correo en la vista de redacción (ComposerView):
1. El usuario adjunta uno o más archivos usando el botón "📎 Adjuntar archivo".
2. No se presenta ningún error durante la selección ni durante el envío.
3. La notificación "Correo enviado correctamente" se muestra.
4. Sin embargo, en **Elementos Enviados** el correo no muestra el icono 📎 de adjunto.
5. El **destinatario** tampoco ve los adjuntos al abrir el correo.

**No hay errores visibles en la UI.** El adjunto simplemente desaparece.

---

## 1. Arquitectura del flujo de adjuntos

```
ComposerView                          service.py                          client.py
   │                                      │                                  │
   │ 1. user clicks "Adjuntar archivo"    │                                  │
   │    files → _attachment_paths         │                                  │
   │                                      │                                  │
   │ 2. user clicks "Enviar"              │                                  │
   │ ─────────────────────────────────►   │                                  │
   │    attachments=self._attachment_paths │                                  │
   │                                      │                                  │
   │                                  3. For each file:                      │
   │                                     client.upload_attachment(path) ───► │
   │                                      │                          │        │
   │                                      │                    4. POST /api/v2/storage/upload
   │                                      │                       (multipart + files=...)
   │                                      │                          │        │
   │                                      │                          │  ⚠️ La sesión tiene:
   │                                      │                          │  Content-Type: application/json
   │                                      │                          │  (conflicto con multipart)
   │                                      │                          │        │
   │                                      │                          │  5. ❌ HTTP 400 ERR_INVALID_JSON
   │                                      │                          │     NocoDB intenta parsear
   │                                      │                          │     el body multipart como JSON
   │                                      │                          │        │
   │                                      │◄── NocoResult.fail() ────────────│
   │                                      │                                  │
   │                                  6. upload_result.success = False       │
   │                                     attachment_objects queda vacío []   │
   │                                      │                                  │
   │                                  7. payload["Attachment"] = NUNCA se    │
   │                                     asigna (attachment_objects vacío)    │
   │                                      │                                  │
   │                                  8. table.create(payload sin Attachment)│
   │                                      │                          │        │
   │                                      │                    9. ✅ Registro creado
   │                                      │                       sin Attachment
   │                                      │                          │        │
   │                                      │◄── éxito sin adjuntos ───────────│
   │                                      │                                  │
   │ 10. ✅ "Correo enviado correctamente" │                                  │
   │      (sin error, sin adjuntos)        │                                  │
   │      attachment_errors = vacío        │                                  │
   │      → warning silencioso en log      │                                  │
```

---

## 2. Causa raíz: `Content-Type: application/json` en la sesión impide la subida multipart

### 2.1. Evidencia de los logs

```
[WARNING] Error al subir adjunto C:/Users/.../file.pdf:
  HTTP 400: {"error":"ERR_INVALID_JSON","message":"Invalid JSON in request body"}
[DEBUG] attachment_objects count=0, structure=[]
```

El upload del archivo **nunca se completa**. El log confirma que `attachment_objects` queda vacío porque el `upload_attachment` retorna `fail`.

### 2.2. Mecanismo del error

En **`noco_lib/noco_core/client.py`**, la sesión se inicializa con:

```python
self._session.headers.update({
    "xc-token": self.token,
    "Content-Type": "application/json",   # ← CABRITA
})
```

Cuando `upload_attachment` ejecuta:

```python
files = {"file": (path.name, fh, mime_type)}
ok, data, errors = self._request("POST", "/api/v2/storage/upload", files=files)
```

Y `_request` hace:

```python
resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
# kwargs = {"files": {"file": (...)}}
```

La librería `requests` DEBERÍA sobrescribir `Content-Type` a `multipart/form-data; boundary=...` cuando se pasa `files`. Sin embargo, el header `Content-Type: application/json` preestablecido en la sesión interfiere con este mecanismo, resultando en que NocoDB recibe el body multipart con `Content-Type: application/json` (o detecta ambos) y falla al intentar parsearlo como JSON.

### 2.3. Confirmación visual

| Header | Esperado | Real |
|---|---|---|
| `Content-Type` | `multipart/form-data; boundary=---...` | `application/json` (conflicto) |
| Body | Datos binarios del archivo con boundary | Multipart → NocoDB no puede parsear como JSON |
| Respuesta | `201 Created` con metadata del adjunto | `400 Bad Request: ERR_INVALID_JSON` |

### 2.4. Nota: no hay error visible en la UI

El método `_on_sent` en `ComposerView` muestra una advertencia de adjuntos fallidos **solo si** `result.meta.get("attachment_errors", [])` tiene elementos. Pero `upload_attachment` retorna `NocoResult.fail()` cuyo error queda en `attachment_errors` como `"HTTP 400: ..."`. Este error se loguea con `logging.warning` y se adjunta al `meta` del resultado final.

Sin embargo, en la UI, la advertencia se muestra solo como un toast warning pasajero. Si el usuario no lo ve (porque el toast desaparece), el bug es invisible.

---

## 3. Causas secundarias

### 3.1. Falta de logging diagnóstico en el punto crítico

No había logging que mostrara:
- Que `upload_attachment` estaba retornando `fail` (no `ok`)
- Que `attachment_objects` quedaba vacío

El `logging.warning` existente registra el error, pero si el usuario no revisa `tardis.log`, el bug es invisible.

### 3.2. `service.py` no propaga el error de adjuntos a la UI

En `_on_sent` de `ComposerView`:

```python
att_errors = result.meta.get("attachment_errors", [])
if att_errors:
    self.main_window.show_notification(
        f"Correo enviado, pero {len(att_errors)} adjunto(s) fallaron",
        "warning",
    )
```

Pero:
- `result.meta` solo recibe `attachment_errors` si `success_count > 0`.
- Si `success_count == 0`, el resultado es `fail` y `_on_sent` solo muestra el error genérico `"; ".join(result.errors)`.
- Si `success_count > 0` (el correo se envía a algunos destinatarios), el toast warning aparece pero es fácil de pasar por alto.
- Además, los errores de adjuntos se registran como `warning` en log, no como `error` — demasiado silencioso.

### 3.3. Fallback de campos URL incompleto en `reader_view.py`

En la línea 415:
```python
url = att.get("signedPath") or att.get("path", "")
```

Faltan los campos `"url"` y `"signedUrl"` en la cadena de resolución. Si NocoDB almacena la URL bajo un nombre diferente, los botones "Abrir" y "Descargar" no tendrían URL (causa secundaria, no relacionada con el bug principal).

---

## 4. Archivos modificados

```
tardis/
  noco_lib/noco_core/client.py          # MODIFIED: fix Content-Type session conflict + normalizar upload response + validar array vacío
  modules/localmail/service.py           # MODIFIED: (logging diagnóstico temporal removido)
  modules/localmail/views/reader_view.py # MODIFIED: ampliar fallback URL (signedUrl→signedPath→url→path)

specs/
  1781827200000_tardis-bugfix-attachments/
    README.md                            # NEW: esta spec (actualizada post-logs)
```

---

## 5. PLAN DE TAREAS (checklist — ejecutar en orden, marcar `[x]` al terminar)

### 5.1 — Logging diagnóstico (COMPLETADO, logs capturados)

> Los pasos 5.1.1 a 5.1.3 se ejecutaron y confirmaron la causa raíz.
> El log capturado muestra:
> ```
> [WARNING] Error al subir adjunto ...: HTTP 400: {"error":"ERR_INVALID_JSON","message":"Invalid JSON in request body"}
> [DEBUG] attachment_objects count=0, structure=[]
> ```
>
> **Conclusión: el upload falla por conflicto de Content-Type en la sesión.**
> El plan de correcciones se actualizó en 5.2 para reflejar la causa real.

- [x] **5.1.1** Agregar logging en `client.py` → `upload_attachment`.
- [x] **5.1.2** Agregar logging en `service.py` → `send_email`.
- [x] **5.1.3** Agregar logging en `reader_view.py` → `_render_attachments`.
- [x] **5.1.4** Solicitar al usuario que ejecute un test manual y comparta logs.
      → Logs recibidos. Hipótesis corregida.

### 5.2 — Correcciones (basadas en logs reales)

- [x] **5.2.1** Eliminar `Content-Type: application/json` de la sesión HTTP en `client.py`.

      **Context:**
      La línea `self._session.headers.update({"Content-Type": "application/json"})`
      interfiere con las peticiones multipart (subida de archivos).
      La librería `requests` ya asigna automáticamente `Content-Type`
      según el contenido enviado:
      - Si se pasa `json=` → asigna `application/json`.
      - Si se pasa `files=` → asigna `multipart/form-data; boundary=...`.
      - Si se pasa `data=` (dict) → asigna `application/x-www-form-urlencoded`.
      - Si no se pasa nada → no envía `Content-Type`.

      Al tener un `Content-Type` fijo en la sesión, se rompe este
      comportamiento automático.

      **Steps:**
      1. En `noco_lib/noco_core/client.py`, localizar la inicialización
         de la sesión (aproximadamente línea 40):
         ```python
         self._session.headers.update({
             "xc-token": self.token,
             "Content-Type": "application/json",
         })
         ```
      2. Eliminar la línea `"Content-Type": "application/json",`
         (pero mantener `"xc-token": self.token`).
      3. En `_request`, cuando el método es `POST`/`PATCH` y se envía
         `json=` como argumento, la librería `requests` asignará
         automáticamente `Content-Type: application/json`.
         Verificar que todos los usos de `_request` que envían JSON
         pasen `json=` correctamente (no `data=`):
         - `create_records`: `json=records` ✅
         - `update_records`: `json=records` ✅
         - `delete_records`: `json=payload` ✅
         - `create_column`: `json=column_def` ✅
         - `get_table_meta`: GET, no body ✅
         - `get_records`: GET, no body ✅
         - `upload_attachment`: `files=files` → multipart ✅

      **Verification:**
      1. Ejecutar la app y enviar un correo con adjunto.
      2. Verificar en el log:
         ```
         upload_attachment OK — type(data)=...
         attachment_objects count=1, structure=[{...}]
         ```
      3. Confirmar que NO aparece el error `ERR_INVALID_JSON`.
      4. Verificar que las operaciones CRUD regulares (crear, leer,
         actualizar registros) siguen funcionando correctamente.

      **Depends on:** 5.1.4 (completado).

- [x] **5.2.2** Normalizar respuesta de `upload_attachment` para extraer el objeto del array.

      **Context:**
      La API de NocoDB devuelve `[{...}]` (array de objetos adjuntos)
      aunque solo se suba un archivo. `service.py` espera un `dict`
      individual. Debemos normalizar en `client.py` para no tener
      que modificar `service.py`.

      **Steps:**
      1. En `noco_lib/noco_core/client.py`, método `upload_attachment`,
         justo después de la validación `if not data:` y antes del
         `return`, reemplazar:
         ```python
         return NocoResult.ok("create", data=data, affected_count=1)
         ```
         con:
         ```python
         # Normalizar: NocoDB devuelve [{}] o {} según versión/configuración
         if isinstance(data, list):
             normalized = data[0] if data else data
         else:
             normalized = data
         return NocoResult.ok("create", data=normalized, affected_count=1)
         ```

      **Verification:**
      `upload_result.data` es siempre un `dict` (no `list`).
      `attachment_objects` después del fix es `[{...}]` (no `[[{...}]]`).

      **Depends on:** 5.2.1.

- [x] **5.2.3** Opcional: agregar validación de respuesta exitosa en `upload_attachment`.

      **Context:**
      Si NocoDB devuelve un array vacío `[]`, el código actual
      retornaría éxito con `data=None` (por `data[0]` con lista vacía).
      Debemos asegurar que solo retornamos éxito si hay datos reales.

      **Steps:**
      1. Revisar el código de 5.2.2 y asegurar que si `data` es una
         lista vacía, se retorne `fail` en vez de `ok`.
      2. Agregar:
         ```python
         if isinstance(data, list) and len(data) == 0:
             return NocoResult.fail("create", "La respuesta del servidor está vacía (array sin elementos).")
         ```

      **Verification:**
      Si NocoDB devuelve `[]`, `upload_attachment` retorna `fail` con
      mensaje claro.

      **Depends on:** 5.2.2.

- [x] **5.2.4** Limpiar logging diagnóstico de `client.py`.

      **Steps:**
      1. Remover el `logger.debug` agregado en 5.1.1.
      2. Si el import de `logging` no se usa en ninguna otra parte
         (CRUD, helpers, etc.), removerlo también.

      **Verification:**
      No hay mensajes de diagnóstico de `upload_attachment` en el log.

      **Depends on:** 5.2.3.

- [x] **5.2.5** Remover logging diagnóstico de `service.py`.

      **Steps:**
      1. Remover los 3 `logger.debug` agregados en 5.1.2.
      2. Asegurarse de que no queden imports innecesarios.

      **Verification:**
      No hay mensajes de diagnóstico de `send_email` en el log.

      **Depends on:** 5.2.4.

- [x] **5.2.6** Ampliar fallback de campos URL en `reader_view.py`.

      **Context:**
      La URL del adjunto puede venir bajo distintos nombres según la
      configuración de almacenamiento de NocoDB (local, S3, etc.).

      **Steps:**
      1. En `modules/localmail/views/reader_view.py`, línea donde se
         extrae la URL del adjunto, reemplazar:
         ```python
         url = att.get("signedPath") or att.get("path", "")
         ```
         con:
         ```python
         url = (att.get("signedUrl") or att.get("signedPath")
                or att.get("url") or att.get("path", ""))
         ```

      **Verification:**
      Los adjuntos se pueden abrir y descargar independientemente del
      nombre del campo URL que use NocoDB.

      **Depends on:** 5.2.5.

- [x] **5.2.7** Remover logging diagnóstico de `reader_view.py`.

      **Steps:**
      1. Remover todos los `logger.debug` y `logger.warning` agregados
         en 5.1.3.
      2. Asegurarse de que no queden imports innecesarios.

      **Verification:**
      No hay mensajes de diagnóstico de `_render_attachments` en el log.

      **Depends on:** 5.2.6.

- [x] **5.2.8** CHECKPOINT — Verificación integral.

      **Steps:**
      1. Enviar un correo con al menos 2 archivos adjuntos.
      2. Verificar en Elementos Enviados:
         - El correo muestra el icono 📎 en la lista.
         - Al abrirlo, se ve la sección "Adjuntos (N)" con los archivos.
      3. Verificar en la bandeja de entrada del destinatario:
         - El correo muestra el icono 📎.
         - Al abrirlo, los adjuntos están presentes.
         - Los botones "Abrir" y "Descargar" funcionan.
      4. Verificar que no hay errores en `logs/tardis.log`.
      5. Verificar que las operaciones CRUD regulares siguen
         funcionando (crear, leer, actualizar emails sin adjuntos).
      6. Ejecutar `python -m pytest tests/test_localmail_service.py -v`
         para asegurar que no hay regresiones.

      **Verification:**
      Todos los puntos anteriores pasan.

      **Depends on:** 5.2.7.

---

## 6. Informe de complejidad (actualizado post-logs)

| Aspecto | Complejidad | Justificación |
|---|---|---|
| **Diagnóstico** | 🟢 Baja | Se agregaron ~10 líneas de logging. Confirmó la causa real. |
| **Fix 1: Content-Type en sesión** | 🟢 Baja | Eliminar 1 línea (`"Content-Type": "application/json"`) + verificar que `requests` maneja automáticamente el header correcto. |
| **Fix 2: Normalizar respuesta array→dict** | 🟢 Baja | 3 líneas con `isinstance` check. |
| **Fix 3: Validar array vacío** | 🟢 Baja | 1 línea adicional. |
| **Fix 4: Fallback URL en reader** | 🟢 Baja | 1 línea: agregar campos al `or` chain. |
| **Limpieza de logging** | 🟢 Baja | Remover ~10 líneas. |
| **Verificación** | 🟡 Media | Requiere prueba manual con NocoDB real. |
| **Riesgo de regresión** | 🟡 Bajo | Eliminar `Content-Type` de la sesión podría afectar endpoints que dependían de ese header. Pero `requests` asigna automáticamente el correcto según el tipo de contenido (json, multipart, form-urlencoded). |

**Complejidad general: MUY BAJA.** El bug principal es un header mal
configurado en la sesión HTTP. Los cambios son mínimos y localizados.

---

## 7. Riesgos identificados (actualizado post-logs)

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| **R1:** Eliminar `Content-Type` de la sesión rompe peticiones JSON | Baja | `requests` asigna automáticamente `application/json` cuando se usa el parámetro `json=`. Todos los endpoints que envían JSON en el proyecto usan `json=`. |
| **R2:** NocoDB versión local devuelve objeto único (no array) desde upload | Baja | El fix `isinstance(data, list)` es seguro: si ya es dict, lo pasa igual. |
| **R3:** NocoDB devuelve array vacío `[]` desde upload | Muy Baja | El fix 5.2.3 lo convierte en `fail` con mensaje claro. |
| **R4:** El campo `signedUrl` es el único que funciona, y expira | Media | El fallback ordena por preferencia: `signedUrl` (firmada, descarga directa) → `signedPath` → `url` → `path`. La función `_download_attachment_file_sync` ya agrega el `xc-token` para URLs que requieren autenticación. |
| **R5:** Las peticiones GET sin `Content-Type` no funcionan | Cero | GET requests no llevan body, por lo que `Content-Type` es irrelevante. El header no se envía, que es el comportamiento correcto. |
