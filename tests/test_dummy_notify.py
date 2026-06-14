"""Tests for the LocalMail notify service.

The dummy_notify_test module was removed in Phase 4b (11.0.7); its
"Send test notification" functionality is now in Settings > Diagnostics.
The underlying ``service.notify()`` call is still tested here.
"""
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

from noco_lib.noco_core.client import NocoClient
from noco_lib.noco_core.result import NocoResult
from modules.localmail.service import notify


def test_notify_service_call():
    """Verify that service.notify correctly delegates to send_email."""
    mock_client = MagicMock(spec=NocoClient)

    with patch("modules.localmail.service.send_email") as mock_send:
        mock_send.return_value = NocoResult.ok("create", data=[{"Id": 123}], affected_count=1)

        res = notify(
            client=mock_client,
            to_users=["test@mailbox.com"],
            subject="Alert",
            body="Notification body",
            module_origin="test_module",
        )

        assert res.success
        mock_send.assert_called_once_with(
            mock_client,
            from_user="sistema:test_module",
            to_users=["test@mailbox.com"],
            subject="Alert",
            body="Notification body",
            priority="Media",
        )
