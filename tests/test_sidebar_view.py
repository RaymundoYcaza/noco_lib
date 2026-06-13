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

from modules.localmail.views.sidebar_view import SidebarTreeView
from app_core.sidebar.tree_model import SidebarNode
from noco_lib.noco_core.client import NocoClient
from noco_lib.noco_core.result import NocoResult

@pytest.fixture
def mock_app():
    app = MagicMock()
    app._extra_sidebar_nodes = [
        SidebarNode(id="dummy_node", label="Dummy", icon=None, node_type="module_root", mailboxes=[], folder=None)
    ]
    return app

@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)

def test_sidebar_tree_view_populate(mock_app, mock_client):
    mailboxes = ["alicia@inorizonti.com"]
    view = SidebarTreeView(mock_app, mock_client, mailboxes)
    
    # Root items: "All Mailboxes", "alicia@inorizonti.com", "Dummy" (from _extra_sidebar_nodes)
    assert view.topLevelItemCount() == 3
    
    # 1. All Mailboxes
    item0 = view.topLevelItem(0)
    assert item0.text(0) == "All Mailboxes"
    assert item0.data(0, Qt.UserRole) == "all"
    assert item0.childCount() == 5
    
    # 2. alicia@inorizonti.com
    item1 = view.topLevelItem(1)
    assert item1.text(0) == "alicia@inorizonti.com"
    assert item1.data(0, Qt.UserRole) == "alicia@inorizonti.com"
    assert item1.childCount() == 5
    
    # 3. Dummy
    item2 = view.topLevelItem(2)
    assert item2.text(0) == "Dummy"
    assert item2.data(0, Qt.UserRole) == "dummy_node"

def test_sidebar_tree_view_selection(mock_app, mock_client):
    mailboxes = ["alicia@inorizonti.com"]
    view = SidebarTreeView(mock_app, mock_client, mailboxes)
    
    selected_node = None
    def on_node_selected(node):
        nonlocal selected_node
        selected_node = node
        
    view.node_selected.connect(on_node_selected)
    
    # Click Inbox under All Mailboxes
    item_inbox = view.topLevelItem(0).child(0)
    view._on_item_clicked(item_inbox, 0)
    
    assert selected_node is not None
    assert selected_node.id == "all:inbox"
    assert selected_node.folder == "inbox"

# Mock run_async to run synchronously
def mock_run_async(fn, *args, on_success=None, on_error=None, **kwargs):
    try:
        result = fn(*args, **kwargs)
        if on_success:
            on_success(result)
    except Exception as e:
        if on_error:
            on_error(e)

@patch("modules.localmail.views.sidebar_view.run_async", side_effect=mock_run_async)
def test_refresh_unread_counts(mock_run, mock_app, mock_client):
    mailboxes = ["alicia@inorizonti.com"]
    view = SidebarTreeView(mock_app, mock_client, mailboxes)
    
    # Mock NocoResult for list_inbox counts
    res = NocoResult.ok("read", data=[], affected_count=5)
    
    with patch("modules.localmail.service.list_inbox", return_value=res) as mock_list:
        view.refresh_unread_counts(mock_client, mock_app)
        
        # 2 inbox nodes should be checked (All Mailboxes and alicia@inorizonti.com)
        assert mock_list.call_count == 2
        
        # Text should be updated with (5) badge count
        item_inbox_all = view.topLevelItem(0).child(0)
        assert item_inbox_all.text(0) == "Inbox (5)"
