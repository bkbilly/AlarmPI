#!/usr/bin/env python3
"""Modular Sensor System for AlarmPI.

Dynamically discovers and loads all sensor plugins placed inside this directory.
"""

import importlib
import inspect
import logging
import os
import pkgutil
from typing import Any, Callable, Dict, List, Optional, Type

from alarmcode.colors import bcolors
from alarmcode.sensors.base import BaseSensorPlugin

logger = logging.getLogger('alarmpi')


def discover_sensor_plugins() -> Dict[str, Type[BaseSensorPlugin]]:
    """Scan the sensors directory and return a dict of {sensor_type_name: sensor_class}."""
    plugins: Dict[str, Type[BaseSensorPlugin]] = {}
    package_dir = os.path.dirname(__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name in ("base", "__init__"):
            continue
        try:
            mod = importlib.import_module(f"alarmcode.sensors.{module_name}")
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, BaseSensorPlugin) and obj is not BaseSensorPlugin:
                    plugins[obj.sensor_type] = obj
        except Exception:
            logger.exception("Failed to load sensor plugin '%s':", module_name)

    return plugins


def get_available_sensor_types() -> List[Dict[str, Any]]:
    """Return schemas and metadata for all available sensor types for the frontend."""
    discovered = discover_sensor_plugins()
    types_list = []
    for s_type, s_cls in sorted(discovered.items(), key=lambda x: x[1].display_name):
        types_list.append({
            "type": s_type,
            "name": s_cls.display_name,
            "description": s_cls.description,
            "icon": s_cls.icon,
            "fields": s_cls.get_schema(),
        })
    return types_list


class Sensor:
    """Manages all active sensors, delegating each to its corresponding plugin."""

    def __init__(self, wd: str = ""):
        self.wd = wd
        self.all_sensors: Dict[str, Dict[str, Any]] = {}
        self.settings: Dict[str, Any] = {}
        self.plugins_registry = discover_sensor_plugins()

        self._event_alert: List[Callable[[str], None]] = []
        self._event_alert_stop: List[Callable[[str], None]] = []
        self._event_error: List[Callable[[str], None]] = []
        self._event_error_stop: List[Callable[[str], None]] = []

    def on_alert(self, callback: Callable[[str], None]) -> None:
        self._event_alert.append(callback)

    def on_alert_stop(self, callback: Callable[[str], None]) -> None:
        self._event_alert_stop.append(callback)

    def on_error(self, callback: Callable[[str], None]) -> None:
        self._event_error.append(callback)

    def on_error_stop(self, callback: Callable[[str], None]) -> None:
        self._event_error_stop.append(callback)

    def _notify_alert(self, sensor_id: str) -> None:
        for cb in self._event_alert:
            try:
                cb(sensor_id)
            except Exception:
                logger.exception("Error in sensor _notify_alert callback")

    def _notify_alert_stop(self, sensor_id: str) -> None:
        for cb in self._event_alert_stop:
            try:
                cb(sensor_id)
            except Exception:
                logger.exception("Error in sensor _notify_alert_stop callback")

    def _notify_error(self, sensor_id: str) -> None:
        for cb in self._event_error:
            try:
                cb(sensor_id)
            except Exception:
                logger.exception("Error in sensor _notify_error callback")

    def _notify_error_stop(self, sensor_id: str) -> None:
        for cb in self._event_error_stop:
            try:
                cb(sensor_id)
            except Exception:
                logger.exception("Error in sensor _notify_error_stop callback")

    def add_sensors(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        sensors_dict = settings.get("sensors", {})

        for sensor_id, sensor_values in sensors_dict.items():
            if sensor_id not in self.all_sensors:
                sensor_type = sensor_values.get("type", "Generic")
                sensor_name = sensor_values.get("name", sensor_id)

                logger.info("Initializing %s%s sensor '%s' (ID: %s)%s",
                            bcolors.OKBLUE, sensor_type, sensor_name, sensor_id, bcolors.ENDC)

                plugin_cls = self.plugins_registry.get(sensor_type, BaseSensorPlugin)
                try:
                    sensor_obj = plugin_cls(sensor_id, wd=self.wd)
                except Exception:
                    logger.exception("Failed to initialize sensor plugin for %s (%s)", sensor_name, sensor_type)
                    sensor_obj = BaseSensorPlugin(sensor_id, wd=self.wd)

                self.all_sensors[sensor_id] = {
                    "values": sensor_values,
                    "obj": sensor_obj,
                    "settings": settings.get("mqtt") if sensor_type == "MQTT" else None
                }

                sensor_obj.on_alert(self._notify_alert)
                sensor_obj.on_alert_stop(self._notify_alert_stop)
                sensor_obj.on_error(self._notify_error)
                sensor_obj.on_error_stop(self._notify_error_stop)

                sensor_obj.add_sensor(
                    self.all_sensors[sensor_id]["values"],
                    self.all_sensors[sensor_id]["settings"]
                )

    def del_sensor(self, sensor_id: str) -> None:
        if sensor_id in self.all_sensors:
            try:
                self.all_sensors[sensor_id]["obj"].del_sensor()
            except Exception:
                pass
            del self.all_sensors[sensor_id]

    def reload(self, sensor_type: Optional[str] = None, settings: Optional[Dict[str, Any]] = None) -> None:
        for sensor_id, s_info in self.all_sensors.items():
            if sensor_type is None or sensor_type == s_info["values"].get("type"):
                s_info["obj"].reload(settings or self.settings)

    def get_all_sensors(self) -> Dict[str, Any]:
        return self.all_sensors
