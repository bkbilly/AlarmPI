#!/usr/bin/env python3
"""Mobile & Browser Push Notifications Plugin for AlarmPI.

Supports instant push notifications via:
- Web Push (VAPID / RFC 8291 / RFC 8292 to Android, iOS, and desktop browsers)
- Telegram Bot (API)
- NTFY (ntfy.sh / self-hosted open-source push)
- Pushover
- Custom Webhooks (Discord, Slack, Home Assistant, generic HTTP POST)
"""

from datetime import datetime
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional
import requests

from alarmcode.notifiers.base import BaseNotifier, NotifierField
from alarmcode.utils import parse_bool
from alarmcode.webpush_helper import get_or_create_vapid_keys, send_webpush_to_all

logger = logging.getLogger('alarmpi')


class PushNotifier(BaseNotifier):
    """Dispatches instant mobile and browser alerts via Web Push, Telegram, NTFY, Pushover, or Webhooks."""

    name = "push"
    display_name = "Push Notifications"
    description = "Send instant alerts to mobile devices and browsers via Web Push, Telegram, NTFY, Pushover, or Webhook."
    icon = "bell"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vapid_pem_path: Optional[str] = None
        self.vapid_public_key: Optional[str] = None

    def setup(self, settings: Dict[str, Any]) -> None:
        super().setup(settings)
        try:
            self.vapid_pem_path, self.vapid_public_key = get_or_create_vapid_keys(self.wd)
        except Exception:
            logger.exception("Failed to initialize VAPID keys for Web Push:")

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        return [
            NotifierField(
                "service",
                "Push Provider",
                "select",
                default="webpush",
                options=[
                    {"value": "webpush", "label": "🌐 Browser Web Push (Direct to Device/Phone)"},
                    {"value": "telegram", "label": "✈️ Telegram Bot"},
                    {"value": "ntfy", "label": "🔔 NTFY (Free & Open-Source)"},
                    {"value": "pushover", "label": "📱 Pushover"},
                    {"value": "webhook", "label": "🌐 Custom Webhook (Discord / Slack / HA)"},
                    {"value": "all_configured", "label": "🚀 All Configured Services"},
                ],
                help_text="Select primary push notification service or send to all configured channels."
            ),
            # Telegram Bot
            NotifierField("telegram_token", "Telegram Bot Token", "password", default="", placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", help_text="Created via @BotFather on Telegram"),
            NotifierField("telegram_chat_id", "Telegram Chat ID", "string", default="", placeholder="12345678 or @channel", help_text="Chat or Channel ID (find with @userinfobot)"),

            # NTFY (ntfy.sh / self-hosted)
            NotifierField("ntfy_topic", "NTFY Topic / URL", "string", default="", placeholder="https://ntfy.sh/my_private_alarm_topic", help_text="Full NTFY topic URL (e.g. https://ntfy.sh/topic or https://ntfy.example.com/topic)"),

            # Pushover
            NotifierField("pushover_user_key", "Pushover User Key", "string", default="", placeholder="uQiRzpo4DXghDmr9Qnox015xxxxxx"),
            NotifierField("pushover_api_token", "Pushover App Token", "password", default="", placeholder="azGDORePK8gMaC0QOYAMyxxxxxx"),

            # Custom Webhook
            NotifierField("webhook_url", "Custom Webhook URL", "string", default="", placeholder="https://discord.com/api/webhooks/... or custom URL"),

            # Notification Event Options
            NotifierField("notify_on_alarm", "Notify on Alarm Breach", "boolean", default=True, help_text="Send high-priority alert when an alarm breach occurs"),
            NotifierField("notify_on_arm_disarm", "Notify on Arm / Disarm", "boolean", default=True, help_text="Send status updates when system is armed or disarmed"),
            NotifierField("notify_on_sensor", "Notify on 24-Hour Emergency Sensors", "boolean", default=True, help_text="Send alert if 24-hour smoke/fire/tamper sensors trigger"),
        ]

    def on_intruder_alert(self, alert_info: Optional[Dict[str, Any]] = None) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")) or not parse_bool(cfg.get("notify_on_alarm", True)):
            return

        sensor_name = "Unknown Sensor"
        zones = "All"
        if isinstance(alert_info, dict):
            sensor_name = alert_info.get("name", alert_info.get("sensor", "Unknown Sensor"))
            if alert_info.get("zones"):
                z = alert_info.get("zones")
                zones = ", ".join(z) if isinstance(z, list) else str(z)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = "🚨 ALARM TRIGGERED!"
        message = f"🚨 <b>ALARM INTRUDER ALERT!</b>\n\n📍 <b>Sensor:</b> {sensor_name}\n🏷️ <b>Zone:</b> {zones}\n⏱️ <b>Time:</b> {now}\n⚠️ <i>Siren has been activated!</i>"

        self._send_push_async(title=title, message=message, priority="urgent", is_alarm=True)

    def on_alarm_state_change(self, state: str) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")) or not parse_bool(cfg.get("notify_on_arm_disarm", True)):
            return

        if state == "triggered":
            return  # Handled by on_intruder_alert

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state_label = {
            "armed": "🛡️ Armed (Away)",
            "disarmed": "🔓 Disarmed",
            "pending": "⏳ Arming (Exit Delay Active)",
        }.get(state, state.capitalize())

        title = f"🛡️ AlarmPI: {state_label}"
        message = f"🛡️ <b>AlarmPI Security Status</b>\n\n<b>State:</b> {state_label}\n⏱️ <b>Time:</b> {now}"

        self._send_push_async(title=title, message=message, priority="normal", is_alarm=False)

    def on_sensor_update(self, sensor_uuid: str, sensor_data: Dict[str, Any], state: str) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")) or not parse_bool(cfg.get("notify_on_sensor", True)):
            return

        behavior = sensor_data.get("behavior", "normal")
        # Notify immediately for 24-hour emergency sensors (smoke, tamper)
        if behavior == "24hours" and state == "on":
            sensor_name = sensor_data.get("name", sensor_uuid)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            title = f"⚠️ 24-Hour Emergency Alert: {sensor_name}"
            message = f"⚠️ <b>24-Hour Emergency Sensor Alert!</b>\n\n📍 <b>Sensor:</b> {sensor_name}\n⏱️ <b>Time:</b> {now}\n🔥 <i>Sensor is active!</i>"
            self._send_push_async(title=title, message=message, priority="urgent", is_alarm=True)

    def _send_push_async(self, title: str, message: str, priority: str = "normal", is_alarm: bool = False) -> None:
        cfg = self.settings.get(self.name, {})
        threading.Thread(
            target=self._send_push_payload,
            args=(cfg, title, message, priority, is_alarm),
            daemon=True
        ).start()

    def _send_push_payload(self, cfg: Dict[str, Any], title: str, message: str, priority: str, is_alarm: bool) -> bool:
        service = str(cfg.get("service", "webpush")).lower().strip()
        success = False

        try:
            if service == "webpush":
                success = self._send_webpush(cfg, title, message, priority, is_alarm)
            elif service == "telegram":
                success = self._send_telegram(cfg, title, message)
            elif service == "ntfy":
                success = self._send_ntfy(cfg, title, message, priority, is_alarm)
            elif service == "pushover":
                success = self._send_pushover(cfg, title, message, is_alarm)
            elif service == "webhook":
                success = self._send_webhook(cfg, title, message, is_alarm)
            elif service == "all_configured":
                results = []
                if cfg.get("subscriptions"):
                    results.append(self._send_webpush(cfg, title, message, priority, is_alarm))
                if cfg.get("telegram_token") and cfg.get("telegram_chat_id"):
                    results.append(self._send_telegram(cfg, title, message))
                if cfg.get("ntfy_topic"):
                    results.append(self._send_ntfy(cfg, title, message, priority, is_alarm))
                if cfg.get("pushover_user_key") and cfg.get("pushover_api_token"):
                    results.append(self._send_pushover(cfg, title, message, is_alarm))
                if cfg.get("webhook_url"):
                    results.append(self._send_webhook(cfg, title, message, is_alarm))
                success = any(results) if results else False
            else:
                logger.warning("PushNotifier: Unknown service '%s'", service)
        except Exception:
            logger.exception("Failed to dispatch push notification via %s:", service)

        return success

    def _send_webpush(self, cfg: Dict[str, Any], title: str, message: str, priority: str, is_alarm: bool) -> bool:
        subscriptions = cfg.get("subscriptions", [])
        if not subscriptions:
            logger.debug("Web Push: No subscribed devices found.")
            return False

        if not self.vapid_pem_path or not os.path.exists(self.vapid_pem_path):
            self.vapid_pem_path, self.vapid_public_key = get_or_create_vapid_keys(self.wd)

        if not self.vapid_pem_path:
            logger.error("Web Push: VAPID private key path unavailable.")
            return False

        plain_msg = message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        payload = {
            "title": title,
            "message": plain_msg,
            "is_alarm": is_alarm,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "url": "/"
        }

        delivered, dead_endpoints = send_webpush_to_all(
            vapid_pem_path=self.vapid_pem_path,
            subscriptions=subscriptions,
            payload=payload,
            is_alarm=is_alarm
        )

        if dead_endpoints:
            self._prune_subscriptions(dead_endpoints)

        logger.info("Delivered Web Push alert to %d device(s).", delivered)
        return delivered > 0

    def _prune_subscriptions(self, dead_endpoints: List[str]) -> None:
        cfg = self.settings.get(self.name, {})
        subs = cfg.get("subscriptions", [])
        if not subs:
            return

        dead_set = set(dead_endpoints)
        new_subs = []
        for s in subs:
            ep = s.get("endpoint") if isinstance(s, dict) else None
            if not ep and isinstance(s, dict) and "subscription" in s:
                ep = s.get("subscription", {}).get("endpoint")
            if ep not in dead_set:
                new_subs.append(s)

        cfg["subscriptions"] = new_subs
        logger.info("Pruned %d expired Web Push device subscription(s). Remaining: %d", len(dead_set), len(new_subs))

    def _send_telegram(self, cfg: Dict[str, Any], title: str, message: str) -> bool:
        token = str(cfg.get("telegram_token", "")).strip()
        chat_id = str(cfg.get("telegram_chat_id", "")).strip()
        if not token or not chat_id:
            logger.warning("Telegram push enabled but token or chat_id is missing.")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        res = requests.post(url, json=payload, timeout=8)
        if res.status_code == 200:
            logger.debug("✅ Telegram push notification delivered successfully.")
            return True
        else:
            logger.error("Telegram API error (%d): %s", res.status_code, res.text)
            return False

    def _send_ntfy(self, cfg: Dict[str, Any], title: str, message: str, priority: str, is_alarm: bool) -> bool:
        topic_url = str(cfg.get("ntfy_topic", "")).strip()
        if not topic_url:
            logger.warning("NTFY push enabled but topic URL is missing.")
            return False

        if not topic_url.startswith("http://") and not topic_url.startswith("https://"):
            topic_url = f"https://ntfy.sh/{topic_url}"

        # Strip HTML tags for plain NTFY message
        plain_msg = message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        headers = {
            "Title": title,
            "Priority": "5" if is_alarm else "3",
            "Tags": "rotating_light,warning" if is_alarm else "shield,lock",
        }
        res = requests.post(topic_url, data=plain_msg.encode("utf-8"), headers=headers, timeout=8)
        return res.status_code in (200, 201)

    def _send_pushover(self, cfg: Dict[str, Any], title: str, message: str, is_alarm: bool) -> bool:
        user_key = str(cfg.get("pushover_user_key", "")).strip()
        api_token = str(cfg.get("pushover_api_token", "")).strip()
        if not user_key or not api_token:
            logger.warning("Pushover push enabled but user_key or api_token is missing.")
            return False

        plain_msg = message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
        url = "https://api.pushover.net/1/messages.json"
        payload = {
            "token": api_token,
            "user": user_key,
            "title": title,
            "message": plain_msg,
            "priority": 1 if is_alarm else 0,
            "sound": "siren" if is_alarm else "pushover",
        }
        res = requests.post(url, data=payload, timeout=8)
        return res.status_code == 200

    def _send_webhook(self, cfg: Dict[str, Any], title: str, message: str, is_alarm: bool) -> bool:
        webhook_url = str(cfg.get("webhook_url", "")).strip()
        if not webhook_url:
            logger.warning("Webhook push enabled but webhook_url is missing.")
            return False

        plain_msg = message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")

        # Format for Discord webhook if applicable
        if "discord.com/api/webhooks" in webhook_url or "discordapp.com/api/webhooks" in webhook_url:
            payload = {
                "username": "AlarmPI",
                "embeds": [{
                    "title": title,
                    "description": plain_msg,
                    "color": 15158332 if is_alarm else 3066993,
                    "footer": {"text": "AlarmPI Security System"}
                }]
            }
        # Format for Slack webhook
        elif "hooks.slack.com" in webhook_url:
            payload = {
                "text": f"*{title}*\n{plain_msg}"
            }
        else:
            payload = {
                "title": title,
                "message": plain_msg,
                "is_alarm": is_alarm,
                "timestamp": datetime.now().isoformat()
            }

        res = requests.post(webhook_url, json=payload, timeout=8)
        return res.status_code in (200, 201, 204)

    def get_status(self) -> bool:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return False
        service = str(cfg.get("service", "webpush")).lower().strip()
        if service == "webpush":
            return len(cfg.get("subscriptions", [])) > 0
        if service == "telegram":
            return bool(cfg.get("telegram_token") and cfg.get("telegram_chat_id"))
        if service == "ntfy":
            return bool(cfg.get("ntfy_topic"))
        if service == "pushover":
            return bool(cfg.get("pushover_user_key") and cfg.get("pushover_api_token"))
        if service == "webhook":
            return bool(cfg.get("webhook_url"))
        if service == "all_configured":
            return any([
                len(cfg.get("subscriptions", [])) > 0,
                bool(cfg.get("telegram_token") and cfg.get("telegram_chat_id")),
                bool(cfg.get("ntfy_topic")),
                bool(cfg.get("pushover_user_key") and cfg.get("pushover_api_token")),
                bool(cfg.get("webhook_url"))
            ])
        return False
