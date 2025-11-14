# arr_omnitool/plugins/plugin_arr_base.py
"""
Base *Arr Plugin
Contains the shared ArrTab logic for Sonarr, Radarr, and Lidarr.
This class is designed to be subclassed and have its task
methods overridden.
"""
import logging
import csv
import json
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QHBoxLayout,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QFileDialog, QGridLayout, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, QTimer
from core.api_client import ApiClient, ApiWorker
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.event_bus import EventBus
from ui.dialogs import SelectionDialog

logger = logging.getLogger(__name__)

class ArrTab(QWidget):
    """
    Shared base tab for *Arr services.
    """
    def __init__(self, service_name: str, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus, parent=None):
        super().__init__(parent)
        
        self.service_name = service_name
        self.logger = logger
        self.settings = settings
        self.secure_storage = secure_storage
        self.api_client = api_client
        self.event_bus = event_bus
        
        # --- Internal State ---
        self.status_thread = None
        self.status_worker = None
        self.folders_thread = None
        self.folders_worker = None
        self.profiles_thread = None
        self.profiles_worker = None
        self.search_thread = None
        self.search_worker = None
        
        self.terms_to_add_queue = []
        self.items_to_add_queue = []
        self.terms_to_add_total_count = 0
        self.current_search_term = None
        self.current_search_type = "item"
        
        # --- Build UI ---
        self._build_ui()
        
        # --- Event Bus Subscription ---
        self.event_bus.subscribe("add_to_arr_requested", self._on_add_request)
        self.event_bus.subscribe("request_all_status", self.check_status)

        # --- Initial Load ---
        QTimer.singleShot(500, self.check_status)

    # --- Properties for Overriding ---
    
    @property
    def api_version(self) -> str:
        """API version (v3 for Sonarr/Radarr, v1 for Lidarr/Readarr)"""
        return "v3" # Default

    @property
    def item_search_endpoint(self) -> str:
        """API endpoint for a lookup"""
        return "movie/lookup" # Radarr default

    @property
    def item_add_endpoint(self) -> str:
        """API endpoint for adding an item"""
        return "movie" # Radarr default

    # --- UI Setup ---

    def _build_ui(self):
        """Creates the common UI elements."""
        layout = QVBoxLayout(self)
        
        # Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel(f"{self.service_name.title()} Status:"))
        self.status_label = QLabel("Unknown")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        self.btn_check_status = QPushButton("Check Status")
        self.btn_check_status.clicked.connect(self.check_status)
        status_layout.addWidget(self.btn_check_status)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Config
        config_layout = QGridLayout()
        config_layout.addWidget(QLabel("Root Folder:"), 0, 0)
        self.combo_root_folder = QComboBox()
        config_layout.addWidget(self.combo_root_folder, 0, 1)
        self.btn_refresh_folders = QPushButton("Refresh")
        self.btn_refresh_folders.clicked.connect(self.refresh_root_folders)
        config_layout.addWidget(self.btn_refresh_folders, 0, 2)
        config_layout.addWidget(QLabel("Quality Profile:"), 1, 0)
        self.combo_quality_profile = QComboBox()
        config_layout.addWidget(self.combo_quality_profile, 1, 1)
        self.btn_refresh_profiles = QPushButton("Refresh")
        self.btn_refresh_profiles.clicked.connect(self.refresh_quality_profiles)
        config_layout.addWidget(self.btn_refresh_profiles, 1, 2)
        layout.addLayout(config_layout)
        
        # Add-on UI (for Lidarr)
        self.addon_layout = QVBoxLayout()
        layout.addLayout(self.addon_layout)
        
        # Add Items
        add_layout = QVBoxLayout()
        add_layout.addWidget(QLabel("<b>Add Items</b>"))
        
        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel("Search Term:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"Enter {self.service_name} search term...")
        self.search_input.returnPressed.connect(self.add_from_text)
        text_input_layout.addWidget(self.search_input)
        self.btn_add_text = QPushButton("Add")
        self.btn_add_text.clicked.connect(self.add_from_text)
        text_input_layout.addWidget(self.btn_add_text)
        add_layout.addLayout(text_input_layout)
        
        csv_layout = QHBoxLayout()
        self.btn_import_csv = QPushButton("Import from CSV")
        self.btn_import_csv.clicked.connect(self.import_from_csv)
        csv_layout.addWidget(self.btn_import_csv)
        csv_layout.addStretch()
        add_layout.addLayout(csv_layout)
        layout.addLayout(add_layout)

    # --- Event Bus Handler ---
    
    def _on_add_request(self, service_name: str, search_term: str, search_type: str):
        """Slot to handle add requests from the event bus."""
        if service_name.lower() == self.service_name.lower():
            self.logger.info(f"'{self.service_name}' tab handling event bus request for '{search_term}'")
            self.start_search_and_add(search_term, search_type)

    # --- Base URL Helper ---

    def _get_arr_base_url(self) -> (str, str):
        """Helper to get base URL and API key for this service."""
        base_url = self.settings.get_plugin_setting(self.service_name, "url")
        api_key = self.secure_storage.get_credential(f"{self.service_name}_api_key")
        if not base_url or not api_key:
            raise ValueError(f"{self.service_name} URL or API Key is not set in settings.")
        return base_url.rstrip("/"), api_key

    # --- Worker Task Functions (Designed to be Overridden) ---

    def _task_get_status(self) -> Dict[str, Any]:
        """Worker task to check *Arr status."""
        base_url, api_key = self._get_arr_base_url()
        try:
            response = self.api_client.api_request(f"{base_url}/api/{self.api_version}/system/status", api_key, self.service_name)
            self.logger.info(f"{self.service_name.title()} is UP. Version: {response.get('version', 'Unknown')}")
            return {"status": "up", "data": response}
        except Exception as e:
            self.logger.error(f"{self.service_name.title()} is DOWN or unreachable: {e}")
            return {"status": "down", "error": str(e)}

    def _task_get_root_folders(self) -> List[Dict[str, Any]]:
        """Worker task to get *Arr root folders."""
        base_url, api_key = self._get_arr_base_url()
        response = self.api_client.api_request(f"{base_url}/api/{self.api_version}/rootfolder", api_key, self.service_name)
        return response if response else []

    def _task_get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Worker task to get *Arr quality profiles."""
        base_url, api_key = self._get_arr_base_url()
        response = self.api_client.api_request(f"{base_url}/api/{self.api_version}/qualityprofile", api_key, self.service_name)
        return response if response else []

    def _task_search_item(self, term: str, search_type: str) -> List[Dict[str, Any]]:
        """Worker task to search for an *Arr item."""
        # Prowlarr integration (common to Sonarr/Radarr)
        if self.service_name in ["sonarr", "radarr"]:
            try:
                prowlarr_results = self._task_prowlarr_search(term)
                if prowlarr_results:
                    arr_results = self._task_prowlarr_to_arr_lookup(prowlarr_results)
                    if arr_results:
                        return arr_results
                self.logger.warning("Prowlarr returned no usable results, falling back to direct search")
            except Exception as e:
                self.logger.warning(f"Prowlarr search failed, falling back to direct search: {e}")
        
        # Standard lookup
        base_url, api_key = self._get_arr_base_url()
        endpoint = f"{base_url}/api/{self.api_version}/{self.item_search_endpoint}"
        params = {"term": term}
        return self.api_client.api_request(endpoint, api_key, self.service_name, params=params)

    def _task_prowlarr_search(self, query: str) -> List[Dict[str, Any]]:
        """Internal Prowlarr search task."""
        prowlarr_url = self.settings.get_plugin_setting("prowlarr", "url").rstrip('/')
        prowlarr_api = self.secure_storage.get_credential("prowlarr_api_key")
        
        if not prowlarr_url or not prowlarr_api or not self.settings.get_plugin_setting("prowlarr", "enabled", False):
             raise ValueError("Prowlarr not enabled or configured.")
        
        media_type = "tv" if self.service_name == "sonarr" else "movie"
        category_map = {"movie": [2000], "tv": [5000]}
        categories = category_map.get(media_type, [])
        
        params = {"query": query, "categories": ",".join(map(str, categories)), "type": "search"}
        return self.api_client.api_request(
            f"{prowlarr_url}/api/v1/search", prowlarr_api, "prowlarr", params=params, timeout=30
        )

    def _task_prowlarr_to_arr_lookup(self, prowlarr_results: List[Dict], ) -> List[Dict[str, Any]]:
        """Internal Prowlarr conversion task."""
        base_url, api_key = self._get_arr_base_url()
        arr_results, seen_ids = [], set()
        
        for item in prowlarr_results[:10]:
            lookup_id = None
            if self.service_name == "sonarr" and item.get("tvdbId"):
                lookup_id = f"tvdb:{item['tvdbId']}"
            elif self.service_name == "radarr":
                if item.get("tmdbId"): lookup_id = f"tmdb:{item['tmdbId']}"
                elif item.get("imdbId"): lookup_id = f"imdb:{item['imdbId']}"
            
            if not lookup_id or lookup_id in seen_ids: continue
            seen_ids.add(lookup_id)

            endpoint = f"{base_url}/api/{self.api_version}/{self.item_search_endpoint}"
            try:
                arr_lookup = self.api_client.api_request(endpoint, api_key, self.service_name, params={"term": lookup_id}, timeout=10)
                if arr_lookup and isinstance(arr_lookup, list) and len(arr_lookup) > 0:
                    arr_results.append(arr_lookup[0])
            except Exception:
                continue
        return arr_results

    def _build_add_payload(self, item_json: Dict[str, Any], item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Builds the JSON payload for adding an item. Designed to be overridden."""
        # Default (Radarr)
        return {
            "tmdbId": item_json.get("tmdbId"),
            "title": item_json.get("title"),
            "qualityProfileId": item_data["quality_profile_id"],
            "rootFolderPath": item_data["root_folder_path"],
            "monitored": True,
            "addOptions": { "searchForMovie": True },
            **{k: item_json[k] for k in ["titleSlug", "images", "year"] if k in item_json}
        }

    def _task_add_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Worker task to add an *Arr item."""
        base_url, api_key = self._get_arr_base_url()
        item_json = item_data["item_json"]
        
        # Build the payload using the (potentially overridden) helper method
        payload = self._build_add_payload(item_json, item_data)
        
        endpoint = f"{base_url}/api/{self.api_version}/{self.item_add_endpoint}"

        return self.api_client.api_request(
            endpoint, api_key, self.service_name, method="POST", json_payload=payload
        )

    # --- Core Class Methods (Status, Folders, Profiles) ---
    
    def _start_worker(self, thread_attr: str, worker_attr: str, task_function: callable, on_finished_slot: callable, **task_kwargs):
        """
        Generic helper to create, connect, and start a worker thread.
        """
        if getattr(self, thread_attr) is not None:
            self.logger.warning(f"Task for {thread_attr} is already running.")
            return

        thread = QThread()
        worker = ApiWorker(task_function, **task_kwargs)
        
        setattr(self, thread_attr, thread)
        setattr(self, worker_attr, worker)

        worker.moveToThread(thread)

        worker.finished.connect(on_finished_slot)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        
        thread.finished.connect(lambda: setattr(self, thread_attr, None))
        thread.finished.connect(lambda: setattr(self, worker_attr, None))
        thread.finished.connect(thread.deleteLater)

        worker.progress.connect(self.logger.info)
        thread.started.connect(worker.run)
        thread.start()

    def check_status(self):
        self.btn_check_status.setEnabled(False)
        self.status_label.setText("Checking...")
        
        self._start_worker(
            "status_thread", "status_worker",
            self._task_get_status,
            self.on_status_finished
        )
    
    def on_status_finished(self, result: Optional[Dict[str, Any]], error: str):
        self.btn_check_status.setEnabled(True)
        
        if error or result is None or result.get("status") == "down":
            self.status_label.setText("UNAVAILABLE")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.logger.warning(f"{self.service_name.title()} service is unavailable: {error}")
            self.event_bus.publish("service_status_changed", self.service_name, "down")
        else:
            self.status_label.setText("UP")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.event_bus.publish("service_status_changed", self.service_name, "up")
            self.refresh_root_folders()
            self.refresh_quality_profiles()
    
    def refresh_root_folders(self):
        self.btn_refresh_folders.setEnabled(False)
        self._start_worker(
            "folders_thread", "folders_worker",
            self._task_get_root_folders,
            self.on_root_folders_finished
        )
    
    def on_root_folders_finished(self, result: Optional[List[Dict[str, Any]]], error: str):
        self.btn_refresh_folders.setEnabled(True)
        if error or result is None:
            self.logger.error(f"Failed to fetch root folders: {error}")
        else:
            self.combo_root_folder.clear()
            for folder in result:
                self.combo_root_folder.addItem(
                    f"{folder.get('path', 'Unknown')} ({folder.get('freeSpace', 0) // (1024**3)} GB free)",
                    {"id": folder.get("id"), "path": folder.get("path")}
                )
    
    def refresh_quality_profiles(self):
        self.btn_refresh_profiles.setEnabled(False)
        self._start_worker(
            "profiles_thread", "profiles_worker",
            self._task_get_quality_profiles,
            self.on_quality_profiles_finished
        )
    
    def on_quality_profiles_finished(self, result: Optional[List[Dict[str, Any]]], error: str):
        self.btn_refresh_profiles.setEnabled(True)
        if error or result is None:
            self.logger.error(f"Failed to fetch quality profiles: {error}")
        else:
            self.combo_quality_profile.clear()
            for profile in result:
                self.combo_quality_profile.addItem(
                    profile.get("name", "Unknown"),
                    {"id": profile.get("id")}
                )
    
    # --- Add/Search Queue Logic ---
    
    def add_from_text(self):
        search_term = self.search_input.text().strip()
        if not self._validate_inputs(search_term):
            return
        
        self.terms_to_add_queue = [search_term]
        self.terms_to_add_total_count = 1
        self.search_input.clear()
        self.process_next_item_in_queue()
    
    def import_from_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv)")
        if not file_path or not self._validate_inputs():
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                try: next(reader, None) # skip header
                except StopIteration: pass
                
                terms = [row[0].strip() for row in reader if row and row[0].strip()]
                
                if not terms:
                    QMessageBox.warning(self, "Empty CSV", "No valid terms found in CSV.")
                    return
                
                self.terms_to_add_queue = terms
                self.terms_to_add_total_count = len(terms)
                self.logger.info(f"Loaded {len(terms)} terms from CSV. Starting batch add...")
                self.process_next_item_in_queue()
                
        except Exception as e:
            self.logger.error(f"Failed to read CSV: {e}")
            QMessageBox.critical(self, "CSV Error", f"Failed to read CSV:\n{e}")
    
    def _validate_inputs(self, search_term: str = "N/A") -> bool:
        """Helper to validate settings before adding."""
        if search_term == "N/A": pass # CSV check
        elif not search_term:
            QMessageBox.warning(self, "No Input", "Please enter a search term.")
            return False
        
        if self.combo_root_folder.count() == 0:
            QMessageBox.warning(self, "No Root Folder", "Please select a root folder first.")
            return False
        if self.combo_quality_profile.count() == 0:
            QMessageBox.warning(self, "No Quality Profile", "Please select a quality profile first.")
            return False
        
        self.terms_to_add_queue = []
        self.items_to_add_queue = []
        return True

    def process_next_item_in_queue(self):
        if self.search_thread is not None:
            self.logger.warning("Search/add queue is already processing.")
            return
        
        if self.items_to_add_queue:
            item_data = self.items_to_add_queue.pop(0)
            title = item_data.get("item_json", {}).get("title", item_data.get("item_json", {}).get("artistName", "Unknown"))
            self.logger.info(f"Processing ADD for: '{title}'")
            self._run_add_worker(item_data)
        
        elif self.terms_to_add_queue:
            self.current_search_term = self.terms_to_add_queue.pop(0)
            self.logger.info(f"Processing SEARCH {self.terms_to_add_total_count - len(self.terms_to_add_queue)}/{self.terms_to_add_total_count}: '{self.current_search_term}'")
            self._run_search_worker(self.current_search_term)
        
        else:
            self.logger.info("Batch add complete.")
            if self.terms_to_add_total_count > 0:
                QMessageBox.information(self, "Complete", "All items have been processed.")
                self.terms_to_add_total_count = 0
            return
 
    def _run_search_worker(self, term: str):
        self._start_worker(
            "search_thread", "search_worker",
            self._task_search_item,
            self.on_search_finished,
            term=term,
            search_type=self.current_search_type
        )
 
    def _run_add_worker(self, item_data: Dict[str, Any]):
        self._start_worker(
            "search_thread", "search_worker",
            self._task_add_item,
            self.on_add_finished,
            item_data=item_data
        )
 
    def on_search_finished(self, result: Optional[List[Dict[str, Any]]], error: str):
        if error or result is None:
            self.logger.error(f"Search failed for '{self.current_search_term}': {error}")
            QMessageBox.critical(self, "Search Error", f"Search failed for '{self.current_search_term}':\n{error}")
        elif not result:
            self.logger.warning(f"No results found for '{self.current_search_term}'. Skipping.")
        elif len(result) == 1:
            self.logger.info(f"Found 1 result for '{self.current_search_term}'. Auto-queueing for add.")
            self.on_item_selected(result[0])
        else:
            self.logger.info(f"Found {len(result)} results for '{self.current_search_term}'. Asking user.")
            dialog = SelectionDialog(self.service_name, self.current_search_term, result, self, search_type=self.current_search_type)
            if dialog.exec():
                selected_items = dialog.get_selected_items()
                if selected_items:
                    for item in selected_items: self.on_item_selected(item)
                else:
                    self.logger.warning("User closed dialog without selection. Skipping.")
            else:
                self.logger.warning("User cancelled selection. Skipping.")
        
        self.process_next_item_in_queue()
 
    def on_item_selected(self, item_json: Dict[str, Any]):
        root_data = self.combo_root_folder.currentData()
        profile_data = self.combo_quality_profile.currentData()
        
        if not root_data or not profile_data:
            self.logger.error("Root folder or quality profile not selected properly.")
            return
        
        item_data = {
            "item_json": item_json,
            "root_folder_id": root_data.get("id"),
            "root_folder_path": root_data.get("path"),
            "quality_profile_id": profile_data.get("id"),
            "search_type": self.current_search_type
        }
        
        self.items_to_add_queue.append(item_data)
        title = item_json.get('title', item_json.get('artistName', 'Unknown'))
        self.logger.info(f"Queued item for adding: '{title}'")
 
    def on_add_finished(self, result: Optional[Dict[str, Any]], error: str):
        if error or result is None:
            if "400" in error and ("already" in error.lower() or "exist" in error.lower()):
                self.logger.warning(f"Item already exists in {self.service_name}. Skipping.")
            else:
                self.logger.error(f"Failed to add item: {error}")
                QMessageBox.critical(self, "Add Error", f"Failed to add item:\n{error}")
        else:
            title = result.get('title', result.get('artistName', "Unknown Item"))
            self.logger.info(f"Successfully added '{title}'.")
            self.event_bus.publish("item_added", self.service_name, result)
 
        self.process_next_item_in_queue()
 
    def start_search_and_add(self, search_term: str, search_type: Optional[str] = None):
        """Public method to trigger an add process from outside (e.g., event bus)."""
        if not search_term or not self._validate_inputs(search_term):
            return
        
        if search_type:
            self.current_search_type = search_type
        
        self.terms_to_add_queue = [search_term]
        self.terms_to_add_total_count = 1
        self.process_next_item_in_queue()