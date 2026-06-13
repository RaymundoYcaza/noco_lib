import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
noco_lib_dir = tardis_dir / "noco_lib"

if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QSettings
import PySide6QtAds as QtAds

from app_core.main_window import MainWindow, FloatingDockWidget
from noco_lib.noco_core.client import NocoClient

# Ensure QApplication is initialized for testing
qapp = QApplication.instance()
if not qapp:
    qapp = QApplication([])


@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)


def test_main_window_add_floating_window(mock_client):
    window = MainWindow(mock_client)
    
    dummy = QWidget()
    title = "Test Floating Window"
    
    with patch("app_core.main_window.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings
        mock_settings.value.return_value = None
        
        dock_widget = window.add_floating_window(dummy, title)
        
        assert isinstance(dock_widget, FloatingDockWidget)
        assert dock_widget.widget() == dummy
        assert dock_widget.title_str == title
        mock_settings_cls.assert_called_with("Tardis", "Tardis")
        mock_settings.value.assert_called_with(f"floating/{title}/geometry")


def test_floating_dock_widget_close_saves_geometry(mock_client):
    window = MainWindow(mock_client)
    dummy = QWidget()
    title = "Test Geometry Saving"
    
    dock_widget = window.add_floating_window(dummy, title)
    
    mock_container = MagicMock()
    mock_container.saveGeometry.return_value = b"mocked-geometry-bytes"
    
    with patch.object(dock_widget, "floatingDockContainer", return_value=mock_container):
        with patch("app_core.main_window.QSettings") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings_cls.return_value = mock_settings
            
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            dock_widget.closeEvent(event)
            
            mock_settings.setValue.assert_called_with(
                f"floating/{title}/geometry", b"mocked-geometry-bytes"
            )


def test_floating_dock_widget_close_propagates_to_child(mock_client):
    window = MainWindow(mock_client)
    
    child = QWidget()
    child.close = MagicMock(return_value=False)
    
    title = "Test Propagate Close"
    dock_widget = window.add_floating_window(child, title)
    
    from PySide6.QtGui import QCloseEvent
    event = QCloseEvent()
    dock_widget.closeEvent(event)
    
    child.close.assert_called_once()
    assert not event.isAccepted()


def test_show_notification(mock_client):
    window = MainWindow(mock_client)
    
    from app_core.widgets.toast import Toast
    initial_count = len(Toast._active_toasts)
    
    window.show_notification("Mensaje de prueba", "success")
    
    assert len(Toast._active_toasts) == initial_count + 1
    toast = Toast._active_toasts[-1]
    assert toast.text == "Mensaje de prueba"
    assert toast.level == "success"
    assert toast.parentWidget() == window
    
    # Clean up
    toast.close_and_remove()


def test_add_sidebar_node(mock_client):
    window = MainWindow(mock_client)
    
    from app_core.sidebar.tree_model import SidebarNode
    node = SidebarNode(id="test_node", label="Test Node", icon="fa.star", node_type="module_root", mailboxes=[], folder=None)
    
    assert len(window._extra_sidebar_nodes) == 0
    window.add_sidebar_node(node)
    assert len(window._extra_sidebar_nodes) == 1
    assert window._extra_sidebar_nodes[0] == node


def test_set_central_widget_keeps_dock_manager(mock_client):
    window = MainWindow(mock_client)
    
    # Verify we have a dock_manager
    assert window.dock_manager is not None
    
    # Create a dummy central widget
    dummy_center = QWidget()
    
    # Call setCentralWidget
    window.setCentralWidget(dummy_center)
    
    # Check that centralWidget() returns the dummy widget
    assert window.centralWidget() == dummy_center
    
    # Create a floating window using the dock manager to make sure it doesn't crash
    widget = QWidget()
    dock_widget = window.add_floating_window(widget, "Prueba test_set_central_widget")
    assert dock_widget is not None
    assert dock_widget.widget() == widget



