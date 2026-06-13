import sys
from pathlib import Path
import getpass

# Add paths to sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

from app_core.config import load_tardis_config
from noco_lib.noco_core import NocoClient
from modules.localmail.service import send_email, list_inbox, list_sent, list_trash, get_email

def main():
    print("=== CHECKPOINT 3 VERIFICATION ===")
    config = load_tardis_config()
    client = NocoClient(
        base_url=config.noco_base_url,
        token=config.noco_token,
        base_id=config.noco_base_id
    )

    sender = "alicia.gentil@inorizonti.com"
    recipients = ["alicia.gentil@inorizonti.com", "dev@bisstox.com"]
    subject = "Test Checkpoint 3 " + getpass.getuser()
    body = "Checking multidestination and sent/inbox lists."

    print(f"Sending email from '{sender}' to {recipients}...")
    send_res = send_email(client, from_user=sender, to_users=recipients, subject=subject, body=body)
    
    if not send_res.success:
        print(f"Error sending email: {send_res.errors}")
        sys.exit(1)
        
    print(f"Email sent successfully! Created {send_res.affected_count} records.")
    
    created_records = send_res.data
    print(f"Created records response: {created_records}")
    
    # Fetch the full record of the first created email using get_email to get the message_uuid
    email_id = created_records[0]["Id"]
    get_res = get_email(client, email_id)
    if not get_res.success or not get_res.data:
        print(f"Failed to retrieve created email with Id={email_id}: {get_res.errors}")
        sys.exit(1)
        
    msg_uuid = get_res.data.get("message_uuid")
    print(f"Retrieved Message UUID: {msg_uuid}")

    # 1. Confirm "Enviados" of the sender
    print("\n--- Checking 'Enviados' list ---")
    sent_res = list_sent(client, [sender], limit=50)
    assert sent_res.success, f"Failed to list sent: {sent_res.errors}"
    
    sent_emails_with_uuid = [e for e in sent_res.data if e.get("message_uuid") == msg_uuid]
    print(f"Found {len(sent_emails_with_uuid)} records with message_uuid in 'Enviados'.")
    assert len(sent_emails_with_uuid) == 1, f"Expected exactly 1 (deduplicated) sent record, found {len(sent_emails_with_uuid)}"
    print("SUCCESS: 'Enviados' is correctly deduplicated!")

    # 2. Confirm "Bandeja de entrada" of destA and destB
    for dest in recipients:
        print(f"\n--- Checking 'Bandeja de entrada' of {dest} ---")
        inbox_res = list_inbox(client, [dest], folder="inbox", limit=50)
        assert inbox_res.success, f"Failed to list inbox: {inbox_res.errors}"
        
        inbox_emails_with_uuid = [e for e in inbox_res.data if e.get("message_uuid") == msg_uuid]
        print(f"Found {len(inbox_emails_with_uuid)} records with message_uuid in '{dest}' inbox.")
        assert len(inbox_emails_with_uuid) == 1, f"Expected 1 record in inbox for {dest}, found {len(inbox_emails_with_uuid)}"
        print(f"SUCCESS: {dest} inbox has the email!")

    # 3. Confirm "Papelera" lists without error
    print("\n--- Checking 'Papelera' list ---")
    trash_res = list_trash(client, config.mailboxes, limit=10)
    assert trash_res.success, f"Failed to list trash: {trash_res.errors}"
    print(f"SUCCESS: Trash list returned successfully with {trash_res.affected_count} items.")

    print("\nALL CHECKPOINT 3 CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
