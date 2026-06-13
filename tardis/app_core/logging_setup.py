import logging
import logging.handlers
import sys
from pathlib import Path

def setup_logging(log_dir: str | None = None) -> None:
    """
    Configures Python's logging module to write to both stdout and a rotating file tardis.log.
    Also registers a global sys.excepthook to capture and log uncaught exceptions.
    """
    if log_dir is None:
        # P:\REPOs\noco_lib\tardis\app_core\logging_setup.py -> parents[2] is P:\REPOs\noco_lib
        log_dir = Path(__file__).resolve().parents[2] / "logs"
    else:
        log_dir = Path(log_dir)
        
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # Fallback to current directory if we cannot write to the root
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
    log_file = log_dir / "tardis.log"
    
    # Formatter configuration
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s (%(threadName)s): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Rotating File Handler: max 2MB, 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Stream Handler: stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    # Configure Root Logger: level INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates on duplicate calls
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    
    # Configure Tardis Logger: level DEBUG
    tardis_logger = logging.getLogger("tardis")
    tardis_logger.setLevel(logging.DEBUG)
    
    # Global exception hook
    original_excepthook = sys.excepthook
    
    def exception_hook(exctype, value, traceback):
        tardis_logger.exception("Unhandled global exception", exc_info=(exctype, value, traceback))
        original_excepthook(exctype, value, traceback)
        
    sys.excepthook = exception_hook
    
    tardis_logger.info("Logging initialized. Log file: %s", log_file)
