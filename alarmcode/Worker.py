#!/usr/bin/env python3
"""Worker orchestrator for AlarmPI."""

from collections import OrderedDict
from copy import deepcopy
import json
import logging
import os
import threading
import uuid
from typing import Any, Dict, List, Optional

from alarmcode.colors import bcolors
from alarmcode.logs import Logs
from alarmcode.notifiers import NotifierManager, discover_notifier_plugins
from alarmcode.sensors import Sensor, get_available_sensor_types
from alarmcode.utils import parse_bool, parse_float, parse_int

logger = logging.getLogger('alarmpi')


class Worker:
    """Core alarm orchestrator handling sensor events, state transitions, notifiers, and persistent settings."""

    def __init__(self, wd: str, jsonfile: str, logfile: str, optsUpdateUI: Optional[Dict[str, Any]] = None):
        self.wd = wd
        self.jsonfile = jsonfile
        self.logfile = logfile
        self.optsUpdateUI = optsUpdateUI or {}
        self.kill_now = False
        self._lock = threading.Lock()

        # Timers for Smart Arming & Alerts
        self.exit_timer: Optional[threading.Timer] = None
        self.entry_timer: Optional[threading.Timer] = None
        self.siren_timer: Optional[threading.Timer] = None
        self.in_entry_delay: bool = False

        # Load and reconcile settings with templates & plugin defaults
        self.settings = self.ReadSettings()

        # Initialize logging
        tz = self.settings.get('settings', {}).get('timezone', 'Europe/Athens')
        self.mylogs = Logs(self.wd, self.logfile, tz)
        trim_lines = parse_int(self.settings.get('settings', {}).get('trim', 1000), 1000)
        self.mylogs.startTrimThread(trim_lines)

        # Initialize modular notifier manager
        self.mynotify = NotifierManager(self.wd, self.settings, self.optsUpdateUI, self.mylogs)
        self.mylogs.setCallbackUpdateUI(self.mynotify.updateUI)
        self.mylogs.writeLog("system", "Alarm Booted")

        # Initialize modular sensor manager
        self.sensors = Sensor(self.wd)
        self.sensors.on_alert(self.sensorAlert)
        self.sensors.on_alert_stop(self.sensorStopAlert)
        self.sensors.on_error(self.sensorError)
        self.sensors.on_error_stop(self.sensorStopError)
        self.sensors.add_sensors(self.settings)

        # Connect notifiers to alarm callbacks
        self.mynotify.on_arm(self.activateAlarm)
        self.mynotify.on_disarm(self.deactivateAlarm)
        self.mynotify.on_sensor_set_alert(self.sensorAlert)
        self.mynotify.on_sensor_set_stopalert(self.sensorStopAlert)

    def sensorAlert(self, sensorUUID: str) -> None:
        """Handle sensor alert event."""
        if sensorUUID not in self.settings.get('sensors', {}):
            return

        sensor_name = self.settings['sensors'][sensorUUID].get('name', sensorUUID)
        logger.info("%s-> Alert Sensor: %s%s", bcolors.OKGREEN, sensor_name, bcolors.ENDC)

        with self._lock:
            self.settings['sensors'][sensorUUID]['alert'] = True
            self.settings['sensors'][sensorUUID]['online'] = True

            behavior = self.settings['sensors'][sensorUUID].get('behavior', 'normal')
            is_enabled = parse_bool(self.settings['sensors'][sensorUUID].get('enabled', True))
            current_state = self.settings.get('settings', {}).get('alarmState', 'disarmed')

            # 1. Door Chime when Disarmed
            if current_state == "disarmed" and is_enabled:
                door_chime_enabled = parse_bool(self.settings.get('settings', {}).get('door_chime', False))
                if door_chime_enabled or behavior == 'chime':
                    logger.info("🔔 Door Chime for sensor %s", sensor_name)
                    self.mynotify.updateUI('doorChime', {
                        'sensor_id': sensorUUID,
                        'name': sensor_name
                    })

            # 2. 24-hours behavior triggers immediately regardless of alarm state
            if behavior == '24hours' and is_enabled:
                self.writeNewSettingsToFile(self.settings)
                self.mynotify.update_sensor(sensorUUID)
                self._trigger_intruder_alert(sensorUUID, self.settings['sensors'][sensorUUID])
                return

            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_sensor(sensorUUID)
            self.checkIntruderAlert(triggered_sensor_uuid=sensorUUID)

    def sensorStopAlert(self, sensorUUID: str) -> None:
        """Handle sensor alert stop event."""
        if sensorUUID not in self.settings.get('sensors', {}):
            return

        sensor_name = self.settings['sensors'][sensorUUID].get('name', sensorUUID)
        logger.info("%s<- Stop Alert Sensor: %s%s", bcolors.OKGREEN, sensor_name, bcolors.ENDC)

        with self._lock:
            self.settings['sensors'][sensorUUID]['alert'] = False
            self.settings['sensors'][sensorUUID]['online'] = True
            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_sensor(sensorUUID)

            current_state = self.settings.get('settings', {}).get('alarmState')
            if current_state == "pending":
                arm_after_closing = parse_bool(self.settings.get('settings', {}).get('arm_after_closing', True))
                if arm_after_closing:
                    has_open = any(
                        s.get('alert') is True and
                        parse_bool(s.get('enabled', True)) and
                        s.get('online') is not False and
                        s.get('behavior') != '24hours'
                        for s in self.settings.get('sensors', {}).values()
                    )
                    if not has_open:
                        logger.info("All sensors closed: Arm after closing immediately activating alarm.")
                        self._cancel_timers()
                        self.settings['settings']['alarmState'] = "armed"
                        self.mylogs.writeLog("alarm", "Arm after closing: all sensors secured, alarm armed")
                        self.writeNewSettingsToFile(self.settings)
                        self.mynotify.update_alarmstate()
                        self.checkIntruderAlert()

    def sensorError(self, sensorUUID: str) -> None:
        """Handle sensor error/offline event."""
        if sensorUUID not in self.settings.get('sensors', {}):
            return

        sensor_name = self.settings['sensors'][sensorUUID].get('name', sensorUUID)
        logger.info("%s!- Error Sensor: %s%s", bcolors.FAIL, sensor_name, bcolors.ENDC)

        with self._lock:
            self.settings['sensors'][sensorUUID]['alert'] = True
            self.settings['sensors'][sensorUUID]['online'] = False
            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_sensor(sensorUUID)

    def sensorStopError(self, sensorUUID: str) -> None:
        """Handle sensor recovery from error."""
        if sensorUUID not in self.settings.get('sensors', {}):
            return

        sensor_name = self.settings['sensors'][sensorUUID].get('name', sensorUUID)
        logger.info("%s-- Error Stop Sensor: %s%s", bcolors.FAIL, sensor_name, bcolors.ENDC)

        with self._lock:
            self.settings['sensors'][sensorUUID]['online'] = True
            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_sensor(sensorUUID)

    def checkIntruderAlert(self, triggered_sensor_uuid: Optional[str] = None) -> None:
        """Check if active sensors should trigger intruder alarm or entry delay."""
        alarm_state = self.settings.get('settings', {}).get('alarmState')
        if alarm_state == "armed":
            for s_id, s_val in self.settings.get('sensors', {}).items():
                if (s_val.get('alert') is True and
                        parse_bool(s_val.get('enabled', True)) and
                        s_val.get('online') is not False and
                        self.settings['settings']['alarmState'] != "triggered"):
                    
                    behavior = s_val.get('behavior', 'normal')
                    entry_delay = parse_float(self.settings.get('settings', {}).get('entry_delay', 30), 30)

                    # Entry/Exit delay behavior
                    if behavior == 'entry_exit' and entry_delay > 0:
                        if not self.in_entry_delay:
                            logger.info("⏳ ENTRY DELAY STARTED by sensor %s (%ss countdown)", s_val.get('name', s_id), entry_delay)
                            self.in_entry_delay = True
                            self.mylogs.writeLog("alarm", f"Entry delay started by {s_val.get('name', s_id)} ({entry_delay}s)")
                            self.mynotify.updateUI('entryDelay', {
                                'sensor_id': s_id,
                                'name': s_val.get('name', s_id),
                                'seconds': entry_delay
                            })
                            self.entry_timer = threading.Timer(entry_delay, self._on_entry_delay_expired, args=(s_id, s_val))
                            self.entry_timer.daemon = True
                            self.entry_timer.start()
                        return

                    # Instant breach
                    logger.info("🚨 INTRUDER ALERT TRIGGERED by sensor %s!", s_val.get('name', s_id))
                    self._trigger_intruder_alert(s_id, s_val)
                    break

    def _on_entry_delay_expired(self, sensor_uuid: str, sensor_val: Dict[str, Any]) -> None:
        """Handle entry delay expiration without disarming."""
        with self._lock:
            if not self.in_entry_delay:
                return
            self.in_entry_delay = False
            current_state = self.settings.get('settings', {}).get('alarmState')
            if current_state in ('armed', 'pending'):
                logger.info("🚨 ENTRY DELAY EXPIRED! Triggering Intruder Alert for %s", sensor_val.get('name', sensor_uuid))
                self.mylogs.writeLog("alarm", f"Entry delay expired! Breach by {sensor_val.get('name', sensor_uuid)}")
                self._trigger_intruder_alert(sensor_uuid, sensor_val)

    def _trigger_intruder_alert(self, sensor_uuid: str, sensor_val: Dict[str, Any]) -> None:
        """Execute intruder alert, start siren with duration timeout, and notify plugins."""
        self._cancel_timers()
        self.in_entry_delay = False
        self.settings['settings']['alarmState'] = "triggered"
        self.writeNewSettingsToFile(self.settings)

        # Siren duration auto-cutoff timer
        siren_dur = parse_float(self.settings.get('settings', {}).get('siren_duration', 180), 180)
        if siren_dur > 0:
            if self.siren_timer:
                try:
                    self.siren_timer.cancel()
                except Exception:
                    pass
            self.siren_timer = threading.Timer(siren_dur, self._on_siren_timeout)
            self.siren_timer.daemon = True
            self.siren_timer.start()

        threading.Thread(
            target=self.mynotify.intruderAlert,
            args=({'sensor_id': sensor_uuid, 'sensor': sensor_val},),
            daemon=True
        ).start()

    def _on_siren_timeout(self) -> None:
        """Auto-cutoff siren after configured siren_duration."""
        logger.info("Siren auto-cutoff timeout reached.")
        self.mylogs.writeLog("alarm", "Siren auto-cutoff timeout reached")
        self.stopSiren()

    def ReadSettings(self) -> Dict[str, Any]:
        """Read settings from JSON file and reconcile with defaults from plugins."""
        settings_template = os.path.join(self.wd, 'config', 'settings_template.json')
        settings, _ = self.settings_reconciliation(settings_template, self.jsonfile)
        return settings

    def settings_reconciliation(self, from_json: str, to_json: str, ignored: Optional[List[str]] = None) -> tuple:
        """Reconcile settings with template and dynamically discovered plugin defaults."""
        ignored = ignored or ['sensors']
        settings_from = {}
        if os.path.exists(from_json):
            try:
                with open(from_json, 'r') as f:
                    settings_from = json.load(f)
            except Exception:
                pass

        # Dynamically inject defaults from discovered notifier plugins
        plugin_defaults = NotifierManager.get_all_defaults()
        for p_name, p_def in plugin_defaults.items():
            if p_name not in settings_from:
                settings_from[p_name] = p_def
            else:
                for k, v in p_def.items():
                    if k not in settings_from[p_name]:
                        settings_from[p_name][k] = v

        if 'settings' not in settings_from:
            settings_from['settings'] = {
                "alarmState": "disarmed",
                "timezone": "Europe/Athens",
                "trim": 1000,
                "exit_delay": 0,
                "entry_delay": 30,
                "arm_after_closing": True,
                "auto_bypass_open": False,
                "door_chime": False,
                "siren_duration": 180
            }
        if 'sensors' not in settings_from:
            settings_from['sensors'] = {}

        settings_to = {}
        if os.path.exists(to_json):
            try:
                with open(to_json, 'r') as f:
                    settings_to = json.load(f)
            except Exception:
                settings_to = {}

        changed = False
        for category, options in settings_from.items():
            if category not in settings_to:
                settings_to[category] = options
                changed = True
            elif category not in ignored and isinstance(options, dict):
                for option, data in options.items():
                    if option not in settings_to[category]:
                        settings_to[category][option] = data
                        changed = True

        if changed or not os.path.exists(to_json):
            os.makedirs(os.path.dirname(os.path.abspath(to_json)), exist_ok=True)
            with open(to_json, 'w') as outfile:
                json.dump(settings_to, outfile, sort_keys=True, indent=4)

        return settings_to, changed

    def writeNewSettingsToFile(self, settings: Dict[str, Any]) -> None:
        """Persist settings to JSON file without resetting plugin connections."""
        self.settings = settings
        with open(self.jsonfile, 'w') as outfile:
            json.dump(settings, outfile, sort_keys=True, indent=4)

    def activateAlarm(self, zones: Any = None, force: bool = False) -> None:
        """Arm the alarm system with smart arming (auto-bypass, exit delay, arm after closing)."""
        with self._lock:
            # 1. Cancel any active entry or exit timers
            self._cancel_timers()
            self.in_entry_delay = False

            # 2. Zone filtering if provided
            if zones is not None:
                if isinstance(zones, str):
                    zones = [z.strip().lower() for z in zones.split(',') if z.strip()]
                self.setSensorsZone(zones)

            settings_cfg = self.settings.get('settings', {})
            auto_bypass = parse_bool(settings_cfg.get('auto_bypass_open', False)) or force
            exit_delay = parse_float(settings_cfg.get('exit_delay', 30), 30)

            # 3. Auto-bypass open sensors if enabled
            if auto_bypass:
                for s_id, s_val in self.settings.get('sensors', {}).items():
                    if (s_val.get('alert') is True and
                            parse_bool(s_val.get('enabled', True)) and
                            s_val.get('behavior') != '24hours'):
                        s_val['enabled'] = False
                        s_name = s_val.get('name', s_id)
                        logger.info("Auto-bypassing open sensor '%s' on arming", s_name)
                        self.mylogs.writeLog("user_action", f"Auto-bypassed open sensor: {s_name}")

            # 4. Check if any active non-24h sensors are in alert
            has_open_sensors = any(
                s.get('alert') is True and
                parse_bool(s.get('enabled', True)) and
                s.get('online') is not False and
                s.get('behavior') != '24hours'
                for s in self.settings.get('sensors', {}).values()
            )

            # 5. Determine whether to start exit delay countdown or arm
            if exit_delay > 0:
                self.settings['settings']['alarmState'] = "pending"
                self.exit_timer = threading.Timer(exit_delay, self._on_exit_delay_expired)
                self.exit_timer.daemon = True
                self.exit_timer.start()
                logger.info("Alarm arming pending (Exit delay: %ds)", exit_delay)
            elif has_open_sensors:
                self.settings['settings']['alarmState'] = "pending"
                logger.info("Alarm arming pending (Waiting for open sensors to close)")
            else:
                self.settings['settings']['alarmState'] = "armed"
                logger.info("Alarm successfully armed (Instant)")

            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_alarmstate()
            self.checkIntruderAlert()

    def _on_exit_delay_expired(self) -> None:
        """Handle exit delay expiration."""
        with self._lock:
            if self.settings.get('settings', {}).get('alarmState') != "pending":
                return
            
            settings_cfg = self.settings.get('settings', {})
            auto_bypass = parse_bool(settings_cfg.get('auto_bypass_open', False))
            
            open_sensors = [
                (s_id, s_val) for s_id, s_val in self.settings.get('sensors', {}).items()
                if (s_val.get('alert') is True and
                    parse_bool(s_val.get('enabled', True)) and
                    s_val.get('online') is not False and
                    s_val.get('behavior') != '24hours')
            ]
            
            if open_sensors:
                if auto_bypass:
                    for s_id, s_val in open_sensors:
                        s_val['enabled'] = False
                        s_name = s_val.get('name', s_id)
                        logger.info("Exit delay expired: auto-bypassing '%s'", s_name)
                        self.mylogs.writeLog("user_action", f"Auto-bypassed open sensor: {s_name}")
                    self.settings['settings']['alarmState'] = "armed"
                    self.mylogs.writeLog("alarm", "Exit delay expired: alarm armed with bypassed sensors")
                else:
                    logger.warning("Exit delay expired but sensors still open!")
                    self.mylogs.writeLog("alarm", "Exit delay expired with sensors still open")
                    return
            else:
                self.settings['settings']['alarmState'] = "armed"
                self.mylogs.writeLog("alarm", "Exit delay expired: alarm fully armed")

            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_alarmstate()
            self.checkIntruderAlert()

    def deactivateAlarm(self) -> None:
        """Disarm the alarm system and cancel active timers."""
        with self._lock:
            self._cancel_timers()
            self.in_entry_delay = False
            self.settings.setdefault('settings', {})['alarmState'] = "disarmed"
            self.writeNewSettingsToFile(self.settings)
            self.mynotify.update_alarmstate()

    def _cancel_timers(self) -> None:
        if self.exit_timer:
            try:
                self.exit_timer.cancel()
            except Exception:
                pass
            self.exit_timer = None
        if self.entry_timer:
            try:
                self.entry_timer.cancel()
            except Exception:
                pass
            self.entry_timer = None
        if self.siren_timer:
            try:
                self.siren_timer.cancel()
            except Exception:
                pass
            self.siren_timer = None

    def startSiren(self, zones: Any = None) -> None:
        self.mynotify.startSiren()

    def stopSiren(self) -> None:
        self.mynotify.stopSiren()

    def getSensorsArmed(self) -> Dict[str, Any]:
        """Return formatted sensors status dictionary for the UI."""
        sensors = self.settings.get('sensors', {})
        ordered_sensors = OrderedDict(
            sorted(sensors.items(), key=lambda item: item[1].get('name', ''))
        )
        alarm_state = self.settings.get('settings', {}).get('alarmState', 'disarmed')
        serene_cfg = self.settings.get('serene', {})
        settings_cfg = self.settings.get('settings', {})
        return {
            'sensors': ordered_sensors,
            'alarmState': alarm_state,
            'alarmArmed': alarm_state in ('armed', 'triggered', 'pending'),
            'inEntryDelay': self.in_entry_delay,
            'exitDelay': parse_int(settings_cfg.get('exit_delay', 0), 0),
            'entryDelay': parse_int(settings_cfg.get('entry_delay', 30), 30),
            'siren': {
                'pin': parse_int(serene_cfg.get('pin', 14), 14),
                'enable': parse_bool(serene_cfg.get('enable', False))
            }
        }

    def getAlarmState(self) -> Dict[str, str]:
        return {"state": self.settings.get('settings', {}).get('alarmState', 'disarmed')}

    def getSensorsLog(self, **args) -> Dict[str, Any]:
        return self.mylogs.getSensorsLog(**args)

    def setLogFilters(self, limit: Any, logtypes: Any) -> None:
        self.mylogs.setLogFilters(limit, logtypes)

    def getNotifiersStatus(self) -> Dict[str, Any]:
        return self.mynotify.status()

    def getSettings(self, set_topic: str) -> Any:
        return self.settings.get(set_topic, {})

    def setSettings(self, message: Dict[str, Any]) -> None:
        """Update settings dynamically for any section."""
        changed_any = False
        for msg_topic, msg_values in message.items():
            if not isinstance(msg_values, dict):
                continue
            if msg_topic not in self.settings:
                self.settings[msg_topic] = {}
            changed_topic = False
            for val_topic, set_value in msg_values.items():
                current_val = self.settings[msg_topic].get(val_topic)
                if current_val != set_value:
                    self.settings[msg_topic][val_topic] = set_value
                    changed_topic = True
                    changed_any = True
            if changed_topic:
                self.mylogs.writeLog("user_action", f"Settings for {msg_topic} updated")

        if changed_any:
            self.writeNewSettingsToFile(self.settings)
            if hasattr(self, 'mynotify'):
                threading.Thread(target=self.mynotify.settings_update, args=(self.settings,), daemon=True).start()

    def setSensorState(self, sensorUUID: str, state: bool) -> None:
        """Enable or disable (arm/bypass) a specific sensor."""
        if sensorUUID not in self.settings.get('sensors', {}):
            return
        self.settings['sensors'][sensorUUID]['enabled'] = bool(state)
        self.writeNewSettingsToFile(self.settings)

        state_str = "Activated" if state else "Deactivated"
        sensor_name = self.settings['sensors'][sensorUUID].get('name', sensorUUID)
        self.mylogs.writeLog("user_action", f"{state_str} sensor: {sensor_name}")
        self.mynotify.updateUI('sensorsChanged', self.getSensorsArmed())

    def setSensorsZone(self, zones: List[str]) -> None:
        """Filter enabled sensors based on matching zone tags."""
        zones_lower = [str(z).strip().lower() for z in zones]
        for _, s_val in self.settings.get('sensors', {}).items():
            s_zones = s_val.get('zones', [])
            if isinstance(s_zones, str):
                s_zones = [s_zones]
            s_zones_lower = [str(z).strip().lower() for z in s_zones]
            if not set(s_zones_lower).isdisjoint(zones_lower):
                s_val['enabled'] = True
            else:
                s_val['enabled'] = False
        self.mynotify.updateUI('sensorsChanged', self.getSensorsArmed())
        self.writeNewSettingsToFile(self.settings)

    def addSensor(self, sensorValues: Dict[str, Any]) -> None:
        """Add or update a sensor."""
        logger.info("%sNew/Updated Sensor: %s%s", bcolors.WARNING, sensorValues, bcolors.ENDC)
        key = next(iter(sensorValues))
        s_data = sensorValues[key]
        s_data.setdefault('enabled', True)
        s_data.setdefault('online', True)
        s_data.setdefault('alert', False)

        if key == 'undefined' or not key:
            sensorUUID = str(uuid.uuid4())
            self.settings.setdefault('sensors', {})[sensorUUID] = s_data
        else:
            sensorUUID = key
            self.sensors.del_sensor(sensorUUID)
            self.settings.setdefault('sensors', {})[sensorUUID] = s_data

        self.writeNewSettingsToFile(self.settings)
        self.sensors.add_sensors(self.settings)
        self.mynotify.updateMQTT()
        self.mynotify.updateUI('sensorsChanged', self.getSensorsArmed())

    def delSensor(self, sensorUUID: str) -> None:
        """Delete a sensor."""
        self.sensors.del_sensor(sensorUUID)
        self.settings.get('sensors', {}).pop(sensorUUID, None)
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.updateMQTT()
        self.mynotify.updateUI('sensorsChanged', self.getSensorsArmed())

    def setSensorStatus(self, name: str, status: str) -> bool:
        """Simulate or externally update a sensor status by name."""
        found = False
        name_clean = name.lower().replace(' ', '_')
        for s_id, s_val in self.settings.get('sensors', {}).items():
            s_name = s_val.get('name', '').lower().replace(' ', '_')
            if s_name == name_clean:
                found = True
                if status == 'on':
                    self.sensorAlert(s_id)
                elif status == 'off':
                    self.sensorStopAlert(s_id)
                elif status == 'error':
                    self.sensorError(s_id)
        return found

    def cleanup(self) -> None:
        """Clean up timers and background threads."""
        self._cancel_timers()
        if hasattr(self, 'sensors'):
            for s_info in self.sensors.get_all_sensors().values():
                try:
                    s_info['obj'].del_sensor()
                except Exception:
                    pass
        if hasattr(self, 'mynotify'):
            self.mynotify.cleanup()
