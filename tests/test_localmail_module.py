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

# Initialize QApplication once for testing GUI components
qapp = QApplication.instance()
if not qapp:
    qapp = QApplication([])

from modules.localmail.module import register
from modules.localmail.views.inbox_view import InboxView
from modules.localmail.views.reader_view import ReaderView
from modules.localmail.views.composer_view import ComposerView
from noco_lib.noco_core.client import NocoClient
from app_core.main_window import MainWindow
from app_core.config import TardisConfig


@pytest.fixture
def mock_app():
    app = MagicMock(spec=MainWindow)
    app.config = MagicMock(spec=TardisConfig)
    app.config.user_id = "test_user"
    app.config.mailboxes = ["test_user"]
    app.add_dock_panel = MagicMock()
    app.add_floating_window = MagicMock()
    app.add_menu_action = MagicMock()
    return app


@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)


def test_register_module(mock_app, mock_client):
    """Test that register() wires up dock panels, connects signals, loads inbox, and adds menu actions."""
    
    # We patch the view constructors to track instances and calls, but still run them
    with patch("modules.localmail.module.InboxView", wraps=InboxView) as mock_inbox_cls, \
         patch("modules.localmail.module.ReaderView", wraps=ReaderView) as mock_reader_cls, \
         patch("modules.localmail.views.inbox_view.run_async") as mock_inbox_run_async:
         
        register(mock_app, mock_client)

        # 1. Check constructors were called with correct args
        assert mock_inbox_cls.call_count == 3
        mock_inbox_cls.assert_any_call(mock_app, mock_client, ["test_user"])
        mock_inbox_cls.assert_any_call(mock_app, mock_client, ["test_user"], mode="sent")
        mock_inbox_cls.assert_any_call(mock_app, mock_client, ["test_user"], mode="trash")
        mock_reader_cls.assert_called_once_with(mock_app, mock_client)

        # 2. Check panels were added to correct dock areas
        assert mock_app.add_dock_panel.call_count == 4
        
        # We can extract the panels added
        panel_calls = mock_app.add_dock_panel.call_args_list
        # Call 1: inbox
        assert isinstance(panel_calls[0][0][0], InboxView)
        assert panel_calls[0][0][0].mode == "inbox"
        assert panel_calls[0][0][1] == "LocalMail - Bandeja de entrada"
        assert panel_calls[0][1].get("area") == "left"

        # Call 2: sent_view
        assert isinstance(panel_calls[1][0][0], InboxView)
        assert panel_calls[1][0][0].mode == "sent"
        assert panel_calls[1][0][1] == "LocalMail - Enviados"
        assert panel_calls[1][1].get("area") == "left"

        # Call 3: trash_view
        assert isinstance(panel_calls[2][0][0], InboxView)
        assert panel_calls[2][0][0].mode == "trash"
        assert panel_calls[2][0][1] == "LocalMail - Papelera"
        assert panel_calls[2][1].get("area") == "left"

        # Call 4: reader
        assert isinstance(panel_calls[3][0][0], ReaderView)
        assert panel_calls[3][0][1] == "LocalMail - Lector"
        assert panel_calls[3][1].get("area") == "center"

        # 3. Check signal connection between views and reader
        inbox_created = panel_calls[0][0][0]
        sent_created = panel_calls[1][0][0]
        trash_created = panel_calls[2][0][0]
        reader_created = panel_calls[3][0][0]
        
        with patch.object(reader_created, "show_email") as mock_show:
            inbox_created.email_selected.emit(12345)
            mock_show.assert_any_call(12345)
            
            sent_created.email_selected.emit(67890)
            mock_show.assert_any_call(67890)
            
            trash_created.email_selected.emit(11111)
            mock_show.assert_any_call(11111)

        # 4. Check initial inbox load was called
        assert mock_inbox_run_async.call_count == 1

        # 5. Check menu actions were registered
        assert mock_app.add_menu_action.call_count == 4
        
        menu_calls = mock_app.add_menu_action.call_args_list
        # Action 1: "Bandeja de entrada"
        assert menu_calls[0][0][0] == "LocalMail"
        assert menu_calls[0][0][1] == "Bandeja de entrada"
        callback_1 = menu_calls[0][0][2]
        
        # Triggering Action 1 callback should load the inbox again
        assert mock_inbox_run_async.call_count == 1
        callback_1()
        assert mock_inbox_run_async.call_count == 2

        # Action 2: "Enviados"
        assert menu_calls[1][0][0] == "LocalMail"
        assert menu_calls[1][0][1] == "Enviados"
        callback_2 = menu_calls[1][0][2]
        
        # Triggering Action 2 callback should load sent view (calls list_sent)
        with patch("modules.localmail.views.inbox_view.run_async") as mock_sent_run_async:
            callback_2()
            assert mock_sent_run_async.call_count == 1

        # Action 3: "Papelera"
        assert menu_calls[2][0][0] == "LocalMail"
        assert menu_calls[2][0][1] == "Papelera"
        callback_3 = menu_calls[2][0][2]
        
        # Triggering Action 3 callback should load trash view (calls list_trash)
        with patch("modules.localmail.views.inbox_view.run_async") as mock_trash_run_async:
            callback_3()
            assert mock_trash_run_async.call_count == 1

        # Action 4: "Redactar"
        assert menu_calls[3][0][0] == "LocalMail"
        assert menu_calls[3][0][1] == "Redactar"
        callback_4 = menu_calls[3][0][2]
        
        assert mock_app.add_floating_window.call_count == 0
        with patch("modules.localmail.module.ComposerView", wraps=ComposerView) as mock_composer_cls:
            callback_4()
            assert mock_app.add_floating_window.call_count == 1
            mock_composer_cls.assert_called_once_with(mock_app, mock_client, ["test_user"])
            
            float_args = mock_app.add_floating_window.call_args[0]
            assert isinstance(float_args[0], ComposerView)
            assert float_args[1] == "Redactar correo"
