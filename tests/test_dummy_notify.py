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

from noco_lib.noco_core.client import NocoClient
from noco_lib.noco_core.result import NocoResult
from modules.localmail.service import notify
from modules.dummy_notify_test.module import register
from app_core.main_window import MainWindow
from app_core.config import TardisConfig

def test_notify_service_call():
    mock_client = MagicMock(spec=NocoClient)
    
    with patch("modules.localmail.service.send_email") as mock_send:
        mock_send.return_value = NocoResult.ok("create", data=[{"Id": 123}], affected_count=1)
        
        res = notify(
            client=mock_client,
            to_users=["test@mailbox.com"],
            subject="Alert",
            body="Notification body",
            module_origin="test_module"
        )
        
        assert res.success
        mock_send.assert_called_once_with(
            mock_client,
            from_user="sistema:test_module",
            to_users=["test@mailbox.com"],
            subject="Alert",
            body="Notification body",
            priority="Media"
        )

def test_dummy_module_register():
    mock_app = MagicMock(spec=MainWindow)
    mock_app.config = MagicMock(spec=TardisConfig)
    mock_app.config.mailboxes = ["alicia@inorizonti.com"]
    mock_app.add_menu_action = MagicMock()
    mock_client = MagicMock(spec=NocoClient)
    
    register(mock_app, mock_client)
    
    # Check that add_menu_action was called for the Dummy module
    mock_app.add_menu_action.assert_called_once()
    args, kwargs = mock_app.add_menu_action.call_args
    
    assert args[0] == "Dummy"
    assert args[1] == "Enviar notificación de prueba"
    
    # Test triggering the action callback
    callback = args[2]
    
    with patch("modules.dummy_notify_test.module.run_async") as mock_run_async:
        callback()
        mock_run_async.assert_called_once()
        # Ensure it calls localmail_service.notify with first mailbox
        called_args = mock_run_async.call_args[0]
        called_kwargs = mock_run_async.call_args[1]
        
        # Verify function passed to run_async is localmail_service.notify
        from modules.localmail import service as localmail_service
        assert called_args[0] == localmail_service.notify
        assert called_args[1] == mock_client
        assert called_kwargs["to_users"] == ["alicia@inorizonti.com"]
        assert called_kwargs["subject"] == "Prueba"
        assert called_kwargs["body"] == "Notificación de prueba desde dummy"
        assert called_kwargs["module_origin"] == "dummy_notify_test"
