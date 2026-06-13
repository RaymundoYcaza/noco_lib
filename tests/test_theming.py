import sys
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

# Make sure tardis is in sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

# Initialize QApplication once for testing GUI components
qapp = QApplication.instance()
if not qapp:
    qapp = QApplication([])

from app_core.theming import apply_theme

def test_apply_theme_success():
    # Clear stylesheet first
    qapp.setStyleSheet("")
    
    # Apply theme "dark"
    apply_theme(qapp, "dark")
    
    # Verify app stylesheet contains dark style rules
    stylesheet = qapp.styleSheet()
    assert len(stylesheet) > 0
    assert "QMainWindow" in stylesheet
    assert "#1e1e1e" in stylesheet

def test_apply_theme_fallback():
    # Clear stylesheet
    qapp.setStyleSheet("/* original stylesheet */")
    
    # Apply a non-existent theme, should fail gracefully and not crash
    apply_theme(qapp, "nonexistent_theme_xyz")
    
    # Verify stylesheet is not modified / not crashed
    assert qapp.styleSheet() == "/* original stylesheet */"
