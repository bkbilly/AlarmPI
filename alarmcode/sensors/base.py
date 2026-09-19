#!/usr/bin/env python3
"""Base classes and utilities for AlarmPI sensor plugins."""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger('alarmpi')


class SensorField:
    """Specification for a sensor configuration field."""

    def __init__(
        self,
        name: str,
        label: str,
        field_type: str = "string",  # 'string', 'password', 'number', 'boolean', 'pin', 'select'
        default: Any = "",
        placeholder: str = "",
        help_text: str = "",
        options: Optional[List[Any]] = None,
        required: bool = False,
    ):
        self.name = name
        self.label = label
        self.field_type = field_type
        self.default = default
        self.placeholder = placeholder
        self.help_text = help_text
        self.options = options or []
        self.required = required

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.field_type,
            "default": self.default,
            "placeholder": self.placeholder,
            "help": self.help_text,
            "options": self.options,
            "required": self.required,
        }


class BaseSensorPlugin:
    """Abstract base class for all sensor types."""

    sensor_type: str = "Generic"
    display_name: str = "Generic Sensor"
    description: str = ""
    icon: str = "radio"

    def __init__(self, sensor_id: str, wd: str = ""):
        self.sensor_id = sensor_id
        self.wd = wd
        self.online: Optional[bool] = True
        self.alert: Optional[bool] = False
        self.sensor_data: Dict[str, Any] = {}

        self._event_alert: List[Callable[[str], None]] = []
        self._event_alert_stop: List[Callable[[str], None]] = []
        self._event_error: List[Callable[[str], None]] = []
        self._event_error_stop: List[Callable[[str], None]] = []

    @classmethod
    def define_fields(cls) -> List[SensorField]:
        """Define the fields specific to this sensor type."""
        return []

    @classmethod
    def get_schema(cls) -> List[Dict[str, Any]]:
        return [f.to_dict() if isinstance(f, SensorField) else f for f in cls.define_fields()]

    def on_alert(self, callback: Callable[[str], None]) -> None:
        self._event_alert.append(callback)

    def on_alert_stop(self, callback: Callable[[str], None]) -> None:
        self._event_alert_stop.append(callback)

    def on_error(self, callback: Callable[[str], None]) -> None:
        self._event_error.append(callback)

    def on_error_stop(self, callback: Callable[[str], None]) -> None:
        self._event_error_stop.append(callback)

    def _notify_alert(self, sensor_id: Optional[str] = None) -> None:
        self.alert = True
        sid = sensor_id or self.sensor_id
        for callback in self._event_alert:
            try:
                callback(sid)
            except Exception:
                logger.exception("Error in sensor on_alert callback")

    def _notify_alert_stop(self, sensor_id: Optional[str] = None) -> None:
        self.alert = False
        sid = sensor_id or self.sensor_id
        for callback in self._event_alert_stop:
            try:
                callback(sid)
            except Exception:
                logger.exception("Error in sensor on_alert_stop callback")

    def _notify_error(self, sensor_id: Optional[str] = None) -> None:
        self.online = False
        sid = sensor_id or self.sensor_id
        for callback in self._event_error:
            try:
                callback(sid)
            except Exception:
                logger.exception("Error in sensor on_error callback")

    def _notify_error_stop(self, sensor_id: Optional[str] = None) -> None:
        self.online = True
        sid = sensor_id or self.sensor_id
        for callback in self._event_error_stop:
            try:
                callback(sid)
            except Exception:
                logger.exception("Error in sensor on_error_stop callback")

    def add_sensor(self, sensor_data: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.sensor_data = sensor_data
        self.reload(global_settings)

    def del_sensor(self) -> None:
        pass

    def reload(self, global_settings: Optional[Dict[str, Any]] = None) -> None:
        pass

    def setAlertStatus(self, alertstate: Optional[bool] = None) -> None:
        self.alert = alertstate
