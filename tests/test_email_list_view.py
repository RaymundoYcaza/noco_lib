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

from modules.localmail.views.email_list_view import EmailListView
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

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.show_notification = MagicMock()
    return app

@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)

@patch("modules.localmail.views.email_list_view.run_async", side_effect=mock_run_async)
class TestEmailListView:
    def test_init_ui(self, mock_run, mock_app, mock_client):
        view = EmailListView(mock_app, mock_client)
        assert view.btn_refresh.text() == "Actualizar"
        assert view.table.columnCount() == 4
        assert [view.table.horizontalHeaderItem(i).text() for i in range(4)] == ["Prioridad", "De", "Asunto", "Fecha"]

    def test_load_inbox_success(self, mock_run, mock_app, mock_client):
        emails = [
            {
                "Id": 101,
                "priority": "Alta",
                "from": "sender@test.com",
                "title": "Asunto Alta",
                "CreatedAt": "2026-06-13T12:00:00Z",
                "read": False
            },
            {
                "Id": 102,
                "priority": "Baja",
                "from": "sender2@test.com",
                "title": "Asunto Baja",
                "CreatedAt": "2026-06-13T12:30:00Z",
                "read": True
            }
        ]
        result = NocoResult.ok("read", data=emails)
        
        with patch("modules.localmail.service.list_inbox", return_value=result) as mock_list:
            view = EmailListView(mock_app, mock_client)
            view.load(mock_client, ["user@test.com"], "inbox")
            
            mock_list.assert_called_once_with(mock_client, ["user@test.com"], "inbox")
            assert view.table.rowCount() == 2
            
            # Alt (unread)
            item_prio0 = view.table.item(0, 0)
            assert item_prio0.data(Qt.UserRole) == 101
            assert item_prio0.font().bold()
            
            # Baja (read)
            item_prio1 = view.table.item(1, 0)
            assert item_prio1.data(Qt.UserRole) == 102
            assert not item_prio1.font().bold()

    def test_load_sent_success(self, mock_run, mock_app, mock_client):
        emails = [
            {
                "Id": 201,
                "priority": "Media",
                "to": "recipient@test.com",
                "title": "Asunto Enviado",
                "CreatedAt": "2026-06-13T12:00:00Z",
                "read": True
            }
        ]
        result = NocoResult.ok("read", data=emails)
        
        with patch("modules.localmail.service.list_sent", return_value=result) as mock_list:
            view = EmailListView(mock_app, mock_client)
            view.load(mock_client, ["user@test.com"], "sent")
            
            mock_list.assert_called_once_with(mock_client, ["user@test.com"])
            assert view.table.rowCount() == 1
            # Column 1 header should be updated to "Para"
            assert view.table.horizontalHeaderItem(1).text() == "Para"
            assert view.table.item(0, 1).text() == "recipient@test.com"

    def test_load_no_mailboxes(self, mock_run, mock_app, mock_client):
        view = EmailListView(mock_app, mock_client)
        view.load(mock_client, [], "inbox")
        assert view.table.isHidden()
        assert not view.placeholder_label.isHidden()
        assert not view.btn_refresh.isEnabled()

    def test_load_error(self, mock_run, mock_app, mock_client):
        result = NocoResult.fail("read", "Error de red")
        with patch("modules.localmail.service.list_inbox", return_value=result):
            view = EmailListView(mock_app, mock_client)
            view.load(mock_client, ["user@test.com"], "inbox")
            mock_app.show_notification.assert_called_once_with("Error de red", "error")
            assert view.table.rowCount() == 0

    def test_single_click_selection(self, mock_run, mock_app, mock_client):
        emails = [{"Id": 301, "priority": "Media", "from": "s", "title": "t", "CreatedAt": "d", "read": True}]
        result = NocoResult.ok("read", data=emails)
        
        with patch("modules.localmail.service.list_inbox", return_value=result):
            view = EmailListView(mock_app, mock_client)
            view.load(mock_client, ["user@test.com"], "inbox")
            
            selected_id = None
            def on_selected(eid):
                nonlocal selected_id
                selected_id = eid
                
            view.email_selected.connect(on_selected)
            
            # Click row item
            item = view.table.item(0, 0)
            view._on_item_clicked(item)
            
            assert selected_id == 301
