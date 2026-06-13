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

from modules.localmail.views.reader_view import ReaderView
from noco_lib.noco_core.client import NocoClient
from noco_lib.noco_core.result import NocoResult


# Mock run_async to run synchronously
def mock_run_async(fn, *args, on_success=None, on_error=None, **kwargs):
    try:
        result = fn(*args, **kwargs)
        if on_success:
            on_success(result)
    except Exception as e:
        if on_error:
            on_error(e)


@pytest.fixture
def mock_client():
    return MagicMock(spec=NocoClient)


@pytest.fixture
def mock_main_window():
    window = MagicMock()
    window.show_notification = MagicMock()
    return window


@patch("modules.localmail.views.reader_view.run_async", side_effect=mock_run_async)
class TestReaderView:
    def test_init_ui(self, mock_run, mock_main_window, mock_client):
        """Check if UI widgets are initialized correctly and have default text."""
        view = ReaderView(mock_main_window, mock_client)
        assert view.title_label.text() == "Lector de Correo"
        assert view.browser.toPlainText() == "Selecciona un correo para leerlo."

    def test_show_email_invalid_id(self, mock_run, mock_main_window, mock_client):
        """Passing an invalid ID should show a message and not trigger a load."""
        view = ReaderView(mock_main_window, mock_client)
        view.show_email(-1)
        assert view.browser.toPlainText() == "ID de correo inválido."
        assert mock_run.call_count == 0

    def test_show_email_success_with_cc(self, mock_run, mock_main_window, mock_client):
        """Check rendering an email with all fields present (including CC)."""
        email_data = {
            "Id": 201,
            "from": "sender@test.com",
            "to": "recipient@test.com",
            "cc": "cc@test.com",
            "CreatedAt": "2026-06-13T10:00:00Z",
            "title": "Asunto de Prueba",
            "body": "Hola,\nEsto es una prueba."
        }
        result = NocoResult.ok("read", data=email_data)

        with patch("modules.localmail.service.get_email", return_value=result) as mock_get:
            view = ReaderView(mock_main_window, mock_client)
            view.show_email(201)

            mock_get.assert_called_once_with(mock_client, 201)
            content = view.browser.toPlainText()
            assert "De:      sender@test.com" in content
            assert "Para:    recipient@test.com" in content
            assert "CC:      cc@test.com" in content
            assert "Fecha:   2026-06-13T10:00:00Z" in content
            assert "Asunto:  Asunto de Prueba" in content
            assert "Hola,\nEsto es una prueba." in content

    def test_show_email_success_without_cc(self, mock_run, mock_main_window, mock_client):
        """Check rendering an email when CC is empty."""
        email_data = {
            "Id": 202,
            "from": "sender@test.com",
            "to": "recipient@test.com",
            "cc": "",
            "CreatedAt": "2026-06-13T10:15:00Z",
            "title": "Sin CC",
            "body": "Cuerpo del correo."
        }
        result = NocoResult.ok("read", data=email_data)

        with patch("modules.localmail.service.get_email", return_value=result):
            view = ReaderView(mock_main_window, mock_client)
            view.show_email(202)

            content = view.browser.toPlainText()
            assert "De:      sender@test.com" in content
            assert "Para:    recipient@test.com" in content
            assert "CC:" not in content
            assert "Fecha:   2026-06-13T10:15:00Z" in content
            assert "Asunto:  Sin CC" in content

    def test_show_email_not_found(self, mock_run, mock_main_window, mock_client):
        """If database returns success=True but data is None (e.g. deleted), show not found."""
        result = NocoResult.ok("read", data=None)

        with patch("modules.localmail.service.get_email", return_value=result):
            view = ReaderView(mock_main_window, mock_client)
            view.show_email(999)
            assert view.browser.toPlainText() == "Correo no encontrado."

    def test_show_email_error(self, mock_run, mock_main_window, mock_client):
        """Database error should be shown and notified."""
        result = NocoResult.fail("read", "Error de red")

        with patch("modules.localmail.service.get_email", return_value=result):
            view = ReaderView(mock_main_window, mock_client)
            view.show_email(301)
            assert "Error: Error de red" in view.browser.toPlainText()
            mock_main_window.show_notification.assert_called_once_with("Error de red", "error")

    def test_show_email_unexpected_exception(self, mock_run, mock_main_window, mock_client):
        """Check exception safety during async execution."""
        with patch("modules.localmail.service.get_email", side_effect=ValueError("Fallo grave")):
            view = ReaderView(mock_main_window, mock_client)
            view.show_email(401)
            assert "Error inesperado: Fallo grave" in view.browser.toPlainText()
            mock_main_window.show_notification.assert_called_once_with("Error inesperado: Fallo grave", "error")
