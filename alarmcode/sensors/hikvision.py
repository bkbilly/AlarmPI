#!/usr/bin/env python3
"""Hikvision Camera Sensor Plugin for AlarmPI."""

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
import requests

from alarmcode.sensors.base import BaseSensorPlugin, SensorField

logger = logging.getLogger('alarmpi')


class HikvisionSensorPlugin(BaseSensorPlugin):
    """Monitors line detection and motion alert streams from Hikvision IP cameras."""

    sensor_type = "Hikvision"
    display_name = "Hikvision IP Camera"
    description = "Stream ISAPI line-detection / motion events directly from Hikvision cameras."
    icon = "video"

    def __init__(self, sensor_id: str, wd: str = ""):
        super().__init__(sensor_id, wd)
        self.alert_time = 8
        self.run_forever = False
        self.stream_thread: Optional[threading.Thread] = None

    @classmethod
    def define_fields(cls) -> List[SensorField]:
        return [
            SensorField("ip", "Camera IP / Host", "string", default="", placeholder="192.168.1.64", required=True),
            SensorField("user", "Camera Username", "string", default="admin", placeholder="admin", required=True),
            SensorField("pass", "Camera Password", "password", default="", required=True),
        ]

    def add_sensor(self, sensor_data: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.sensor_data = sensor_data
        self.reload(global_settings)

    def reload(self, global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.run_forever = False
        ip = self.sensor_data.get("ip", "")
        user = self.sensor_data.get("user", "")
        pwd = self.sensor_data.get("pass", "")

        if not ip:
            return

        self.stream_thread = threading.Thread(
            target=self._stream_listener,
            args=(ip, user, pwd),
            daemon=True
        )
        self.stream_thread.start()
        self._notify_alert_stop()

    def _stream_listener(self, ip: str, username: str, password: str) -> None:
        self.run_forever = True
        stream_url = f"http://{ip}/ISAPI/Event/notification/alertStream"
        auth = requests.auth.HTTPBasicAuth(username, password)

        while self.run_forever:
            try:
                response = requests.get(stream_url, auth=auth, timeout=15, stream=True)
                if not self.online:
                    self._notify_error_stop()

                for chunk in response.iter_lines():
                    if not self.run_forever:
                        break
                    if chunk:
                        text = chunk.decode("utf-8", errors="ignore")
                        match = re.search(r"<eventType>(.*?)</eventType>", text)
                        if match and match.group(1).lower() in ("linedetection", "motiondetection", "fielddetection"):
                            self.setAlertStatus(True)
            except Exception:
                if self.online:
                    self._notify_error()
                time.sleep(3)

    def setAlertStatus(self, alertstate: Optional[bool] = None) -> None:
        self.alert = True
        self._notify_alert()
        threading.Thread(target=self._auto_reset_alert, daemon=True).start()

    def _auto_reset_alert(self) -> None:
        time.sleep(self.alert_time)
        self._notify_alert_stop()

    def del_sensor(self) -> None:
        self.run_forever = False
