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
def mock_client():
    client = MagicMock(spec=NocoClient)
    return client


@pytest.fixture
def mock_main_window():
    window = MagicMock()
    window.show_notification = MagicMock()
    return window


@patch("modules.localmail.views.inbox_view.run_async", side_effect=mock_run_async)
class TestInboxView:
    def test_init_ui(self, mock_run, mock_main_window, mock_client):
        """Check if UI widgets are initialized correctly."""
        view = InboxView(mock_main_window, mock_client, ["user1"])
        assert view.title_label.text() == "Bandeja de Entrada (user1)"
        assert view.btn_refresh.text() == "Actualizar"
        assert view.btn_archive.text() == "Archivar"
        assert not view.btn_archive.isEnabled()
        assert view.table.columnCount() == 4
        assert [view.table.horizontalHeaderItem(i).text() for i in range(4)] == ["Prioridad", "De", "Asunto", "Fecha"]

    def test_load_success_unread_and_read(self, mock_run, mock_main_window, mock_client):
        """Check loading emails and applying formatting (read vs unread, priorities)."""
        emails = [
            {
                "Id": 101,
                "priority": "Alta",
                "from": "alice@test.com",
                "title": "Urgente",
                "CreatedAt": "2026-06-13T12:00:00Z",
                "read": False
            },
            {
                "Id": 102,
                "priority": "Media",
                "from": "bob@test.com",
                "title": "Reunión",
                "CreatedAt": "2026-06-13T12:30:00Z",
                "read": True
            },
            {
                "Id": 103,
                "priority": "Baja",
                "from": "charlie@test.com",
                "title": "Hola",
                "CreatedAt": "2026-06-13T13:00:00Z",
                "read": 0 # NocoDB representation of False
            }
        ]

        result = NocoResult.ok("read", data=emails)
        
        with patch("modules.localmail.service.list_inbox", return_value=result) as mock_list:
            view = InboxView(mock_main_window, mock_client, ["user1"])
            view.load()

            mock_list.assert_called_once_with(mock_client, ["user1"])
            assert view.table.rowCount() == 3

            # Row 0 (Id 101 - Alta, unread)
            assert view.table.item(0, 0).text() == "🔴 Alta"
            assert view.table.item(0, 0).data(Qt.UserRole) == 101
            assert view.table.item(0, 1).text() == "alice@test.com"
            assert view.table.item(0, 2).text() == "Urgente"
            assert view.table.item(0, 3).text() == "2026-06-13T12:00"
            # Must be bold since it is unread
            assert view.table.item(0, 0).font().bold()

            # Row 1 (Id 102 - Media, read)
            assert view.table.item(1, 0).text() == "⚪ Media"
            assert view.table.item(1, 0).data(Qt.UserRole) == 102
            # Must not be bold
            assert not view.table.item(1, 0).font().bold()

            # Row 2 (Id 103 - Baja, unread via 0)
            assert view.table.item(2, 0).text() == "🟢 Baja"
            assert view.table.item(2, 0).data(Qt.UserRole) == 103
            # Must be bold since 0 is evaluated as unread
            assert view.table.item(2, 0).font().bold()

    def test_load_failure(self, mock_run, mock_main_window, mock_client):
        """Check handling of load failure and showing notification."""
        result = NocoResult.fail("read", "Conexión rechazada")
        
        with patch("modules.localmail.service.list_inbox", return_value=result):
            view = InboxView(mock_main_window, mock_client, ["user1"])
            view.load()
            
            mock_main_window.show_notification.assert_called_once_with("Conexión rechazada", "error")

    def test_selection_changed_enables_archive(self, mock_run, mock_main_window, mock_client):
        """Check if selecting a row enables the archive button."""
        emails = [{"Id": 101, "priority": "Media", "from": "a", "title": "b", "CreatedAt": "c", "read": True}]
        result = NocoResult.ok("read", data=emails)

        with patch("modules.localmail.service.list_inbox", return_value=result):
            view = InboxView(mock_main_window, mock_client, ["user1"])
            view.load()
            
            # Select row
            view.table.selectRow(0)
            assert view.btn_archive.isEnabled()

            # Clear selection
            view.table.clearSelection()
            assert not view.btn_archive.isEnabled()

    def test_double_click_marks_as_read_and_emits_signal(self, mock_run, mock_main_window, mock_client):
        """Double clicking an email should mark it as read and emit email_selected signal."""
        emails = [{"Id": 105, "priority": "Media", "from": "a", "title": "b", "CreatedAt": "c", "read": False}]
        result_load = NocoResult.ok("read", data=emails)
        result_read = NocoResult.ok("update", data=[{"Id": 105, "read": True}])

        # Track signal emission
        emitted_id = None
        def on_email_selected(eid):
            nonlocal emitted_id
            emitted_id = eid

        with patch("modules.localmail.service.list_inbox", return_value=result_load):
            view = InboxView(mock_main_window, mock_client, ["user1"])
            view.email_selected.connect(on_email_selected)
            view.load()

            # Trigger double click on item
            item = view.table.item(0, 0)
            with patch("modules.localmail.service.mark_as_read", return_value=result_read) as mock_mark:
                view._on_double_click(item)
                mock_mark.assert_called_once_with(mock_client, 105)
                assert emitted_id == 105

    def test_archive_action(self, mock_run, mock_main_window, mock_client):
        """Clicking Archive should call archive_email and reload."""
        emails = [{"Id": 106, "priority": "Media", "from": "a", "title": "b", "CreatedAt": "c", "read": True}]
        result_load = NocoResult.ok("read", data=emails)
        result_archive = NocoResult.ok("update", data=[{"Id": 106, "folder": "archive"}])

        with patch("modules.localmail.service.list_inbox", return_value=result_load) as mock_load:
            view = InboxView(mock_main_window, mock_client, ["user1"])
            view.load()

            # Select row
            view.table.selectRow(0)
            
            with patch("modules.localmail.service.archive_email", return_value=result_archive) as mock_arch:
                # Click archive button (or call handler)
                view._on_archive()
                mock_arch.assert_called_once_with(mock_client, 106)
                # Should have refreshed the list
                assert mock_load.call_count == 2

    def test_context_menu_archive(self, mock_run, mock_main_window, mock_client):
        """Right-clicking and selecting Archive from context menu calls archive_email and reloads."""
        emails = [{"Id": 107, "priority": "Media", "from": "a", "title": "b", "CreatedAt": "c", "read": True}]
        result_load = NocoResult.ok("read", data=emails)
        result_archive = NocoResult.ok("update", data=[{"Id": 107, "folder": "archive"}])

        with patch("modules.localmail.service.list_inbox", return_value=result_load) as mock_load:
            view = InboxView(mock_main_window, mock_client, ["user1"])
            view.load()

            # Directly trigger the context menu helper
            with patch("modules.localmail.service.archive_email", return_value=result_archive) as mock_arch:
                view._archive_by_id(107)
                mock_arch.assert_called_once_with(mock_client, 107)
                assert mock_load.call_count == 2

