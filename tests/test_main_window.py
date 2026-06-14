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

from app_core.main_window import MainWindow, FloatingWindow
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

        floating = window.add_floating_window(dummy, title)

        assert isinstance(floating, FloatingWindow)
        # FloatingWindow wraps the child widget; check that it's visible
        assert floating._child_widget == dummy
        assert floating._title_str == title
        # Clean up
        floating.close()


def test_floating_window_close_saves_geometry(mock_client):
    window = MainWindow(mock_client)
    dummy = QWidget()
    title = "Test Geometry Saving"

    with patch("app_core.main_window.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings
        mock_settings.value.return_value = None

        floating = window.add_floating_window(dummy, title)

        with patch.object(floating, "saveGeometry", return_value=b"mocked-geometry-bytes"):
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent()
            floating.closeEvent(event)

            mock_settings.setValue.assert_called_with(
                f"floating/{title}/geometry", b"mocked-geometry-bytes"
            )

        floating.close()


def test_floating_window_close_propagates_to_child(mock_client):
    window = MainWindow(mock_client)

    child = QWidget()
    child.close = MagicMock(return_value=False)

    title = "Test Propagate Close"

    with patch("app_core.main_window.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings

        floating = window.add_floating_window(child, title)

        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        floating.closeEvent(event)

        child.close.assert_called_once()
        assert not event.isAccepted()
        floating.close()


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
    node = SidebarNode(id="test_node", label="Test Node", icon="fa.star",
                       node_type="module_root", mailboxes=[], folder=None)

    assert len(window._extra_sidebar_nodes) == 0
    window.add_sidebar_node(node)
    assert len(window._extra_sidebar_nodes) == 1
    assert window._extra_sidebar_nodes[0] == node


def test_register_nav_item_and_activate(mock_client):
    """Test that register_nav_item stores the widget and _activate_module switches the stack."""
    window = MainWindow(mock_client)

    # Register a nav item
    screen = QWidget()
    window.register_nav_item(
        module_id="test_module",
        icon="fa5s.star",
        label="Test Module",
        widget=screen,
        position="middle",
    )

    assert "test_module" in window._module_screens
    assert window._module_screens["test_module"] == screen
    assert screen in [window._stack.widget(i) for i in range(window._stack.count())]

    # Activate it
    window._activate_module("test_module")
    assert window._stack.currentWidget() == screen
    assert window._nav_bar._buttons["test_module"].active is True


def test_set_central_widget_backward_compat(mock_client):
    """Test that setCentralWidget still works (backward compat for LocalMail)."""
    window = MainWindow(mock_client)

    # No dock_manager in the new layout
    assert not hasattr(window, "dock_manager")

    # setCentralWidget should add to the stack
    dummy_center = QWidget()
    window.setCentralWidget(dummy_center)

    assert window.centralWidget() == dummy_center
    assert window._stack.currentWidget() == dummy_center

    # Floating window should still work
    widget = QWidget()
    with patch("app_core.main_window.QSettings"):
        floating = window.add_floating_window(widget, "Prueba")
        assert floating is not None
        assert floating._child_widget == widget
        floating.close()


def test_add_dock_panel_raises(mock_client):
    """Test that add_dock_panel raises NotImplementedError."""
    window = MainWindow(mock_client)
    with pytest.raises(NotImplementedError, match="register_nav_item"):
        window.add_dock_panel(QWidget(), "Test", area="right")


def test_restore_last_module(mock_client):
    """Test that last active module is restored from QSettings."""
    window = MainWindow(mock_client)

    # Register two modules
    s1 = QWidget()
    s2 = QWidget()
    window.register_nav_item("mod_a", "fa5s.a", "Mod A", s1, position="top")
    window.register_nav_item("mod_b", "fa5s.b", "Mod B", s2, position="middle")

    # Activate mod_b and simulate save
    with patch("app_core.main_window.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings

        window._activate_module("mod_b")
        mock_settings.setValue.assert_called_with("nav/last_active_module", "mod_b")

    # _restore_last_module reads from QSettings
    with patch("app_core.main_window.QSettings") as mock_settings_cls:
        mock_settings = MagicMock()
        mock_settings_cls.return_value = mock_settings
        mock_settings.value.return_value = "mod_b"

        window._restore_last_module()
        assert window._stack.currentWidget() == s2
