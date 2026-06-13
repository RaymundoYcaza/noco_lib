import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Make sure tardis and noco_lib are in sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
noco_lib_dir = tardis_dir / "noco_lib"

if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Initialize QApplication once for testing GUI components
qapp = QApplication.instance()
if not qapp:
    qapp = QApplication([])

from modules.localmail.views.inbox_view import InboxView
from modules.localmail.views.reader_view import ReaderView
from modules.localmail.views.composer_view import ComposerView
from noco_lib.noco_core.client import NocoClient
from noco_lib.noco_core.result import NocoResult


# Mock run_async to run synchronously
def mock_run_async(fn, *args, on_success=None, on_error=None, **kwargs):
    try:
        result = fn(*args, **kwargs)
        if on_success:
            on_success(result)
    except Exception as e:
        if on_error:
            on_error(e)


class TestIntegrationFlow:
    @patch("modules.localmail.views.inbox_view.run_async", side_effect=mock_run_async)
    @patch("modules.localmail.views.reader_view.run_async", side_effect=mock_run_async)
    @patch("modules.localmail.views.composer_view.run_async", side_effect=mock_run_async)
    def test_e2e_flow_simulation(self, mock_comp_async, mock_read_async, mock_inbox_async):
        """
        Simulates the entire Phase 1 Flow (Checkpoint 8.4.7):
        1. User A (alice) opens ComposerView and sends email to User B (bob).
        2. User B (bob) opens InboxView and loads their inbox, seeing the email.
        3. User B double clicks the email, which marks it as read and loads it in ReaderView.
        4. User B archives the email, removing it from their inbox.
        """
        
        # State store to simulate NocoDB records in-memory
        db_records = []
        next_id = 1
        
        def mock_create(payload):
            nonlocal next_id
            record = dict(payload)
            record["Id"] = next_id
            record["CreatedAt"] = "2026-06-13T12:00:00Z"
            next_id += 1
            db_records.append(record)
            return NocoResult.ok("create", data=record)
            
        def mock_read(where=None, limit=50, sort=None):
            filtered = list(db_records)
            if where:
                if "mailbox_owner,eq,bob" in where or "mailbox_owner,in,bob" in where:
                    filtered = [r for r in filtered if r.get("mailbox_owner") == "bob"]
                if "folder,eq,inbox" in where:
                    filtered = [r for r in filtered if r.get("folder") == "inbox"]
                if "read,eq,false" in where or "read,eq,0" in where:
                    filtered = [r for r in filtered if not r.get("read")]
            return NocoResult.ok("read", data=filtered)
            
        def mock_update_records(table_id, records):
            for update in records:
                rec_id = update.get("Id")
                for r in db_records:
                    if r.get("Id") == rec_id:
                        r.update(update)
            return NocoResult.ok("update", data=records)

        # Mock NocoClient & NocoTable
        mock_client = MagicMock(spec=NocoClient)
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_client.update_records.side_effect = mock_update_records
        
        mock_table.create.side_effect = mock_create
        mock_table.read.side_effect = mock_read
        mock_table.is_unresolved.return_value = False
        mock_table.table_id = "table_123"

        # Mock MainWindow
        mock_window = MagicMock()
        mock_window.show_notification = MagicMock()
        mock_window.config = MagicMock()
        mock_window.config.user_id = "bob"

        # --- STEP 1: User A (alice) sends email to User B (bob) ---
        composer = ComposerView(mock_window, mock_client, ["alice"])
        composer.to_input.setText("bob")
        composer.subject_input.setText("Hola Bob")
        composer.body_input.setText("Este es un correo de prueba de Alice.")
        composer.priority_combo.setCurrentText("Alta")
        
        # Trigger sending
        composer._on_send_clicked()
        
        assert len(db_records) == 1
        assert db_records[0]["from"] == "alice"
        assert db_records[0]["to"] == "bob"
        assert db_records[0]["mailbox_owner"] == "bob"
        assert db_records[0]["title"] == "Hola Bob"
        assert db_records[0]["body"] == "Este es un correo de prueba de Alice."
        assert db_records[0]["priority"] == "Alta"
        assert db_records[0]["folder"] == "inbox"
        assert not db_records[0]["read"]

        # --- STEP 2: User B (bob) opens InboxView and loads inbox ---
        inbox = InboxView(mock_window, mock_client, ["bob"])
        inbox.load()
        
        assert inbox.table.rowCount() == 1
        assert inbox.table.item(0, 0).text() == "🔴 Alta"
        assert inbox.table.item(0, 0).data(Qt.UserRole) == 1  # ID of the mail
        assert inbox.table.item(0, 1).text() == "alice"
        assert inbox.table.item(0, 2).text() == "Hola Bob"

        # --- STEP 3: User B double clicks to read email ---
        reader = ReaderView(mock_window, mock_client)
        inbox.email_selected.connect(reader.show_email)
        
        # Double click the first item in the table
        item = inbox.table.item(0, 0)
        inbox._on_double_click(item)
        
        # Mail should be marked as read
        assert db_records[0]["read"] is True
        # Reader should display the content
        assert reader.lbl_subject.text() == "Hola Bob"
        assert reader.lbl_from.text() == "alice"
        assert reader.lbl_to.text() == "bob"
        assert reader.browser.toPlainText() == "Este es un correo de prueba de Alice."

        # --- STEP 4: User B archives the email ---
        inbox.table.selectRow(0)
        inbox._on_archive()
        
        # Mail folder should be archive
        assert db_records[0]["folder"] == "archive"
        # InboxView should be reloaded and empty
        assert inbox.table.rowCount() == 0
