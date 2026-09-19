#!/usr/bin/env python3
"""MQTT Sensor Plugin for AlarmPI."""

from typing import Any, Dict, List, Optional
from alarmcode.sensors.base import BaseSensorPlugin, SensorField


class MQTTSensorPlugin(BaseSensorPlugin):
    """Monitors custom MQTT state topics (e.g., Zigbee2MQTT, ESPHome, Shelly)."""

    sensor_type = "MQTT"
    display_name = "MQTT Topic"
    description = "Listen to custom MQTT topic payloads from smart sensors."
    icon = "wifi"

    @classmethod
    def define_fields(cls) -> List[SensorField]:
        return [
            SensorField("topic", "Custom MQTT Topic", "string", default="", placeholder="zigbee2mqtt/front_door/contact", required=True),
            SensorField("payload", "Alert Evaluation Python Expr", "string", default="contact == True", placeholder="contact == False or state == 'OPEN'", help_text="Expression evaluated against incoming JSON payload"),
        ]

    def add_sensor(self, sensor_data: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.sensor_data = sensor_data
        self.online = True
        self.alert = False
