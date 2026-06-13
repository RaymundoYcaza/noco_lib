# Módulo LocalMail

Módulo de correo electrónico local integrado en el cliente de escritorio Tardis.

## Estado de Implementación (Fase 2)

- **Bandeja de entrada (InboxView)**: Completamente funcional. Muestra correos cargados desde la tabla `DIR_LOCAL-MAIL` en NocoDB y estilizados según prioridad y estado de lectura (negrita/normal) con soporte de filtros multi-casilla.
- **Enviados y Papelera**: Completamente funcional. Añadidas las vistas para correos Enviados y en la Papelera, con la posibilidad de mover elementos a la papelera, restaurar correos y eliminar de forma permanente.
- **Lector de correos (ReaderView)**: Muestra los detalles de un correo al hacer doble click en la bandeja de entrada, enviados o papelera.
- **Redacción de correos (ComposerView)**: Permite enviar correos en ventanas flotantes con persistencia de geometría (gracias a `QSettings` guardando/restaurando la clave `floating/<title>/geometry`).
- **Confirmación de descarte**: Se previene el descarte accidental de borradores. Si el usuario intenta cerrar el `ComposerView` con contenido no vacío en destinatario, asunto o mensaje, se solicita confirmación con un `QMessageBox`.
- **Archivado**: Se puede archivar un correo mediante el botón "Archivar" de la barra de acciones o bien a través del menú contextual (click derecho).
- **Administración de Módulos (ModuleAdmin)**: Refleja el estado real (activo/inactivo) de los módulos en el cliente Tardis.
- **Tematización**: Se aplica el estilo oscuro personalizado de forma global.

---

## Notas para Fases Futuras

### 1. Reuso de `service.py` en Layout "Three-Pane" (Fase 3)
En la Fase 3 se diseñará un layout de tres paneles:
```
┌─────────┬─────────────┬─────────────────┐
│ Menú    │ Lista       │ Detalle         │
│ lateral │ Emails      │ Contenido       │
└─────────┴─────────────┴─────────────────┘
```
El panel de "Menú lateral" consistirá en un árbol jerárquico `Casilla > Carpeta`. Cada nodo (por ejemplo, una combinación de una casilla y una carpeta) corresponderá a una llamada a la función del servicio `service.list_inbox(client, mailboxes=[esa_casilla], folder=esa_carpeta)`.
La lógica implementada en la Fase 2 en `service.py` (el parámetro `mailboxes: list[str]`) está diseñada para ser reutilizada directamente sin cambios en la Fase 3; sólo cambiará la interfaz de usuario al invocarla desde un árbol en lugar de pestañas.

### 2. Tabla `DIR_USERS` como Reemplazo Futuro de `TARDIS_MAILBOXES`
Se recomienda crear en el futuro una tabla `DIR_USERS` en NocoDB para relacionar dinámicamente cada usuario del sistema operativo (Windows user) con la lista de casillas de correo electrónico que tiene asignadas. Esto permitirá reemplazar la variable de entorno local `TARDIS_MAILBOXES` por una configuración centralizada y administrable directamente en la base de datos de NocoDB.
