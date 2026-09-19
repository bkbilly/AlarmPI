#!/usr/bin/env python3
"""Backward compatibility module for AlarmPI Notifier."""

from alarmcode.notifiers import NotifierManager as Notify, discover_notifier_plugins
from alarmcode.notifiers.base import BaseNotifier, NotifierField

__all__ = ["Notify", "BaseNotifier", "NotifierField", "discover_notifier_plugins"]
