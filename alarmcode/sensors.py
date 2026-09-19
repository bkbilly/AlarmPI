#!/usr/bin/env python3
"""Backward compatibility module for AlarmPI Sensors."""

from alarmcode.sensors import Sensor, discover_sensor_plugins, get_available_sensor_types
from alarmcode.sensors.base import BaseSensorPlugin as sensorGeneral, SensorField
from alarmcode.sensors.gpio import GPIOSensorPlugin as sensorGPIO
from alarmcode.sensors.hikvision import HikvisionSensorPlugin as sensorHikvision
from alarmcode.sensors.mqtt import MQTTSensorPlugin as sensorMQTT

__all__ = [
    "Sensor",
    "sensorGeneral",
    "sensorGPIO",
    "sensorHikvision",
    "sensorMQTT",
    "SensorField",
    "discover_sensor_plugins",
    "get_available_sensor_types",
]
