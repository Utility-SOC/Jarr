# arr_omnitool/plugins/plugin_prowlarr.py
"""
Prowlarr Plugin - Indexer management and smart search
Phase 3 - New service with smart integration
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from core.plugin_base import PluginBase
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.api_client import ApiClient
from core.event_bus import EventBus
import logging


class ProwlarrPlugin(PluginBase):
    """Prowlarr indexer management."""
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus)
        self.widget = None

    def get_name(self) -> str:
        return "Prowlarr"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Centralized indexer management and search"
    
    def get_widget(self) -> QWidget:
        if not self.widget:
            self.widget = QWidget()
            layout = QVBoxLayout(self.widget)
            
            label = QLabel(
                "<h2>🔍 Prowlarr Plugin</h2>"
                "<p><b>Phase 3 - Smart Integration</b></p>"
                "<p>This service will be implemented in Phase 3.</p>"
                "<p>When enabled, this plugin will provide search results to other plugins.</p>"
            )
            label.setWordWrap(True)
            layout.addWidget(label)
        
        return self.widget
    
    def get_tab_name(self) -> str:
        return "Prowlarr (Search)"
    
    def get_icon(self) -> str:
        return "🔍"
    
    def is_enabled(self) -> bool:
        enabled = self.settings.get_plugin_setting("prowlarr", "enabled", False)
        url = self.settings.get_plugin_setting("prowlarr", "url", "")
        api_key = self.secure_storage.get_credential("prowlarr_api_key")
        return enabled and bool(url and api_key)