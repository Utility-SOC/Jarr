# arr_omnitool/core/plugin_registry.py
"""
Plugin discovery, loading, and management system.
"""

import os
import importlib
import inspect
import logging
from typing import List, Optional
from .plugin_base import PluginBase

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Handles discovery, loading, and management of plugins.
    Provides plugin lifecycle management and service discovery.
    """
    
    def __init__(self, *plugin_args):
        """
        Initialize registry with core services to pass to plugins.
        Args:
            *plugin_args: Arguments to pass to plugin constructors
                          (logger, settings, secure_storage, api_client, event_bus)
        """
        self.plugins: List[PluginBase] = []
        self.plugin_args = plugin_args

    def discover_plugins(self, plugin_dir: str):
        """
        Auto-discover plugins in the specified directory.
        Looks for modules named 'plugin_*.py' and loads them.
        
        Args:
            plugin_dir: Absolute file system path to the plugins directory
        """
        logger.info(f"🔍 Discovering plugins in '{plugin_dir}'...")
        
        if not os.path.exists(plugin_dir):
            logger.warning(f"Plugin directory not found: {plugin_dir}")
            try:
                os.makedirs(plugin_dir)
                logger.info(f"Created plugin directory: {plugin_dir}")
            except Exception as e:
                logger.error(f"Could not create plugin directory: {e}")
            return

        plugin_files = []
        for filename in os.listdir(plugin_dir):
            if filename.startswith("plugin_") and filename.endswith(".py"):
                plugin_files.append(filename)
        
        logger.info(f"Found {len(plugin_files)} plugin files: {plugin_files}")
        
        package_name = os.path.basename(plugin_dir)
        
        for filename in plugin_files:
            module_name = f"{package_name}.{filename[:-3]}"
            
            try:
                self._load_plugin(module_name)
            except Exception as e:
                logger.error(f"❌ Failed to load plugin {module_name}: {e}", exc_info=True)
        
        logger.info(f"✅ Loaded {len(self.plugins)} plugins successfully")

    def _load_plugin(self, module_name: str):
        """
        Loads a single plugin module and instantiates its PluginBase class.
        Args:
            module_name: Full module name (e.g., 'plugins.plugin_jellyfin')
        """
        logger.debug(f"Loading plugin module: {module_name}")
        module = importlib.import_module(module_name)
        
        plugin_classes = []
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, PluginBase) and 
                obj is not PluginBase):
                plugin_classes.append((name, obj))
        
        if not plugin_classes:
            logger.warning(f"No PluginBase subclass found in {module_name}")
            return
        
        # Instantiate each plugin class found
        for class_name, plugin_class in plugin_classes:
            try:
                plugin_instance = plugin_class(*self.plugin_args)
                self.plugins.append(plugin_instance)
                logger.info(
                    f"✅ Loaded plugin: {plugin_instance.get_name()} "
                    f"v{plugin_instance.get_version()}"
                )
            except Exception as e:
                logger.error(f"❌ Failed to instantiate {class_name}: {e}", exc_info=True)

    def get_all_plugins(self) -> List[PluginBase]:
        """
        Returns all loaded plugin instances.
        Returns:
            List of PluginBase instances
        """
        return self.plugins
        
    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """
        Find a plugin by its name (case-insensitive).
        Args:
            name: Plugin name to search for
            
        Returns:
            PluginBase instance or None if not found
        """
        name_lower = name.lower()
        for plugin in self.plugins:
            if plugin.get_name().lower() == name_lower:
                return plugin
        return None
    
    def get_enabled_plugins(self) -> List[PluginBase]:
        """
        Returns only enabled plugins.
        Returns:
            List of enabled PluginBase instances
        """
        return [p for p in self.plugins if p.is_enabled()]
    
    def cleanup_all(self):
        """
        Call cleanup() on all loaded plugins.
        Should be called before application shutdown.
        """
        logger.info("Cleaning up all plugins...")
        for plugin in self.plugins:
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin.get_name()}: {e}")