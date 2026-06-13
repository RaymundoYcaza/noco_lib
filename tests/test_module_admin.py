import sys
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

# Make sure tardis and noco_lib are in sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
noco_lib_dir = tardis_dir / "noco_lib"

if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))
if str(noco_lib_dir) not in sys.path:
    sys.path.insert(0, str(noco_lib_dir))

# Initialize QApplication once for testing GUI components
qapp = QApplication.instance()
if not qapp:
    qapp = QApplication([])

from app_core.module_registry import ModuleInfo
from app_core.views.module_admin_view import ModuleAdminView

def test_module_admin_view_population():
    # Construct test dictionary
    test_info = {
        "foo": ModuleInfo(name="foo", loaded=True, error=None),
        "bar": ModuleInfo(name="bar", loaded=False, error="ImportError: x")
    }

    # Instantiate the view
    view = ModuleAdminView(test_info)

    # Verify rows and columns
    assert view.table.rowCount() == 2
    assert view.table.columnCount() == 3

    # Row 0: foo
    assert view.table.item(0, 0).text() == "foo"
    assert view.table.item(0, 1).text() == "Cargado"
    assert view.table.item(0, 2).text() == ""

    # Row 1: bar
    assert view.table.item(1, 0).text() == "bar"
    assert view.table.item(1, 1).text() == "Error"
    assert view.table.item(1, 2).text() == "ImportError: x"

def test_discover_and_register_error_handling():
    from unittest.mock import MagicMock, patch
    from app_core.module_registry import discover_and_register

    mock_window = MagicMock()
    mock_client = MagicMock()
    
    # Mock pkgutil.iter_modules to yield one good module, one bad module, and one ignored
    with patch("app_core.module_registry.pkgutil.iter_modules") as mock_iter, \
         patch("app_core.module_registry.importlib.import_module") as mock_import:
         
        mock_iter.return_value = [
            (None, "good_module", True),
            (None, "bad_module", True),
            (None, "_template_module", True),
        ]
        
        mock_good_mod = MagicMock()
        # mock_good_mod has register
        assert hasattr(mock_good_mod, "register")
        
        def import_side_effect(name):
            if name == "modules.good_module.module":
                return mock_good_mod
            elif name == "modules.bad_module.module":
                raise SyntaxError("invalid syntax")
            else:
                raise ImportError()
                
        mock_import.side_effect = import_side_effect
        
        results = discover_and_register(mock_window, mock_client)
        
        assert "good_module" in results
        assert results["good_module"].loaded is True
        assert results["good_module"].error is None
        
        assert "bad_module" in results
        assert results["bad_module"].loaded is False
        assert "invalid syntax" in results["bad_module"].error
        
        assert "_template_module" not in results
