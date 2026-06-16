import sys
import uuid
import datetime
import logging
from typing import Any
from pathlib import Path

# Add paths to sys.path
tardis_dir = Path(__file__).resolve().parent.parent.parent
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

noco_lib_dir = tardis_dir / "noco_lib"
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from noco_lib.noco_core.result import NocoResult
from noco_lib.noco_core.client import NocoClient

def list_inbox(client: NocoClient, mailboxes: list[str], folder: str = "inbox",
               only_unread: bool = False, limit: int = 50) -> NocoResult:
    """
    where = (mailbox_owner,in,<mailboxes>)~and(folder,eq,<folder>)
    si only_unread: ~and(read,eq,0)
    sort = "-CreatedAt" (más recientes primero)
    """
    if not mailboxes:
        return NocoResult.fail("read", "No hay casillas configuradas (TARDIS_MAILBOXES vacío).", table="DIR_LOCAL-MAIL")
        
    table = client.table("DIR_LOCAL-MAIL")
    in_values = ",".join(mailboxes)
    where = f"(mailbox_owner,in,{in_values})~and(folder,eq,{folder})"
    if only_unread:
        where += "~and(read,eq,0)"
        
    result = table.read(where=where, limit=limit, sort="-CreatedAt")
    if result.success:
        return NocoResult.ok("read", data=result.data, table="DIR_LOCAL-MAIL", affected_count=len(result.data) if result.data else 0)
    return result

def list_sent(client: NocoClient, mailboxes: list[str], limit: int = 50) -> NocoResult:
    """
    where = (from,in,<mailboxes>)
    sort = "-CreatedAt" (más recientes primero)
    """
    if not mailboxes:
        return NocoResult.fail("read", "No hay casillas configuradas (TARDIS_MAILBOXES vacío).", table="DIR_LOCAL-MAIL")
        
    table = client.table("DIR_LOCAL-MAIL")
    in_values = ",".join(mailboxes)
    where = f"(from,in,{in_values})"
    
    result = table.read(where=where, limit=limit, sort="-CreatedAt")
    if result.success:
        # Deduplicar en Python por message_uuid (conservar el primero en el orden recibido, ya viene ordenado por -CreatedAt)
        seen_uuids = set()
        deduplicated_data = []
        if result.data:
            for record in result.data:
                msg_uuid = record.get("message_uuid")
                if not msg_uuid:
                    deduplicated_data.append(record)
                elif msg_uuid not in seen_uuids:
                    seen_uuids.add(msg_uuid)
                    deduplicated_data.append(record)
        return NocoResult.ok(
            operation="read",
            data=deduplicated_data,
            table="DIR_LOCAL-MAIL",
            affected_count=len(deduplicated_data)
        )
    return result

def list_trash(client: NocoClient, mailboxes: list[str], limit: int = 50) -> NocoResult:
    """
    where = (mailbox_owner,in,<mailboxes>)~and(folder,eq,trash)
    sort = "-CreatedAt" (más recientes primero)
    """
    return list_inbox(client, mailboxes, folder="trash", limit=limit)

def get_email(client: NocoClient, email_id: int) -> NocoResult:
    """read(where=f"(Id,eq,{email_id})"), data = registro único o None"""
    if not isinstance(email_id, int) or email_id <= 0:
        return NocoResult.fail("read", "email_id inválido", table="DIR_LOCAL-MAIL")
        
    table = client.table("DIR_LOCAL-MAIL")
    result = table.read(where=f"(Id,eq,{email_id})")
    if result.success:
        if isinstance(result.data, list) and len(result.data) > 0:
            result.data = result.data[0]
        else:
            result.data = None
    return result

def mark_as_read(client: NocoClient, email_id: int) -> NocoResult:
    """update [{"Id": email_id, "read": True, "read_date": <iso now>}]"""
    if not isinstance(email_id, int) or email_id <= 0:
        return NocoResult.fail("update", "email_id inválido", table="DIR_LOCAL-MAIL")
        
    table = client.table("DIR_LOCAL-MAIL")
    if table.is_unresolved():
        return NocoResult.fail("update", f"No se pudo resolver la tabla '{table.name}': {table.resolution_error}", table=table.name)
        
    now_iso = datetime.datetime.now().isoformat()
    return client.update_records(table.table_id, [{"Id": email_id, "read": True, "read_date": now_iso}])

def archive_email(client: NocoClient, email_id: int) -> NocoResult:
    """update [{"Id": email_id, "folder": "archive"}]"""
    if not isinstance(email_id, int) or email_id <= 0:
        return NocoResult.fail("update", "email_id inválido", table="DIR_LOCAL-MAIL")
        
    table = client.table("DIR_LOCAL-MAIL")
    if table.is_unresolved():
        return NocoResult.fail("update", f"No se pudo resolver la tabla '{table.name}': {table.resolution_error}", table=table.name)
        
    return client.update_records(table.table_id, [{"Id": email_id, "folder": "archive"}])

def move_to_trash(client: NocoClient, email_id: int) -> NocoResult:
    """update [{"Id": email_id, "folder": "trash"}]"""
    if not isinstance(email_id, int) or email_id <= 0:
        return NocoResult.fail("update", "email_id inválido", table="DIR_LOCAL-MAIL")
        
    table = client.table("DIR_LOCAL-MAIL")
    if table.is_unresolved():
        return NocoResult.fail("update", f"No se pudo resolver la tabla '{table.name}': {table.resolution_error}", table=table.name)
        
    return client.update_records(table.table_id, [{"Id": email_id, "folder": "trash"}])

