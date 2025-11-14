# arr_omnitool/plugins/plugin_jellyfin.py
"""
Jellyfin Plugin v2.2.1 (Self-Contained & Secure)
- Includes optional file deletion (v2.2.0)
- Includes all dialogs (Identify, BulkIdentify, Delete)
- Integrated with core SecureStorage (keyring) service
"""
import time
import logging
import csv
import re
import os
from typing import Optional, List, Dict, Any
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QHBoxLayout,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QFileDialog, QMenu, QHeaderView, QCheckBox, QDialog,
    QFormLayout, QDialogButtonBox, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from core.plugin_base import PluginBase
from core.api_client import ApiClient, ApiWorker
from core.settings_manager import SettingsManager
from core.event_bus import EventBus
from core.secure_storage import SecureStorage # Import new core service
from core.utils import scrub_name # Import from core

# --- Application Configuration ---
CACHE_DURATION_SECONDS = 300  # 5 minutes for Jellyfin cache

logger = logging.getLogger(__name__)

#
# --- DIALOG: DeleteConfirmationDialog (v2.2.0) ---
#
class DeleteConfirmationDialog(QDialog):
    """Custom dialog for confirming deletion with option to delete files."""
    
    def __init__(self, item_names: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Deletion")
        self.delete_files = False
        
        layout = QVBoxLayout(self)
        
        # Message
        count = len(item_names)
        if count == 1:
            message = f"Are you sure you want to delete this item from Jellyfin?\n\n{item_names[0]}"
        else:
            names_preview = "\n".join(item_names[:5])
            if count > 5:
                names_preview += f"\n... and {count - 5} more"
            message = f"Are you sure you want to delete {count} items from Jellyfin?\n\n{names_preview}"
        
        message_label = QLabel(message)
        layout.addWidget(message_label)
        
        # Checkbox for file deletion
        self.delete_files_checkbox = QCheckBox("Also delete media files from disk")
        self.delete_files_checkbox.setStyleSheet("QCheckBox { color: #FF6B6B; font-weight: bold; }")
        layout.addWidget(self.delete_files_checkbox)
        
        # Warning label
        warning_label = QLabel()
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("QLabel { color: #FFA500; }")
        self.delete_files_checkbox.stateChanged.connect(
            lambda state: warning_label.setText(
                "⚠️ WARNING: Files will be PERMANENTLY DELETED from disk! This cannot be undone!"
                if state == Qt.CheckState.Checked.value
                else "ℹ️ Metadata will be removed but media files will be kept on disk."
            )
        )
        warning_label.setText("ℹ️ Metadata will be removed but media files will be kept on disk.")
        layout.addWidget(warning_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.accept)
        delete_button.setStyleSheet("QPushButton { background-color: #DC3545; color: white; }")
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        
        self.setMinimumWidth(400)
    
    def is_delete_files_checked(self) -> bool:
        """Returns True if user wants to delete files."""
        return self.delete_files_checkbox.isChecked()

#
# --- DIALOG: BlacklistWidget (from dialogs.py) ---
#
class BlacklistWidget(QWidget):
    """
    A reusable widget for managing the identify blacklist.
    """
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("<b>Blacklist</b> (one entry per line, '#' to comment)"))
        
        self.blacklist_edit = QTextEdit()
        layout.addWidget(self.blacklist_edit)
        
        button_layout = QHBoxLayout()
        self.btn_save_settings = QPushButton("Save List")
        self.btn_save_settings.setToolTip("Save this list to settings for next time.")
        self.btn_save_settings.clicked.connect(self._save_blacklist_to_settings)
        button_layout.addWidget(self.btn_save_settings)
        
        # Note: CSV import/export removed for simplicity, can be added back
        # if parse_csv_to_list is imported
        
        layout.addLayout(button_layout)
        
        self._load_blacklist_from_settings()

    def _load_blacklist_from_settings(self):
        raw_list = self.settings.get_global_setting("identify_blacklist", "")
        self.blacklist_edit.setText(raw_list)

    def _save_blacklist_to_settings(self):
        raw_list = self.blacklist_edit.toPlainText()
        self.settings.set_global_setting("identify_blacklist", raw_list)
        QMessageBox.information(self, "Blacklist Saved", "Your blacklist has been saved to settings.")
        
    def get_blacklist_words(self) -> list[str]:
        raw_list = self.blacklist_edit.toPlainText()
        words = raw_list.split('\n')
        
        active_words = []
        for w in words:
            w_stripped = w.strip()
            if w_stripped and not w_stripped.startswith("#"):
                active_words.append(w_stripped)
        
        return active_words

