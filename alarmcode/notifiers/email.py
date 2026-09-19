#!/usr/bin/env python3
"""Email / SMTP Notifier Plugin for AlarmPI."""

from email.mime.text import MIMEText
import logging
import smtplib
from typing import Any, Dict, List

from alarmcode.notifiers.base import BaseNotifier, NotifierField
from alarmcode.utils import parse_bool, parse_int

logger = logging.getLogger('alarmpi')


class EmailNotifier(BaseNotifier):
    """Sends email alerts with sensor breach history via SMTP."""

    name = "mail"
    display_name = "Email (SMTP)"
    description = "Send incident reports and alert emails when the alarm is triggered."
    icon = "mail"

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        return [
            NotifierField("smtpServer", "SMTP Server", "string", default="smtp.gmail.com", placeholder="smtp.gmail.com"),
            NotifierField("smtpPort", "SMTP Port", "number", default=587),
            NotifierField("username", "SMTP Username / Email", "string", default="", placeholder="user@gmail.com"),
            NotifierField("password", "SMTP Password / App Key", "password", default=""),
            NotifierField("recipients", "Recipients", "list", default=[], placeholder="user1@domain.com, user2@domain.com"),
            NotifierField("messageSubject", "Subject Template", "string", default="🚨 Home Security Alert"),
            NotifierField("messageBody", "Body Template", "string", default="Alarm breach detected!"),
        ]

    def on_intruder_alert(self, alert_info: Any = None) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return

        try:
            mail_user = cfg.get("username", "")
            mail_pwd = cfg.get("password", "")
            smtp_server = cfg.get("smtpServer", "smtp.gmail.com")
            smtp_port = parse_int(cfg.get("smtpPort"), 587)
            recipients = cfg.get("recipients", [])

            if isinstance(recipients, str):
                recipients = [r.strip() for r in recipients.replace(",", " ").split() if r.strip()]

            if not mail_user or not recipients:
                logger.warning("Email notifier enabled but username or recipients missing")
                return

            body = cfg.get("messageBody", "Alarm Alert")
            if self.mylogs:
                logs_res = self.mylogs.getSensorsLog(fromText="Alarm activated")
                triggered_logs = logs_res.get("log", [])
                if triggered_logs:
                    body += "<br><br><b>Recent Event Log:</b><br>" + "<br>".join(reversed(triggered_logs))

            msg = MIMEText(body, "html")
            msg["Subject"] = cfg.get("messageSubject", "Alarm Alert")
            msg["From"] = mail_user
            msg["To"] = ", ".join(recipients)

            with smtplib.SMTP(smtp_server, smtp_port, timeout=3) as server:
                server.ehlo()
                server.starttls()
                server.login(mail_user, mail_pwd)
                server.sendmail(mail_user, recipients, msg.as_string())

            if self.mylogs:
                self.mylogs.writeLog("alarm", f"Mail sent to: {', '.join(recipients)}")
            logger.info("Email alert successfully sent to %s", recipients)
        except Exception:
            logger.exception("Failed to send alert email:")

    def get_status(self) -> bool:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return False
        return bool(cfg.get("username") and cfg.get("password") and cfg.get("smtpServer"))
