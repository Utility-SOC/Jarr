# Plugin Templates and Migration Guide

This guide shows you exactly how to migrate the existing functionality from `arr_omnitool.py` into plugins.

## Quick Reference

| Original Code | New Plugin File | Lines to Migrate |
|--------------|-----------------|------------------|
| JellyfinTab (line 1089) | plugin_jellyfin.py | ~900 lines |
| ArrTab for Sonarr | plugin_sonarr.py | ~400 lines |
| ArrTab for Radarr | plugin_radarr.py | ~400 lines |
| ArrTab for Lidarr | plugin_lidarr.py | ~400 lines |
| (New) Readarr | plugin_readarr.py | ~400 lines |
| (New) Bazarr | plugin_bazarr.py | ~300 lines |
| (New) Prowlarr | plugin_prowlarr.py | ~300 lines |

## Pattern: How to Migrate

### Step 1: Copy the Tab Class

From `arr_omnitool.py`, find the tab class (e.g., `JellyfinTab` or `ArrTab`).

### Step 2: Wrap in Plugin Class

```python
from PyQt6.QtWidgets import QWidget
from core.plugin_base import PluginBase

class MyServicePlugin(PluginBase):
    def get_name(self) -> str:
        return "Service Name"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Description"
    
    def get_widget(self) -> QWidget:
        # Create the widget here
        widget = MyServiceTab(self.logger, self.settings, self.api_client, self.event_bus)
        return widget
    
    def get_tab_name(self) -> str:
        return "Tab Name"
    
    def get_icon(self) -> str:
        return "🎬"

# Then paste the original Tab class below
class MyServiceTab(QWidget):
    # Paste original tab code here
    pass
```

### Step 3: Update the Constructor

**OLD:**
```python
def __init__(self, logger_instance, settings, parent=None):
    super().__init__(parent)
    self.logger = logger_instance
    self.settings = settings
```

**NEW:**
```python
def __init__(self, logger, settings, api_client, event_bus, parent=None):
    super().__init__(parent)
    self.logger = logger
    self.settings = settings
    self.api_client = api_client
    self.event_bus = event_bus
```

### Step 4: Update API Calls

**OLD Pattern (using ApiWorker with task names):**
```python
self.worker = ApiWorker(self.settings, "get_jellyfin_items", item_type="Movie")
self.worker.moveToThread(self.thread)
self.thread.started.connect(self.worker.run)
```

**NEW Pattern (using ApiWorker with callables):**
```python
from core.api_client import ApiWorker

def _fetch_items():
    url = self.settings.get_plugin_setting("jellyfin", "url")
    api_key = self.settings.get_plugin_setting("jellyfin", "api_key")
    # Make API call
    return self.api_client.api_request(url + "/endpoint", api_key, "jellyfin")

self.worker = ApiWorker(_fetch_items)
self.worker.moveToThread(self.thread)
self.thread.started.connect(self.worker.run)
```

### Step 5: Update Settings Access

**OLD:**
```python
url = self.settings.value("jellyfin/url", "")
```

**NEW:**
```python
url = self.settings.get_plugin_setting("jellyfin", "url", "")
```

### Step 6: Emit Events

When something important happens, emit events:

```python
# When item is added
self.event_bus.publish("item_added", "sonarr", item_data)

# When status changes
self.event_bus.publish("service_status_changed", "jellyfin", "up")
```

## Example: Complete Jellyfin Plugin Structure

```python
"""
Jellyfin Plugin - Media library management
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from core.plugin_base import PluginBase

class JellyfinPlugin(PluginBase):
    """Jellyfin integration plugin."""
    
    def get_name(self) -> str:
        return "Jellyfin"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Manage Jellyfin media library"
    
    def get_widget(self) -> QWidget:
        widget = JellyfinTab(
            self.logger, 
            self.settings, 
            self.api_client, 
            self.event_bus
        )
        return widget
    
    def get_tab_name(self) -> str:
        return "Jellyfin"
    
    def get_icon(self) -> str:
        return "🎬"


class JellyfinTab(QWidget):
    """
    Jellyfin tab widget - paste original JellyfinTab code here
    and update as per migration guide.
    """
    def __init__(self, logger, settings, api_client, event_bus, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.settings = settings
        self.api_client = api_client
        self.event_bus = event_bus
        
        # ... rest of original JellyfinTab code ...
```

## Checklist Per Plugin

- [ ] Copy tab class from original
- [ ] Wrap in PluginBase class
- [ ] Update constructor parameters
- [ ] Update settings access (settings.value → settings.get_plugin_setting)
- [ ] Update API worker pattern
- [ ] Add event bus emissions
- [ ] Test the plugin loads
- [ ] Test all functionality works
- [ ] Add to git

## Common Issues

### Issue: Settings not found
**Solution:** Make sure you're using `get_plugin_setting("service", "key")` not `value("service/key")`

### Issue: ApiWorker doesn't work
**Solution:** New ApiWorker takes a callable function, not a task name string

### Issue: Plugin doesn't appear
**Solution:** Make sure filename starts with `plugin_` and class inherits from `PluginBase`

## Need Help?

1. Look at `plugin_demo.py` for a simple example
2. Look at `plugin_dashboard.py` for a more complex example
3. Refer to `core/plugin_base.py` for the full interface
4. Check the logs - they'll show if a plugin failed to load
