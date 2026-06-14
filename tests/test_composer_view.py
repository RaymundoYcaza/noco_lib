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

from modules.localmail.views.composer_view import ComposerView
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


@patch("modules.localmail.views.composer_view.run_async", side_effect=mock_run_async)
class TestComposerView:
    def test_init_ui(self, mock_run, mock_main_window, mock_client):
        """Check if widgets are initialized with default values."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        assert view.title_label.text() == "Redactar Nuevo Correo"
        assert view.error_label.isHidden()
        assert view.to_input.text() == ""
        assert view.cc_input.text() == ""
        assert view.subject_input.text() == ""
        assert view.body_input.toPlainText() == ""
        assert view.priority_combo.currentText() == "Media"
        assert view.btn_send.text() == "Enviar"

    def test_validation_empty_to(self, mock_run, mock_main_window, mock_client):
        """Should show error message locally if 'Para' (to) field is empty."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.subject_input.setText("Hola")
        view.to_input.setText("")  # Empty
        view._on_send_clicked()

        assert not view.error_label.isHidden()
        assert "destinatario" in view.error_label.text()
        assert mock_run.call_count == 0

    def test_validation_empty_subject(self, mock_run, mock_main_window, mock_client):
        """Should show error message locally if 'Asunto' (subject) field is empty."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.to_input.setText("receiver@test.com")
        view.subject_input.setText("")  # Empty
        view._on_send_clicked()

        assert not view.error_label.isHidden()
        assert "asunto" in view.error_label.text()
        assert mock_run.call_count == 0

    def test_send_success(self, mock_run, mock_main_window, mock_client):
        """Successfully sending an email clears fields and closes form."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.to_input.setText("receiver@test.com")
        view.cc_input.setText("cc@test.com")
        view.subject_input.setText("Saludo")
        view.body_input.setText("Hola a todos")
        view.priority_combo.setCurrentText("Alta")

        result_send = NocoResult.ok("create", data={"Id": 501})

        with patch("modules.localmail.service.send_email", return_value=result_send) as mock_send:
            # Track close calls
            close_called = False
            def mock_close():
                nonlocal close_called
                close_called = True
            view.close = mock_close

            view._on_send_clicked()

            mock_send.assert_called_once_with(
                mock_client,
                from_user="sender_user",
                to_users=["receiver@test.com"],
                subject="Saludo",
                body="Hola a todos",
                cc_users=["cc@test.com"],
                priority="Alta"
            )

            mock_main_window.show_notification.assert_called_once_with("Email sent", "success")
            assert view.to_input.text() == ""
            assert view.cc_input.text() == ""
            assert view.subject_input.text() == ""
            assert view.body_input.toPlainText() == ""
            assert view.priority_combo.currentText() == "Media"
            assert close_called

    def test_send_failure(self, mock_run, mock_main_window, mock_client):
        """Sending fails: show errors in UI, do not close or clear fields."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.to_input.setText("receiver@test.com")
        view.subject_input.setText("Saludo")
        view.body_input.setText("Hola")

        result_send = NocoResult.fail("create", ["Fallo de conexión con NocoDB"])

        with patch("modules.localmail.service.send_email", return_value=result_send):
            close_called = False
            view.close = lambda: exec("close_called = True")

            view._on_send_clicked()

            assert not view.error_label.isHidden()
            assert "Fallo de conexión con NocoDB" in view.error_label.text()
            assert view.to_input.text() == "receiver@test.com"
            assert not close_called

    def test_send_unexpected_exception(self, mock_run, mock_main_window, mock_client):
        """Unexpected exception: display error, restore button, do not close."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.to_input.setText("receiver@test.com")
        view.subject_input.setText("Saludo")

        with patch("modules.localmail.service.send_email", side_effect=RuntimeError("Fallo crítico")):
            view._on_send_clicked()

            assert not view.error_label.isHidden()
            assert "Fallo crítico" in view.error_label.text()
            assert view.btn_send.isEnabled()
            assert view.btn_send.text() == "Enviar"

    def test_close_event_empty(self, mock_run, mock_main_window, mock_client):
        """If the composer fields are empty, closing it should not show a message box."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.to_input.setText("   ")
        view.subject_input.setText("")
        view.body_input.setText("\n")
        
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            view.closeEvent(event)
            mock_question.assert_not_called()
            assert event.isAccepted()

    def test_close_event_non_empty_discard_no(self, mock_run, mock_main_window, mock_client):
        """If fields have content and user chooses not to discard, ignore the close event."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.subject_input.setText("Some subject")
        
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.No) as mock_question:
            view.closeEvent(event)
            mock_question.assert_called_once()
            assert not event.isAccepted()

    def test_close_event_non_empty_discard_yes(self, mock_run, mock_main_window, mock_client):
        """If fields have content and user chooses to discard, accept the close event."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.body_input.setText("Some body")
        
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes) as mock_question:
            view.closeEvent(event)
            mock_question.assert_called_once()
            assert event.isAccepted()

    def test_close_event_sent_successfully_bypass(self, mock_run, mock_main_window, mock_client):
        """If fields have content but the email was sent successfully, bypass discard confirmation."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.subject_input.setText("Bypass me")
        view._sent_successfully = True
        
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            view.closeEvent(event)
            mock_question.assert_not_called()
            assert event.isAccepted()

    def test_close_event_question_text(self, mock_run, mock_main_window, mock_client):
        """Verify the exact English title and message are used for discard confirmation."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        view.subject_input.setText("Test Text")
        
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes) as mock_question:
            view.closeEvent(event)
            mock_question.assert_called_once_with(
                view,
                "Discard draft?",
                "You have unsent content. Discard this email?",
                QMessageBox.Yes | QMessageBox.No
            )

    def test_close_event_saves_geometry(self, mock_run, mock_main_window, mock_client):
        """Verify that closing saves geometry to QSettings under 'floating/Compose/geometry'."""
        view = ComposerView(mock_main_window, mock_client, ["sender_user"])
        
        from PySide6.QtCore import QSettings
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        
        settings = QSettings("Tardis", "Tardis")
        settings.remove("floating/Compose/geometry")
        
        view.closeEvent(event)
        assert event.isAccepted()
        
        saved_geom = settings.value("floating/Compose/geometry")
        assert saved_geom is not None
