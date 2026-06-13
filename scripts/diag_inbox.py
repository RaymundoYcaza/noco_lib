import sys
from pathlib import Path

# Add paths to sys.path so we can import app_core and noco_lib
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

from app_core.config import load_tardis_config
from noco_lib.noco_core import NocoClient

def main():
    print("--- 8.0.1 Diagnóstico de Bandeja ---")
    
    # 1. Cargar config
    config = load_tardis_config()
    
    # 2. Imprimir config.user_id
    print(f"config.user_id: {config.user_id}")
    
    # Inicializar cliente
    client = NocoClient(
        base_url=config.noco_base_url,
        token=config.noco_token,
        base_id=config.noco_base_id
    )
    
    # 3. Llamar a la tabla "DIR_LOCAL-MAIL" sin filtro
    table_name = config.localmail_table
    print(f"Leyendo de la tabla: {table_name}")
    
    result = client.table(table_name).read(limit=10)
    
    print(f"Result success: {result.success}")
    if result.errors:
        print(f"Result errors: {result.errors}")
        
    if result.data:
        print("\nPrimeros 10 registros:")
        for i, row in enumerate(result.data):
            row_id = row.get("Id")
            row_from = row.get("from")
            row_to = row.get("to")
            row_mailbox_owner = row.get("mailbox_owner")
            row_folder = row.get("folder")
            row_read = row.get("read")
            print(f"[{i+1}] Id: {row_id} | From: {row_from} | To: {row_to} | Owner: {row_mailbox_owner} | Folder: {row_folder} | Read: {row_read}")

    else:
        print("No se encontraron registros o falló la consulta.")

    # --- 8.0.3 Prueba de sintaxis #1 (in) ---
    print("\n--- 8.0.3 Prueba de sintaxis #1 (in) ---")
    if config.mailboxes:
        mb = config.mailboxes[0]
        print(f"Probando con mailbox: {mb}")
        where = f"(mailbox_owner,in,{mb})"
        print(f"where = '{where}'")
        result_syntax1 = client.table(table_name).read(where=where, sort="-CreatedAt")
        print(f"Result success: {result_syntax1.success}")
        if result_syntax1.errors:
            print(f"Result errors: {result_syntax1.errors}")
        print(f"Registros devueltos: {len(result_syntax1.data) if result_syntax1.data else 0}")
    else:
        print("Error: No mailboxes configured in config.mailboxes (TARDIS_MAILBOXES is empty).")

    # --- 8.0.4 Prueba de sintaxis #2 (eq) con 1 casilla ---
    print("\n--- 8.0.4 Prueba de sintaxis #2 (eq) con 1 casilla ---")
    if config.mailboxes:
        mb = config.mailboxes[0]
        where = f"((mailbox_owner,eq,{mb}))"
        print(f"where = '{where}'")
        result_syntax2 = client.table(table_name).read(where=where, sort="-CreatedAt")
        print(f"Result success: {result_syntax2.success}")
        if result_syntax2.errors:
            print(f"Result errors: {result_syntax2.errors}")
        print(f"Registros devueltos: {len(result_syntax2.data) if result_syntax2.data else 0}")

    # --- 8.0.5 Prueba con DOS casillas ---
    print("\n--- 8.0.5 Prueba con DOS casillas ---")
    if len(config.mailboxes) >= 2:
        mbs = config.mailboxes[:2]
        print(f"Probando con mailboxes: {mbs}")
        
        # Sintaxis IN: (mailbox_owner,in,a@x.com,b@y.com)
        in_values = ",".join(mbs)
        where_in = f"(mailbox_owner,in,{in_values})"
        print(f"IN: where = '{where_in}'")
        result_in = client.table(table_name).read(where=where_in, sort="-CreatedAt")
        print(f"IN - Success: {result_in.success}")
        if result_in.errors:
            print(f"IN - Errors: {result_in.errors}")
        print(f"IN - Registros devueltos: {len(result_in.data) if result_in.data else 0}")
        if result_in.data:
            owners = set(r.get("mailbox_owner") for r in result_in.data)
            print(f"IN - Mailbox owners in results: {owners}")
            
        # Sintaxis ~or: ((mailbox_owner,eq,a@x.com)~or(mailbox_owner,eq,b@y.com))
        or_conditions = "~or".join([f"(mailbox_owner,eq,{mb})" for mb in mbs])
        where_or = f"({or_conditions})"
        print(f"~OR: where = '{where_or}'")
        result_or = client.table(table_name).read(where=where_or, sort="-CreatedAt")
        print(f"~OR - Success: {result_or.success}")
        if result_or.errors:
            print(f"~OR - Errors: {result_or.errors}")
        print(f"~OR - Registros devueltos: {len(result_or.data) if result_or.data else 0}")
        if result_or.data:
            owners = set(r.get("mailbox_owner") for r in result_or.data)
            print(f"~OR - Mailbox owners in results: {owners}")
    else:
        print("Error: Se necesitan al menos 2 casillas configuradas para probar 8.0.5.")

    # --- 8.0.6 Prueba de filtro combinado completo ---
    print("\n--- 8.0.6 Prueba de filtro combinado completo ---")
    if config.mailboxes:
        mbs = config.mailboxes
        in_values = ",".join(mbs)
        filtro_multicasilla = f"(mailbox_owner,in,{in_values})"
        
        # Probaremos diferentes variantes de read (0, false, 1, true) y carpetas
        for folder_test, read_val in [("inbox", "0"), ("inbox", "false"), ("archive", "1"), ("archive", "true")]:
            where_comb = f"{filtro_multicasilla}~and(folder,eq,{folder_test})~and(read,eq,{read_val})"
            print(f"Probando: where = '{where_comb}'")
            result_comb = client.table(table_name).read(where=where_comb, sort="-CreatedAt")
            print(f" -> Success: {result_comb.success} | Registros: {len(result_comb.data) if result_comb.data else 0}")
            if result_comb.errors:
                print(f" -> Errors: {result_comb.errors}")
    else:
        print("Error: No mailboxes configured.")

    # --- 8.0.7 Prueba de service.list_inbox ---
    print("\n--- 8.0.7 Prueba de service.list_inbox ---")
    from modules.localmail.service import list_inbox
    test_mailboxes = ["alicia.gentil@inorizonti.com"]
    print(f"Llamando list_inbox con mailboxes={test_mailboxes}, folder='sent'...")
    res_inbox = list_inbox(client, test_mailboxes, folder="sent", limit=5)
    print(f"Result success: {res_inbox.success}")
    if res_inbox.errors:
        print(f"Result errors: {res_inbox.errors}")
    print(f"affected_count: {res_inbox.affected_count}")
    if res_inbox.data:
        print("Registros devueltos:")
        for idx, row in enumerate(res_inbox.data):
            print(f" - [{idx+1}] Id: {row.get('Id')} | Owner: {row.get('mailbox_owner')} | Folder: {row.get('folder')}")

if __name__ == "__main__":
    main()
