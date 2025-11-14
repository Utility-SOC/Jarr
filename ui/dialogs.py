# arr_omnitool/ui/dialogs.py
"""
Shared UI dialogs (Selection, Identify, Bulk Identify)
Refactored to include a blacklist panel for scrubbing search terms.
"""

import logging
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout,
    QLineEdit, QFormLayout, QDialogButtonBox, QMessageBox, QHBoxLayout,
    QLabel, QHeaderView, QTextEdit, QFileDialog, QSplitter, QWidget,
    QGridLayout
)
from PyQt6.QtCore import QSettings, QThread, QTimer, pyqtSignal, Qt
from core.api_client import ApiWorker, ApiClient
from core.settings_manager import SettingsManager
from core.utils import scrub_name, parse_csv_to_list, save_list_to_csv

logger = logging.getLogger(__name__)

# --- Selection Dialog (Updated) ---
class SelectionDialog(QDialog):
    """
    Dialog for selecting one or more items from search results.
    """
    def __init__(self, service: str, search_term: str, results: List[Dict[str, Any]], parent=None, search_type: str = "artist"):
        super().__init__(parent)
        self.setWindowTitle(f"Select Item(s) - {service.title()}")
        self.setModal(True)
        self.resize(700, 400)
        
        self.results = results
        self.selected_items = []
        self.service = service
        self.search_type = search_type
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel(f"Found {len(results)} results for '{search_term}'. Please select one or more:")
        layout.addWidget(info_label)
        
        self.table = QTableWidget()
        
        if service == "lidarr" and search_type == "album":
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Album", "Artist", "Year"])
        elif service == "lidarr" and search_type == "artist":
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Artist", "Disambiguation", "Overview"])
        else: # Sonarr/Radarr
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Title", "Year", "Overview"])
            
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemDoubleClicked.connect(self.on_double_click)
        
        # --- NEW: Enable Sorting (from Review) ---
        self.table.setSortingEnabled(True)
        # --- END NEW ---
        
        layout.addWidget(self.table)
        
        self.table.setRowCount(len(results))
        for i, item in enumerate(results):
            if service == "lidarr":
                if search_type == "album":
                    title = item.get("title", "Unknown")
                    artist = item.get("artist", {}).get("artistName", "Unknown")
                    year = str(item.get("releaseDate", "N/A"))[:4]
                    self.table.setItem(i, 0, QTableWidgetItem(title))
                    self.table.setItem(i, 1, QTableWidgetItem(artist))
                    self.table.setItem(i, 2, QTableWidgetItem(year))
                else: # artist
                    title = item.get("artistName", "Unknown")
                    year = item.get("disambiguation", "")
                    overview = item.get("overview", "")[:100] + "..."
                    self.table.setItem(i, 0, QTableWidgetItem(title))
                    self.table.setItem(i, 1, QTableWidgetItem(year))
                    self.table.setItem(i, 2, QTableWidgetItem(overview))
            else:
                title = item.get("title", "Unknown")
                year = str(item.get("year", ""))
                overview = item.get("overview", "")[:100] + "..."
                self.table.setItem(i, 0, QTableWidgetItem(title))
                self.table.setItem(i, 1, QTableWidgetItem(year))
                self.table.setItem(i, 2, QTableWidgetItem(overview))
        
        self.button_box = QDialogButtonBox()
        self.button_box.addButton("Select", QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton("Skip", QDialogButtonBox.ButtonRole.RejectRole)
        
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        
        layout.addWidget(self.button_box)
    
    def validate_and_accept(self):
        selected_rows = sorted(set(item.row() for item in self.table.selectedItems()))
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one item, or click Skip.")
            return
        
        self.selected_items = [self.results[row] for row in selected_rows]
        self.accept()
    
    def on_double_click(self, item):
        row = item.row()
        self.selected_items = [self.results[row]]
        self.accept()
    
    def get_selected_items(self) -> List[Dict[str, Any]]:
        return self.selected_items


# --- Blacklist Widget ---
class BlacklistWidget(QWidget):
    """
    A reusable widget for managing the identify blacklist.
    Supports comments (starting with #) to disable rules.
    """
    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("<b>Blacklist</b> (one entry per line, '#' to comment)"))
        
        self.blacklist_edit = QTextEdit()
        layout.addWidget(self.blacklist_edit)
        
        button_layout = QGridLayout()
        self.btn_save_settings = QPushButton("Save List")
        self.btn_save_settings.setToolTip("Save this list to settings for next time.")
        self.btn_save_settings.clicked.connect(self._save_blacklist_to_settings)
        button_layout.addWidget(self.btn_save_settings, 0, 0)

        self.btn_import_csv = QPushButton("Import CSV")
        self.btn_import_csv.setToolTip("Load a list from a CSV file (one item per row).")
        self.btn_import_csv.clicked.connect(self._load_blacklist_from_csv)
        button_layout.addWidget(self.btn_import_csv, 1, 0)
        
        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.setToolTip("Save this list to a CSV file.")
        self.btn_export_csv.clicked.connect(self._save_blacklist_to_csv)
        button_layout.addWidget(self.btn_export_csv, 1, 1)

        layout.addLayout(button_layout)
        
        self._load_blacklist_from_settings()

    def _load_blacklist_from_settings(self):
        """Load the saved list from the global settings."""
        raw_list = self.settings.get_global_setting("identify_blacklist", "")
        self.blacklist_edit.setText(raw_list)

    def _save_blacklist_to_settings(self):
        """Save the current list to global settings."""
        raw_list = self.blacklist_edit.toPlainText()
        self.settings.set_global_setting("identify_blacklist", raw_list)
        QMessageBox.information(self, "Blacklist Saved", "Your blacklist has been saved to settings.")

    def _load_blacklist_from_csv(self):
        """Load a blacklist from a CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Blacklist CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
        
        words = parse_csv_to_list(file_path)
        if words:
            # Append to existing text, ensuring no double newlines
            current_text = self.blacklist_edit.toPlainText().strip()
            new_text = "\n".join(words)
            if current_text:
                self.blacklist_edit.setText(current_text + "\n" + new_text)
            else:
                self.blacklist_edit.setText(new_text)
            QMessageBox.information(self, "Import Complete", f"Imported and appended {len(words)} words from CSV.")

    def _save_blacklist_to_csv(self):
        """Save the current blacklist to a CSV file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Blacklist CSV", "blacklist.csv", "CSV Files (*.csv)")
        if not file_path:
            return
        
        # We save ALL lines, including comments
        words = self.blacklist_edit.toPlainText().split('\n')
        
        save_list_to_csv(file_path, words)
        QMessageBox.information(self, "Export Complete", f"Exported {len(words)} lines to {file_path}.")
        
    def get_blacklist_words(self) -> list[str]:
        """
        Get the current list of *active* (non-commented) words.
        This is our "enable/disable" feature.
        """
        raw_list = self.blacklist_edit.toPlainText()
        words = raw_list.split('\n')
        
        active_words = []
        for w in words:
            w_stripped = w.strip()
            if w_stripped and not w_stripped.startswith("#"):
                active_words.append(w_stripped)
        
        return active_words


