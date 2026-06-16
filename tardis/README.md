# 🛸 Tardis

Cliente de escritorio modular tipo Outlook/Thunderbird en Python + PySide6.

**Versión actual:** `v0.1.0.1` (ver `tardis/VERSION`)

---

## Funcionalidades

- 📧 **LocalMail** — Cliente de correo electrónico con bandeja de entrada, redacción, visor y firma digital
- 📄 **PDF Export** — Exportación de documentos a PDF con branding, plantillas Jinja2 y Chromium
- 🤖 **AI Corrections** — Módulo de correcciones asistidas por IA (Ollama)
- 🔔 **Notificaciones** — Sonido, destello en barra de tareas y toasts con acción
- ⚙️ **Configuración** — Gestión de módulos, conexión NocoDB, firmas y diagnóstico
- 🎨 **Temas dinámicos** — Basados en JSON (Inorizonti como tema predeterminado)

---

## Instalación

### Opción 1: Instalador (recomendado)

1. Descarga el instalador desde la ruta de red:
   ```
   X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis\Tardis-v0.1.0.X-Setup.exe
   ```
2. Ejecuta el instalador y sigue los pasos.
3. Copia el archivo `.env.example` (junto al .exe) a `.env` y configura tus credenciales:
   ```env
   NOCO_BASE_URL=https://tu-servidor.nocodb.com
   NOCO_TOKEN=tu-token-de-api
   NOCO_BASE_ID=id-de-tu-base
   TARDIS_MAILBOXES=usuario1@empresa.com;usuario2@empresa.com
   ```
4. Ejecuta Tardis desde el acceso directo.

### Opción 2: Carpeta portable

1. Copia la carpeta `Tardis-vX.X.X.X/` desde la ruta de red a tu PC.
2. Coloca el archivo `.env` junto a `Tardis.exe`.
3. Ejecuta `Tardis.exe`.

> **Nota:** No necesitas tener Python instalado. El ejecutable incluye todo lo necesario.

---

## Actualización

Tardis busca actualizaciones automáticamente 3 segundos después de iniciar:

1. Consulta la ruta configurada (`TARDIS_UPDATE_PATH`) en busca de un archivo `VERSION` remoto.
2. Si la versión remota es mayor, muestra un diálogo:
   ```
   Hay una nueva versión disponible: v0.2.0.1 (actual: v0.1.0.42)
   ¿Deseas descargar e instalar la actualización?
   ```
3. Al aceptar, se ejecuta el instalador y Tardis se cierra.

### Configurar la ruta de actualización

Puedes cambiar la ruta en **Configuración > Apariencia > Actualizaciones**
o mediante la variable de entorno:
```env
TARDIS_UPDATE_PATH=X:\B02_SOFTWARE-LIBRARY\00-INTERNOS\Tardis
```

> Si la ruta de red no está disponible, Tardis continúa normalmente sin mostrar error.

---

## Compilación desde código fuente

### Requisitos

- Python 3.13+
- PySide6
- PyInstaller (para empaquetado)
- Poppler (para PDF, opcional)

### Pasos

```bash
# Clonar el repositorio
git clone <repo-url>
cd tardis-monorepo/tardis

# Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate

# Instalar dependencias
pip install -e .
pip install pyinstaller

# Copiar archivo de configuración
copy .env.example .env
# Editar .env con tus credenciales NocoDB

# Ejecutar en desarrollo
python app_core/main.py

# Compilar para distribución
python build.py                # Build estándar (carpeta)
python build.py --portable      # Build portable (un solo .exe)
python build.py --installer     # Build + instalador Inno Setup
```

### Estructura del proyecto

```
tardis/
├── VERSION                     # Versión de la aplicación (x.y.z.build)
├── build.py                    # Script de build con PyInstaller
├── .env.example                # Template de configuración
├── app_core/                   # Núcleo de la aplicación
│   ├── main.py                 # Punto de entrada
│   ├── main_window.py          # Ventana principal
│   ├── config.py               # Configuración (.env + entorno)
│   ├── version.py              # Sistema de versionado
│   ├── updater.py              # Actualización automática
│   ├── notifier.py             # Notificador de bandeja de entrada
│   ├── concurrency.py          # Utilidades de concurrencia (run_async)
│   ├── splash.py               # Pantalla de inicio
│   ├── theme_engine.py         # Motor de temas JSON
│   ├── views/                  # Vistas de configuración
│   └── widgets/                # Widgets reutilizables
├── modules/                    # Módulos funcionales
│   ├── localmail/              # Cliente de correo
│   ├── pdf_export/             # Exportación PDF
│   ├── ai_corrections/         # Correcciones con IA
│   └── _template_module/       # Template para nuevos módulos
├── shared/                     # Assets compartidos
│   ├── brands/                 # Logos y estilos por marca
│   ├── schemas/                # Esquemas JSON
│   ├── sounds/                 # Sonidos de notificación
│   └── templates/              # Plantillas Jinja2
├── scripts/                    # Scripts de utilidad
│   └── bump_version.py         # Auto-incremento de build
├── installer/                  # Instalador Inno Setup
│   └── tardis_setup.iss
└── specs/                      # Especificaciones por fase
    └── 1781569500000_tardis-spec-phase6/
```

---

## Resoluciones de Diseño

### noco_lib

Para mantener el código existente de `noco_lib` (`noco_core`, `noco_discovery`, `noco_ext`, `noco_modules`, `noco_cli`) completamente idéntico y sin modificar su contenido (evitando romper sus imports absolutos internos como `from noco_core.config import load_env`), se ha decidido:
- Mantener la estructura interna intacta dentro de `tardis/noco_lib/`.
- En el punto de entrada de la aplicación (`app_core/main.py`), los scripts de test y de CLI, se añadirá la ruta de `tardis/noco_lib/` al `sys.path` de Python al iniciar.
- Esto asegura la compatibilidad tanto para llamadas internas como para imports estructurados desde módulos externos del monorepo (`from noco_lib.noco_core import NocoClient`).

### NocoDB: almacenamiento local

Esta instancia de NocoDB usa almacenamiento **local** (no S3).
Los attachments devuelven `signedPath` en lugar de `signedUrl`.
Ver `EXTENSION_POINTS.md` sección 5 para más detalles.