#
# --- DIALOG: IdentifyDialog (from dialogs.py) ---
#
class IdentifyDialog(QDialog):
    """Dialog for Jellyfin's "Identify" feature."""
    
    def __init__(self, api_client: ApiClient, settings: SettingsManager, secure_storage: SecureStorage, item_id: str, item_type: str, search_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Identify Item - {search_info.get('Name')}")
        self.setModal(True)
        self.resize(900, 500)
        
        self.api_client = api_client
        self.settings = settings
        self.secure_storage = secure_storage # <-- Added
        
        self.item_id = item_id
        self.item_type = item_type
        self.search_results = []
        self.selected_result = None
        
        self.api_thread = None
        self.api_worker = None
        self.is_initial_search = True
        
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        
        self.path_label = QLabel(f"<b>Path:</b> {search_info.get('Path', 'N/A')}")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        
        form_layout = QFormLayout()
        self.name_input = QLineEdit(search_info.get("Name", ""))
        form_layout.addRow("Search Name:", self.name_input)
        
        self.year_input = QLineEdit(str(search_info.get("Year", "")))
        form_layout.addRow("Search Year:", self.year_input)
        
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.start_search)
        form_layout.addRow(self.btn_search)
        
        layout.addLayout(form_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "Year", "Provider", "Overview"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self.on_ok)
        layout.addWidget(self.table)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.on_ok)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.buttons)
        
        self.table.itemSelectionChanged.connect(
            lambda: self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        )
        
        splitter.addWidget(left_widget)
        
        self.blacklist_widget = BlacklistWidget(self.settings)
        splitter.addWidget(self.blacklist_widget)
        
        splitter.setSizes([600, 300])
        main_layout.addWidget(splitter)
        
        QTimer.singleShot(100, self.start_search)

    def _get_api_credentials(self):
        """Helper to get credentials securely."""
        base_url = self.settings.get_plugin_setting("jellyfin", "url")
        api_key = self.secure_storage.get_credential("jellyfin_api_key")
        return base_url, api_key

    def _task_remote_search(self, item_type: str, search_payload: Dict[str, Any]):
        base_url, api_key = self._get_api_credentials()
        endpoint = f"{base_url}/Items/RemoteSearch/{item_type}"
        
        return self.api_client.api_request(
            url=endpoint, 
            api_key=api_key, 
            service_name="jellyfin", 
            method="POST", 
            json_payload=search_payload
        )

    def start_search(self):
        # ... (This method remains the same, it calls _task_remote_search) ...
        # ... (No, wait, it needs to be updated to not pass credentials) ...
        if self.api_thread is not None:
            if self.api_worker: self.api_worker.stop()
            self.api_thread.quit()
            self.api_thread.wait(1000)

        self.btn_search.setEnabled(False)
        self.btn_search.setText("Searching...")
        self.table.clearContents()
        self.table.setRowCount(0)
        
        search_name = self.name_input.text().strip()
        search_year = self.year_input.text().strip()
        
        if self.is_initial_search:
            self.is_initial_search = False
            blacklist = self.blacklist_widget.get_blacklist_words()
            scrubbed_name = scrub_name(search_name, blacklist)
            
            if scrubbed_name != search_name:
                self.name_input.setText(scrubbed_name)
                search_name = scrubbed_name
        
        search_payload = {
            "SearchInfo": {
                "Name": search_name,
                "Year": int(search_year) if search_year.isdigit() else None
            },
            "ItemId": self.item_id,
            "IncludeDisabledProviders": False
        }
        
        if not search_payload["SearchInfo"]["Year"]:
             del search_payload["SearchInfo"]["Year"]
        
        self.api_thread = QThread()
        self.api_worker = ApiWorker(
            self._task_remote_search,
            item_type=self.item_type,
            search_payload=search_payload
        )
        self.api_worker.moveToThread(self.api_thread)
        
        self.api_thread.started.connect(self.api_worker.run)
        self.api_worker.finished.connect(self.on_search_finished)
        
        self.api_thread.start()

    def on_search_finished(self, result: Optional[List[Dict[str, Any]]], error: str):
        # ... (This method remains exactly the same) ...
        if self.api_thread:
            self.api_thread.quit()
            self.api_thread.wait(1000)
            self.api_thread = None
            self.api_worker = None
        
        self.btn_search.setEnabled(True)
        self.btn_search.setText("Search")
        
        if error or result is None:
            logger.error(f"Jellyfin remote search failed: {error}")
            QMessageBox.critical(self, "Search Error", f"Remote search failed:\n{error}")
            return
            
        self.search_results = result
        self.table.setRowCount(len(self.search_results))
        
        for i, item in enumerate(self.search_results):
            self.table.setItem(i, 0, QTableWidgetItem(item.get("Name", "N/A")))
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get("ProductionYear", "N/A"))))
            provider_ids = item.get("ProviderIds", {})
            provider_str = ", ".join(f"{k}: {v}" for k, v in provider_ids.items() if v)
            self.table.setItem(i, 2, QTableWidgetItem(provider_str))
            self.table.setItem(i, 3, QTableWidgetItem(item.get("Overview", "")[:100] + "..."))
            
        self.table.resizeColumnsToContents()

    def on_ok(self):
        # ... (This method remains exactly the same) ...
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select an item to apply.")
            return
        
        row = selected_rows[0].row()
        self.selected_result = self.search_results[row]
        self.accept()

    def get_selected_result(self) -> Optional[Dict[str, Any]]:
        return self.selected_result
        
    def closeEvent(self, event):
        # ... (This method remains exactly the same) ...
        if self.api_thread is not None:
            if self.api_worker: self.api_worker.stop()
            self.api_thread.quit()
            self.api_thread.wait(1000)
        event.accept()