# --- Identify Dialog ---
class IdentifyDialog(QDialog):
    """
    Dialog for Jellyfin's "Identify" feature.
    Now shows the file path and has a blacklist panel.
    """
    def __init__(self, api_client: ApiClient, settings: SettingsManager, item_id: str, item_type: str, search_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Identify Item - {search_info.get('Name')}")
        self.setModal(True)
        self.resize(900, 500) # Made wider
        
        self.api_client = api_client
        self.settings = settings
        
        self.item_id = item_id
        self.item_type = item_type
        self.search_results = []
        self.selected_result = None
        
        self.api_thread = None
        self.api_worker = None
        self.is_initial_search = True # Flag for auto-scrubbing
        
        # --- Main Layout (Splitter) ---
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel (Search/Results) ---
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        
        self.path_label = QLabel(f"<b>Path:</b> {search_info.get('Path', 'N/A')}")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("font-size: 9pt; color: #aaa;")
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
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.on_ok)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        layout.addWidget(self.buttons)
        
        self.table.itemSelectionChanged.connect(
            lambda: self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        )
        
        splitter.addWidget(left_widget)
        
        # --- Right Panel (Blacklist) ---
        self.blacklist_widget = BlacklistWidget(self.settings)
        splitter.addWidget(self.blacklist_widget)
        
        splitter.setSizes([600, 300]) # Set initial sizes
        main_layout.addWidget(splitter)
        
        # Auto-search on open (will be scrubbed)
        QTimer.singleShot(100, self.start_search)

    def _task_remote_search(self, item_type: str, search_payload: Dict[str, Any]):
        """Worker task function."""
        base_url = self.settings.get_plugin_setting("jellyfin", "url")
        api_key = self.settings.get_plugin_setting("jellyfin", "api_key")
        endpoint = f"{base_url}/Items/RemoteSearch/{item_type}"
        
        return self.api_client.api_request(
            url=endpoint, 
            api_key=api_key, 
            service_name="jellyfin", 
            method="POST", 
            json_payload=search_payload
        )

    def start_search(self):
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
        if self.api_thread is not None:
            if self.api_worker: self.api_worker.stop()
            self.api_thread.quit()
            self.api_thread.wait(1000)
        event.accept()


