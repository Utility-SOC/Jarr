# arr_omnitool/plugins/plugin_lidarr.py
"""
Lidarr Plugin - Music management
Inherits from ArrTab and provides Lidarr-specific overrides for API v1.
"""
import logging
from PyQt6.QtWidgets import QWidget, QComboBox, QHBoxLayout, QLabel
from typing import Dict, Any, List

from core.plugin_base import PluginBase
from core.api_client import ApiClient
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.event_bus import EventBus
from .plugin_arr_base import ArrTab # Import the base class

# Define a Lidarr-specific tab
class LidarrTab(ArrTab):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add Lidarr-specific UI
        search_type_layout = QHBoxLayout()
        search_type_layout.addWidget(QLabel("Search Type:"))
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["Artist", "Album"])
        self.search_type_combo.currentTextChanged.connect(self._on_search_type_changed)
        search_type_layout.addWidget(self.search_type_combo)
        search_type_layout.addStretch()
        
        # Add this to the "addon_layout" defined in the base class
        self.addon_layout.addLayout(search_type_layout)
        
        # Set initial search type
        self.current_search_type = "artist"

    def _on_search_type_changed(self, text: str):
        self.current_search_type = text.lower()

    # --- Override Properties ---
    
    @property
    def api_version(self) -> str:
        return "v1"
    
    # Lidarr's search endpoint is different
    @property
    def item_search_endpoint(self) -> str:
        # This is handled by _task_search_item override
        return "" 

    @property
    def item_add_endpoint(self) -> str:
        return "artist" # Lidarr only adds artists

    # --- Override Task Functions ---

    def _task_search_item(self, term: str, search_type: str) -> List[Dict[str, Any]]:
        """
        Worker task to search for a Lidarr item (Artist or Album).
        """
        base_url, api_key = self._get_arr_base_url()
        
        if search_type == "album":
            self.logger.info(f"Lidarr searching for ALBUM: {term}...")
            endpoint = f"{base_url}/api/v1/album/lookup"
            params = {"term": term}
            response = self.api_client.api_request(endpoint, api_key, self.service_name, params=params)
        else: # artist
            self.logger.info(f"Lidarr searching for ARTIST: {term}...")
            endpoint = f"{base_url}/api/v1/search"
            params = {"term": term}
            response = self.api_client.api_request(endpoint, api_key, self.service_name, params=params)
            # Unwrap artist from response
            response = [item.get("artist") for item in response if item.get("artist")]

        return response if response else []

    def _build_add_payload(self, item_json: Dict[str, Any], item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Builds the JSON payload for adding a Lidarr artist."""
        
        if item_data.get("search_type") == "album":
            # We can't add an album directly, we must add the artist
            raise ValueError("Adding albums directly is not supported by this tool. Please search for and add the artist.")

        return {
            "foreignArtistId": item_json.get("foreignArtistId"),
            "artistName": item_json.get("artistName"),
            "qualityProfileId": item_data["quality_profile_id"],
            "metadataProfileId": 1, # Default metadata profile
            "rootFolderPath": item_data["root_folder_path"],
            "monitored": True,
            "addOptions": {
                "searchForMissingAlbums": True,
                "monitor": "all"
            },
            **{k: item_json[k] for k in ["artistName", "foreignArtistId", "images"] if k in item_json}
        }

# Define the plugin wrapper
class LidarrPlugin(PluginBase):
    """Lidarr music management."""
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus)
        self.widget = None
    
    def get_name(self) -> str:
        return "lidarr"
    
    def get_version(self) -> str:
        return "2.0.0"
    
    def get_description(self) -> str:
        return "Manage music with Lidarr"
    
    def get_widget(self) -> QWidget:
        self.widget = LidarrTab(
            service_name="lidarr",
            logger=self.logger,
            settings=self.settings,
            secure_storage=self.secure_storage,
            api_client=self.api_client,
            event_bus=self.event_bus
        )
        return self.widget
    
    def get_tab_name(self) -> str:
        return "Lidarr (Music)"
    
    def get_icon(self) -> str:
        return "🎵"

    def cleanup(self):
        if self.widget:
            if self.widget.status_thread: self.widget.status_thread.quit()
            if self.widget.folders_thread: self.widget.folders_thread.quit()
            if self.widget.profiles_thread: self.widget.profiles_thread.quit()
            if self.widget.search_thread: self.widget.search_thread.quit()