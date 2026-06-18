"""
Cliente core: capa más baja, habla directo con la API v2 de NocoDB.

Responsabilidades:
- Autenticación (header xc-token).
- Construcción de URLs.
- Paginación automática en lecturas.
- Reintentos simples ante fallos transitorios.
- Traducción de errores HTTP a NocoResult.fail(...)

NO contiene lógica de negocio ni de descubrimiento de relaciones.
Eso vive en noco_discovery y noco_ext.
"""

from __future__ import annotations
import time
import requests
from typing import Optional, Any

from .result import NocoResult


class NocoClient:
    """
    Cliente base. Se instancia una vez por base de datos / token.

    Ejemplo:
        client = NocoClient(base_url="https://app.nocodb.com", token="xxx")
        table = client.table("Clientes")
        result = table.read()
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        base_id: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2,
        page_size: int = 100,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.base_id = base_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.page_size = page_size
        self._session = requests.Session()
        self._session.headers.update({
            "xc-token": self.token,
            # NOTA: NO fijamos Content-Type aquí. La librería requests lo asigna
            # automáticamente según el contenido: json= → application/json,
            # files= → multipart/form-data, data=dict → application/x-www-form-urlencoded.
        })

    # ------------------------------------------------------------------
    # Bajo nivel
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> tuple[bool, Any, list[str]]:
        url = f"{self.base_url}{path}"
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(method, url, timeout=self.timeout, **kwargs)
                if resp.status_code >= 400:
                    return False, None, [f"HTTP {resp.status_code}: {resp.text[:500]}"]
                if resp.content:
                    return True, resp.json(), []
                return True, None, []
            except requests.RequestException as exc:
                last_err = str(exc)
                time.sleep(0.5 * (attempt + 1))
        return False, None, [f"Fallo de red tras reintentos: {last_err}"]

    # ------------------------------------------------------------------
    # Metadatos de tablas
    # ------------------------------------------------------------------
    def get_table_meta(self, table_id: str) -> NocoResult:
        ok, data, errors = self._request("GET", f"/api/v2/meta/tables/{table_id}")
        if not ok:
            return NocoResult.fail("schema", errors, table=table_id)
        return NocoResult.ok("schema", data=data, table=table_id)

    def list_tables(self, base_id: Optional[str] = None) -> NocoResult:
        bid = base_id or self.base_id
        if not bid:
            return NocoResult.fail("schema", "Se requiere base_id (no fue provisto ni configurado en el cliente).")
        ok, data, errors = self._request("GET", f"/api/v2/meta/bases/{bid}/tables")
        if not ok:
            return NocoResult.fail("schema", errors)
        return NocoResult.ok("schema", data=data.get("list", []), meta={"raw": data})

    def find_table_id_by_name(self, name: str, base_id: Optional[str] = None) -> NocoResult:
        listing = self.list_tables(base_id=base_id)
        if not listing.success:
            return listing
        for t in listing.data:
            if t.get("title", "").lower() == name.lower() or t.get("table_name", "").lower() == name.lower():
                return NocoResult.ok("schema", data=t, table=name)
        return NocoResult.fail("schema", f"No se encontró ninguna tabla llamada '{name}'.", table=name)

    # ------------------------------------------------------------------
    # CRUD de registros (operados sobre table_id)
    # ------------------------------------------------------------------
    def get_records(self, table_id: str, where: Optional[str] = None,
                     limit: Optional[int] = None, offset: int = 0,
                     fields: Optional[list[str]] = None,
                     sort: Optional[str] = None) -> NocoResult:
        params = {"offset": offset, "limit": self.page_size}
        if where:
            params["where"] = where
        if fields:
            params["fields"] = ",".join(fields)
        if sort:
            params["sort"] = sort

        all_records = []
        fetched = 0
        while True:
            ok, data, errors = self._request(
                "GET", f"/api/v2/tables/{table_id}/records", params=params
            )
            if not ok:
                return NocoResult.fail("read", errors, table=table_id)

            records = data.get("list", [])
            all_records.extend(records)
            fetched += len(records)

            page_info = data.get("pageInfo", {})
            if limit and fetched >= limit:
                all_records = all_records[:limit]
                break
            if page_info.get("isLastPage", True):
                break
            params["offset"] += self.page_size

        return NocoResult.ok("read", data=all_records, table=table_id,
                              affected_count=len(all_records))

    def create_records(self, table_id: str, records: dict | list[dict]) -> NocoResult:
        ok, data, errors = self._request(
            "POST", f"/api/v2/tables/{table_id}/records", json=records
        )
        if not ok:
            return NocoResult.fail("create", errors, table=table_id)
        affected = len(data) if isinstance(data, list) else 1
        return NocoResult.ok("create", data=data, table=table_id, affected_count=affected)

    def update_records(self, table_id: str, records: dict | list[dict]) -> NocoResult:
        """records debe incluir 'Id' (o el primary key) de cada fila a actualizar."""
        ok, data, errors = self._request(
            "PATCH", f"/api/v2/tables/{table_id}/records", json=records
        )
        if not ok:
            return NocoResult.fail("update", errors, table=table_id)
        affected = len(data) if isinstance(data, list) else 1
        return NocoResult.ok("update", data=data, table=table_id, affected_count=affected)

    def delete_records(self, table_id: str, record_ids: int | list[int]) -> NocoResult:
        if isinstance(record_ids, int):
            payload = {"Id": record_ids}
        else:
            payload = [{"Id": i} for i in record_ids]
        ok, data, errors = self._request(
            "DELETE", f"/api/v2/tables/{table_id}/records", json=payload
        )
        if not ok:
            return NocoResult.fail("delete", errors, table=table_id)
        affected = len(payload) if isinstance(payload, list) else 1
        return NocoResult.ok("delete", data=data, table=table_id, affected_count=affected)

    # ------------------------------------------------------------------
    # Gestión de columnas
    # ------------------------------------------------------------------
    def create_column(self, table_id: str, column_def: dict) -> NocoResult:
        """
        column_def ejemplo:
            {"title": "Categoria", "uidt": "SingleSelect",
             "colOptions": {"options": [{"title": "A"}, {"title": "B"}]}}
        """
        ok, data, errors = self._request(
            "POST", f"/api/v2/meta/tables/{table_id}/columns", json=column_def
        )
        if not ok:
            return NocoResult.fail("update", errors, table=table_id)
        return NocoResult.ok("update", data=data, table=table_id, affected_count=1)

    def update_column(self, column_id: str, column_def: dict) -> NocoResult:
        """
        Para renombrar un campo: column_def = {"title": "Categoria"}
        Para modificar opciones de un select: column_def = {"colOptions": {"options": [...]}}
        """
        ok, data, errors = self._request(
            "PATCH", f"/api/v2/meta/columns/{column_id}", json=column_def
        )
        if not ok:
            return NocoResult.fail("update", errors)
        return NocoResult.ok("update", data=data, affected_count=1)

    # ------------------------------------------------------------------
    # Carga de archivos adjuntos (storage upload)
    # ------------------------------------------------------------------
    def upload_attachment(self, file_path: str) -> NocoResult:
        """
        Sube un archivo adjunto al almacenamiento de NocoDB.

        Realiza un POST multipart a ``/api/v2/storage/upload``.
        Verifica que el archivo exista y no supere el límite configurado
        en ``TARDIS_MAX_ATTACHMENT_MB`` (default 10 MB).

        Parameters
        ----------
        file_path : str
            Ruta local del archivo a subir.

        Returns
        -------
        NocoResult
            Con ``data`` conteniendo el objeto attachment de NocoDB:
            ``{"url": ..., "title": ..., "mimetype": ..., "size": ...}``
            en caso de éxito.
        """
        import os
        import mimetypes
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return NocoResult.fail("create", f"Archivo no encontrado: {file_path}")

        # Validar tamaño máximo
        max_mb = int(os.environ.get("TARDIS_MAX_ATTACHMENT_MB", "10"))
        max_bytes = max_mb * 1024 * 1024
        file_size = path.stat().st_size
        if file_size > max_bytes:
            return NocoResult.fail(
                "create",
                f"El archivo supera el límite de {max_mb}MB: {file_path} ({file_size / 1024 / 1024:.1f}MB)"
            )

        # Detectar mimetype
        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(file_path, "rb") as fh:
                files = {"file": (path.name, fh, mime_type)}
                ok, data, errors = self._request(
                    "POST", "/api/v2/storage/upload", files=files
                )

            if not ok:
                return NocoResult.fail("create", errors)

            if not data:
                return NocoResult.fail("create", "La respuesta del servidor no contiene datos.")

            # Normalizar: la API de NocoDB puede devolver [{}] (array) o {} (dict)
            if isinstance(data, list):
                if len(data) == 0:
                    return NocoResult.fail(
                        "create",
                        "La respuesta del servidor está vacía (array sin elementos)."
                    )
                normalized = data[0]
            else:
                normalized = data
            return NocoResult.ok("create", data=normalized, affected_count=1)

        except Exception as exc:
            return NocoResult.fail("create", [f"Error al subir archivo: {str(exc)}"])

    # ------------------------------------------------------------------
    # Atajo de uso "tabla"
    # ------------------------------------------------------------------
    def table(self, name_or_id: str, base_id: Optional[str] = None) -> "NocoTable":
        """
        Obtiene una instancia de NocoTable resolviendo name_or_id como ID directo
        o como nombre de tabla.
        
        Estrategia:
        1. Intentar primero como table_id directo (llamada GET a /meta/tables/{id})
        2. Si falla, intentar como nombre con find_table_id_by_name()
        3. Si ambas fallan, devolver NocoTable en estado "no resuelto" (NO lanza excepción)
        
        Args:
            name_or_id: Nombre de la tabla o table_id de NocoDB
            base_id: ID de la base de datos (opcional, usa el default si None)
            
        Returns:
            NocoTable: Instancia de tabla (puede estar en estado no resuelto)
        """
        from .table import NocoTable

        target_base = base_id or self.base_id

        # 1) Intentar como table_id directo
        meta = self.get_table_meta(name_or_id)
        if meta.success:
            table_name = meta.data.get("title", name_or_id) if meta.data else name_or_id
            return NocoTable(client=self, table_id=name_or_id, name=table_name)

        # 2) Intentar como nombre
        lookup = self.find_table_id_by_name(name_or_id, base_id=target_base)
        if lookup.success:
            table_name = lookup.data.get("title", name_or_id) if lookup.data else name_or_id
            table_id = lookup.data.get("id") if lookup.data else None
            return NocoTable(client=self, table_id=table_id, name=table_name)

        # 3) No resuelto: NO lanzar excepción
        meta_errors = meta.errors if meta.errors else "Sin detalles"
        lookup_errors = lookup.errors if lookup.errors else "Sin detalles"
        
        combined_error = (
            f"No se encontró tabla con id o nombre '{name_or_id}'. "
            f"Detalle por id: {meta_errors}. "
            f"Detalle por nombre: {lookup_errors}."
        )
        
        return NocoTable(
            client=self,
            table_id=None,
            name=name_or_id,
            resolution_error=combined_error
        )
