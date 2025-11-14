# arr_omnitool/plugins/plugin_radarr.py
"""
Radarr Plugin - Movie management
Inherits from ArrTab and uses the default (v3) logic.
"""
import logging
from PyQt6.QtWidgets import QWidget
from typing import Dict, Any

from core.plugin_base import PluginBase
from core.api_client import ApiClient
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.event_bus import EventBus
from .plugin_arr_base import ArrTab # Import the base class

# Define a Radarr-specific tab
class RadarrTab(ArrTab):
    # This class is Radarr-specific, so we override
    # the properties to be correct for Radarr
    
    @property
    def api_version(self) -> str:
        return "v3"
    
    @property
    def item_search_endpoint(self) -> str:
        return "movie/lookup"

    @property
    def item_add_endpoint(self) -> str:
        return "movie"

    def _build_add_payload(self, item_json: Dict[str, Any], item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Builds the JSON payload for adding a Radarr movie."""
        return {
            "tmdbId": item_json.get("tmdbId"),
            "title": item_json.get("title"),
            "qualityProfileId": item_data["quality_profile_id"],
            "rootFolderPath": item_data["root_folder_path"],
            "monitored": True,
            "addOptions": { "searchForMovie": True },
            **{k: item_json[k] for k in ["titleSlug", "images", "year"] if k in item_json}
        }

# Define the plugin wrapper
class RadarrPlugin(PluginBase):
    """Radarr movie management."""
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus)
        self.widget = None
    
    def get_name(self) -> str:
        return "radarr"
    
    def get_version(self) -> str:
        return "2.0.0"
    
    def get_description(self) -> str:
        return "Manage movies with Radarr"
    
    def get_widget(self) -> QWidget:
        self.widget = RadarrTab(
            service_name="radarr",
            logger=self.logger,
            settings=self.settings,
            secure_storage=self.secure_storage,
            api_client=self.api_client,
            event_bus=self.event_bus
        )
        return self.widget
    
    def get_tab_name(self) -> str:
        return "Radarr (Movies)"
    
    def get_icon(self) -> str:
        return "🎞️"

    def cleanup(self):
        if self.widget:
            if self.widget.status_thread: self.widget.status_thread.quit()
            if self.widget.folders_thread: self.widget.folders_thread.quit()
            if self.widget.profiles_thread: self.widget.profiles_thread.quit()
            if self.widget.search_thread: self.widget.search_thread.quit()