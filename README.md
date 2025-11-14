# ARR Omni-Tool 2.0 - Modular Plugin Architecture

A PyQt6-based media management dashboard for Sonarr, Radarr, Lidarr, Jellyfin, and more.

## 🎯 Project Status: Phase 1 Complete

**Phase 1: Foundation** ✅ **COMPLETE**

The core infrastructure is fully implemented and ready for plugin migration.

### What's Working:
- ✅ Complete directory structure
- ✅ Core framework (logging, settings, API client, themes)
- ✅ Plugin system (discovery, loading, lifecycle)
- ✅ Event bus for inter-plugin communication
- ✅ Settings dialog
- ✅ Main application with plugin loader
- ✅ Demo plugin proving the system works

### Next Steps (Phase 2):
- Migrate Jellyfin tab to plugin
- Migrate Sonarr/Radarr/Lidarr tabs to plugins
- Create Dashboard plugin
- Test inter-plugin communication

## 📁 Directory Structure

```
arr_omnitool/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── jarr.png                   # Application icon (optional)
│
├── core/                      # Core framework
│   ├── __init__.py
│   ├── logging_handler.py    # Custom Qt logging
│   ├── settings_manager.py   # Settings abstraction
│   ├── api_client.py         # HTTP client with retry
│   ├── plugin_base.py        # Base plugin class
│   ├── plugin_registry.py    # Plugin management
│   ├── event_bus.py          # Inter-plugin events
│   ├── themes.py             # UI themes/styles
│   ├── models.py             # Data models
│   └── utils.py              # Helper functions
│
├── plugins/                   # Service plugins
│   ├── __init__.py
│   └── plugin_demo.py        # Demo plugin
│
├── ui/                        # Shared UI components
│   ├── __init__.py
│   ├── settings_dialog.py    # Settings UI
│   ├── dialogs.py            # Common dialogs
│   └── widgets.py            # Custom widgets
│
└── tests/                     # Test suite
    └── __init__.py
```

## 🚀 Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd arr_omnitool
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
```bash
python main.py
```

## 💻 Usage

### First Run
On first run, the settings dialog will open automatically. Configure your services:
- Prowlarr (optional - for enhanced search)
- Jellyfin
- Sonarr
- Radarr
- Lidarr
- Readarr (Phase 3)
- Bazarr (Phase 3)

### Settings
Access settings via:
- Menu: File → Settings
- Keyboard: `Ctrl+,` (Cmd+, on Mac)

### Tabs
Each plugin appears as a tab in the main window. The Log tab shows all application activity.

## 🔌 Creating Plugins

Plugins must inherit from `PluginBase` and implement required methods:

```python
from PyQt6.QtWidgets import QWidget
from core.plugin_base import PluginBase

class MyPlugin(PluginBase):
    def get_name(self) -> str:
        return "My Plugin"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Description of my plugin"
    
    def get_widget(self) -> QWidget:
        # Return your UI widget
        pass
    
    def get_tab_name(self) -> str:
        return "My Tab"
    
    def get_icon(self) -> str:
        return "🔥"  # Emoji or icon
```

Save as `plugins/plugin_myname.py` and it will be auto-discovered on startup.

## 🏗️ Architecture

### Three-Layer Design

1. **Core Framework** - Essential services
   - Logging, settings, API client
   - Plugin system, event bus, themes

2. **Plugin System** - Base classes and lifecycle
   - Plugin discovery and loading
   - Inter-plugin communication
   - Event-driven architecture

3. **Service Plugins** - Individual service integrations
   - Jellyfin, Sonarr, Radarr, Lidarr
   - Readarr, Bazarr, Prowlarr (Phase 3)
   - Dashboard (Phase 2)

### Communication Patterns

Plugins can communicate via:
- **Event Bus**: Publish/subscribe pattern
- **Plugin Registry**: Direct plugin lookup
- **Settings Manager**: Shared configuration
- **Qt Signals**: UI updates

## 📊 Development Phases

### Phase 1: Foundation ✅ (Complete)
- Core infrastructure
- Plugin system
- Settings management
- Demo plugin

### Phase 2: Migration (Weeks 3-4)
- Migrate Jellyfin plugin
- Migrate ARR plugins (Sonarr, Radarr, Lidarr)
- Create Dashboard plugin
- Test integration

### Phase 3: New Services (Weeks 5-6)
- Add Readarr plugin
- Add Bazarr plugin
- Add Prowlarr plugin
- Smart search integration

### Phase 4: Enhancement (Weeks 7-8)
- Advanced filtering
- Batch operations
- Health monitoring
- Activity history

## 🧪 Testing

Run tests with pytest:
```bash
pytest tests/
```

## 📝 License

This is free and unencumbered software released into the public domain.

See [UNLICENSE](https://unlicense.org) for details.

## 🤝 Contributing

1. Follow the plugin architecture
2. Use type hints
3. Add logging for debugging
4. Test your changes
5. Update documentation

## 📖 Documentation

See [ARR_Omnitool_Architecture_Blueprint.docx](ARR_Omnitool_Architecture_Blueprint.docx) for comprehensive architectural documentation.

## 🐛 Known Issues

None in Phase 1. The foundation is stable.

## ❓ FAQ

**Q: Why refactor to plugins?**
A: Separation of concerns, maintainability, extensibility

**Q: Will my settings be preserved?**
A: Yes, settings are backward compatible

**Q: Can I disable plugins?**
A: Yes, via the `is_enabled()` method in plugins

**Q: How do I add a new service?**
A: Create a new plugin file in `plugins/`

## 📧 Contact

For questions or issues, please open a GitHub issue.
