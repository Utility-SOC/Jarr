"""
Custom Qt logging handler for thread-safe GUI logging.
Migrated from arr_omnitool.py (line 97)
"""

import logging
import sys
from PyQt6.QtCore import QObject, pyqtSignal


class QtLogHandler(logging.Handler, QObject):
    """
    Custom logging handler that emits a Qt signal with the log message.
    This allows safe logging from worker threads to the GUI.
    """
    log_updated = pyqtSignal(str)
 
    def __init__(self, *args, **kwargs):
        logging.Handler.__init__(self, *args, **kwargs)
        QObject.__init__(self)
 
    def emit(self, record):
        """
        Emit the log message as a formatted string via Qt signal.
        """
        msg = self.format(record)
        self.log_updated.emit(msg)


# Global reference to the Qt handler for retrieval
_qt_handler = None


def setup_logging(log_widget_append_slot) -> logging.Logger:
    """
    Configures the root logger with both a console handler
    and the custom Qt handler for GUI display.
    
    Args:
        log_widget_append_slot: Qt slot (function) to receive log messages
        
    Returns:
        Configured logger instance
    """
    global _qt_handler
    
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Clear existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Add GUI handler
    _qt_handler = QtLogHandler()
    _qt_handler.setFormatter(formatter)
    _qt_handler.log_updated.connect(log_widget_append_slot)
    logger.addHandler(_qt_handler)

    # Add Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info("✅ Logging system initialized")
    return logger


def get_log_handler() -> QtLogHandler:
    """
    Returns the global Qt log handler for additional signal connections.
    """
    return _qt_handler
