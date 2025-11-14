# arr_omnitool/main.py
#!/usr/bin/env python3
"""
ARR Omni-Tool 2.0 - Modular Plugin Architecture
Main application entry point that auto-discovers and loads plugins.
This is free and unencumbered software released into the public domain.
"""

import sys
import os
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QTextEdit, QDialog
)
from PyQt6.QtCore import QTimer, QByteArray
from PyQt6.QtGui import QIcon, QKeySequence, QAction

# Import core components
from core import (
    setup_logging,
    SettingsManager,
    SecureStorage,
    ApiClient,
    PluginRegistry,
    EventBus,
    apply_theme,
    Theme
)
from core.settings_manager import APP_NAME, APP_ORGANIZATION
from core.utils import parse_csv_to_list # For blacklist import
from ui import SettingsDialog

# --- Robust Pathing ---
if getattr(sys, 'frozen', False):
    APP_ROOT = sys._MEIPASS
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))


class MainWindow(QMainWindow):
    """
    The main application window, dynamically populated with plugins.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARR Omni-Tool 2.0 (Modular)")
        
        # 1. Initialize Core Services
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        
        self.logger = setup_logging(self.log_widget.append)
        self.settings = SettingsManager()
        self.secure_storage = SecureStorage()
        self.api_client = ApiClient()
        self.event_bus = EventBus()
        
        geom = self.settings.get_global_setting("main_window_geometry", b'')
        
        if isinstance(geom, QByteArray): # QSettings may return QByteArray
             self.restoreGeometry(geom)
        elif isinstance(geom, bytes): # Or it may return raw bytes
             self.restoreGeometry(QByteArray(geom))
        else:
            self.setGeometry(100, 100, 1000, 700) # Default
        
        self._set_app_icon()
        
        self.logger.info(f"🚀 Starting {APP_NAME} 2.0...")
        
        # 2. Setup Core UI
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)
        self._create_menus()
        
        # 3. Load Plugins
        self.logger.info("Loading plugins...")
        self.registry = PluginRegistry(
            self.logger, 
            self.settings, 
            self.secure_storage, 
            self.api_client, 
            self.event_bus
        )
        
        plugins_path = os.path.join(APP_ROOT, "plugins")
        self.logger.info(f"Discovering plugins in: {plugins_path}")
        self.registry.discover_plugins(plugins_path)
        
        # 4. Populate UI from Plugins
        self._load_plugin_tabs()
        
        # Add core Log tab at the end
        self.tabs.addTab(self.log_widget, "📋 Log")
        
        self._setup_keyboard_shortcuts()
        
        # 5. Apply Theme
        apply_theme(QApplication.instance(), Theme.DARK)
        self.logger.info("✅ Dark theme applied")

        # 6. Check for first run
        self._check_first_run()

    def _create_menus(self):
        """Create application menu bar."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _load_plugin_tabs(self):
        """
        Get all loaded plugins and add their widgets as tabs.
        """
        plugins = self.registry.get_enabled_plugins()
        
        if not plugins:
            self.logger.warning("⚠️  No plugins loaded. Application will have limited functionality.")
            return
        
        plugins.sort(key=lambda p: (p.get_tab_name() != "Dashboard", p.get_tab_name()))
        
        for plugin in plugins:
            try:
                widget = plugin.get_widget()
                if widget:
                    icon_str = plugin.get_icon()
                    tab_name = f"{icon_str} {plugin.get_tab_name()}" if icon_str else plugin.get_tab_name()
                    tab_index = self.tabs.addTab(widget, tab_name)
                    self.logger.info(f"✅ Added tab for plugin: {plugin.get_name()}")
                else:
                    self.logger.error(f"❌ Plugin {plugin.get_name()} returned None widget")
            except Exception as e:
                self.logger.error(f"❌ Failed to load widget for {plugin.get_name()}: {e}", exc_info=True)

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for tab navigation (from Review)."""
        log_tab_index = self.tabs.count() - 1
        for i in range(self.tabs.count()):
            key = None
            if i == log_tab_index:
                key = "Ctrl+L" # Special key for Log
            elif i < 9: # 1-9
                key = f"Ctrl+{i+1}"
            
            if key:
                shortcut = QAction(self)
                shortcut.setShortcut(QKeySequence(key))
                # Use lambda to capture the tab index 'i'
                shortcut.triggered.connect(lambda checked=False, index=i: self.tabs.setCurrentIndex(index))
                self.addAction(shortcut)
        
        # Also map Ctrl+9 to the Log tab if there are fewer than 9 tabs
        if log_tab_index < 9:
             shortcut = QAction(self)
             shortcut.setShortcut(QKeySequence("Ctrl+9"))
             shortcut.triggered.connect(lambda: self.tabs.setCurrentIndex(log_tab_index))
             self.addAction(shortcut)

    def _on_tab_changed(self, index: int):
        """
        Handle tab changes to activate/deactivate plugins.
        """
        widget = self.tabs.widget(index)
        if not widget:
            return
        
        for plugin in self.registry.get_all_plugins():
            try:
                if plugin.get_widget() == widget:
                    plugin.on_activate()
                    break
            except:
                pass

    def open_settings(self):
        """
        Open the settings dialog.
        """
        dialog = SettingsDialog(self.api_client, self.secure_storage, self)
        if dialog.exec():
            self.logger.info("✅ Settings saved successfully")
            self.event_bus.publish("settings_changed", "all")
        else:
            self.logger.info("Settings dialog cancelled")

    def _check_first_run(self):
        """
        Check for first run:
        1. Open settings if no keys exist.
        2. Auto-load blacklist.csv if it exists and blacklist is empty.
        """
        if not self.settings.has_any_settings():
            self.logger.warning("⚠️  No settings found. Opening settings dialog for first run...")
            QTimer.singleShot(100, self.open_settings)
        
        blacklist_key = "identify_blacklist"
        if not self.settings.get_global_setting(blacklist_key, ""):
            blacklist_path = os.path.join(APP_ROOT, "blacklist.csv")
            if os.path.exists(blacklist_path):
                self.logger.info(f"Found 'blacklist.csv', loading to settings...")
                words = parse_csv_to_list(blacklist_path)
                if words:
                    self.settings.set_global_setting(blacklist_key, "\n".join(words))
                    self.logger.info(f"Successfully loaded {len(words)} items from 'blacklist.csv' into settings.")

    def _set_app_icon(self):
        """
        Find and set the application icon (jarr.png).
        """
        icon_path = os.path.join(APP_ROOT, "jarr.png")
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            self.logger.debug(f"Icon loaded from: {icon_path}")

    def closeEvent(self, event):
        """
        Handle application close event.
        """
        self.logger.info("Application shutting down...")
        
        self.settings.set_global_setting("main_window_geometry", self.saveGeometry())
        
        self.registry.cleanup_all()
        self.api_client.close()
        event.accept()


def main():
    """
    Application entry point.
    """
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()