def send_email(client: NocoClient, from_user: str, to_users: list[str], subject: str, body: str,
               cc_users: list[str] | None = None, priority: str = "Media",
               reply_to_uuid: str = "",
               thread_uuid_override: str | None = None,
               attachments: list[str] | None = None) -> NocoResult:
    """
    Envía un correo a los destinatarios especificados.

    Parameters
    ----------
    client : NocoClient
        Instancia del cliente NocoDB.
    from_user : str
        Remitente del correo.
    to_users : list[str]
        Lista de destinatarios principales.
    subject : str
        Asunto del correo.
    body : str
        Cuerpo del mensaje.
    cc_users : list[str] | None
        Lista de destinatarios en copia.
    priority : str
        Prioridad del correo ("Baja", "Media", "Alta").
    reply_to_uuid : str
        UUID del mensaje original al que se responde (vacío si no es respuesta).
    thread_uuid_override : str | None
        Si se proporciona, usa este valor como thread_uuid en lugar de generar uno nuevo.
    attachments : list[str] | None
        Lista de rutas de archivos locales para adjuntar.
        Cada archivo se sube a NocoDB vía client.upload_attachment().
    """
    to_users_valid = [u.strip() for u in to_users if u and u.strip()] if to_users else []
    cc_users_valid = [u.strip() for u in cc_users if u and u.strip()] if cc_users else []

    if not from_user or not from_user.strip():
        return NocoResult.fail("create", ["El remitente (from_user) no puede estar vacío."], table="DIR_LOCAL-MAIL")

    if not to_users_valid:
        return NocoResult.fail("create", ["El destinatario (to_users) no puede estar vacío."], table="DIR_LOCAL-MAIL")

    if not subject or not subject.strip():
        return NocoResult.fail("create", ["El asunto (subject) no puede estar vacío."], table="DIR_LOCAL-MAIL")

    # Validación de prioridad
    if priority not in ["Baja", "Media", "Alta"]:
        priority = "Media"

    # Procesar adjuntos: subir cada archivo a NocoDB antes de crear el registro
    attachment_objects: list[dict] = []
    attachment_errors: list[str] = []
    if attachments:
        for file_path in attachments:
            upload_result = client.upload_attachment(file_path)
            if upload_result.success:
                attachment_objects.append(upload_result.data)
            else:
                err_msg = upload_result.errors[0] if upload_result.errors else f"Error al subir {file_path}"
                attachment_errors.append(err_msg)
                logging.getLogger("tardis").warning("Error al subir adjunto %s: %s", file_path, err_msg)

    message_uuid = str(uuid.uuid4())
    thread_uuid = thread_uuid_override if thread_uuid_override else message_uuid
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    to_str = "; ".join(to_users_valid)
    cc_str = "; ".join(cc_users_valid) if cc_users_valid else ""

    recipients = to_users_valid + cc_users_valid
    success_count = 0
    created_records = []
    partial_errors = []

    table = client.table("DIR_LOCAL-MAIL")

    for recipient in recipients:
        payload = {
            "title": subject,
            "body": body,
            "from": from_user,
            "to": to_str,
            "cc": cc_str,
            "priority": priority,
            "folder": "inbox",
            "mailbox_owner": recipient,
            "read": False,
            "message_uuid": message_uuid,
            "thread_uuid": thread_uuid,
            "reply_to_uuid": reply_to_uuid,
            "message_source": "tardis",
            "schema_version": "1.0.0",
            "client_updated_at": now_iso
        }
        # Agregar adjuntos si los hay
        if attachment_objects:
            payload["Attachment"] = attachment_objects
        res = table.create(payload)
        if res.success:
            success_count += 1
            if res.data:
                created_records.append(res.data)
        else:
            partial_errors.extend(res.errors if isinstance(res.errors, list) else [str(res.errors)])

    meta = {}
    if partial_errors:
        meta["partial_errors"] = partial_errors
    if attachment_errors:
        meta["attachment_errors"] = attachment_errors

    if success_count > 0:
        return NocoResult.ok(
            operation="create",
            data=created_records,
            table="DIR_LOCAL-MAIL",
            affected_count=success_count,
            meta=meta
        )
    else:
        errors = partial_errors if partial_errors else ["No se pudo crear ningún registro de correo."]
        return NocoResult.fail(
            operation="create",
            errors=errors,
            table="DIR_LOCAL-MAIL",
            meta=meta
        )


def restore_email(client: NocoClient, email_id: int, mailbox_id: str) -> NocoResult:
    """
    Restaura un correo archivado o en la papelera a la bandeja de entrada.

    update([{"Id": email_id, "folder": "inbox", "mailbox_owner": mailbox_id}])
    """
    if not isinstance(email_id, int) or email_id <= 0:
        return NocoResult.fail("update", "email_id inválido", table="DIR_LOCAL-MAIL")

    table = client.table("DIR_LOCAL-MAIL")
    if table.is_unresolved():
        return NocoResult.fail("update", f"No se pudo resolver la tabla '{table.name}': {table.resolution_error}", table=table.name)

    return client.update_records(table.table_id, [{"Id": email_id, "folder": "inbox", "mailbox_owner": mailbox_id}])

def notify(client: NocoClient, to_users: list[str], subject: str, body: str, module_origin: str) -> NocoResult:
    """
    Atajo para otros módulos. Igual que send_email pero:
    from_user = f"sistema:{module_origin}"
    priority = "Media"
    """
    from_user = f"sistema:{module_origin}"
    return send_email(client, from_user=from_user, to_users=to_users, subject=subject, body=body, priority="Media")
