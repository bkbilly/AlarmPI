#!/usr/bin/env python3
"""GPIO Sensor Plugin for AlarmPI.

Implements glitch-filtered, timer-verified GPIO state monitoring
similar to lnxlink's GpioHandle architecture.
"""

import logging
from threading import Timer
from typing import Any, Dict, List, Optional

from alarmcode.gpio_adapter import GPIO
from alarmcode.sensors.base import BaseSensorPlugin, SensorField
from alarmcode.utils import parse_float, parse_int

logger = logging.getLogger('alarmpi')


class GPIOSensorPlugin(BaseSensorPlugin):
    """Monitors physical magnetic door contacts, PIR motion sensors, or tamper switches on Raspberry Pi GPIO pins with glitch filtering and delayed state verification."""

    sensor_type = "GPIO"
    display_name = "GPIO Pin"
    description = "Physical sensor connected directly to Raspberry Pi GPIO header with glitch-filtered state verification."
    icon = "cpu"

    def __init__(self, sensor_id: str, wd: str = ""):
        super().__init__(sensor_id, wd)
        self.pin: Optional[int] = None
        self.delay: float = 0.15
        self.timer: Optional[Timer] = None
        self.last_reported_state: Optional[int] = None

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
        except Exception:
            logger.exception("Error setting up GPIO mode for sensor %s:", sensor_id)

    @classmethod
    def define_fields(cls) -> List[SensorField]:
        return [
            SensorField("pin", "BCM Pin Number", "pin", default=1, required=True, help_text="GPIO pin in BCM numbering"),
            SensorField("delay", "Glitch Filter / Delay (s)", "number", default=0.15, placeholder="0.15", help_text="Verification delay in seconds before confirming ON/OFF state change"),
        ]

    def add_sensor(self, sensor_data: Dict[str, Any], global_settings: Optional[Dict[str, Any]] = None) -> None:
        self.sensor_data = sensor_data
        self.pin = parse_int(sensor_data.get("pin"), 1)
        self.delay = parse_float(sensor_data.get("delay", 0.15), 0.15)

        if self.timer is not None:
            try:
                self.timer.cancel()
            except Exception:
                pass
            self.timer = None

        try:
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.remove_event_detect(self.pin)
        except Exception:
            pass

        try:
            # Establish the initial baseline state and report it immediately upon boot
            self.last_reported_state = GPIO.input(self.pin)
            if self.last_reported_state == 1:
                self._notify_alert()
            else:
                self._notify_alert_stop()

            GPIO.add_event_detect(
                self.pin,
                GPIO.BOTH,
                callback=self._edge_detected,
                bouncetime=20,
            )
        except Exception:
            logger.exception("Error setting up GPIO pin %s for sensor %s:", self.pin, self.sensor_id)
            self._notify_error()

    def _edge_detected(self, channel: int) -> None:
        """Cancels active timers and starts a new verification countdown upon detecting a state change."""
        try:
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None

            current_state = GPIO.input(self.pin)

            if current_state == self.last_reported_state:
                return

            if self.delay > 0:
                self.timer = Timer(
                    self.delay, self._verify_and_trigger, args=[current_state]
                )
                self.timer.daemon = True
                self.timer.start()
            else:
                self._verify_and_trigger(current_state)
        except Exception:
            logger.exception("Error handling edge detection for sensor %s:", self.sensor_id)
            self._notify_error()

    def _verify_and_trigger(self, target_state: int) -> None:
        """Verifies GPIO state after a delay and triggers external alert callbacks."""
        try:
            current_state = GPIO.input(self.pin)

            if current_state == target_state and current_state != self.last_reported_state:
                self.last_reported_state = current_state
                if current_state == 1:
                    self._notify_alert()
                else:
                    self._notify_alert_stop()
        except Exception:
            logger.exception("Error verifying GPIO state for sensor %s:", self.sensor_id)
            self._notify_error()

    def del_sensor(self) -> None:
        if self.timer is not None:
            try:
                self.timer.cancel()
            except Exception:
                pass
            self.timer = None

        if self.pin is not None:
            try:
                GPIO.remove_event_detect(self.pin)
            except Exception:
                pass