# --- Bulk Identify Dialog (Updated) ---
class BulkIdentifyDialog(QDialog):
    """
    Dialog for Jellyfin's "Bulk Identify" feature.
    Now shows the file path and has a blacklist panel.
    """
    apply_requested = pyqtSignal(str, dict)

    def __init__(self, api_client: ApiClient, settings: SettingsManager, items_list: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Identify")
        self.setModal(True)
        self.resize(900, 600) # Made wider
        
        self.api_client = api_client
        self.settings = settings
        
        self.items_list = items_list
        self.current_item_index = -1
        self.current_item_data = None
        self.search_results = []
        
        self.api_thread = None
        self.api_worker = None
        
        # --- Main Layout (Splitter) ---
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Panel (Search/Results) ---
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)

        self.item_label = QLabel("Loading first item...")
        self.item_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(self.item_label)
        
        self.path_label = QLabel("<b>Path:</b> N/A")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("font-size: 9pt; color: #aaa;")
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
        
        # --- Right Panel (Blacklist) ---
        self.blacklist_widget = BlacklistWidget(self.settings)
        splitter.addWidget(self.blacklist_widget)

        splitter.setSizes([600, 300]) # Set initial sizes
        main_layout.addWidget(splitter)
        
        # Load the first item
        QTimer.singleShot(100, self.load_next_item)

    def load_next_item(self):
        """
        Loads the next item from the list into the UI and starts a search.
        """
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

        self.item_label.setText(item_name) # Show original name in label
        self.path_label.setText(f"<b>Path:</b> {item_path}")
        self.item_count_label.setText(f"Item {self.current_item_index + 1} of {len(self.items_list)}")
        self.name_input.setText(scrubbed_name) # Search with scrubbed name
        self.year_input.setText(item_year)
        self.btn_apply_next.setEnabled(False)
        
        self.start_search(is_auto_search=True)

    def _task_remote_search(self, item_type: str, search_payload: Dict[str, Any]):
        """Worker task function."""
        base_url = self.settings.get_plugin_setting("jellyfin", "url")
        api_key = self.settings.get_plugin_setting("jellyfin", "api_key")
        endpoint = f"{base_url}/Items/RemoteSearch/{item_type}"
        
        return self.api_client.api_request(
            url=endpoint, 
            api_key=api_key, 
            service_name="jellyfin", 
            method="POST", 
            json_payload=search_payload
        )

    def start_search(self, is_auto_search=False):
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
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            # This can be triggered by a double-click on an empty table
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
        if self.api_thread is not None:
            if self.api_worker: self.api_worker.stop()
            self.api_thread.quit()
            # --- THIS IS THE FIX ---
            self.api_thread.wait(1000) # Changed 1Player to 1000
            # --- END FIX ---
        event.accept()