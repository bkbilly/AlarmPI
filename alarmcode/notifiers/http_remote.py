#!/usr/bin/env python3
"""HTTP Remote Sync Notifier Plugin for AlarmPI."""

import logging
import threading
from typing import Any, Dict, List
import requests

from alarmcode.notifiers.base import BaseNotifier, NotifierField
from alarmcode.utils import parse_bool, parse_int

logger = logging.getLogger('alarmpi')


class HTTPRemoteNotifier(BaseNotifier):
    """Syncs sensor status changes to a remote AlarmPI instance over HTTP/HTTPS."""

    name = "http"
    display_name = "HTTP Sync"
    description = "Forward sensor events to a secondary or central AlarmPI server."
    icon = "globe"

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        return [
            NotifierField("enable", "Enable HTTP Forwarding", "boolean", default=False),
            NotifierField("host", "Remote Server Host", "string", default="", placeholder="remote.alarmpi.local"),
            NotifierField("port", "Remote Server Port", "number", default=443),
            NotifierField("https", "Use HTTPS", "boolean", default=True),
            NotifierField("username", "Remote Username", "string", default=""),
            NotifierField("password", "Remote Password", "password", default=""),
        ]

    def on_sensor_update(self, sensor_uuid: str, sensor_data: Dict[str, Any], state: str) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return

        threading.Thread(target=self._send_http_async, args=(sensor_uuid, sensor_data, state), daemon=True).start()

    def _send_http_async(self, sensor_uuid: str, sensor_data: Dict[str, Any], state: str) -> None:
        cfg = self.settings.get(self.name, {})
        try:
            s_name = sensor_data.get("name", sensor_uuid)
            proto = "https" if parse_bool(cfg.get("https", True)) else "http"
            host = cfg.get("host", "")
            port = parse_int(cfg.get("port"), 443)
            user = cfg.get("username", "")
            pwd = cfg.get("password", "")

            if not host:
                return

            auth_part = f"{user}:{pwd}@" if user or pwd else ""
            url = f"{proto}://{auth_part}{host}:{port}/setSensorStatus?name={s_name}&state={state}"
            requests.get(url, timeout=4, verify=False)
        except Exception:
            logger.exception("Failed to send sensor HTTP sync:")

    def get_status(self) -> bool:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return False
        return bool(cfg.get("host"))