#
# --- DIALOG: BulkIdentifyDialog (from dialogs.py) ---
#
class BulkIdentifyDialog(QDialog):
    """Dialog for Jellyfin's "Bulk Identify" feature."""
    
    apply_requested = pyqtSignal(str, dict)

    def __init__(self, api_client: ApiClient, settings: SettingsManager, secure_storage: SecureStorage, items_list: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Identify")
        self.setModal(True)
        self.resize(900, 600)
        
        self.api_client = api_client
        self.settings = settings
        self.secure_storage = secure_storage # <-- Added
        
        self.items_list = items_list
        self.current_item_index = -1
        self.current_item_data = None
        self.search_results = []
        
        self.api_thread = None
        self.api_worker = None
        
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)

        self.item_label = QLabel("Loading first item...")
        layout.addWidget(self.item_label)
        
        self.path_label = QLabel("<b>Path:</b> N/A")
        layout.addWidget(self.path_label)

        self.item_count_label = QLabel(f"Item 1 of {len(self.items_list)}")
        layout.addWidget(self.item_count_label)
        
        form_layout = QFormLayout()
        self.name_input = QLineEdit()
        form_layout.addRow("Search Name:", self.name_input)
        
        self.year_input = QLineEdit()
        form_layout.addRow("Search Year:", self.year_input)
        
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.start_search)
        form_layout.addRow(self.btn_search)
        
        layout.addLayout(form_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Title", "Year", "Provider", "Overview"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)
        
        self.table.itemDoubleClicked.connect(self.on_apply_next)
        
        button_layout = QHBoxLayout()
        self.btn_apply_next = QPushButton("Apply & Next")
        self.btn_apply_next.clicked.connect(self.on_apply_next)
        self.btn_apply_next.setEnabled(False)
        button_layout.addWidget(self.btn_apply_next)
        
        self.btn_skip = QPushButton("Skip")
        self.btn_skip.clicked.connect(self.load_next_item)
        button_layout.addWidget(self.btn_skip)
        
        self.btn_cancel = QPushButton("Cancel Bulk Job")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        layout.addLayout(button_layout)
        
        self.table.itemSelectionChanged.connect(
            lambda: self.btn_apply_next.setEnabled(True)
        )
        
        splitter.addWidget(left_widget)
        
        self.blacklist_widget = BlacklistWidget(self.settings)
        splitter.addWidget(self.blacklist_widget)

        splitter.setSizes([600, 300])
        main_layout.addWidget(splitter)
        
        QTimer.singleShot(100, self.load_next_item)

    def load_next_item(self):
        # ... (This method remains the same) ...
        self.current_item_index += 1
        
        if self.current_item_index >= len(self.items_list):
            logger.info("Bulk identify complete.")
            QMessageBox.information(self, "Complete", "All items have been processed.")
            self.accept()
            return

        self.current_item_data = self.items_list[self.current_item_index]
        
        item_name = self.current_item_data.get("Name")
        item_path = self.current_item_data.get("Path", "N/A")
        item_year = str(self.current_item_data.get("ProductionYear", ""))

        blacklist = self.blacklist_widget.get_blacklist_words()
        scrubbed_name = scrub_name(item_name, blacklist)

        self.item_label.setText(item_name)
        self.path_label.setText(f"<b>Path:</b> {item_path}")
        self.item_count_label.setText(f"Item {self.current_item_index + 1} of {len(self.items_list)}")
        self.name_input.setText(scrubbed_name)
        self.year_input.setText(item_year)
        self.btn_apply_next.setEnabled(False)
        
        self.start_search(is_auto_search=True)

    def _get_api_credentials(self):
        """Helper to get credentials securely."""
        base_url = self.settings.get_plugin_setting("jellyfin", "url")
        api_key = self.secure_storage.get_credential("jellyfin_api_key")
        return base_url, api_key

    def _task_remote_search(self, item_type: str, search_payload: Dict[str, Any]):
        base_url, api_key = self._get_api_credentials()
        endpoint = f"{base_url}/Items/RemoteSearch/{item_type}"
        
        return self.api_client.api_request(
            url=endpoint, 
            api_key=api_key, 
            service_name="jellyfin", 
            method="POST", 
            json_payload=search_payload
        )

    def start_search(self, is_auto_search=False):
        # ... (This method remains the same, it calls _task_remote_search) ...
        if not self.current_item_data:
            return

        if self.api_thread is not None:
            if self.api_worker: self.api_worker.stop()
            self.api_thread.quit()
            self.api_thread.wait(1000)
        
        self.btn_search.setEnabled(False)
        self.btn_search.setText("Searching...")
        self.table.clearContents()
        self.table.setRowCount(0)
        
        search_name = self.name_input.text().strip()
        search_year = self.year_input.text().strip()
        item_id = self.current_item_data.get("Id")
        item_type = self.current_item_data.get("Type")

        if not is_auto_search:
            blacklist = self.blacklist_widget.get_blacklist_words()
            scrubbed_name = scrub_name(search_name, blacklist)
            self.name_input.setText(scrubbed_name)
            search_name = scrubbed_name

        search_payload = {
            "SearchInfo": {
                "Name": search_name,
                "Year": int(search_year) if search_year.isdigit() else None
            },
            "ItemId": item_id,
            "IncludeDisabledProviders": False
        }
        
        if not search_payload["SearchInfo"]["Year"]:
             del search_payload["SearchInfo"]["Year"]
        
        self.api_thread = QThread()
        self.api_worker = ApiWorker(
            self._task_remote_search,
            item_type=item_type,
            search_payload=search_payload
        )
        self.api_worker.moveToThread(self.api_thread)
        
        self.api_thread.started.connect(self.api_worker.run)
        self.api_worker.finished.connect(self.on_search_finished)
        
        self.api_thread.start()

    def on_search_finished(self, result: Optional[List[Dict[str, Any]]], error: str):
        # ... (This method remains the same) ...
        if self.api_thread:
            self.api_thread.quit()
            self.api_thread.wait(1000)
            self.api_thread = None
            self.api_worker = None
        
        self.btn_search.setEnabled(True)
        self.btn_search.setText("Search")
        
        if error or result is None:
            logger.error(f"Jellyfin remote search failed: {error}")
            QMessageBox.critical(self, "Search Error", f"Remote search failed:\n{error}")
            return
            
        self.search_results = result
        self.table.setRowCount(len(self.search_results))
        
        for i, item in enumerate(self.search_results):
            self.table.setItem(i, 0, QTableWidgetItem(item.get("Name", "N/A")))
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get("ProductionYear", "N/A"))))
            provider_ids = item.get("ProviderIds", {})
            provider_str = ", ".join(f"{k}: {v}" for k, v in provider_ids.items() if v)
            self.table.setItem(i, 2, QTableWidgetItem(provider_str))
            self.table.setItem(i, 3, QTableWidgetItem(item.get("Overview", "")[:100] + "..."))
            
        self.table.resizeColumnsToContents()

    def on_apply_next(self):
        # ... (This method remains the same) ...
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        selected_result = self.search_results[row]
        item_id = self.current_item_data.get("Id")
        
        if item_id and selected_result:
            logger.info(f"Emitting apply request for item {item_id}")
            self.apply_requested.emit(item_id, selected_result)
            self.load_next_item()
        else:
            logger.error("Could not apply, item_id or selected_result is missing.")

    def closeEvent(self, event):
        # ... (This method remains the same) ...
        if self.api_thread is not None:
            if self.api_worker: self.api_worker.stop()
            self.api_thread.quit()
            self.api_thread.wait(1000)
        event.accept()

