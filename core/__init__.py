"""
ARR Omni-Tool Core Framework
Provides essential services for the plugin system.
"""

__version__ = "2.0.0"

from .logging_handler import setup_logging, QtLogHandler
from .settings_manager import SettingsManager
from .secure_storage import SecureStorage
from .api_client import ApiClient, ApiWorker
from .plugin_base import PluginBase
from .plugin_registry import PluginRegistry
from .event_bus import EventBus
from .themes import apply_theme, Theme, DARK_STYLESHEET

__all__ = [
    'setup_logging',
    'QtLogHandler',
    'SettingsManager',
    'SecureStorage',
    'ApiClient',
    'ApiWorker',
    'PluginBase',
    'PluginRegistry',
    'EventBus',
    'apply_theme',
    'Theme',
    'DARK_STYLESHEET'
]