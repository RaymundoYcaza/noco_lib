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

from PySide6.QtWidgets import QApplication, QSplitter, QWidget
from PySide6.QtCore import Qt


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
    """Test that register() wires up central three-pane layout, menu actions, etc."""
    
    # We patch the view constructors to track instances and calls, but still run them
    from modules.localmail.views.sidebar_view import SidebarTreeView
    with patch("modules.localmail.module.SidebarTreeView", wraps=SidebarTreeView) as mock_sidebar_cls, \
         patch("modules.localmail.module.ReaderView", wraps=ReaderView) as mock_reader_cls, \
         patch("app_core.main_window.QSettings") as mock_settings_cls:
         
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings
        mock_settings.value.return_value = None
         
        register(mock_app, mock_client)

        # 1. Check constructors were called with correct args
        mock_sidebar_cls.assert_called_once_with(mock_app, mock_client, ["test_user"])
        mock_reader_cls.assert_called_once_with(mock_app, mock_client)

        # 2. Check setCentralWidget was called on app
        assert mock_app.setCentralWidget.call_count == 1
        central_widget = mock_app.setCentralWidget.call_args[0][0]
        assert isinstance(central_widget, QSplitter)
        assert central_widget.orientation() == Qt.Horizontal
        
        # Splitter has 3 widgets: sidebar, center container, reader
        assert central_widget.count() == 3
        assert isinstance(central_widget.widget(0), SidebarTreeView)
        assert isinstance(central_widget.widget(1), QWidget)
        assert isinstance(central_widget.widget(2), ReaderView)

        # 3. Check menu actions were registered (Only "Redactar" action under "LocalMail")
        assert mock_app.add_menu_action.call_count == 1
        
        menu_calls = mock_app.add_menu_action.call_args_list
        assert menu_calls[0][0][0] == "LocalMail"
        assert menu_calls[0][0][1] == "Redactar"
        callback_compose = menu_calls[0][0][2]
        
        assert mock_app.add_floating_window.call_count == 0
        with patch("modules.localmail.module.ComposerView", wraps=ComposerView) as mock_composer_cls:
            callback_compose()
            assert mock_app.add_floating_window.call_count == 1
            mock_composer_cls.assert_called_once_with(mock_app, mock_client, ["test_user"])
            
            float_args = mock_app.add_floating_window.call_args[0]
            assert isinstance(float_args[0], ComposerView)
            assert float_args[1] == "Redactar correo"

