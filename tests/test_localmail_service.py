import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock

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
from modules.localmail.service import list_sent

def test_list_sent_empty_mailboxes():
    mock_client = MagicMock(spec=NocoClient)
    result = list_sent(mock_client, [])
    assert not result.success
    assert "No hay casillas" in result.errors[0]

def test_list_sent_success_and_deduplication():
    mock_client = MagicMock(spec=NocoClient)
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    
    # Mock records returned by NocoDB
    # Notice we have duplicates on message_uuid "uuid-123"
    records = [
        {
            "Id": 1,
            "message_uuid": "uuid-123",
            "from": "alice.gentil@inorizonti.com",
            "title": "Email 1",
            "CreatedAt": "2026-06-13T12:00:00Z"
        },
        {
            "Id": 2,
            "message_uuid": "uuid-123",  # Duplicate uuid
            "from": "alice.gentil@inorizonti.com",
            "title": "Email 1 Duplicate",
            "CreatedAt": "2026-06-13T11:59:00Z"
        },
        {
            "Id": 3,
            "message_uuid": "uuid-456",
            "from": "dev@bisstox.com",
            "title": "Email 2",
            "CreatedAt": "2026-06-13T11:30:00Z"
        },
        {
            "Id": 4,
            "message_uuid": "",  # Empty uuid
            "from": "dev@bisstox.com",
            "title": "Email 3",
            "CreatedAt": "2026-06-13T11:00:00Z"
        }
    ]
    
    mock_table.read.return_value = NocoResult.ok("read", data=records)
    
    mailboxes = ["alice.gentil@inorizonti.com", "dev@bisstox.com"]
    result = list_sent(mock_client, mailboxes)
    
    assert result.success
    mock_table.read.assert_called_once_with(
        where="(from,in,alice.gentil@inorizonti.com,dev@bisstox.com)",
        limit=50,
        sort="-CreatedAt"
    )
    
    # Check deduplication: Id 2 should be filtered out, Id 1, 3, 4 should remain
    assert len(result.data) == 3
    assert result.affected_count == 3
    assert [r["Id"] for r in result.data] == [1, 3, 4]
