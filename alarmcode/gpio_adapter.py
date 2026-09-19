#!/usr/bin/env python3
"""GPIO Abstraction Layer for AlarmPI.

Provides transparent compatibility across:
- Standard RPi.GPIO (Raspberry Pi 3/4 on legacy kernels)
- rpi-lgpio (Raspberry Pi 5 and Debian Bookworm / modern kernels)
- MockGPIO (Safe virtual fallback for development, testing, x86_64, macOS, Docker)
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger('alarmpi')


class MockGPIOModule:
    """Mock implementation of RPi.GPIO for non-Raspberry Pi environments."""

    BCM = 11
    BOARD = 10
    IN = 1
    OUT = 0
    HIGH = 1
    LOW = 0
    PUD_OFF = 20
    PUD_DOWN = 21
    PUD_UP = 22
    RISING = 31
    FALLING = 32
    BOTH = 33

    def __init__(self):
        self._mode = self.BCM
        self._warnings = False
        self._pins: Dict[int, Dict[str, Any]] = {}
        self._callbacks: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def setmode(self, mode: int) -> None:
        self._mode = mode

    def getmode(self) -> int:
        return self._mode

    def setwarnings(self, state: bool) -> None:
        self._warnings = state

    def setup(self, pin: int, direction: int, pull_up_down: int = PUD_OFF, initial: int = LOW) -> None:
        with self._lock:
            # Default input pin to LOW (0 = normal / closed) so mock mode isn't stuck on alert
            self._pins[pin] = {
                'direction': direction,
                'pull_up_down': pull_up_down,
                'state': initial if direction == self.OUT else self.LOW
            }

    def output(self, pin: int, state: int) -> None:
        with self._lock:
            if pin in self._pins:
                self._pins[pin]['state'] = state
                logger.debug("MockGPIO: Pin %d output set to %s", pin, "HIGH" if state == self.HIGH else "LOW")

    def input(self, pin: int) -> int:
        with self._lock:
            if pin in self._pins:
                return self._pins[pin]['state']
            return self.LOW

    def add_event_detect(self, pin: int, edge: int, callback: Optional[Callable[[int], None]] = None, bouncetime: int = 0) -> None:
        with self._lock:
            self._callbacks[pin] = {
                'edge': edge,
                'callback': callback,
                'bouncetime': bouncetime,
                'last_trigger': 0
            }

    def remove_event_detect(self, pin: int) -> None:
        with self._lock:
            self._callbacks.pop(pin, None)

    def cleanup(self, pin: Optional[int] = None) -> None:
        with self._lock:
            if pin is None:
                self._pins.clear()
                self._callbacks.clear()
            else:
                self._pins.pop(pin, None)
                self._callbacks.pop(pin, None)

    # Helper for testing / simulated events
    def simulate_pin_change(self, pin: int, new_state: int) -> None:
        cb_info = None
        with self._lock:
            if pin in self._pins:
                self._pins[pin]['state'] = new_state
                cb_info = self._callbacks.get(pin)

        if cb_info and cb_info.get('callback'):
            now = time.time()
            if (now - cb_info['last_trigger']) * 1000 >= cb_info.get('bouncetime', 0):
                cb_info['last_trigger'] = now
                threading.Thread(target=cb_info['callback'], args=(pin,), daemon=True).start()


def get_gpio():
    """Attempt to import real GPIO driver, otherwise return MockGPIO."""
    # 1. Try standard RPi.GPIO
    try:
        import RPi.GPIO as rpi_gpio
        rpi_gpio.setmode(rpi_gpio.BCM)
        rpi_gpio.setwarnings(False)
        logger.info("✅ Hardware GPIO initialized using RPi.GPIO.")
        return rpi_gpio, True
    except Exception as e:
        logger.debug("RPi.GPIO not loaded: %s", e)

    # 2. Try rpi_lgpio (Raspberry Pi 5 / Bookworm)
    try:
        import rpi_lgpio as rpi_gpio
        rpi_gpio.setmode(rpi_gpio.BCM)
        rpi_gpio.setwarnings(False)
        logger.info("✅ Hardware GPIO initialized using rpi_lgpio.")
        return rpi_gpio, True
    except Exception as e:
        logger.debug("rpi_lgpio not loaded: %s", e)

    # 3. Fallback to mock
    logger.warning("⚠️ Hardware GPIO library (RPi.GPIO or rpi-lgpio) is not installed! Running in MockGPIO virtual mode. Physical GPIO pins will NOT be read.")
    return MockGPIOModule(), False


GPIO, IS_REAL_HARDWARE = get_gpio()
