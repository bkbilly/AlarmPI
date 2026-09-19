#!/usr/bin/env python3
"""GPIO Siren Notifier Plugin for AlarmPI."""

import logging
from typing import Any, Dict, List
import requests

from alarmcode.gpio_adapter import GPIO, IS_REAL_HARDWARE
from alarmcode.notifiers.base import BaseNotifier, NotifierField
from alarmcode.utils import parse_bool, parse_int

logger = logging.getLogger('alarmpi')


class GPIOSirenNotifier(BaseNotifier):
    """Controls physical siren via GPIO output pin and/or external HTTP siren triggers."""

    name = "serene"
    display_name = "Siren"
    description = "Control physical sirens via Raspberry Pi GPIO output pins or webhook HTTP triggers."
    icon = "volume-2"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connected = True
        try:
            GPIO.setmode(GPIO.BCM)
        except Exception:
            logger.exception("Error initializing GPIO for siren:")
            self.connected = False

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        return [
            NotifierField("enable", "Enable Siren", "boolean", default=False, help_text="Enable physical/HTTP siren on alarm breach"),
            NotifierField("pin", "BCM Pin", "pin", default=14, help_text="Raspberry Pi BCM GPIO pin connected to siren relay"),
            NotifierField("http_start", "Start Siren HTTP URL", "string", default="", placeholder="http://192.168.1.50/siren/on", help_text="Optional URL to trigger on alarm activation"),
            NotifierField("http_stop", "Stop Siren HTTP URL", "string", default="", placeholder="http://192.168.1.50/siren/off", help_text="Optional URL to trigger on alarm deactivation"),
        ]

    def setup(self, settings: Dict[str, Any]) -> None:
        super().setup(settings)

    def start_siren(self) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return

        if self.mylogs:
            self.mylogs.writeLog("alarm", "Serene started")

        pin = parse_int(cfg.get("pin"), 14)
        self._enable_pin(pin)

        http_start = cfg.get("http_start", "")
        if http_start:
            try:
                requests.get(http_start, timeout=5)
            except Exception:
                logger.exception("Failed to call http_start for siren:")

    def stop_siren(self) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return

        pin = parse_int(cfg.get("pin"), 14)
        self._disable_pin(pin)

        http_stop = cfg.get("http_stop", "")
        if http_stop:
            try:
                requests.get(http_stop, timeout=5)
            except Exception:
                logger.exception("Failed to call http_stop for siren:")

    def _enable_pin(self, pin: int) -> None:
        try:
            GPIO.setup(pin, GPIO.OUT)
            state = GPIO.input(pin)
            if state == GPIO.LOW:
                logger.info("Enabling GPIO Siren on pin %d", pin)
                GPIO.output(pin, GPIO.HIGH)
        except Exception:
            logger.exception("Error enabling GPIO pin %s", pin)

    def _disable_pin(self, pin: int) -> None:
        try:
            GPIO.setup(pin, GPIO.OUT)
            if GPIO.input(pin) == GPIO.HIGH:
                logger.info("Disabling GPIO Siren on pin %d", pin)
                GPIO.output(pin, GPIO.LOW)
            GPIO.setup(pin, GPIO.IN)
        except Exception:
            logger.exception("Error disabling GPIO pin %s", pin)

    def get_status(self) -> bool:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return False
        return self.connected
