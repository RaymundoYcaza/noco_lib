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

from modules.localmail.views.filter_bar import FilterBarView
from modules.localmail.views.email_list_view import EmailListView
from noco_lib.noco_core.client import NocoClient

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.show_notification = MagicMock()
    return app

@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)

def test_filter_bar_init(mock_app):
    view = FilterBarView(mock_app)
    assert view.search_input is not None
    assert view.search_input.placeholderText() == "Search subject or sender..."
    assert view.priority_combo is not None
    assert [view.priority_combo.itemText(i) for i in range(4)] == ["All", "Baja", "Media", "Alta"]

def test_filter_bar_signals(mock_app):
    view = FilterBarView(mock_app)
    
    emitted = []
    def on_filter_changed(text, priority):
        emitted.append((text, priority))
        
    view.filter_changed.connect(on_filter_changed)
    
    # Simulate text change
    view.search_input.setText("test query")
    assert len(emitted) == 1
    assert emitted[-1] == ("test query", "All")
    
    # Simulate priority change
    view.priority_combo.setCurrentText("Alta")
    assert len(emitted) == 2
    assert emitted[-1] == ("test query", "Alta")

def test_email_list_view_filtering(mock_app, mock_client):
    emails = [
        {"Id": 1, "priority": "Alta", "from": "alicia@test.com", "title": "Reunion urgente", "read": False},
        {"Id": 2, "priority": "Media", "from": "bob@test.com", "title": "Reporte mensual", "read": True},
        {"Id": 3, "priority": "Baja", "from": "charlie@test.com", "title": "Dudas sobre el reporte", "read": True},
    ]
    
    view = EmailListView(mock_app, mock_client)
    view._all_rows = emails
    view._current_folder = "inbox"
    
    # 1. No filter
    view.apply_filter("", "All")
    assert view.table.rowCount() == 3
    
    # 2. Filter by search text (subject match)
    view.apply_filter("reporte", "All")
    assert view.table.rowCount() == 2
    assert view.table.item(0, 0).data(Qt.UserRole) == 2
    assert view.table.item(1, 0).data(Qt.UserRole) == 3
    
    # 3. Filter by search text (sender match)
    view.apply_filter("alicia", "All")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 0).data(Qt.UserRole) == 1
    
    # 4. Filter by priority only
    view.apply_filter("", "Media")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 0).data(Qt.UserRole) == 2
    
    # 5. Filter by both search text and priority
    view.apply_filter("reporte", "Baja")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 0).data(Qt.UserRole) == 3
    
    # 6. Filter with no matches
    view.apply_filter("notfound", "Alta")
    assert view.table.rowCount() == 0
