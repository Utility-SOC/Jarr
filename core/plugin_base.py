"""
Abstract base class for all plugins.
Defines the plugin interface and lifecycle.
"""

import logging
from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QWidget
from .settings_manager import SettingsManager
from .secure_storage import SecureStorage
from .api_client import ApiClient
from .event_bus import EventBus


class PluginBase(ABC):
    """
    Abstract base class that all plugins must inherit from.
    Defines the standard interface for plugins in the system.
    """
    
    def __init__(self, logger: logging.Logger, settings: SettingsManager, secure_storage: SecureStorage, api_client: ApiClient, event_bus: EventBus):
        """
        Initialize plugin with core services.
        
        Args:
            logger: Application logger
            settings: SettingsManager instance
            secure_storage: SecureStorage instance for credentials
            api_client: ApiClient instance
            event_bus: EventBus instance for inter-plugin communication
        """
        self.logger = logger
        self.settings = settings
        self.secure_storage = secure_storage
        self.api_client = api_client
        self.event_bus = event_bus

    # --- Required Methods ---
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Return the display name of the plugin.
        
        Returns:
            Plugin name (e.g., "Jellyfin Manager")
        """
        pass

    @abstractmethod
    def get_version(self) -> str:
        """
        Return the plugin's version string.
        
        Returns:
            Version string (e.g., "1.0.0")
        """
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """
        Return a brief description of the plugin.
        
        Returns:
            Description text
        """
        pass

    @abstractmethod
    def get_widget(self) -> QWidget:
        """
        Return the main QWidget for this plugin's tab.
        This widget will be added to the main tab widget.
        
        Returns:
            QWidget instance
        """
        pass
    
    @abstractmethod
    def get_tab_name(self) -> str:
        """
        Return the text to be displayed on the tab.
        
        Returns:
            Tab label (e.g., "Jellyfin")
        """
        pass
    
    # --- Optional Methods ---
    
    def get_icon(self) -> str:
        """
        Return an emoji or icon identifier for the tab.
        
        Returns:
            Icon string (emoji or icon name)
        """
        return ""

    def is_enabled(self) -> bool:
        """
        Return True if the plugin is enabled in settings.
        Disabled plugins won't be shown in the UI.
        
        Returns:
            True if enabled, False otherwise
        """
        return True

    def get_settings_widget(self) -> QWidget:
        """
        Return a QWidget for the settings dialog (optional).
        If None, plugin has no user-configurable settings.
        
        Returns:
            Settings widget or None
        """
        return None
    
    def get_dependencies(self) -> list[str]:
        """
        Return list of plugin names this plugin depends on.
        
        Returns:
            List of plugin names (e.g., ['jellyfin'])
        """
        return []

    # --- Lifecycle Hooks ---
    
    def on_activate(self):
        """
        Called when the plugin's tab is shown/activated.
        Use this to refresh data or start polling.
        """
        pass

    def on_deactivate(self):
        """
        Called when the plugin's tab is hidden/deactivated.
        Use this to pause polling or cleanup temporary resources.
        """
        pass

    def cleanup(self):
        """
        Called just before the plugin is unloaded.
        Use this to close connections, cancel threads, etc.
        """
        pass
    
    # --- Helper Methods ---
    
    def get_setting(self, key: str, default=None):
        """
        Convenience method to get a plugin-namespaced setting.
        
        Args:
            key: Setting key
            default: Default value
            
        Returns:
            Setting value
        """
        plugin_name = self.get_name().lower().replace(" ", "_")
        return self.settings.get_plugin_setting(plugin_name, key, default)
    
    def set_setting(self, key: str, value):
        """
        Convenience method to set a plugin-namespaced setting.
        
        Args:
            key: Setting key
            value: Value to store
        """
        plugin_name = self.get_name().lower().replace(" ", "_")
        self.settings.set_plugin_setting(plugin_name, key, value)