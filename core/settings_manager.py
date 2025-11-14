# arr_omnitool/core/settings_manager.py
"""
Centralized settings management with per-plugin namespaces.
Based on QSettings from arr_omnitool.py (line 2152)
"""

from PyQt6.QtCore import QSettings
from typing import Any

# Application constants
APP_NAME = "ARROmniTool"
APP_ORGANIZATION = "volunteer"


class SettingsManager:
    """
    Centralized settings management with per-plugin namespaces
    and type-safe access.
    """
    def __init__(self):
        self.qsettings = QSettings(APP_ORGANIZATION, APP_NAME)

    def get_plugin_setting(self, plugin_name: str, key: str, default: Any = None) -> Any:
        """
        Gets a namespaced setting for a plugin.
        Type is inferred from the default value.
        """
        # --- THIS IS THE FIX ---
        # Removed the 'type=setting_type' argument.
        # QSettings will now infer the type from the 'default' value.
        value = self.qsettings.value(f"{plugin_name}/{key}", default)
        # --- END FIX ---

        # Handle case where QSettings returns string for bool
        if isinstance(default, bool) and isinstance(value, str):
            return value.lower() == 'true'
            
        return value

    def set_plugin_setting(self, plugin_name: str, key: str, value: Any):
        """
        Sets a namespaced setting for a plugin.
        """
        self.qsettings.setValue(f"{plugin_name}/{key}", value)

    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """
        Gets a global (application-level) setting.
        Type is inferred from the default value.
        """
        # --- THIS IS THE FIX ---
        # Removed the 'type=setting_type' argument.
        value = self.qsettings.value(key, default)
        # --- END FIX ---
        
        # Handle case where QSettings returns string for bool
        if isinstance(default, bool) and isinstance(value, str):
            return value.lower() == 'true'
            
        return value

    def set_global_setting(self, key: str, value: Any):
        """
        Sets a global (application-level) setting.
        """
        self.qsettings.setValue(key, value)
        
    def get_qsettings(self) -> QSettings:
        """
        Provides direct access to the underlying QSettings object.
        """
        return self.qsettings
    
    def has_any_settings(self) -> bool:
        """
        Check if any settings have been saved (for first-run detection).
        """
        return bool(self.qsettings.allKeys())
    
    def clear_plugin_settings(self, plugin_name: str):
        """
        Clear all settings for a specific plugin.
        """
        self.qsettings.beginGroup(plugin_name)
        self.qsettings.remove("")  # Remove all keys in this group
        self.qsettings.endGroup()