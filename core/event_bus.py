# arr_omnitool/core/event_bus.py
"""
Event bus for decoupled inter-plugin communication.
Uses Qt signals for type-safe event publishing and subscription.
"""

import logging
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EventBus(QObject):
    """
    A simple event bus for decoupled plugin communication.
    Uses named signals for different event types.
    """
    
    # Predefined event signals (from blueprint)
    item_added = pyqtSignal(str, dict)           # service_name, item_data
    item_identified = pyqtSignal(str, dict)      # item_id, identification_data
    service_status_changed = pyqtSignal(str, str) # service_name, status (up/down)
    search_completed = pyqtSignal(str, list)     # service_name, results
    refresh_requested = pyqtSignal(str)          # service_name
    settings_changed = pyqtSignal(str)           # plugin_name (or "all")
    
    # --- NEWLY ADDED EVENTS (Fixes "unknown event" warnings) ---
    add_to_arr_requested = pyqtSignal(str, str, str) # service_name, search_term, search_type
    request_all_status = pyqtSignal()                # Broadcast signal asking all plugins for status
    # --- END NEW EVENTS ---
    
    # Generic event for custom use
    custom_event = pyqtSignal(str, dict)         # event_name, data

    def __init__(self):
        super().__init__()
        logger.debug("EventBus initialized")

    def publish(self, event_name: str, *args):
        """
        Publishes an event to the corresponding signal.
        """
        if hasattr(self, event_name):
            signal = getattr(self, event_name)
            try:
                signal.emit(*args)
                logger.debug(f"📢 Event published: {event_name} with args: {args}")
            except Exception as e:
                logger.error(f"Error emitting event {event_name}: {e}")
        else:
            logger.warning(f"⚠️ Attempted to publish unknown event: {event_name}")

    def subscribe(self, event_name: str, slot: callable):
        """
        Subscribes a slot (callback function) to an event signal.
        """
        if hasattr(self, event_name):
            signal = getattr(self, event_name)
            try:
                signal.connect(slot)
                logger.debug(f"📩 Subscribed to event: {event_name}")
            except Exception as e:
                # Catch "signal already connected" errors gracefully
                if "already connected" not in str(e):
                    logger.error(f"Error subscribing to event {event_name}: {e}")
        else:
            logger.warning(f"⚠️ Attempted to subscribe to unknown event: {event_name}")
    
    def unsubscribe(self, event_name: str, slot: callable):
        """
        Unsubscribes a slot from an event signal.
        """
        if hasattr(self, event_name):
            signal = getattr(self, event_name)
            try:
                signal.disconnect(slot)
                logger.debug(f"📤 Unsubscribed from event: {event_name}")
            except Exception as e:
                logger.error(f"Error unsubscribing from event {event_name}: {e}")
        else:
            logger.warning(f"⚠️ Attempted to unsubscribe from unknown event: {event_name}")
    
    def clear(self):
        """
        Disconnects all slots from all signals.
        """
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, pyqtSignal):
                try:
                    attr.disconnect()
                except TypeError:
                    pass
        logger.debug("EventBus cleared all connections")