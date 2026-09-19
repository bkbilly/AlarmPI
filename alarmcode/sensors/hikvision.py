#!/usr/bin/env python3
"""Hikvision Camera Sensor Plugin for AlarmPI.

Connects to Hikvision IP Cameras and NVRs via ISAPI to discover and stream
events like Line Crossing, Intrusion Detection, Motion (VMD), PIR, Alarm Inputs, and AcuSense targets.
"""

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
import requests

from alarmcode.sensors.base import BaseSensorPlugin, SensorField
from alarmcode.utils import parse_int

logger = logging.getLogger('alarmpi')


def discover_hikvision(ip: str, username: str, password: str) -> Dict[str, Any]:
    """Probes a Hikvision camera / NVR via ISAPI to discover device information, channels, and available sensors/events."""
    if not ip:
        return {"status": "error", "message": "IP address is required."}

    host = ip.replace("http://", "").replace("https://", "").rstrip("/")
    base_url = f"http://{host}"

    auth_digest = requests.auth.HTTPDigestAuth(username, password)
    auth_basic = requests.auth.HTTPBasicAuth(username, password)

    def request_isapi(path: str, timeout: int = 5):
        try:
            r = requests.get(f"{base_url}{path}", auth=auth_digest, timeout=timeout)
            if r.status_code == 401:
                r = requests.get(f"{base_url}{path}", auth=auth_basic, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return None

    # 1. Device Info Probe
    device_info_xml = request_isapi("/ISAPI/System/deviceInfo")
    if not device_info_xml:
        return {
            "status": "error",
            "message": f"Could not connect to Hikvision device at {ip}. Verify IP address, port, and credentials."
        }

    device_name_m = re.search(r"<deviceName>(.*?)</deviceName>", device_info_xml, re.IGNORECASE)
    model_m = re.search(r"<model>(.*?)</model>", device_info_xml, re.IGNORECASE)
    device_name = device_name_m.group(1).strip() if device_name_m else "Hikvision Device"
    model = model_m.group(1).strip() if model_m else "IP Camera"

    # 2. Channels Probe (for NVRs or multi-channel cameras)
    channels = []
    channels_xml = request_isapi("/ISAPI/System/Video/inputs/channels")
    if channels_xml:
        ch_blocks = re.findall(r"<VideoInputChannel.*?</VideoInputChannel>", channels_xml, re.DOTALL | re.IGNORECASE)
        for block in ch_blocks:
            id_m = re.search(r"<id>(.*?)</id>", block, re.IGNORECASE)
            name_m = re.search(r"<name>(.*?)</name>", block, re.IGNORECASE)
            if id_m:
                ch_id = id_m.group(1).strip()
                ch_name = name_m.group(1).strip() if name_m and name_m.group(1).strip() else f"Channel {ch_id}"
                channels.append({"id": ch_id, "name": ch_name})

    # 3. Build Available Sensors List
    events = []
    if len(channels) > 1:
        for ch in channels:
            events.append({
                "value": f"ch{ch['id']}_linedetection",
                "label": f"📏 {ch['name']} — Line Crossing Detection",
                "category": "line",
                "default_name": f"{ch['name']} Line Crossing",
                "device_class": "motion"
            })
            events.append({
                "value": f"ch{ch['id']}_fielddetection",
                "label": f"🛡️ {ch['name']} — Intrusion / Area Detection",
                "category": "intrusion",
                "default_name": f"{ch['name']} Intrusion",
                "device_class": "motion"
            })
            events.append({
                "value": f"ch{ch['id']}_motiondetection",
                "label": f"🏃 {ch['name']} — Motion Detection (VMD)",
                "category": "motion",
                "default_name": f"{ch['name']} Motion",
                "device_class": "motion"
            })
            events.append({
                "value": f"ch{ch['id']}_all",
                "label": f"🌐 {ch['name']} — Any Event",
                "category": "all",
                "default_name": f"{ch['name']} Alert",
                "device_class": "motion"
            })
    else:
        cam_label = channels[0]['name'] if channels else device_name
        events = [
            {
                "value": "linedetection",
                "label": "📏 Line Crossing Detection (Virtual Tripwire)",
                "category": "line",
                "default_name": f"{cam_label} Line Crossing",
                "device_class": "motion"
            },
            {
                "value": "fielddetection",
                "label": "🛡️ Intrusion / Region Detection",
                "category": "intrusion",
                "default_name": f"{cam_label} Intrusion",
                "device_class": "motion"
            },
            {
                "value": "motiondetection",
                "label": "🏃 Motion Detection (VMD)",
                "category": "motion",
                "default_name": f"{cam_label} Motion",
                "device_class": "motion"
            },
            {
                "value": "regionEntrance",
                "label": "🚪 Region Entrance Detection",
                "category": "entrance",
                "default_name": f"{cam_label} Entrance",
                "device_class": "door"
            },
            {
                "value": "regionExiting",
                "label": "🚪 Region Exiting Detection",
                "category": "exit",
                "default_name": f"{cam_label} Exit",
                "device_class": "door"
            },
            {
                "value": "PIR",
                "label": "⚡ Built-in Hardware PIR Sensor",
                "category": "pir",
                "default_name": f"{cam_label} PIR",
                "device_class": "motion"
            },
            {
                "value": "IO",
                "label": "🔌 Physical Alarm Input (IO Port)",
                "category": "io",
                "default_name": f"{cam_label} Alarm Input",
                "device_class": "door"
            },
            {
                "value": "tamperdetection",
                "label": "⚠️ Video Tampering / Lens Blinding",
                "category": "tamper",
                "default_name": f"{cam_label} Tamper",
                "device_class": "tamper"
            },
            {
                "value": "scenechangedetection",
                "label": "🔄 Scene Change / Angle Defocus",
                "category": "scene",
                "default_name": f"{cam_label} Scene Change",
                "device_class": "tamper"
            },
            {
                "value": "all",
                "label": "🌐 All Events (Any trigger from camera)",
                "category": "all",
                "default_name": f"{cam_label} Event",
                "device_class": "motion"
            }
        ]

    return {
        "status": "success",
        "device": {
            "name": device_name,
            "model": model,
            "channels_count": len(channels)
        },
        "channels": channels,
        "events": events
    }


class HikvisionSensorPlugin(BaseSensorPlugin):
    """Monitors line detection, motion, intrusion, and smart event streams from Hikvision IP cameras."""

    sensor_type = "Hikvision"
    display_name = "Hikvision IP Camera"
    description = "Stream ISAPI line-crossing, motion, intrusion, and alarm events directly from Hikvision cameras."
    icon = "video"

    def __init__(self, sensor_id: str, wd: str = ""):
        super().__init__(sensor_id, wd)
        self.alert_time = 8
        self.run_forever = False
        self.stream_thread: Optional[threading.Thread] = None
        self.event_filter = "linedetection"
        self.target_type = "all"

    @classmethod
    def define_fields(cls) -> List[SensorField]:
        return [
            SensorField("ip", "Camera IP / Host", "string", default="", placeholder="192.168.1.64", required=True),
            SensorField("user", "Camera Username", "string", default="admin", placeholder="admin", required=True),
            SensorField("pass", "Camera Password", "password", default="", required=True),
            SensorField(
                "event_filter",
                "Trigger Event / Sensor",
                "select",
                default="linedetection",
                options=[
                    {"value": "linedetection", "label": "📏 Line Crossing Detection"},
                    {"value": "fielddetection", "label": "🛡️ Intrusion / Region Detection"},
                    {"value": "motiondetection", "label": "🏃 Motion Detection (VMD)"},
                    {"value": "regionEntrance", "label": "🚪 Region Entrance"},
                    {"value": "regionExiting", "label": "🚪 Region Exiting"},
                    {"value": "PIR", "label": "⚡ Built-in PIR Sensor"},
                    {"value": "IO", "label": "🔌 Physical Alarm Input (IO)"},
                    {"value": "tamperdetection", "label": "⚠️ Tampering / Blinding"},
                    {"value": "scenechangedetection", "label": "🔄 Scene Change"},
                    {"value": "all", "label": "🌐 All Events (Any Trigger)"},
                ],
                help_text="Choose which specific camera event or channel triggers this alarm sensor."
            ),
            SensorField(
                "target_type",
                "Detection Target (AcuSense)",
                "select",
                default="all",
                options=[
                    {"value": "all", "label": "All Targets (Human, Vehicle, Other)"},
                    {"value": "human", "label": "🚶 Humans Only"},
                    {"value": "vehicle", "label": "🚗 Vehicles Only"},
                ],
                help_text="Filter smart AcuSense events by target classification."
            ),
            SensorField("alert_time", "Alert Duration (s)", "number", default=8, placeholder="8", help_text="Duration in seconds before sensor returns to normal."),
        ]

    def add_sensor(self, sensor_data: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.sensor_data = sensor_data
        self.event_filter = str(sensor_data.get("event_filter", "linedetection")).strip()
        self.target_type = str(sensor_data.get("target_type", "all")).strip().lower()
        self.alert_time = parse_int(sensor_data.get("alert_time", 8), 8)
        self.reload(global_settings)

    def reload(self, global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.run_forever = False
        ip = self.sensor_data.get("ip", "").strip()
        user = self.sensor_data.get("user", "").strip()
        pwd = self.sensor_data.get("pass", "").strip()

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
        host = ip.replace("http://", "").replace("https://", "").rstrip("/")
        stream_url = f"http://{host}/ISAPI/Event/notification/alertStream"

        auth_digest = requests.auth.HTTPDigestAuth(username, password)
        auth_basic = requests.auth.HTTPBasicAuth(username, password)

        while self.run_forever:
            try:
                try:
                    auth = auth_digest
                    response = requests.get(stream_url, auth=auth, timeout=15, stream=True)
                    if response.status_code == 401:
                        auth = auth_basic
                        response = requests.get(stream_url, auth=auth, timeout=15, stream=True)
                except Exception:
                    auth = auth_basic
                    response = requests.get(stream_url, auth=auth, timeout=15, stream=True)

                if response.status_code != 200:
                    if self.online:
                        self._notify_error()
                    time.sleep(5)
                    continue

                if not self.online:
                    self._notify_error_stop()

                buffer = ""
                for chunk in response.iter_lines():
                    if not self.run_forever:
                        break
                    if chunk:
                        text = chunk.decode("utf-8", errors="ignore")
                        buffer += text + "\n"

                        if "</EventNotificationAlert>" in buffer or "</eventState>" in buffer or "<eventType>" in buffer:
                            self._process_event_xml(buffer)
                            buffer = ""

            except Exception:
                if self.online:
                    self._notify_error()
                time.sleep(3)

    def _process_event_xml(self, xml_text: str) -> None:
        """Evaluates incoming ISAPI XML event against configured sensor filters."""
        ev_match = re.search(r"<eventType>(.*?)</eventType>", xml_text, re.IGNORECASE)
        if not ev_match:
            return

        event_type = ev_match.group(1).strip().lower()

        # Check eventState (ignore inactive / pulse ends)
        state_match = re.search(r"<eventState>(.*?)</eventState>", xml_text, re.IGNORECASE)
        event_state = state_match.group(1).strip().lower() if state_match else "active"
        if event_state not in ("active", "start", ""):
            return

        # Check channel ID (e.g. channelID or dynChannelID)
        ch_match = re.search(r"<(?:dynChannelID|channelID)>(.*?)</(?:dynChannelID|channelID)>", xml_text, re.IGNORECASE)
        channel_id = ch_match.group(1).strip() if ch_match else ""

        # Check target classification (human / vehicle)
        target_match = re.search(r"<(?:detectionTarget|targetType)>(.*?)</(?:detectionTarget|targetType)>", xml_text, re.IGNORECASE)
        detected_target = target_match.group(1).strip().lower() if target_match else ""

        # Match Channel / Event filter
        filter_lower = self.event_filter.lower()
        is_matched = False

        if filter_lower.startswith("ch") and "_" in filter_lower:
            ch_prefix, ev_part = filter_lower.split("_", 1)
            expected_ch = ch_prefix.replace("ch", "")
            if (not channel_id or channel_id == expected_ch) and (ev_part == "all" or ev_part == event_type or (ev_part == "motiondetection" and event_type in ("vmd", "motiondetection"))):
                is_matched = True
        elif filter_lower == "all":
            if event_type in ("linedetection", "motiondetection", "vmd", "fielddetection", "regionentrance", "regionexiting", "pir", "io", "tamperdetection", "scenechangedetection", "facesnap"):
                is_matched = True
        elif filter_lower == event_type:
            is_matched = True
        elif filter_lower == "motiondetection" and event_type in ("vmd", "motiondetection"):
            is_matched = True
        elif filter_lower in event_type:
            is_matched = True

        if not is_matched:
            return

        # Match AcuSense Target Type filter
        if self.target_type in ("human", "vehicle") and detected_target:
            if detected_target != self.target_type:
                return

        logger.info("🎥 Hikvision event triggered on sensor %s: type=%s, ch=%s, target=%s", self.sensor_id, event_type, channel_id, detected_target)
        self.setAlertStatus(True)

    def setAlertStatus(self, alertstate: Optional[bool] = None) -> None:
        self.alert = True
        self._notify_alert()
        threading.Thread(target=self._auto_reset_alert, daemon=True).start()

    def _auto_reset_alert(self) -> None:
        time.sleep(self.alert_time)
        self._notify_alert_stop()

    def del_sensor(self) -> None:
        self.run_forever = False
