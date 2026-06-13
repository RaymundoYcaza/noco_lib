import pytest
from PySide6.QtGui import QIcon
import qtawesome as qta

def test_qtawesome_icon():
    # Verify qtawesome can be imported and creates a non-null QIcon
    icon = qta.icon('fa5s.inbox')
    assert isinstance(icon, QIcon)
    assert not icon.isNull()
