#!/usr/bin/env python3
"""Virtual / Software-Triggered Sensor Plugin for AlarmPI."""

from typing import Any, Dict, List, Optional
from alarmcode.sensors.base import BaseSensorPlugin, SensorField


class VirtualSensorPlugin(BaseSensorPlugin):
    """Virtual software sensor that can be triggered via HTTP API, webhooks, or UI testing."""

    sensor_type = "Virtual"
    display_name = "Virtual / Software Sensor"
    description = "Software-controlled sensor triggered via API or web interface."
    icon = "code"

    @classmethod
    def define_fields(cls) -> List[SensorField]:
        return [
            SensorField("description", "Notes / Description", "string", default="", placeholder="Virtual button / webhook"),
        ]

    def add_sensor(self, sensor_data: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.sensor_data = sensor_data
        self.online = True
        self.alert = False
