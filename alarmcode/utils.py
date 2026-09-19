#!/usr/bin/env python3
"""Utility functions for AlarmPI."""

import re
from typing import Any


def parse_bool(value: Any, default: bool = False) -> bool:
    """Safely parse various values into a boolean (Python 3.12+ replacement for distutils.util.strtobool)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    
    val_str = str(value).strip().lower()
    if val_str in ("true", "1", "yes", "y", "on", "t", "enabled", "enable"):
        return True
    if val_str in ("false", "0", "no", "n", "off", "f", "disabled", "disable", ""):
        return False
    return default


def parse_int(value: Any, default: int = 0) -> int:
    """Safely parse value into an integer."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_float(value: Any, default: float = 0.0) -> float:
    """Safely parse value into a float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def sanitize_sensor_name(name: str) -> str:
    """Convert a sensor name to a snake_case topic-safe identifier."""
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_")
