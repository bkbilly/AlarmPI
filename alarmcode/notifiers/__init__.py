#!/usr/bin/env python3
"""Modular Notification System for AlarmPI.

Dynamically discovers and loads all notification plugins placed inside this directory.
"""

import importlib
import inspect
import logging
import os
import pkgutil
import threading
from typing import Any, Dict, List, Optional, Type

from alarmcode.notifiers.base import BaseNotifier

logger = logging.getLogger('alarmpi')


def discover_notifier_plugins() -> Dict[str, Type[BaseNotifier]]:
    """Scan the notifiers directory and return a dict of {plugin_name: plugin_class}."""
    plugins: Dict[str, Type[BaseNotifier]] = {}
    package_dir = os.path.dirname(__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name in ("base", "__init__"):
            continue
        try:
            mod = importlib.import_module(f"alarmcode.notifiers.{module_name}")
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, BaseNotifier) and obj is not BaseNotifier:
                    plugins[obj.name] = obj
        except Exception:
            logger.exception("Failed to load notifier plugin '%s':", module_name)

    return plugins


class NotifierManager:
    """Manages all registered notification plugins, schema reconciliation, and event dispatch."""

    def __init__(self, wd: str, settings: Dict[str, Any], opts_ui: Optional[Dict[str, Any]] = None, logs: Any = None):
        self.wd = wd
        self.settings = settings
        self.opts_ui = opts_ui or {}
        self.mylogs = logs
        self.callbacks: Dict[str, Any] = {
            "deactivateAlarm": lambda *args: None,
            "activateAlarm": lambda *args: None,
            "sensorAlert": lambda *args: None,
            "sensorStopAlert": lambda *args: None,
            "sirenStart": self.startSiren,
            "sirenStop": self.stopSiren,
        }
        self.plugins: Dict[str, BaseNotifier] = {}
        self._load_plugins()

    def _load_plugins(self) -> None:
        discovered = discover_notifier_plugins()
        for name, cls in discovered.items():
            try:
                plugin_instance = cls(
                    wd=self.wd,
                    callbacks=self.callbacks,
                    opts_ui=self.opts_ui,
                    logs=self.mylogs
                )
                plugin_instance.setup(self.settings)
                self.plugins[name] = plugin_instance
                # Legacy attribute aliases for backward compatibility
                if name == "serene":
                    self.gpio = plugin_instance
                elif name == "mqtt":
                    self.mqtt = plugin_instance
                elif name == "mail":
                    self.email = plugin_instance
                elif name == "voip":
                    self.voip = plugin_instance
                elif name == "http":
                    self.http = plugin_instance
                logger.debug("Initialized notifier plugin: %s (%s)", name, cls.display_name)
            except Exception:
                logger.exception("Error initializing notifier plugin '%s':", name)

    @classmethod
    def get_registered_schemas(cls) -> List[Dict[str, Any]]:
        """Return schema metadata for all discovered plugins."""
        discovered = discover_notifier_plugins()
        schemas = []
        for name, p_cls in sorted(discovered.items(), key=lambda item: item[1].display_name):
            schemas.append({
                "id": name,
                "title": p_cls.display_name,
                "description": p_cls.description,
                "icon": p_cls.icon,
                "has_enable": True,
                "fields": p_cls.get_schema(),
            })
        return schemas

    @classmethod
    def get_all_defaults(cls) -> Dict[str, Any]:
        """Return default settings dictionaries for all discovered plugins."""
        discovered = discover_notifier_plugins()
        return {name: p_cls.get_default_settings() for name, p_cls in discovered.items()}

    def setup_all(self, settings: Dict[str, Any]) -> None:
        """Update settings and reload all plugins."""
        self.settings = settings
        for plugin in self.plugins.values():
            try:
                plugin.setup(settings)
            except Exception:
                logger.exception("Error setting up plugin '%s':", plugin.name)

    def settings_update(self, settings: Dict[str, Any]) -> None:
        self.setup_all(settings)

    def updateMQTT(self) -> None:
        if "mqtt" in self.plugins:
            self.plugins["mqtt"].setup(self.settings)

    def updateUI(self, event: str, data: Any) -> None:
        if self.opts_ui and "obj" in self.opts_ui:
            self.opts_ui["obj"](event, data, room=self.opts_ui.get("room"))

    def status(self) -> Dict[str, Any]:
        """Return status dict for all plugins."""
        res = {}
        for name, plugin in self.plugins.items():
            try:
                res[name] = plugin.get_status()
            except Exception:
                res[name] = False
        # Aliases for legacy UI compatibility
        if "serene" in res and "gpio" not in res:
            res["gpio"] = res["serene"]
        if "mail" in res and "email" not in res:
            res["email"] = res["mail"]
        return res

    def startSiren(self) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.start_siren()
            except Exception:
                logger.exception("Error in plugin %s start_siren:", plugin.name)

    def stopSiren(self) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.stop_siren()
            except Exception:
                logger.exception("Error in plugin %s stop_siren:", plugin.name)

    def intruderAlert(self, alert_info: Optional[Dict[str, Any]] = None) -> None:
        if self.mylogs:
            self.mylogs.writeLog("alarm", "Intruder Alert")
        self.startSiren()
        self.update_alarmstate()

        for plugin in self.plugins.values():
            try:
                threading.Thread(target=plugin.on_intruder_alert, args=(alert_info,), daemon=True).start()
            except Exception:
                logger.exception("Error triggering on_intruder_alert for %s:", plugin.name)

    def update_sensor(self, sensor_uuid: str) -> None:
        sensor_data = self.settings.get("sensors", {}).get(sensor_uuid, {})
        name = sensor_data.get("name", sensor_uuid)

        if sensor_data.get("online") is False:
            sensor_state = "error"
        elif sensor_data.get("alert") is True:
            sensor_state = "on"
        else:
            sensor_state = "off"

        if self.mylogs:
            self.mylogs.writeLog(f"sensor,{sensor_state},{sensor_uuid}", name)

        self.updateUI("sensorsChanged", self.getSensorsArmed())

        for plugin in self.plugins.values():
            try:
                plugin.on_sensor_update(sensor_uuid, sensor_data, sensor_state)
            except Exception:
                logger.exception("Error in plugin %s on_sensor_update:", plugin.name)

    def update_alarmstate(self) -> None:
        state = self.settings.get("settings", {}).get("alarmState", "disarmed")
        if self.mylogs:
            if state == "armed":
                self.mylogs.writeLog("user_action", "Alarm activated")
            elif state == "disarmed":
                self.mylogs.writeLog("user_action", "Alarm deactivated")
            elif state == "pending":
                self.mylogs.writeLog("user_action", "Alarm is pending for activation")

        if state != "triggered":
            self.stopSiren()

        self.updateUI("sensorsChanged", self.getSensorsArmed())

        for plugin in self.plugins.values():
            try:
                plugin.on_alarm_state_change(state)
            except Exception:
                logger.exception("Error in plugin %s on_alarm_state_change:", plugin.name)

    def getSensorsArmed(self) -> Dict[str, Any]:
        sensors = self.settings.get("sensors", {})
        ordered_sensors = dict(sorted(sensors.items(), key=lambda item: item[1].get("name", "")))
        alarm_state = self.settings.get("settings", {}).get("alarmState", "disarmed")
        return {
            "sensors": ordered_sensors,
            "alarmState": alarm_state,
            "alarmArmed": alarm_state in ("armed", "triggered", "pending"),
        }

    def on_disarm(self, callback: Any) -> None:
        self.callbacks["deactivateAlarm"] = callback

    def on_arm(self, callback: Any) -> None:
        self.callbacks["activateAlarm"] = callback

    def on_sensor_set_alert(self, callback: Any) -> None:
        self.callbacks["sensorAlert"] = callback

    def on_sensor_set_stopalert(self, callback: Any) -> None:
        self.callbacks["sensorStopAlert"] = callback

    def cleanup(self) -> None:
        for plugin in self.plugins.values():
            try:
                plugin.cleanup()
            except Exception:
                pass
