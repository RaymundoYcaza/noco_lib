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
    # add_menu_action fue ELIMINADO en Phase 6 — ya no se usa
    return app


@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)


def test_register_module(mock_app, mock_client):
    """Test that register() calls register_nav_item and wires up views."""
    
    mock_app.register_nav_item = MagicMock()
    
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

        # 2. Check register_nav_item was called with correct params
        assert mock_app.register_nav_item.call_count == 1
        nav_args = mock_app.register_nav_item.call_args[1]
        assert nav_args["module_id"] == "localmail"
        assert nav_args["icon"] == "fa5s.envelope"
        assert nav_args["position"] == "top"
        assert nav_args["toolbar"] is None
        screen = nav_args["widget"]
        # The screen wraps the splitter in a LocalMailScreen
        from modules.localmail.module import LocalMailScreen
        assert isinstance(screen, LocalMailScreen)
        assert isinstance(screen._splitter, QSplitter)
        assert screen._splitter.orientation() == Qt.Horizontal
        assert screen._splitter.count() == 3
        assert isinstance(screen._splitter.widget(0), SidebarTreeView)
        assert isinstance(screen._splitter.widget(2), ReaderView)

        # 3. Menu actions were ELIMINADOS en Phase 6 (menú superior eliminado).
        #    La navegación se hace exclusivamente mediante la NavBar y el botón
        #    "+ Nuevo mensaje" en la sidebar. No se registran add_menu_action.
        #    Roadmap: en Phase 7+ se implementará un botón hamburguesa (☰).


def test_register_module_restores_and_wires(mock_app, mock_client):
    """Test that register() restores last selected node and wires selection to email_list_view."""
    from modules.localmail.views.sidebar_view import SidebarTreeView
    from modules.localmail.views.email_list_view import EmailListView
    
    # We patch QSettings to simulate last selected node as "all:sent"
    with patch("modules.localmail.module.QSettings") as mock_settings_cls, \
         patch("modules.localmail.views.email_list_view.run_async") as mock_run_async:
         
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings
        
        # Simulate value for three_pane/splitter_sizes and three_pane/last_selected_node
        def get_setting_value(key):
            if key == "three_pane/last_selected_node":
                return "all:sent"
            return None
        mock_settings.value.side_effect = get_setting_value
        
        # Call register
        register(mock_app, mock_client)
        
        # Verify email_list_view exists
        assert hasattr(mock_app, "email_list_view")
        assert isinstance(mock_app.email_list_view, EmailListView)
        
        # Since last_selected was "all:sent", verify load was called on email_list_view with "sent" folder
        assert mock_app.email_list_view._current_folder == "sent"
        assert mock_app.email_list_view._current_mailboxes == ["test_user"]
        
        # Now trigger another node selection programmatically in the sidebar tree
        # Click Inbox under Alicia (which is node ID: "test_user:inbox", with mailboxes=["test_user"])
        mock_app.sidebar_view.select_node_by_id("test_user:inbox")
        
        # Assert load was triggered for "inbox" folder
        assert mock_app.email_list_view._current_folder == "inbox"
        assert mock_app.email_list_view._current_mailboxes == ["test_user"]
        
        # Check that it attempted to persist the new node selection
        mock_settings.setValue.assert_any_call("three_pane/last_selected_node", "test_user:inbox")
