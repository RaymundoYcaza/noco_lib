# Módulo LocalMail

Módulo de correo electrónico local integrado en el cliente de escritorio Tardis.

## Estado de Implementación (Fase 1)

- **Bandeja de entrada (InboxView)**: Completamente funcional. Muestra correos cargados desde la tabla `DIR_LOCAL-MAIL` en NocoDB y estilizados según prioridad y estado de lectura (negrita/normal).
- **Lector de correos (ReaderView)**: Completamente funcional. Muestra los detalles de un correo al hacer doble click en la bandeja de entrada.
- **Redacción de correos (ComposerView)**: Completamente funcional en ventana flotante independiente.
- **Archivado**: Se puede archivar un correo mediante el botón "Archivar" de la barra de acciones o bien a través del menú contextual (click derecho) sobre cualquier fila de la bandeja de entrada.

### Nota sobre la Papelera (move_to_trash)

La lógica para enviar correos a la papelera (`move_to_trash`) está completamente implementada a nivel de servicio en `service.py`, pero la integración con la interfaz de usuario queda pendiente para la **Fase 2** (donde se añadirán vistas explícitas para la "Papelera" y la carpeta de "Enviados").
