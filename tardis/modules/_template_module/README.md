---
nombre: _template_module
paneles: []               # Paneles agregados con app.add_dock_panel
ventanas_flotantes: []     # Ventanas agregadas con app.add_floating_window
tablas_noco_usadas: []     # Tablas consultadas/modificadas de NocoDB (ej. DIR_LOCAL-MAIL)
descripcion: >
  Plantilla base para crear nuevos módulos autoinstalables en la interfaz de Tardis.
---

# Plantilla de Módulo Tardis

Este directorio sirve como plantilla de referencia para el desarrollo de módulos auto-registrables para la aplicación Tardis.

## Estructura Recomendada

Cualquier módulo debe estructurarse idealmente de la siguiente manera:

```
mi_modulo/
├── __init__.py
├── README.md              # Este archivo con front-matter YAML de metadatos
├── module.py              # Contiene la función register(app, client)
├── service.py             # Lógica de negocio/consultas a noco_lib
└── views/                 # Interfaces de usuario PySide6 (widgets)
    ├── __init__.py
    └── mi_vista.py
```

## Reglas de Oro

1. **Sin Llamadas Bloqueantes:** Nunca llames a la API de NocoDB (ej. `table.read()`, `table.create()`) directamente desde el hilo principal de la UI o en la función `register`.
2. **Uso de Concurrencia:** Utiliza `app_core.concurrency.run_async` desde tus componentes visuales para disparar llamadas de red en segundo plano y recibir los callbacks de respuesta.
3. **Manejo de Errores:** Las llamadas de negocio en `service.py` deben retornar un objeto `NocoResult` e internamente capturar cualquier error sin lanzar excepciones no controladas.
