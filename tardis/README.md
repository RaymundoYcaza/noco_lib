# Tardis Monorepo

Proyecto "Tardis" - Cliente de escritorio modular (Outlook/Thunderbird) en Python + PySide6.

## Resoluciones de Diseño e Importación

### noco_lib
Para mantener el código existente de `noco_lib` (`noco_core`, `noco_discovery`, `noco_ext`, `noco_modules`, `noco_cli`) completamente idéntico y sin modificar su contenido (evitando romper sus imports absolutos internos como `from noco_core.config import load_env`), se ha decidido:
- Mantener la estructura interna intacta dentro de `tardis/noco_lib/`.
- En el punto de entrada de la aplicación (`app_core/main.py`), los scripts de test y de CLI, se añadirá la ruta de `tardis/noco_lib/` al `sys.path` de Python al iniciar.
- Esto asegura la compatibilidad tanto para llamadas internas como para imports estructurados desde módulos externos del monorepo (`from noco_lib.noco_core import NocoClient`).

## Empaquetado y Distribución

### 1. Proceso de Build
Para compilar la aplicación en modo **one-folder** (carpeta autocontenida), sigue estos pasos:

1. Asegúrate de tener el entorno virtual activo y todas las dependencias instaladas.
2. Ejecuta el siguiente comando desde el directorio `tardis/`:
   ```powershell
   # Si ya existe una compilación previa, limpia el directorio de salida
   Remove-Item -Recurse -Force dist
   
   # Ejecutar el empaquetado con PyInstaller usando la configuración del archivo spec
   ..\.venv_win\Scripts\pyinstaller --clean --noconfirm tardis.spec
   ```
3. Al finalizar, el resultado compilado se ubicará en la carpeta `tardis/dist/Tardis/`.

### 2. Distribución a Compañeros
Para compartir la aplicación:
1. Copia toda la carpeta `tardis/dist/Tardis/` (y no solo el archivo `Tardis.exe`, ya que requiere las librerías e intérprete ubicados en `_internal`).
2. Comprime la carpeta en un archivo `.zip` para facilitar su distribución.
3. Tus compañeros **no necesitan tener Python instalado** en sus computadoras para ejecutarlo.

### 3. Configuración del Entorno (.env)
El ejecutable no incluye credenciales de base de datos de manera estática.
- Para conectarse, el usuario debe colocar un archivo `.env` en la raíz de la carpeta (junto a `Tardis.exe`).
- Se incluye un archivo `.env.example` en la carpeta `_internal` como referencia. Las variables requeridas son:
  ```env
  NOCO_BASE_URL = <URL_de_tu_servidor_NocoDB>
  NOCO_TOKEN = <Token_de_acceso_NocoDB>
  NOCO_BASE_ID = <ID_de_la_base_de_datos>
  TARDIS_LOCALMAIL_TABLE = DIR_LOCAL-MAIL
  ```

### 4. Cómo Actualizar
Cuando realices cambios en el código y necesites distribuir una nueva versión:
1. Asegúrate de que no haya ninguna instancia de `Tardis.exe` ejecutándose en segundo plano (para evitar bloqueos de archivos en `dist/`). Puedes forzar su cierre desde PowerShell con:
   ```powershell
   Stop-Process -Name Tardis -Force -ErrorAction SilentlyContinue
   ```
2. Limpia la carpeta `dist/` y vuelve a ejecutar el comando de PyInstaller.
3. Distribuye la carpeta `dist/Tardis/` actualizada.
4. **Nota importante:** Advierte a tus compañeros que no sobrescriban su archivo `.env` existente al descomprimir la nueva versión para que conserven su configuración de conexión.
