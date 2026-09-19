#!/usr/bin/env python3
"""Base classes and utilities for AlarmPI notification plugins."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger('alarmpi')


class NotifierField:
    """Specification for a single configurable field in a notifier plugin."""

    def __init__(
        self,
        name: str,
        label: str,
        field_type: str = "string",
        default: Any = "",
        placeholder: str = "",
        help_text: str = "",
        options: Optional[List[Any]] = None,
        readonly: bool = False,
    ):
        self.name = name
        self.label = label
        self.field_type = field_type  # 'boolean', 'string', 'password', 'number', 'list', 'select', 'pin'
        self.default = default
        self.placeholder = placeholder
        self.help_text = help_text
        self.options = options or []
        self.readonly = readonly

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.field_type,
            "default": self.default,
            "placeholder": self.placeholder,
            "help": self.help_text,
            "options": self.options,
            "readonly": self.readonly,
        }


class BaseNotifier:
    """Abstract base class for all notification plugins."""

    name: str = "base"
    display_name: str = "Base Notifier"
    description: str = ""
    icon: str = "bell"  # Icon hint for the modern UI

    def __init__(self, wd: str, callbacks: Optional[Dict[str, Any]] = None, opts_ui: Optional[Dict[str, Any]] = None, logs: Any = None):
        self.wd = wd
        self.callbacks = callbacks or {}
        self.opts_ui = opts_ui or {}
        self.mylogs = logs
        self.settings: Dict[str, Any] = {}

    @classmethod
    def get_schema(cls) -> List[Dict[str, Any]]:
        """Return the list of field definitions for this plugin."""
        fields = cls.define_fields()
        return [f.to_dict() if isinstance(f, NotifierField) else f for f in fields]

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        """Override this method to define the fields for the plugin."""
        return []

    @classmethod
    def get_default_settings(cls) -> Dict[str, Any]:
        """Generate default configuration dictionary from schema."""
        defaults = {"enable": False}
        for f in cls.define_fields():
            if isinstance(f, NotifierField):
                defaults[f.name] = f.default
            elif isinstance(f, dict):
                defaults[f.get("name", "")] = f.get("default", "")
        return defaults

    def is_enabled(self) -> bool:
        """Check if plugin is currently enabled in settings."""
        plugin_settings = self.settings.get(self.name, {})
        return bool(plugin_settings.get("enable", False))

    def setup(self, settings: Dict[str, Any]) -> None:
        """Initialize or reconfigure the plugin with current settings."""
        self.settings = settings

    def get_status(self) -> Any:
        """Return connection/health status (True, False, or detail dict)."""
        return self.is_enabled()

    def on_intruder_alert(self, alert_info: Optional[Dict[str, Any]] = None) -> None:
        """Hook called when an intruder is detected."""
        pass

    def on_alarm_state_change(self, new_state: str) -> None:
        """Hook called when the overall alarm state changes (armed, disarmed, triggered, pending)."""
        pass

    def on_sensor_update(self, sensor_uuid: str, sensor_data: Dict[str, Any], state: str) -> None:
        """Hook called when any sensor changes state (on, off, error)."""
        pass

    def start_siren(self) -> None:
        """Hook called to trigger siren action."""
        pass

    def stop_siren(self) -> None:
        """Hook called to silence siren action."""
        pass

    def cleanup(self) -> None:
        """Hook called on application reload or shutdown."""
        pass
