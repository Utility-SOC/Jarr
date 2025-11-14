# arr_omnitool/plugins/plugin_bazarr.py
"""
Bazarr Plugin - Subtitle management
Phase 3 - New service
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from core.plugin_base import PluginBase
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.api_client import ApiClient
from core.event_bus import EventBus
import logging

class BazarrPlugin(PluginBase):
    """Bazarr subtitle management."""
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus)
        self.widget = None
        
    def get_name(self) -> str:
        return "Bazarr"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Manage subtitles with Bazarr"
    
    def get_widget(self) -> QWidget:
        if not self.widget:
            self.widget = QWidget()
            layout = QVBoxLayout(self.widget)
            
            label = QLabel(
                "<h2>💬 Bazarr Plugin</h2>"
                "<p><b>Phase 3 - New Service</b></p>"
                "<p>This service will be implemented in Phase 3.</p>"
                "<p>Features:</p>"
                "<ul>"
                "<li>List movies/series with subtitle status</li>"
                "<li>Search for subtitles by language</li>"
                "<li>Download subtitles</li>"
                "<li>Missing subtitles report</li>"
                "</ul>"
            )
            label.setWordWrap(True)
            layout.addWidget(label)
        
        return self.widget
    
    def get_tab_name(self) -> str:
        return "Bazarr (Subtitles)"
    
    def get_icon(self) -> str:
        return "💬"
    
    def is_enabled(self) -> bool:
        url = self.settings.get_plugin_setting("bazarr", "url", "")
        api_key = self.secure_storage.get_credential("bazarr_api_key")
        return bool(url and api_key)