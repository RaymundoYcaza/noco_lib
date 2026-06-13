import sys
import logging
from pathlib import Path
import pytest
import tempfile
import shutil

# Make sure tardis is in sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

from app_core.logging_setup import setup_logging

def test_setup_logging():
    # Use a temporary directory for logs to avoid cluttering local files
    temp_log_dir = Path(tempfile.mkdtemp())
    try:
        # Save original excepthook
        original_hook = sys.excepthook
        
        # Initialize logging
        setup_logging(log_dir=str(temp_log_dir))
        
        # Check that sys.excepthook was overridden
        assert sys.excepthook != original_hook
        
        # Log some test messages
        tardis_logger = logging.getLogger("tardis")
        root_logger = logging.getLogger()
        
        assert tardis_logger.level == logging.DEBUG
        assert root_logger.level == logging.INFO
        
        tardis_logger.debug("Debug message from tardis")
        tardis_logger.info("Info message from tardis")
        root_logger.info("Info message from root")
        root_logger.debug("Debug message from root (should not be logged since root level is INFO)")
        
        # Verify log file exists and contains the expected content
        log_file = temp_log_dir / "tardis.log"
        assert log_file.exists()
        
        log_content = log_file.read_text(encoding="utf-8")
        assert "Debug message from tardis" in log_content
        assert "Info message from tardis" in log_content
        assert "Info message from root" in log_content
        assert "Debug message from root" not in log_content
        
        # Restore sys.excepthook
        sys.excepthook = original_hook
    finally:
        # Clean up temp folder
        shutil.rmtree(temp_log_dir, ignore_errors=True)