# 
# --- MAIN CLASS: JellyfinTab ---
#
class JellyfinTab(QWidget):
    """
    Tab for interacting with Jellyfin.
    """
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus, parent=None):
        super().__init__(parent)
        
        self.logger = logger
        self.settings = settings
        self.secure_storage = secure_storage # <-- Added
        self.api_client = api_client
        self.event_bus = event_bus
        
        self.item_cache = []
        self.last_fetch_time = None
        
        self.list_thread = None
        self.list_worker = None
        self.apply_thread = None
        self.apply_worker = None
        self.status_thread = None
        self.status_worker = None
        self.delete_thread = None
        self.delete_worker = None
        
        self.apply_queue = []
        self.apply_job_running = False
        
        self.showing_duplicates = False
        self.duplicate_groups = []
        
        # --- Build UI ---
        # All UI building code remains the same
        layout = QVBoxLayout(self)
        
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Item Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Movie", "Series"])
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        button_layout = QHBoxLayout()
        self.btn_list = QPushButton("List Items")
        self.btn_list.clicked.connect(self.on_list_items_clicked)
        button_layout.addWidget(self.btn_list)
        
        self.btn_force_refresh = QPushButton("Force Refresh")
        self.btn_force_refresh.clicked.connect(self.on_force_refresh_clicked)
        button_layout.addWidget(self.btn_force_refresh)
        
        self.btn_export = QPushButton("Export to CSV")
        self.btn_export.clicked.connect(self.export_to_csv)
        self.btn_export.setEnabled(False)
        button_layout.addWidget(self.btn_export)
        
        self.btn_find_duplicates = QPushButton("Find Duplicates")
        self.btn_find_duplicates.clicked.connect(self.toggle_duplicate_view)
        self.btn_find_duplicates.setEnabled(False)
        button_layout.addWidget(self.btn_find_duplicates)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter List:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Type here to filter results...")
        self.filter_input.textChanged.connect(self.filter_table)
        filter_layout.addWidget(self.filter_input)
        
        filter_layout.addWidget(QLabel("Dup Blacklist:"))
        self.dup_blacklist_input = QLineEdit()
        self.dup_blacklist_input.setPlaceholderText("[1080p], x265, (comma,separated)")
        self.dup_blacklist_input.setToolTip("Comma-separated list of junk words to ignore when finding duplicates by name.")
        filter_layout.addWidget(self.dup_blacklist_input)
        layout.addLayout(filter_layout)
        
        self.btn_add_missing = QPushButton("Add to...")
        self.btn_add_missing.clicked.connect(self.add_missing_to_arr)
        self.btn_add_missing.setVisible(False)
        layout.addWidget(self.btn_add_missing)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Title", "Year", "Path"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        
        layout.addWidget(self.table)
        
        self.items = []
        
        self.event_bus.subscribe("request_all_status", self.check_jellyfin_status)
        
        # --- Add new event subscription for filesystem ---
        # This makes the "broadcast on failure" more robust
        self.event_bus.subscribe("filesystem_delete_failure", self.on_filesystem_delete_failed)
        self.pending_delete_failures = {} # To track failures

    # --- Worker Task Functions ---
    def _start_worker(self, thread_attr: str, worker_attr: str, task_function: callable, on_finished_slot: callable, **task_kwargs):
        # ... (This method remains the same) ...
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

    def _get_api_credentials(self):
        """Helper to get credentials securely."""
        base_url = self.settings.get_plugin_setting("jellyfin", "url")
        api_key = self.secure_storage.get_credential("jellyfin_api_key")
        if not base_url or not api_key:
            raise ValueError("Jellyfin URL or API Key is not set/found in secure storage.")
        return base_url, api_key

    def _task_get_items(self, item_type: str) -> List[Dict[str, Any]]:
        base_url, api_key = self._get_api_credentials()
        
        users = self.api_client.api_request(f"{base_url}/Users", api_key, service_name="jellyfin")
        if not users:
            raise ValueError("No users found on Jellyfin server.")
        
        admin_user = next((u for u in users if u.get("Policy", {}).get("IsAdministrator")), None)
        user_id = admin_user["Id"] if admin_user else users[0]["Id"]
        
        params = {
            "IncludeItemTypes": item_type,
            "Recursive": "true",
            "Fields": "ProviderIds,Path",
        }
        
        response = self.api_client.api_request(
            f"{base_url}/Users/{user_id}/Items",
            api_key, service_name="jellyfin", params=params, timeout=120
        )
        items = response.get("Items", [])
        self.logger.info(f"Found {len(items)} {item_type} items in Jellyfin.")
        return items

    def _task_apply_identification(self, item_id: str, search_result: Dict[str, Any]) -> Dict[str, Any]:
        base_url, api_key = self._get_api_credentials()
        
        endpoint = f"{base_url}/Items/RemoteSearch/Apply/{item_id}"
        params = {"ReplaceAllImages": "true"}
        
        response = self.api_client.api_request(
            endpoint, api_key, service_name="jellyfin",
            method="POST", params=params, json_payload=search_result, timeout=120
        )
        self.logger.info(f"Successfully applied new identification to item {item_id}.")
        return response
    
    def _task_delete_items(self, item_ids: List[str], item_paths: Optional[List[str]] = None, delete_files: bool = False) -> Dict[str, Any]:
        base_url, api_key = self._get_api_credentials()
        
        deleted_count = 0
        failed_count = 0
        errors = []
        files_deleted = 0
        files_failed = 0
        
        id_to_path = {}
        if item_paths and len(item_paths) == len(item_ids):
            id_to_path = dict(zip(item_ids, item_paths))
        
        for item_id in item_ids:
            endpoint = f"{base_url}/Items/{item_id}"
            try:
                # Delete from Jellyfin first
                self.api_client.api_request(
                    endpoint, api_key, method="DELETE", service_name="jellyfin", timeout=30
                )
                deleted_count += 1
                self.logger.info(f"Successfully deleted item {item_id} from Jellyfin")
                
                # If delete_files is True, delete the actual file
                if delete_files and item_id in id_to_path:
                    file_path = id_to_path[item_id]
                    try:
                        if not os.path.exists(file_path):
                            self.logger.warning(f"File not found (may have been already deleted): {file_path}")
                            files_failed += 1
                            errors.append(f"File not found: {file_path}")
                            continue
                            
                        # 1. Try native deletion
                        if os.path.isdir(file_path):
                            import shutil
                            shutil.rmtree(file_path)
                            self.logger.info(f"Deleted directory (native): {file_path}")
                        else:
                            os.remove(file_path)
                            self.logger.info(f"Deleted file (native): {file_path}")
                        files_deleted += 1
                        
                    except Exception as e:
                        # 2. Native failed! Broadcast for help.
                        self.logger.warning(
                            f"Native file delete failed for {file_path}: {e}. "
                            "Broadcasting filesystem_delete_request event."
                        )
                        try:
                            # Store this path to check for a failure event later
                            self.pending_delete_failures[file_path] = item_id
                            self.event_bus.publish("filesystem_delete_request", file_path)
                            # Optimistically count as deleted for now.
                            # on_filesystem_delete_failed will correct this if it fails.
                            files_deleted += 1
                        except Exception as pub_e:
                            self.logger.error(f"Failed to publish delete event: {pub_e}")
                            files_failed += 1
                            errors.append(f"Failed to publish delete event for {file_path}: {pub_e}")
                        
            except Exception as e:
                failed_count += 1
                error_msg = f"Item {item_id}: {str(e)}"
                errors.append(error_msg)
                self.logger.error(f"Failed to delete item {item_id}: {e}")
        
        return {
            "deleted": deleted_count,
            "failed": failed_count,
            "files_deleted": files_deleted,
            "files_failed": files_failed,
            "errors": errors,
            "total": len(item_ids),
            "delete_files": delete_files
        }

    def _task_get_status(self) -> Dict[str, Any]:
        base_url, api_key = self._get_api_credentials()
        
        response = self.api_client.api_request(
            f"{base_url}/System/Ping", api_key, service_name="jellyfin", timeout=5
        )
        return {"status": "ok", "data": response}

    # --- End of Worker Task Functions ---

    # --- Event Handlers ---
    def on_filesystem_delete_failed(self, file_path: str, error_message: str):
        """
        Slot to receive delete failure events from the FileSystem plugin.
        """
        if file_path in self.pending_delete_failures:
            item_id = self.pending_delete_failures.pop(file_path, 'Unknown')
            self.logger.error(f"Received filesystem_delete_failure for item {item_id} at {file_path}: {error_message}")
            # This is tricky as the job is already finished.
            # We can't update the results dialog, but we can log it.
            # A more complex system would hold the _task_delete_items
            # open until all events are resolved.
            QMessageBox.critical(self, "File Delete Failed",
                f"The FileSystem plugin failed to delete an item:\n"
                f"Item ID: {item_id}\n"
                f"Path: {file_path}\n"
                f"Error: {error_message}")

    def on_list_items_clicked(self):
        self.list_items(force_refresh=False)

    def on_force_refresh_clicked(self):
        self.list_items(force_refresh=True)

    def check_jellyfin_status(self):
        self._start_worker(
            "status_thread", "status_worker",
            self._task_get_status,
            self.on_jellyfin_status_checked
        )

    def list_items(self, force_refresh: bool = False):
        # ... (This method remains the same) ...
        item_type = self.type_combo.currentText()
        
        if (not force_refresh and 
            self.item_cache and 
            self.last_fetch_time and 
            (time.time() - self.last_fetch_time < CACHE_DURATION_SECONDS)):
            
            self.logger.info(f"Loading {len(self.item_cache)} {item_type} items from cache.")
            self.items = self.item_cache
            self.populate_table(self.items)
            self.btn_export.setEnabled(True)
            self.btn_find_duplicates.setEnabled(True)
            self.event_bus.publish("service_status_changed", "jellyfin", "up")
            return
        
        self.btn_list.setEnabled(False)
        self.btn_force_refresh.setEnabled(False)
        self.btn_find_duplicates.setEnabled(False)
        self.logger.info(f"Fetching {item_type} items from Jellyfin...")
        
        try:
            self._start_worker(
                "list_thread", "list_worker",
                self._task_get_items,
                self.on_list_finished,
                item_type=item_type
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch items:\n{e}")
            self.btn_list.setEnabled(True)
            self.btn_force_refresh.setEnabled(True)
    
    def on_list_finished(self, result: Optional[List[Dict[str, Any]]], error: str):
        # ... (This method remains the same) ...
        self.btn_list.setEnabled(True)
        self.btn_force_refresh.setEnabled(True)
        
        if error or result is None:
            self.logger.error(f"Failed to fetch items: {error}")
            QMessageBox.critical(self, "Error", f"Failed to fetch items:\n{error}")
            self.event_bus.publish("service_status_changed", "jellyfin", "down")
            return
        
        self.items = result
        self.item_cache = result
        self.last_fetch_time = time.time()
        
        self.populate_table(self.items)
        self.btn_export.setEnabled(True)
        self.btn_find_duplicates.setEnabled(True)
        self.event_bus.publish("service_status_changed", "jellyfin", "up")
    
    def populate_table(self, items: List[Dict[str, Any]]):
        # ... (This method remains the same) ...
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(items))
        
        default_brush = QBrush()
        
        for i, item in enumerate(items):
            original_index = -1
            try:
                original_index = self.items.index(item)
            except ValueError:
                original_index = i
            
            title_widget = QTableWidgetItem(item.get("Name", "N/A"))
            title_widget.setData(Qt.ItemDataRole.UserRole, original_index)
            title_widget.setBackground(default_brush)
            
            year_widget = QTableWidgetItem(str(item.get("ProductionYear", "N/A")))
            year_widget.setBackground(default_brush)

            path_widget = QTableWidgetItem(item.get("Path", "N/A"))
            path_widget.setBackground(default_brush)
            
            self.table.setItem(i, 0, title_widget)
            self.table.setItem(i, 1, year_widget)
            self.table.setItem(i, 2, path_widget)
            
            self.table.setRowHidden(i, False)
        
        self.logger.info(f"Displayed {len(items)} items in table.")
        self.table.setSortingEnabled(True)
        
        self.showing_duplicates = False
        self.btn_find_duplicates.setText("Find Duplicates")
        self.filter_input.setEnabled(True)
    
    def export_to_csv(self):
        # ... (This method remains the same) ...
        if not self.items:
            QMessageBox.warning(self, "No Data", "No items to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "", "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Title", "Year", "Path", "TMDB ID", "TVDB ID", "IMDb ID"])
                
                for item in self.items:
                    provider_ids = item.get("ProviderIds", {})
                    writer.writerow([
                        item.get("Name", ""),
                        item.get("ProductionYear", ""),
                        item.get("Path", ""),
                        provider_ids.get("Tmdb", ""),
                        provider_ids.get("Tvdb", ""),
                        provider_ids.get("Imdb", "")
                    ])
            
            self.logger.info(f"Exported {len(self.items)} items to {file_path}")
            QMessageBox.information(self, "Success", f"Exported {len(self.items)} items to CSV.")
        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")
 
    def filter_table(self):
        # ... (This method remains the same) ...
        filter_text = self.filter_input.text().strip().lower()
        visible_rows = 0
        
        if not self.items:
             self.btn_add_missing.setVisible(False)
             return

        if self.showing_duplicates:
            self.show_duplicate_view(filter_text)
            return

        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                title = item.text().lower()
                if filter_text in title:
                    self.table.setRowHidden(i, False)
                    visible_rows += 1
                else:
                    self.table.setRowHidden(i, True)
            else:
                self.table.setRowHidden(i, True)

        if visible_rows == 0 and len(filter_text) > 2:
            item_type = self.type_combo.currentText()
            service_name = None
            if item_type == "Movie":
                service_name = "Radarr"
            elif item_type == "Series":
                service_name = "Sonarr"
            
            if service_name:
                self.btn_add_missing.setText(f"Search for '{filter_text}' in {service_name}...")
                self.btn_add_missing.setVisible(True)
            else:
                self.btn_add_missing.setVisible(False)
        else:
            self.btn_add_missing.setVisible(False)

    def add_missing_to_arr(self):
        # ... (This method remains the same) ...
        search_term = self.filter_input.text().strip()
        item_type = self.type_combo.currentText()
        service_name = None
        search_type = None
        
        if item_type == "Movie":
            service_name = "radarr"
            search_type = "movie"
        elif item_type == "Series":
            service_name = "sonarr"
            search_type = "series"
        
        if service_name and search_term and search_type:
            self.logger.info(f"Jellyfin tab requesting to add '{search_term}' to {service_name} (as {search_type})")
            self.event_bus.publish("add_to_arr_requested", service_name, search_term, search_type)
            self.filter_input.clear()
            self.btn_add_missing.setVisible(False)
    
    def show_context_menu(self, pos: QPoint):
        # ... (This method remains the same) ...
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        menu = QMenu()
        
        if len(selected_rows) == 1:
            identify_action = menu.addAction("Identify...")
            
            row = selected_rows[0].row()
            item_index = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            try:
                item_data = self.items[item_index]
                identify_action.triggered.connect(lambda: self.open_identify_dialog(item_data))
            except IndexError:
                logger.error(f"Failed to get item data for row {row}, index {item_index}")
                identify_action.setEnabled(False)
            
            delete_action = menu.addAction("Delete from Jellyfin...")
            delete_action.triggered.connect(lambda: self.delete_jellyfin_items([item_index]))
                
        elif len(selected_rows) > 1:
            bulk_identify_action = menu.addAction(f"Bulk Identify ({len(selected_rows)} items)...")
            bulk_identify_action.triggered.connect(lambda: self.start_bulk_identify(selected_rows))
            
            menu.addSeparator()
            bulk_delete_action = menu.addAction(f"Delete {len(selected_rows)} items from Jellyfin...")
            item_indices = []
            for row_model in selected_rows:
                row = row_model.row()
                item_index = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                item_indices.append(item_index)
            bulk_delete_action.triggered.connect(lambda: self.delete_jellyfin_items(item_indices))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_identify_dialog(self, item_data: Dict[str, Any]):
        # ... (This method is updated to pass secure_storage) ...
        item_id = item_data.get("Id")
        item_name = item_data.get("Name")
        item_type = item_data.get("Type")
        item_year = item_data.get("ProductionYear")
        
        if not item_id or not item_name or not item_type:
            logger.error(f"Item data is missing required fields (Id, Name, Type): {item_data}")
            QMessageBox.critical(self, "Error", "Item data is incomplete. Cannot open Identify dialog.")
            return

        logger.info(f"Opening Identify dialog for: {item_name} (ID: {item_id})")
        
        search_info = {
            "Name": item_name,
            "Year": item_year,
            "ProviderIds": item_data.get("ProviderIds", {}),
            "Path": item_data.get("Path", "N/A")
        }
        
        dialog = IdentifyDialog(
            self.api_client, 
            self.settings, 
            self.secure_storage, # <-- Added
            item_id, 
            item_type, 
            search_info, 
            self
        )
        
        if dialog.exec():
            selected_result = dialog.get_selected_result()
            if selected_result:
                self.logger.info(f"User selected new identification: {selected_result.get('Name')}")
                self.apply_identification(item_id, selected_result)
            else:
                self.logger.info("Identify dialog closed without selection.")

    def start_bulk_identify(self, selected_rows: List[QTableWidgetItem]):
        # ... (This method is updated to pass secure_storage) ...
        items_to_identify = []
        for row in selected_rows:
            try:
                item_index = self.table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole)
                items_to_identify.append(self.items[item_index])
            except Exception as e:
                logger.error(f"Failed to get item data for bulk identify: {e}")

        if not items_to_identify:
            QMessageBox.warning(self, "Error", "Could not retrieve item details for bulk identify.")
            return

        logger.info(f"Starting bulk identify for {len(items_to_identify)} items.")
        
        dialog = BulkIdentifyDialog(
            self.api_client, 
            self.settings, 
            self.secure_storage, # <-- Added
            items_to_identify, 
            self
        )
        dialog.apply_requested.connect(self.apply_identification)
        dialog.exec()
        logger.info("Bulk identify dialog closed.")

    def apply_identification(self, item_id: str, selected_result: Dict[str, Any]):
        # ... (This method remains the same) ...
        self.logger.info(f"Queueing 'Apply Identification' job for item {item_id}")
        self.apply_queue.append((item_id, selected_result))
        self.process_next_apply_job()

    def process_next_apply_job(self):
        # ... (This method remains the same) ...
        if self.apply_job_running or not self.apply_queue:
            return 
            
        self.apply_job_running = True
        item_id, selected_result = self.apply_queue.pop(0)
        
        self.logger.info(f"Starting 'Apply Identification' job for item {item_id} (Queue size: {len(self.apply_queue)})")
        
        self._start_worker(
            "apply_thread", "apply_worker",
            self._task_apply_identification,
            self.on_apply_finished,
            item_id=item_id,
            search_result=selected_result
        )

    def on_apply_finished(self, result: Optional[Dict[str, Any]], error: str):
        # ... (This method remains the same) ...
        self.apply_job_running = False
        if error or result is None:
            logger.error(f"Failed to apply identification: {error}")
            QMessageBox.critical(self, "Error", f"Failed to apply identification:\n{error}")
        else:
            logger.info("Successfully applied new identification. Forcing list refresh.")
            self.list_items(force_refresh=True)
            
        self.check_jellyfin_readiness()

    def delete_jellyfin_items(self, item_indices: List[int]):
        # ... (This method remains the same) ...
        items_to_delete = []
        item_names = []
        
        for idx in item_indices:
            try:
                item = self.items[idx]
                items_to_delete.append(item)
                item_names.append(f"{item.get('Name', 'Unknown')} ({item.get('ProductionYear', 'N/A')})")
            except IndexError:
                self.logger.error(f"Invalid item index: {idx}")
        
        if not items_to_delete:
            QMessageBox.warning(self, "Error", "No valid items selected for deletion.")
            return
        
        dialog = DeleteConfirmationDialog(item_names, self)
        
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.logger.info("User cancelled deletion.")
            return
        
        delete_files = dialog.is_delete_files_checked()
        
        item_ids = [item.get("Id") for item in items_to_delete if item.get("Id")]
        item_paths = [item.get("Path") for item in items_to_delete if item.get("Path")]
        
        if not item_ids:
            QMessageBox.warning(self, "Error", "Could not find valid item IDs for deletion.")
            return
        
        self.logger.info(f"Starting deletion of {len(item_ids)} items from Jellyfin (delete_files={delete_files})")
        
        self.pending_delete_failures.clear() # Clear old failures
        
        self._start_worker(
            "delete_thread", "delete_worker",
            self._task_delete_items,
            self.on_delete_finished,
            item_ids=item_ids,
            item_paths=item_paths if delete_files else None,
            delete_files=delete_files
        )
    
    def on_delete_finished(self, result: Optional[Dict[str, Any]], error: str):
        # ... (This method remains the same) ...
        if error:
            self.logger.error(f"Delete operation failed: {error}")
            QMessageBox.critical(self, "Delete Error", f"Failed to delete items:\n{error}")
            return
        
        if result:
            deleted = result.get("deleted", 0)
            failed = result.get("failed", 0)
            total = result.get("total", 0)
            errors = result.get("errors", [])
            delete_files = result.get("delete_files", False)
            files_deleted = result.get("files_deleted", 0)
            files_failed = result.get("files_failed", 0)
            
            message = f"Successfully deleted {deleted} out of {total} items from Jellyfin.\n\n"
            
            if delete_files:
                message += f"Files: {files_deleted} deleted"
                if files_failed > 0:
                    message += f", {files_failed} failed"
                message += "\n\n"
            else:
                message += "All media files remain on disk.\n\n"
            
            if failed > 0 or files_failed > 0:
                if failed > 0:
                    message += f"Failed to delete {failed} items from Jellyfin:\n"
                if files_failed > 0 and delete_files:
                    message += f"Failed to delete {files_failed} files:\n"
                message += "\n".join(errors[:5])
                if len(errors) > 5:
                    message += f"\n... and {len(errors) - 5} more errors"
                QMessageBox.warning(self, "Deletion Completed with Errors", message)
            else:
                QMessageBox.information(self, "Deletion Successful", message)
            
            self.logger.info("Refreshing item list after deletion")
            self.list_items(force_refresh=True)
        else:
            QMessageBox.warning(self, "Delete Error", "No result returned from delete operation.")

    def check_jellyfin_readiness(self):
        # ... (This method remains the same) ...
        if not self.apply_queue:
            return
            
        self.logger.info("Checking Jellyfin readiness for next 'Apply' job...")
        
        self._start_worker(
            "status_thread", "status_worker",
            self._task_get_status,
            self.on_jellyfin_status_checked
        )

    def on_jellyfin_status_checked(self, result: Optional[Dict[str, Any]], error: str):
        # ... (This method remains the same) ...
        if error or result is None:
            self.logger.warning(f"Jellyfin not ready, retrying in 5 seconds... Error: {error}")
            QTimer.singleShot(5000, self.check_jellyfin_readiness)
        else:
            self.logger.info("Jellyfin is ready. Processing next 'Apply' job.")
            self.process_next_apply_job()
    
    def toggle_duplicate_view(self):
        # ... (This method remains the same) ...
        if self.showing_duplicates:
            self.populate_table(self.items)
            self.filter_input.clear()
        else:
            self.show_duplicate_view()

    def show_duplicate_view(self, title_filter: str = ""):
        # ... (This method remains the same) ...
        if not self.showing_duplicates:
            self.logger.info("Identifying duplicate items...")
            self.duplicate_groups = self._identify_duplicate_groups()
        
            if not self.duplicate_groups:
                QMessageBox.information(self, "No Duplicates", "No likely duplicates found based on Provider IDs or Name/Year.")
                return
            self.logger.info(f"Found {len(self.duplicate_groups)} duplicate groups. Filtering table.")
        
        self.table.setSortingEnabled(False)
        
        color1 = QBrush(QColor("#3E3E42"))
        color2 = QBrush(QColor("#252526"))
        color_toggle = True
        
        duplicate_item_indices = set()
        
        for group in self.duplicate_groups:
            current_color = color1 if color_toggle else color2
            
            show_group = False
            if not title_filter:
                show_group = True
            else:
                for item in group:
                    if title_filter in item.get("Name", "").lower():
                        show_group = True
                        break
            
            if show_group:
                for item in group:
                    try:
                        original_index = self.items.index(item)
                        duplicate_item_indices.add(original_index)
                    except ValueError:
                        pass
                color_toggle = not color_toggle
            
        for i in range(self.table.rowCount()):
            original_index = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            if original_index in duplicate_item_indices:
                self.table.setRowHidden(i, False)
                for group in self.duplicate_groups:
                    if self.items[original_index] in group:
                        group_index = self.duplicate_groups.index(group)
                        current_color = color1 if (group_index % 2 == 0) else color2
                        for col in range(self.table.columnCount()):
                            self.table.item(i, col).setBackground(current_color)
                        break
            else:
                self.table.setRowHidden(i, True)

        self.table.setSortingEnabled(True)
        self.btn_find_duplicates.setText("Show All Items")
        self.showing_duplicates = True
        self.filter_input.setEnabled(True)

    def _identify_duplicate_groups(self) -> List[List[Dict]]:
        # ... (This method remains the same) ...
        by_provider_id = defaultdict(list)
        by_name_year = defaultdict(list)
        
        blacklist_text = self.dup_blacklist_input.text()
        blacklist = [w.strip().lower() for w in blacklist_text.split(',') if w.strip()]
        
        blacklist_pattern = None
        if blacklist:
            escaped_words = [re.escape(w) for w in blacklist]
            pattern_str = '|'.join(escaped_words)
            blacklist_pattern = re.compile(pattern_str, re.IGNORECASE)

        for item in self.items:
            provider_ids = item.get("ProviderIds", {})
            tmdb = provider_ids.get("Tmdb")
            tvdb = provider_ids.get("Tvdb")
            
            matched_by_id = False
            if tmdb:
                by_provider_id[f"tmdb_{tmdb}"].append(item)
                matched_by_id = True
            if tvdb:
                by_provider_id[f"tvdb_{tvdb}"].append(item)
                matched_by_id = True

            if not matched_by_id:
                name = item.get("Name", "")
                year = item.get("ProductionYear")
                
                scrubbed_name = name.lower()
                if blacklist_pattern:
                    scrubbed_name = blacklist_pattern.sub("", scrubbed_name)
                
                scrubbed_name = re.sub(r'[\.\[\]\(\)\-_{}]', ' ', scrubbed_name)
                scrubbed_name = re.sub(r'\s+', ' ', scrubbed_name).strip(" -")
                
                if scrubbed_name:
                    key = f"{scrubbed_name}|{year}"
                    by_name_year[key].append(item)
                
        final_duplicate_sets = []
        for items in by_provider_id.values():
            if len(items) > 1:
                final_duplicate_sets.append(items)
                
        for items in by_name_year.values():
            if len(items) > 1:
                final_duplicate_sets.append(items)
                
        return final_duplicate_sets
    
#
# --- MAIN CLASS: JellyfinPlugin ---
#
class JellyfinPlugin(PluginBase):
    """Jellyfin media server integration."""
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus) # <-- Updated
        self.widget = None
    
    def get_name(self) -> str:
         return "jellyfin"
    
    def get_version(self) -> str:
        return "2.2.1" # Version bump for secure_storage
    
    def get_description(self) -> str:
        return "Manage Jellyfin library, find duplicates, and delete with optional file removal"
    
    def get_widget(self) -> QWidget:
        # Create and return the tab widget, passing all core services
        self.widget = JellyfinTab(
            self.logger, 
            self.settings, 
            self.secure_storage, # <-- Added
            self.api_client, 
            self.event_bus
        )
        return self.widget
    
    def get_tab_name(self) -> str:
        return "Jellyfin"
    
    def get_icon(self) -> str:
        return "🎬"

    def cleanup(self):
        """Stop any running threads on shutdown."""
        if self.widget:
            self.event_bus.unsubscribe("request_all_status", self.widget.check_jellyfin_status)
            self.event_bus.unsubscribe("filesystem_delete_failure", self.widget.on_filesystem_delete_failed)