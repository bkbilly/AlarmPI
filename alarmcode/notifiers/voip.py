#!/usr/bin/env python3
"""VoIP Call Notifier Plugin for AlarmPI."""

import logging
import os
import subprocess
import sys
from typing import Any, Dict, List

from alarmcode.notifiers.base import BaseNotifier, NotifierField
from alarmcode.utils import parse_bool, parse_int

logger = logging.getLogger('alarmpi')


class VoIPNotifier(BaseNotifier):
    """Places automated VoIP phone calls via SIP using sipcall utility."""

    name = "voip"
    display_name = "VoIP Calls"
    description = "Dial emergency phone numbers via SIP on alarm breach."
    icon = "phone-call"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sipcall_bin = os.path.join(self.wd, "voip", "sipcall")

    @classmethod
    def define_fields(cls) -> List[NotifierField]:
        return [
            NotifierField("domain", "SIP Domain / Server", "string", default="", placeholder="sip.provider.com"),
            NotifierField("username", "SIP Username", "string", default="", placeholder="sip_user"),
            NotifierField("password", "SIP Password", "password", default=""),
            NotifierField("numbersToCall", "Phone Numbers to Dial", "list", default=[], placeholder="+1234567890, +0987654321"),
            NotifierField("timesOfRepeat", "Repeat Count", "number", default=2, help_text="Number of times to replay audio message"),
        ]

    def on_intruder_alert(self, alert_info: Any = None) -> None:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return

        domain = str(cfg.get("domain", ""))
        user = str(cfg.get("username", ""))
        pwd = str(cfg.get("password", ""))
        repeat = str(cfg.get("timesOfRepeat", "2"))
        numbers = cfg.get("numbersToCall", [])

        if isinstance(numbers, str):
            numbers = [n.strip() for n in numbers.replace(",", " ").split() if n.strip()]

        if not os.path.exists(self.sipcall_bin):
            logger.warning("sipcall binary not found at %s", self.sipcall_bin)
            return

        play_wav = os.path.join(self.wd, "play.wav")
        if not os.path.exists(play_wav):
            play_wav = os.path.join(self.wd, "play_template.wav")

        for num in numbers:
            try:
                num_str = str(num).strip()
                if self.mylogs:
                    self.mylogs.writeLog("alarm", f"Calling {num_str}")

                cmd = [
                    self.sipcall_bin,
                    "-sd", domain,
                    "-su", user,
                    "-sp", pwd,
                    "-pn", num_str,
                    "-s", "1",
                    "-mr", repeat,
                    "-ttsf", play_wav
                ]
                logger.info("Executing VoIP command: %s", " ".join(cmd))
                proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                proc.communicate(timeout=60)

                if self.mylogs:
                    self.mylogs.writeLog("alarm", f"Call to {num_str} ended")
            except Exception:
                logger.exception("Error executing VoIP call to %s", num)

    def get_status(self) -> bool:
        cfg = self.settings.get(self.name, {})
        if not parse_bool(cfg.get("enable")):
            return False
        return os.path.exists(self.sipcall_bin)
