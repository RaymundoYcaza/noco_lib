# Módulo LocalMail

Módulo de correo electrónico local integrado en el cliente de escritorio Tardis.

## Estado de Implementación (Fase 3)

- **Layout de Tres Paneles (Three-Pane Layout)**: Implementado utilizando un `QSplitter` central que divide la pantalla en:
  1. **Navegación Lateral (SidebarTreeView)**: Muestra un árbol jerárquico (`All Mailboxes` y casillas individuales) con un total de 5 carpetas básicas cada una. Dispone de insignias (badges) con el conteo de correos no leídos en la bandeja de entrada (Inbox).
  2. **Bandeja de Entrada / Lista de Correos (EmailListView)**: Muestra correos cargados desde la tabla `DIR_LOCAL-MAIL` en NocoDB y estilizados según prioridad y estado de lectura (negrita/normal) con soporte de filtros multi-casilla.
  3. **Lector de Correos (ReaderView)**: Permite visualizar los metadatos y cuerpo de los correos seleccionados.

- **Filtrado en Tiempo Real**: El panel de la lista de correos se actualiza en vivo al escribir en la barra de búsqueda o al cambiar la prioridad en la barra de filtros (`FilterBarView`), sin necesidad de realizar llamadas de red adicionales a NocoDB.
- **Marca de Lectura Automática**: Seleccionar un correo marca automáticamente el mensaje como leído, actualizando su estado tanto visualmente en la interfaz como en el registro de NocoDB (`read = True` y `read_date`).
- **Acciones Rápidas de Archivación y Papelera**: El lector dispone de botones de acción rápida para archivar (`Archive`) o mover a la papelera (`Move to Trash`), refrescando la lista de correos automáticamente al finalizar la operación y desactivándose si ya se encuentra en dicha carpeta.
- **Redacción de Correos (ComposerView)**: Permite redactar correos en ventanas flotantes independientes.
- **Confirmación de Descarte de Borradores**: Si se intenta cerrar la ventana de redacción con texto en alguno de los campos de dirección, asunto o cuerpo, se solicita confirmación en inglés (`Discard draft?`) para evitar pérdidas accidentales, a menos que el correo se haya enviado con éxito.
- **Persistencia de Geometría**: Recuerda el tamaño y posición de la ventana del redactor guardando y recuperando su geometría en `QSettings` bajo la clave `floating/Compose/geometry`.

---

## Notas para Módulos y Desarrolladores

Para una descripción detallada sobre cómo integrar nuevos módulos, usar el sistema de notificaciones/toasts, registrar nodos en el sidebar o persistir la geometría de paneles flotantes, consulte la guía general de desarrollo en [EXTENSION_POINTS.md](file:///P:/REPOs/noco_lib/tardis/app_core/EXTENSION_POINTS.md).
