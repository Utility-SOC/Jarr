# arr_omnitool/plugins/plugin_dashboard.py
"""
Dashboard Plugin - Overview of all services
Provides service status monitoring and statistics.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGridLayout, 
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from core.plugin_base import PluginBase
from core.settings_manager import SettingsManager
from core.secure_storage import SecureStorage
from core.api_client import ApiClient
from core.event_bus import EventBus
import logging

class DashboardPlugin(PluginBase):
    """
    Dashboard showing status and statistics for all services.
    """
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        super().__init__(logger, settings, secure_storage, api_client, event_bus)
        self.widget = None
        self.service_cards = {}
        self.services_to_monitor = [
            ("jellyfin", "Jellyfin", "🎬"),
            ("sonarr", "Sonarr", "📺"),
            ("radarr", "Radarr", "🎞️"),
            ("lidarr", "Lidarr", "🎵"),
            ("readarr", "Readarr", "📚"),
            ("bazarr", "Bazarr", "💬"),
            ("prowlarr", "Prowlarr", "🔍")
        ]
        # Subscribe to status update events
        self.event_bus.subscribe("service_status_changed", self._on_status_update)

    def get_name(self) -> str:
        return "dashboard"
    
    def get_version(self) -> str:
        return "2.0.0"
    
    def get_description(self) -> str:
        return "Overview dashboard showing status of all media services"
    
    def get_widget(self) -> QWidget:
        """Create the dashboard widget."""
        self.widget = QWidget()
        layout = QVBoxLayout(self.widget)
        
        title = QLabel("<h1>📊 Media Dashboard</h1>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        grid = QGridLayout()
        self.service_cards = {}
        
        row, col = 0, 0
        for key, name, icon in self.services_to_monitor:
            card = self._create_service_card(name, icon, key)
            self.service_cards[key] = card
            grid.addWidget(card, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        layout.addLayout(grid)
        
        refresh_btn = QPushButton("Request Status Refresh")
        refresh_btn.clicked.connect(self._request_all_status)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        
        # On first load, manually update status from settings
        QTimer.singleShot(100, self._initial_status_check)
        
        return self.widget
    
    def _create_service_card(self, name: str, icon: str, key: str) -> QFrame:
        """Create a status card for a service."""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        frame.setLineWidth(2)
        
        layout = QVBoxLayout(frame)
        title = QLabel(f"<h3>{icon} {name}</h3>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        status_label = QLabel("⚪ Unknown")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setProperty("status_label", True)
        layout.addWidget(status_label)
        
        frame.status_label = status_label
        frame.service_key = key
        
        return frame

    def _initial_status_check(self):
        """Checks config status on load, before events arrive."""
        for key, card in self.service_cards.items():
            url = self.settings.get_plugin_setting(key, "url", "")
            # Check for API key in secure storage
            api_key = self.secure_storage.get_credential(f"{key}_api_key")
            
            if not url or not api_key:
                card.status_label.setText("⚫ Not Configured")
                card.status_label.setStyleSheet("color: #888;")

    def _request_all_status(self):
        """
        Broadcasts an event asking all listening plugins to check their status.
        """
        self.logger.info("Dashboard requesting status refresh from all plugins...")
        self.event_bus.publish("request_all_status")

    def _on_status_update(self, service_name: str, status: str):
        """
        Slot that receives 'service_status_changed' events.
        """
        if service_name in self.service_cards:
            card = self.service_cards[service_name]
            if status == "up":
                card.status_label.setText("🟢 Online")
                card.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            elif status == "down":
                card.status_label.setText("🔴 Offline")
                card.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            else:
                card.status_label.setText("⚪ Unknown")
                card.status_label.setStyleSheet("color: #FFF;")
            self.logger.info(f"Dashboard updated status for '{service_name}' to '{status}'")
  
    def get_tab_name(self) -> str:
        return "Dashboard"
    
    def get_icon(self) -> str:
        return "📊"
    
    def on_activate(self):
        """Request refresh when tab is shown."""
        self._request_all_status()