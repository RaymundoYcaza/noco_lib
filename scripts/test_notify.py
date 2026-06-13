import sys
from pathlib import Path

# Add paths to sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

from app_core.config import load_tardis_config
from noco_lib.noco_core import NocoClient
from modules.localmail.service import notify, list_inbox

def main():
    print("=== TESTING NOTIFY (TASK 8.3.1) ===")
    config = load_tardis_config()
    if not config.mailboxes:
        print("Error: TARDIS_MAILBOXES is empty in config.")
        sys.exit(1)
        
    client = NocoClient(
        base_url=config.noco_base_url,
        token=config.noco_token,
        base_id=config.noco_base_id
    )

    test_mailbox = config.mailboxes[0]
    print(f"Sending test notification to: {test_mailbox}")
    
    res = notify(
        client=client,
        to_users=[test_mailbox],
        subject="Test notification from dummy",
        body="This is a test notification body.",
        module_origin="test"
    )
    
    if not res.success:
        print(f"Failed to send notification: {res.errors}")
        sys.exit(1)
        
    print(f"Notification sent successfully! affected_count={res.affected_count}")
    
    # Verify the created record has from = 'sistema:test'
    created_id = res.data[0]["Id"]
    print(f"Checking details of created notification record Id={created_id}...")
    
    table = client.table("DIR_LOCAL-MAIL")
    get_res = table.read(where=f"(Id,eq,{created_id})")
    if not get_res.success or not get_res.data:
        print(f"Failed to query created record: {get_res.errors}")
        sys.exit(1)
        
    record = get_res.data[0]
    from_field = record.get("from")
    print(f"Record 'from' field value: '{from_field}'")
    assert from_field == "sistema:test", f"Expected 'from' to be 'sistema:test', got '{from_field}'"
    print("SUCCESS: notify works as expected!")

if __name__ == "__main__":
    main()
