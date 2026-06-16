# Módulo LocalMail

Módulo de correo electrónico local integrado en el cliente de escritorio Tardis.

## Estado de Implementación (Fase 5)

### Layout de Tres Paneles (Three-Pane Layout)
Implementado utilizando un `QSplitter` central que divide la pantalla en:
1. **Navegación Lateral (SidebarTreeView)**: Muestra un árbol jerárquico (`All Mailboxes` y casillas individuales) con 5 carpetas básicas cada una. Dispone de insignias (badges) con el conteo de correos no leídos en la bandeja de entrada (Inbox). **Nuevo en Fase 5**: Botón "+ Nuevo mensaje" de color rojo acento en la parte superior.
2. **Bandeja de Entrada / Lista de Correos (EmailListView)**: Muestra correos cargados desde la tabla `DIR_LOCAL-MAIL` en NocoDB y estilizados según prioridad y estado de lectura (negrita/normal) con soporte de filtros multi-casilla.
3. **Lector de Correos (ReaderView)**: Permite visualizar los metadatos y cuerpo de los correos seleccionados.

### Filtrado en Tiempo Real
El panel de la lista de correos se actualiza en vivo al escribir en la barra de búsqueda o al cambiar la prioridad en la barra de filtros (`FilterBarView`), sin necesidad de realizar llamadas de red adicionales a NocoDB.

### Marca de Lectura Automática
Seleccionar un correo marca automáticamente el mensaje como leído, actualizando su estado tanto visualmente en la interfaz como en el registro de NocoDB (`read = True` y `read_date`).

### Acciones Rápidas (Fase 5)
El lector dispone de una barra de acciones con 6 botones:

| Botón        | Descripción                                      |
|--------------|--------------------------------------------------|
| Responder    | Abre el compositor prellenado para responder     |
| Reenviar     | Abre el compositor prellenado para reenviar      |
| Archivar     | Mueve el correo a la carpeta Archive             |
| Eliminar     | Mueve el correo a la carpeta Trash               |
| Restaurar    | Restaura desde Archive/Trash a Inbox (oculto si no aplica) |
| Más          | Menú desplegable con "Ver encabezados técnicos"  |

### Responder y Reenviar (Fase 5)
- **Responder**: Abre el compositor con `to` = remitente original, asunto prefijo `"Re: "`, cuerpo citado con `"> "` por línea, y vincula `reply_to_uuid` y `thread_uuid`.
- **Reenviar**: Abre el compositor con `to` vacío, asunto prefijo `"Fwd: "`, cuerpo completo sin citar, y nuevo `thread_uuid` independiente.

### Adjuntos (Fase 5)
- **Subida**: `client.upload_attachment(file_path)` via `POST /api/v2/storage/upload`.
- **Límite**: 10MB por archivo configurable via `TARDIS_MAX_ATTACHMENT_MB`.
- **En compositor**: Botón "Adjuntar archivo" que abre `QFileDialog`. Los archivos se muestran como chips con nombre/tamaño y botón "×" para remover. Se suben solo al hacer clic en "Enviar".
- **En lector**: Sección "Adjuntos (N)" con botones "Abrir" (abre con app predeterminada) y "Descargar" (guarda mediante diálogo).

### Redacción de Correos (ComposerView)
Permite redactar correos en ventanas flotantes independientes.

**Nuevo en Fase 5**:
- Selector de firma (`QComboBox`) debajo del cuerpo, poblado con firmas de la casilla seleccionada.
- Auto-inserción de la firma predeterminada al abrir el compositor.
- Adjuntar archivos con validación de tamaño.
- Soporte para responder y reenviar via métodos de clase `for_reply()` y `for_forward()`.

### Confirmación de Descarte de Borradores
Si se intenta cerrar la ventana de redacción con texto en alguno de los campos de dirección, asunto o cuerpo, se solicita confirmación para evitar pérdidas accidentales, a menos que el correo se haya enviado con éxito.

### Persistencia de Geometría
Recuerda el tamaño y posición de la ventana del redactor guardando y recuperando su geometría en `QSettings` bajo la clave `floating/Compose/geometry`.

### Notificaciones en Tiempo Real (Fase 5)
- **Sondeo**: El `InboxNotifier` consulta la bandeja de entrada cada `TARDIS_POLL_INTERVAL_SECONDS` (default 60s).
- **Sonido**: Reproduce `shared/sounds/notify.wav` al detectar nuevos correos.
- **Destello**: Si la ventana no está enfocada, el icono de la barra de tareas destella.
- **Toast**: Muestra notificación con botón "Ver bandeja" que navega directamente a Inbox.
- **Configuración**: El sonido se puede activar/desactivar desde Settings > Apariencia.

### Firmas de Correo (Fase 5)
- **Almacenamiento**: Archivo `tardis_signatures.json` en la raíz del proyecto.
- **Editor**: Settings > Firmas con lista, formulario (nombre, casilla, HTML, logo, predeterminada) y vista previa en vivo con debounce de 300ms.
- **Soporte multi-casilla**: Cada firma se asocia a una casilla; se puede tener una firma predeterminada por casilla.
- **Logo inline**: Los SVGs de marca se incrustan directamente en el HTML de la firma.

---

## Servicios (modules/localmail/service.py)

### Funciones públicas

| Función | Descripción |
|---|---|
| `list_inbox(client, mailboxes, folder, only_unread, limit)` | Lista correos de bandeja/archivo/papelera |
| `list_sent(client, mailboxes, limit)` | Lista correos enviados (deduplicados) |
| `get_email(client, email_id)` | Obtiene un correo por ID |
| `mark_as_read(client, email_id)` | Marca como leído |
| `archive_email(client, email_id)` | Archiva un correo |
| `move_to_trash(client, email_id)` | Mueve a papelera |
| `send_email(client, from_user, to_users, subject, body, cc_users, priority, reply_to_uuid, thread_uuid_override, attachments)` | Envía un correo |
| `restore_email(client, email_id, mailbox_id)` | Restaura a bandeja de entrada (Fase 5) |
| `notify(client, to_users, subject, body, module_origin)` | Notificación desde otros módulos |

### Parámetros nuevos de send_email (Fase 5)
- `reply_to_uuid: str = ""` — UUID del mensaje original al que se responde.
- `thread_uuid_override: str | None = None` — UUID de hilo existente para mantener la conversación.
- `attachments: list[str] | None = None` — Rutas de archivos locales a adjuntar.

---

## Notas para Módulos y Desarrolladores

Para una descripción detallada sobre cómo integrar nuevos módulos, usar el sistema de notificaciones/toasts, registrar nodos en el sidebar, usar las utilidades de firmas, o persistir la geometría de paneles flotantes, consulte la guía general de desarrollo en [EXTENSION_POINTS.md](../../app_core/EXTENSION_POINTS.md).
