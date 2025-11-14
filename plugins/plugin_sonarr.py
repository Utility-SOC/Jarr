# arr_omnitool/plugins/plugin_sonarr.py
"""
Sonarr Plugin - TV Show management
This is a wrapper for the shared ArrTab logic.
"""
import logging
from PyQt6.QtWidgets import QWidget
from core.plugin_base import PluginBase
from core.api_client import ApiClient
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.event_bus import EventBus

# Import the shared ArrTab
from .plugin_arr_base import ArrTab

class SonarrPlugin(PluginBase):
    """Sonarr TV show management."""
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus)
        self.widget = None
    
    def get_name(self) -> str:
        return "sonarr"
    
    def get_version(self) -> str:
        return "2.0.0"
    
    def get_description(self) -> str:
        return "Manage TV shows with Sonarr"
    
    def get_widget(self) -> QWidget:
        # Create and return the tab widget
        self.widget = ArrTab(
            service_name="sonarr",
            logger=self.logger,
            settings=self.settings,
            secure_storage=self.secure_storage,
            api_client=self.api_client,
            event_bus=self.event_bus
        )
        return self.widget
    
    def get_tab_name(self) -> str:
        return "Sonarr (Shows)"
    
    def get_icon(self) -> str:
        return "📺"

    def cleanup(self):
        """Stop any running threads on shutdown."""
        if self.widget:
            if self.widget.status_thread: self.widget.status_thread.quit()
            if self.widget.folders_thread: self.widget.folders_thread.quit()
            if self.widget.profiles_thread: self.widget.profiles_thread.quit()
            if self.widget.search_thread: self.widget.search_thread.quit()