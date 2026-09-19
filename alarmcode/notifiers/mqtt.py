#!/usr/bin/env python3
"""MQTT & Home Assistant Notifier Plugin for AlarmPI."""

import json
import logging
import random
import threading
from typing import Any, Dict, List, Optional
import paho.mqtt.client as mqtt

from alarmcode.notifiers.base import BaseNotifier, NotifierField
from alarmcode.utils import parse_bool, parse_int, sanitize_sensor_name

logger = logging.getLogger('alarmpi')


class MQTTNotifier(BaseNotifier):
    """Integrates AlarmPI with MQTT brokers and Home Assistant MQTT Discovery."""

    name = "mqtt"
    display_name = "MQTT & HA"
    description = "Publish alarm state and sensor status to MQTT, with native Home Assistant auto-discovery."
    icon = "wifi"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_connected = False
        self.mqtt_client: Optional[mqtt.Client] = None
        self.version = "5.0"

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        return [
            NotifierField("host", "MQTT Broker Host", "string", default="127.0.0.1", placeholder="192.168.1.100"),
            NotifierField("port", "MQTT Broker Port", "number", default=1883),
            NotifierField("authentication", "Require Auth", "boolean", default=False),
            NotifierField("username", "MQTT Username", "string", default="", placeholder="mqtt_user"),
            NotifierField("password", "MQTT Password", "password", default=""),
            NotifierField("state_topic", "State Topic", "string", default="home/alarm", placeholder="home/alarm"),
            NotifierField("command_topic", "Command Topic", "string", default="home/alarm/set", placeholder="home/alarm/set"),
            NotifierField("homeassistant", "Home Assistant Auto-Discovery", "boolean", default=False, help_text="Broadcast MQTT Discovery payloads for Home Assistant"),
            NotifierField("code", "HA Disarm Code", "string", default="", placeholder="Optional PIN code for HA panel"),
        ]

    def setup(self, settings: Dict[str, Any]) -> None:
        super().setup(settings)
        cfg = self.settings.get(self.name, {})

        # Teardown existing client asynchronously
        if self.mqtt_client:
            old_client = self.mqtt_client
            self.mqtt_client = None
            self.is_connected = False
            def _stop(c):
                try:
                    c.loop_stop()
                    c.disconnect()
                except Exception:
                    pass
            threading.Thread(target=_stop, args=(old_client,), daemon=True).start()

        if not parse_bool(cfg.get("enable")):
            return

        try:
            client_id = f"alarmpi_{self.opts_ui.get('room', 'main')}_{random.randint(1000, 9999)}"
            if hasattr(mqtt, "CallbackAPIVersion"):
                self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
            else:
                self.mqtt_client = mqtt.Client(client_id=client_id, clean_session=False)

            if cfg.get("username") or cfg.get("password"):
                self.mqtt_client.username_pw_set(
                    username=cfg.get("username", ""),
                    password=cfg.get("password", "")
                )

            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_message = self._on_message

            host = cfg.get("host", "127.0.0.1")
            port = parse_int(cfg.get("port"), 1883)
            logger.info("Connecting to MQTT broker asynchronously at %s:%d", host, port)
            if hasattr(self.mqtt_client, "connect_async"):
                self.mqtt_client.connect_async(host, port, 60)
            else:
                threading.Thread(target=self.mqtt_client.connect, args=(host, port, 15), daemon=True).start()
            self.mqtt_client.loop_start()
        except Exception:
            logger.exception("Failed to initialize MQTT client:")
            self.is_connected = False

    def _on_connect(self, client, userdata, flags, *args):
        self.is_connected = True
        logger.info("MQTT connected successfully")
        cfg = self.settings.get(self.name, {})
        cmd_topic = cfg.get("command_topic", "home/alarm/set")
        state_topic = cfg.get("state_topic", "home/alarm")
        room = self.opts_ui.get("room", "main")

        # Subscriptions
        client.subscribe(cmd_topic)
        client.subscribe(f"{cmd_topic}/siren")
        client.subscribe(f"{cmd_topic}/available")

        device = {
            "identifiers": f"alarmpi-{room}",
            "name": f"AlarmPI-{room}",
            "sw_version": f"AlarmPI {self.version}",
            "model": "Raspberry PI Security System",
            "manufacturer": "AlarmPI"
        }

        # Subscribe to sensor commands & publish HA sensor discovery
        sensors = self.settings.get("sensors", {})
        for sensor_id, s_data in sensors.items():
            s_name = s_data.get("name", sensor_id)
            s_slug = sanitize_sensor_name(s_name)

            client.subscribe(f"{cmd_topic}/sensor/{s_slug}")

            # Custom sensor topic if specified
            if s_data.get("type", "").lower() == "mqtt" and s_data.get("topic"):
                client.subscribe(s_data["topic"])

            if parse_bool(cfg.get("homeassistant")):
                ha_sensor_topic = f"homeassistant/binary_sensor/{room}_{s_slug}/config"
                ha_config = {
                    "payload_on": "on",
                    "payload_off": "off",
                    "device_class": s_data.get("device_class", "door"),
                    "state_topic": f"{state_topic}/sensor/{s_name}",
                    "name": f"AlarmPI-{room}-{s_name}",
                    "unique_id": f"alarmpi_{room}_{s_slug}",
                    "device": device
                }
                client.publish(ha_sensor_topic, json.dumps(ha_config), retain=True, qos=1)

        # Home Assistant Alarm Control Panel Discovery
        if parse_bool(cfg.get("homeassistant")):
            ha_alarm_topic = f"homeassistant/alarm_control_panel/{room}/config"
            ha_alarm_config = {
                "name": f"AlarmPI {room}",
                "payload_arm_home": "ARM_HOME",
                "payload_arm_away": "ARM_AWAY",
                "payload_arm_night": "ARM_NIGHT",
                "state_topic": state_topic,
                "command_topic": cmd_topic,
                "unique_id": f"alarmpi_{room}",
                "device": device
            }
            if cfg.get("code"):
                ha_alarm_config["code"] = cfg["code"]
            client.publish(ha_alarm_topic, json.dumps(ha_alarm_config), retain=True, qos=1)

            # Siren discovery
            if parse_bool(self.settings.get("serene", {}).get("enable")):
                ha_siren_topic = f"homeassistant/siren/{room}/config"
                ha_siren_config = {
                    "name": f"AlarmPI Siren {room}",
                    "state_topic": f"{state_topic}/siren",
                    "command_topic": f"{cmd_topic}/siren",
                    "unique_id": f"alarmpi_{room}_siren",
                    "device": device
                }
                client.publish(ha_siren_topic, json.dumps(ha_siren_config), retain=True, qos=1)

    def _on_disconnect(self, client, userdata, *args):
        self.is_connected = False
        logger.warning("MQTT disconnected")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8").strip()
            topic = msg.topic
            cfg = self.settings.get(self.name, {})
            cmd_topic = cfg.get("command_topic", "home/alarm/set")
            state_topic = cfg.get("state_topic", "home/alarm")

            logger.info("MQTT received message on %s: %s", topic, payload)

            if topic == cmd_topic:
                if payload == "DISARM" and "deactivateAlarm" in self.callbacks:
                    self.callbacks["deactivateAlarm"]()
                elif payload == "ARM_HOME" and "activateAlarm" in self.callbacks:
                    self.callbacks["activateAlarm"]("home")
                elif payload == "ARM_AWAY" and "activateAlarm" in self.callbacks:
                    self.callbacks["activateAlarm"]("away")
                elif payload == "ARM_NIGHT" and "activateAlarm" in self.callbacks:
                    self.callbacks["activateAlarm"]("night")

            elif topic == f"{cmd_topic}/siren":
                try:
                    s_data = json.loads(payload) if "{" in payload else {"state": payload}
                    state_val = s_data.get("state", "").lower()
                    if state_val == "on" and "sirenStart" in self.callbacks:
                        self.callbacks["sirenStart"]()
                    elif state_val == "off" and "sirenStop" in self.callbacks:
                        self.callbacks["sirenStop"]()
                except Exception:
                    logger.exception("Error processing MQTT siren message")

            elif topic == f"{cmd_topic}/available":
                if self.mqtt_client:
                    self.mqtt_client.publish(f"{state_topic}/available", "online", retain=True, qos=1)

            elif f"{cmd_topic}/sensor/" in topic:
                sensor_slug = topic.replace(f"{cmd_topic}/sensor/", "")
                for s_id, s_val in self.settings.get("sensors", {}).items():
                    if sanitize_sensor_name(s_val.get("name", "")) == sensor_slug:
                        if payload.lower() in ("on", "1", "true"):
                            if "sensorAlert" in self.callbacks:
                                self.callbacks["sensorAlert"](s_id)
                        else:
                            if "sensorStopAlert" in self.callbacks:
                                self.callbacks["sensorStopAlert"](s_id)

            # Custom sensor topics
            for s_id, s_val in self.settings.get("sensors", {}).items():
                if s_val.get("topic") == topic:
                    try:
                        p_json = json.loads(payload)
                        payload_expr = s_val.get("payload", "True")
                        eval_res = eval(payload_expr, {"__builtins__": {}}, p_json)
                        if eval_res is True:
                            if "sensorStopAlert" in self.callbacks:
                                self.callbacks["sensorStopAlert"](s_id)
                        else:
                            if "sensorAlert" in self.callbacks:
                                self.callbacks["sensorAlert"](s_id)
                    except Exception:
                        logger.exception("Error evaluating custom MQTT sensor payload")
        except Exception:
            logger.exception("Error handling MQTT message:")

    def on_alarm_state_change(self, new_state: str) -> None:
        if not self.is_connected or not self.mqtt_client:
            return
        cfg = self.settings.get(self.name, {})
        state_topic = cfg.get("state_topic", "home/alarm")
        state_str = "armed_away" if new_state == "armed" else new_state
        self.mqtt_client.publish(state_topic, state_str, retain=True, qos=1)

    def on_sensor_update(self, sensor_uuid: str, sensor_data: Dict[str, Any], state: str) -> None:
        if not self.is_connected or not self.mqtt_client:
            return
        cfg = self.settings.get(self.name, {})
        state_topic = cfg.get("state_topic", "home/alarm")
        s_name = sensor_data.get("name", sensor_uuid)
        topic = f"{state_topic}/sensor/{s_name}"
        self.mqtt_client.publish(topic, state, retain=True, qos=1)

    def start_siren(self) -> None:
        if self.is_connected and self.mqtt_client:
            cfg = self.settings.get(self.name, {})
            self.mqtt_client.publish(f"{cfg.get('state_topic', 'home/alarm')}/siren", "ON", retain=True, qos=1)

    def stop_siren(self) -> None:
        if self.is_connected and self.mqtt_client:
            cfg = self.settings.get(self.name, {})
            self.mqtt_client.publish(f"{cfg.get('state_topic', 'home/alarm')}/siren", "OFF", retain=True, qos=1)

    def get_status(self) -> bool:
        return self.is_connected

    def cleanup(self) -> None:
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
            except Exception:
                pass
            self.mqtt_client = None
            self.is_connected = False
