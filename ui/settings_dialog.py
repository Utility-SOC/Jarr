# arr_omnitool/ui/settings_dialog.py
"""
Settings dialog for configuring all service URLs and API keys.
Now uses SecureStorage (keyring) for API keys and manages volumes.
"""
import logging
from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox,
    QLabel, QCheckBox, QWidget, QVBoxLayout, QPushButton,
    QHBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem,
    QComboBox, QAbstractItemView
)
from PyQt6.QtCore import QSettings, QThread, Qt
from core.settings_manager import APP_ORGANIZATION, APP_NAME
from core.api_client import ApiClient, ApiWorker
from core.secure_storage import SecureStorage

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """
    Settings dialog for configuring all service URLs and API keys.
    """
    def __init__(self, api_client: ApiClient, secure_storage: SecureStorage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(500, 750)
        
        self.api_client = api_client
        self.secure_storage = secure_storage
        
        self.settings = QSettings(APP_ORGANIZATION, APP_NAME)
        self.test_thread = None
        self.test_worker = None
        
        layout = QFormLayout(self)
        
        # --- Prowlarr ---
        layout.addRow(QLabel("<b>Prowlarr (Optional - Enhanced Search)</b>"))
        self.prowlarr_enabled = QCheckBox("Enable Prowlarr for searches")
        self.prowlarr_enabled.setChecked(self.settings.value("prowlarr/enabled", False, type=bool))
        layout.addRow(self.prowlarr_enabled)
        
        self.prowlarr_url = QLineEdit(self.settings.value("prowlarr/url", ""))
        layout.addRow("URL:", self.prowlarr_url)
        self.prowlarr_api = self._create_api_key_input("prowlarr")
        layout.addRow("API Key:", self.prowlarr_api)
        layout.addRow(self._create_test_button("prowlarr", "v1"))

        # --- Jellyfin ---
        layout.addRow(QLabel("<b>Jellyfin</b>"))
        self.jellyfin_url = QLineEdit(self.settings.value("jellyfin/url", ""))
        layout.addRow("URL:", self.jellyfin_url)
        self.jellyfin_api = self._create_api_key_input("jellyfin")
        layout.addRow("API Key:", self.jellyfin_api)
        layout.addRow(self._create_test_button("jellyfin", "v1"))
        
        # --- Sonarr ---
        layout.addRow(QLabel("<b>Sonarr (TV Shows)</b>"))
        self.sonarr_url = QLineEdit(self.settings.value("sonarr/url", ""))
        layout.addRow("URL:", self.sonarr_url)
        self.sonarr_api = self._create_api_key_input("sonarr")
        layout.addRow("API Key:", self.sonarr_api)
        layout.addRow(self._create_test_button("sonarr", "v3"))

        # --- Radarr ---
        layout.addRow(QLabel("<b>Radarr (Movies)</b>"))
        self.radarr_url = QLineEdit(self.settings.value("radarr/url", ""))
        layout.addRow("URL:", self.radarr_url)
        self.radarr_api = self._create_api_key_input("radarr")
        layout.addRow("API Key:", self.radarr_api)
        layout.addRow(self._create_test_button("radarr", "v3"))

        # --- Lidarr ---
        layout.addRow(QLabel("<b>Lidarr (Music)</b>"))
        self.lidarr_url = QLineEdit(self.settings.value("lidarr/url", ""))
        layout.addRow("URL:", self.lidarr_url)
        self.lidarr_api = self._create_api_key_input("lidarr")
        layout.addRow("API Key:", self.lidarr_api)
        layout.addRow(self._create_test_button("lidarr", "v1"))

        # --- Readarr ---
        layout.addRow(QLabel("<b>Readarr (Books)</b>"))
        self.readarr_url = QLineEdit(self.settings.value("readarr/url", ""))
        layout.addRow("URL:", self.readarr_url)
        self.readarr_api = self._create_api_key_input("readarr")
        layout.addRow("API Key:", self.readarr_api)
        layout.addRow(self._create_test_button("readarr", "v1"))

        # --- Bazarr ---
        layout.addRow(QLabel("<b>Bazarr (Subtitles)</b>"))
        self.bazarr_url = QLineEdit(self.settings.value("bazarr/url", ""))
        layout.addRow("URL:", self.bazarr_url)
        self.bazarr_api = self._create_api_key_input("bazarr")
        layout.addRow("API Key:", self.bazarr_api)
        layout.addRow(self._create_test_button("bazarr", "v1"))
        
        # --- File System ---
        layout.addRow(QLabel("<b>File System Volumes</b>"))
        self.btn_manage_volumes = QPushButton("Manage Network Volumes...")
        self.btn_manage_volumes.clicked.connect(self.open_volume_manager)
        layout.addRow(self.btn_manage_volumes)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def _create_api_key_input(self, service_name: str) -> QLineEdit:
        """Checks keyring and returns a pre-filled line edit."""
        line_edit = QLineEdit()
        if self.secure_storage.get_credential(f"{service_name}_api_key"):
            line_edit.setPlaceholderText("[Saved in secure storage]")
        else:
            line_edit.setPlaceholderText(f"Enter {service_name.title()} API key...")
        line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        return line_edit

    def _create_test_button(self, service_name: str, api_version: str) -> QWidget:
        """Helper to create a "Test" button for a service."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(f"Test {service_name.title()}")
        button.clicked.connect(lambda: self._test_service(service_name, api_version, button))
        layout.addStretch()
        layout.addWidget(button)
        return widget

    def _test_service(self, service: str, api_version: str, button: QPushButton):
        """Runs the API test in a worker thread."""
        if self.test_thread is not None:
            QMessageBox.warning(self, "Test in Progress", "Another test is already running. Please wait.")
            return

        url_widget = getattr(self, f"{service}_url")
        api_widget = getattr(self, f"{service}_api")
        url = url_widget.text().strip().rstrip('/')
        
        api_key = api_widget.text().strip()
        if not api_key or api_key == "[Saved in secure storage]":
            api_key = self.secure_storage.get_credential(f"{service}_api_key")

        if not url or not api_key:
            QMessageBox.warning(self, "Missing Info", f"Please enter a URL and API key for {service.title()} to test.")
            return

        button.setEnabled(False)
        button.setText("Testing...")

        self.test_thread = QThread()
        self.test_worker = ApiWorker(
            self._task_test_api,
            service=service,
            api_version=api_version,
            url=url,
            api_key=api_key
        )
        self.test_worker.moveToThread(self.test_thread)
        
        self.test_worker.finished.connect(lambda result, error: self._on_test_finished(button, result, error))
        self.test_worker.finished.connect(self.test_thread.quit)
        self.test_worker.finished.connect(self.test_worker.deleteLater)
        self.test_thread.finished.connect(self.test_thread.deleteLater)
        self.test_thread.finished.connect(self._clear_test_thread)

        self.test_thread.started.connect(self.test_worker.run)
        self.test_thread.start()

    def _task_test_api(self, service: str, api_version: str, url: str, api_key: str) -> dict:
        """Worker task to test a service connection."""
        if service == 'jellyfin':
            endpoint = f"{url}/System/Info"
        elif service == 'bazarr':
            endpoint = f"{url}/api/status"
        else:
            endpoint = f"{url}/api/{api_version}/system/status"
        
        response = self.api_client.api_request(
            url=endpoint,
            api_key=api_key,
            service_name=service,
            timeout=5
        )
        
        if service == 'jellyfin':
            return {"service": service, "version": response.get("Version", "Unknown")}
        elif service == 'bazarr':
            return {"service": service, "version": response.get("bazarr_version", "Unknown")}
        else:
            return {"service": service, "version": response.get("version", "Unknown")}

    def _on_test_finished(self, button: QPushButton, result: dict, error: str):
        """Handles the result of the connection test."""
        service_name = button.text().replace("Testing...", "").replace("Test ", "").strip()
        button.setEnabled(True)
        button.setText(f"Test {service_name}")

        if error:
            logger.error(f"Test connection failed: {error}")
            QMessageBox.critical(self, "Test Failed", f"Connection failed:\n{error}")
        else:
            QMessageBox.information(self, "Test Successful",
                f"Successfully connected to {result['service'].title()}!\n"
                f"Version: {result['version']}"
            )
    
    def _clear_test_thread(self):
        """Clear thread references."""
        self.test_thread = None
        self.test_worker = None
        
    def open_volume_manager(self):
        """Opens the dialog to manage file system volumes."""
        dialog = VolumeManagerDialog(self.secure_storage, self)
        dialog.exec()

    def save_settings(self):
        """
        Save all settings to QSettings and SecureStorage.
        """
        # Save non-sensitive settings
        self.settings.setValue("prowlarr/enabled", self.prowlarr_enabled.isChecked())
        self.settings.setValue("prowlarr/url", self.prowlarr_url.text().strip())
        self.settings.setValue("jellyfin/url", self.jellyfin_url.text().strip())
        self.settings.setValue("sonarr/url", self.sonarr_url.text().strip())
        self.settings.setValue("radarr/url", self.radarr_url.text().strip())
        self.settings.setValue("lidarr/url", self.lidarr_url.text().strip())
        self.settings.setValue("readarr/url", self.readarr_url.text().strip())
        self.settings.setValue("bazarr/url", self.bazarr_url.text().strip())
        
        # Save API keys to secure storage
        self._save_api_key_if_entered("prowlarr", self.prowlarr_api)
        self._save_api_key_if_entered("jellyfin", self.jellyfin_api)
        self._save_api_key_if_entered("sonarr", self.sonarr_api)
        self._save_api_key_if_entered("radarr", self.radarr_api)
        self._save_api_key_if_entered("lidarr", self.lidarr_api)
        self._save_api_key_if_entered("readarr", self.readarr_api)
        self._save_api_key_if_entered("bazarr", self.bazarr_api)
        
        self.accept()
        
    def _save_api_key_if_entered(self, service_name: str, line_edit: QLineEdit):
        """Helper to save API key only if user entered new text."""
        api_key = line_edit.text().strip()
        if api_key and api_key != "[Saved in secure storage]":
            self.secure_storage.set_credential(f"{service_name}_api_key", api_key)


# --- Volume Manager Dialogs (New) ---

class VolumeManagerDialog(QDialog):
    """A dialog to add, edit, and remove network volumes."""
    
    def __init__(self, secure_storage: SecureStorage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Volume Manager")
        self.resize(700, 400)
        self.secure_storage = secure_storage
        self.settings = QSettings(APP_ORGANIZATION, APP_NAME)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Configure network volumes for the File System plugin."))
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Host", "Jellyfin Path Prefix", "Remote Path/Share"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add...")
        self.btn_add.clicked.connect(self.add_volume)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton("Edit...")
        self.btn_edit.clicked.connect(self.edit_volume)
        btn_layout.addWidget(self.btn_edit)
        
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self.remove_volume)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        self.load_volumes()

    def load_volumes(self):
        """Load volumes from QSettings (excluding passwords)."""
        volumes = self.settings.value("filesystem_volumes", [])
        self.table.setRowCount(len(volumes))
        for i, volume in enumerate(volumes):
            self.table.setItem(i, 0, QTableWidgetItem(volume.get("name")))
            self.table.setItem(i, 1, QTableWidgetItem(volume.get("type")))
            self.table.setItem(i, 2, QTableWidgetItem(volume.get("host")))
            self.table.setItem(i, 3, QTableWidgetItem(volume.get("path_prefix")))
            self.table.setItem(i, 4, QTableWidgetItem(volume.get("remote_path")))
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, volume)

    def add_volume(self):
        """Open dialog to add a new volume."""
        dialog = VolumeEditDialog(self)
        if dialog.exec():
            new_volume = dialog.get_volume_data()
            volumes = self.settings.value("filesystem_volumes", [])
            volumes.append(new_volume)
            self.settings.setValue("filesystem_volumes", volumes)
            self._save_password(new_volume['name'], dialog.get_password())
            self.load_volumes()

    def edit_volume(self):
        """Open dialog to edit an existing volume."""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return
        
        volume_data = self.table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        
        dialog = VolumeEditDialog(self, volume_data)
        if dialog.exec():
            updated_volume = dialog.get_volume_data()
            volumes = self.settings.value("filesystem_volumes", [])
            volumes[selected_row] = updated_volume
            self.settings.setValue("filesystem_volumes", volumes)
            self._save_password(updated_volume['name'], dialog.get_password())
            self.load_volumes()

    def remove_volume(self):
        """Remove the selected volume."""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return
            
        volume_data = self.table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole)
        volume_name = volume_data.get('name')
        
        reply = QMessageBox.question(self, "Remove Volume", 
            f"Are you sure you want to remove '{volume_name}'?")
            
        if reply == QMessageBox.StandardButton.Yes:
            volumes = self.settings.value("filesystem_volumes", [])
            volumes.pop(selected_row)
            self.settings.setValue("filesystem_volumes", volumes)
            self._delete_password(volume_name)
            self.load_volumes()

    def _get_keyring_key(self, volume_name):
        return f"volume_{volume_name}"

    def _save_password(self, volume_name, password):
        if not password: # User left it blank, don't update
            return
        if not self.secure_storage.is_available:
            QMessageBox.warning(self, "Keyring Error", "keyring library not found. Password not saved.")
            return
        try:
            self.secure_storage.set_credential(self._get_keyring_key(volume_name), password)
        except Exception as e:
            logger.error(f"Failed to store password: {e}")
            QMessageBox.critical(self, "Keyring Error", f"Failed to store password:\n{e}")

    def _delete_password(self, volume_name):
        if not self.secure_storage.is_available:
            return
        try:
            self.secure_storage.delete_credential(self._get_keyring_key(volume_name))
        except Exception as e:
            logger.error(f"Failed to delete password: {e}")


class VolumeEditDialog(QDialog):
    """Simple form to add/edit a volume's details."""
    def __init__(self, parent=None, volume_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Volume" if volume_data else "Add Volume")
        
        layout = QFormLayout(self)
        
        self.name = QLineEdit(volume_data.get("name") if volume_data else "")
        self.type = QComboBox()
        self.type.addItems(["SMB", "SCP/SFTP"])
        if volume_data:
            self.type.setCurrentText(volume_data.get("type"))
            
        self.host = QLineEdit(volume_data.get("host") if volume_data else "")
        self.port = QLineEdit(volume_data.get("port") if volume_data else "")
        self.port.setPlaceholderText("e.g. 445 (SMB) or 22 (SFTP)")
        
        self.path_prefix = QLineEdit(volume_data.get("path_prefix") if volume_data else "")
        self.path_prefix.setPlaceholderText("Path as Jellyfin sees it (e.g. /media/movies)")
        
        self.remote_path = QLineEdit(volume_data.get("remote_path") if volume_data else "")
        self.remote_path.setPlaceholderText("Remote path (e.g. /volume1/movies or 'share_name')")
        
        self.username = QLineEdit(volume_data.get("username") if volume_data else "")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Leave blank to keep unchanged" if volume_data else "")

        layout.addRow("Friendly Name (Unique):", self.name)
        layout.addRow("Type:", self.type)
        layout.addRow("Host / IP Address:", self.host)
        layout.addRow("Port (blank for default):", self.port)
        layout.addRow("Jellyfin Path Prefix:", self.path_prefix)
        layout.addRow("Remote Path / Share Name:", self.remote_path)
        layout.addRow("Username:", self.username)
        layout.addRow("Password:", self.password)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_volume_data(self) -> dict:
        return {
            "name": self.name.text(),
            "type": self.type.currentText(),
            "host": self.host.text(),
            "port": self.port.text(),
            "path_prefix": self.path_prefix.text(),
            "remote_path": self.remote_path.text(),
            "username": self.username.text()
        }
    
    def get_password(self) -> str:
        return self.password.text()