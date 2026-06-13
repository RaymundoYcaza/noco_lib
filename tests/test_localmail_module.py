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
        mock_inbox_cls.assert_called_once_with(mock_app, mock_client, ["test_user"])
        mock_reader_cls.assert_called_once_with(mock_app, mock_client)

        # 2. Check panels were added to correct dock areas
        # Get actual instances created
        inbox_instance = mock_inbox_cls.call_args[0][0]  # wraps allows us to get the created view, wait, call_args doesn't give returns
        # Let's inspect mock_app.add_dock_panel calls instead
        assert mock_app.add_dock_panel.call_count == 2
        
        # First panel call
        args_1 = mock_app.add_dock_panel.call_args_list[0][0]
        kwargs_1 = mock_app.add_dock_panel.call_args_list[0][1]
        assert isinstance(args_1[0], InboxView)
        assert args_1[1] == "LocalMail - Bandeja de entrada"
        assert kwargs_1.get("area") == "left"

        # Second panel call
        args_2 = mock_app.add_dock_panel.call_args_list[1][0]
        kwargs_2 = mock_app.add_dock_panel.call_args_list[1][1]
        assert isinstance(args_2[0], ReaderView)
        assert args_2[1] == "LocalMail - Lector"
        assert kwargs_2.get("area") == "center"

        # 3. Check signal connection between inbox and reader
        # InboxView instance should be connected to ReaderView's show_email slot
        inbox_created = args_1[0]
        reader_created = args_2[0]
        # In mock wraps, we can check if signals were emitted or connected
        # Let's verify signal exists and we can emit it to call reader's show_email
        with patch.object(reader_created, "show_email") as mock_show:
            inbox_created.email_selected.emit(12345)
            mock_show.assert_called_once_with(12345)

        # 4. Check initial inbox load was called
        # mock_inbox_run_async tracks load
        assert mock_inbox_run_async.call_count == 1

        # 5. Check menu actions were registered
        assert mock_app.add_menu_action.call_count == 2
        
        # Action 1: "Bandeja de entrada"
        menu_args_1 = mock_app.add_menu_action.call_args_list[0][0]
        assert menu_args_1[0] == "LocalMail"
        assert menu_args_1[1] == "Bandeja de entrada"
        
        # Triggering Action 1 callback should load the inbox again
        callback_1 = menu_args_1[2]
        assert mock_inbox_run_async.call_count == 1
        callback_1()
        assert mock_inbox_run_async.call_count == 2

        # Action 2: "Redactar"
        menu_args_2 = mock_app.add_menu_action.call_args_list[1][0]
        assert menu_args_2[0] == "LocalMail"
        assert menu_args_2[1] == "Redactar"
        
        # Triggering Action 2 callback should add floating ComposerView window
        callback_2 = menu_args_2[2]
        assert mock_app.add_floating_window.call_count == 0
        
        with patch("modules.localmail.module.ComposerView", wraps=ComposerView) as mock_composer_cls:
            callback_2()
            assert mock_app.add_floating_window.call_count == 1
            mock_composer_cls.assert_called_once_with(mock_app, mock_client, ["test_user"])
            
            # Check floating window args
            float_args = mock_app.add_floating_window.call_args[0]
            assert isinstance(float_args[0], ComposerView)
            assert float_args[1] == "Redactar correo"
