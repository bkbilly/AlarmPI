# AlarmPI ![Build Status](https://github.com/bkbilly/AlarmPI/workflows/build/badge.svg) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/bkbilly/AlarmPI)](https://github.com/bkbilly/AlarmPI/releases/latest)

**AlarmPI** is a modern, modular home security and automation system designed for Raspberry Pi and Linux systems. It features a fully dynamic, plugin-based architecture for both **Sensors** and **Notifiers**, backed by a sleek real-time Web dashboard and Home Assistant integration.

---

## Key Features

- **Folder-Based Modular Plugins**:
  - **Notifiers** (`alarmcode/notifiers/`): Drop in any `.py` file to automatically register new notification channels (e.g., Telegram, Pushover, Discord, Webhooks) without editing core code.
  - **Sensors** (`alarmcode/sensors/`): Easily add custom sensor drivers (GPIO, Hikvision cameras, MQTT, Virtual/Webhooks).
- **Smart Arming & Sensor Behaviors**:
  - **Arm After Closing**: Instantly arms the system as soon as entry/exit doors close without waiting for remaining exit delay.
  - **Auto-Bypass Open Sensors (Force Arm)**: Automatically bypasses open windows/doors upon arming without blocking system arming.
  - **Entry & Exit Delays**: Configurable grace periods with live countdown and audio warning beeps.
  - **Door Chime**: Plays gentle browser & system chimes when perimeter doors open while disarmed.
  - **Rich Sensor Behaviors**: `Normal (Armed only)`, `Entry/Exit (Delay Countdown)`, `Instant Breach`, `24-Hours (Always Active: Smoke/Tamper)`, and `Chime`.
  - **Siren Auto-Cutoff**: Configurable siren timeout to prevent battery drain and comply with noise ordinances.
- **Dynamic Backend Settings**: All plugin schemas and configuration parameters are defined on the backend and dynamically rendered on the frontend UI.
- **Modern Hardware & OS Compatibility**: Compatible with Python 3.10 – 3.14+, Raspberry Pi OS (Debian Bookworm / Pi 5), with transparent hardware/virtual GPIO fallback for development and testing.
- **Real-Time Web Dashboard**: Responsive dark-mode interface with live Socket.IO state synchronization, interactive zone arming/disarming, and visual sensor timelines.
- **Home Assistant & MQTT Discovery**: Instant integration with Home Assistant via MQTT Discovery (Alarm Control Panel, Siren, Binary Sensors).

---

## Modular Plugin Architecture

### Adding a Notification Plugin
Create a new file in [`alarmcode/notifiers/`](file:///home/bkbilly/Documents/AlarmPI/alarmcode/notifiers/) (e.g. `telegram.py`):

```python
from alarmcode.notifiers.base import BaseNotifier, NotifierField

class TelegramNotifier(BaseNotifier):
    name = "telegram"
    display_name = "Telegram Bot"
    description = "Send instant alert messages and photos via Telegram Bot API."
    icon = "send"

    @classmethod
    def define_fields(cls):
        return [
            NotifierField("enable", "Enable Telegram", "boolean", default=False),
            NotifierField("bot_token", "Bot Token", "password", default=""),
            NotifierField("chat_ids", "Chat IDs", "list", default=[], placeholder="1234567, 9876543"),
        ]

    def on_intruder_alert(self, alert_info=None):
        if self.is_enabled():
            # Send alert to Telegram...
            pass
```
*AlarmPI will automatically discover your plugin, add its configuration schema to the backend, and render its controls and live status badge in the Settings UI!*

---

### Adding a Sensor Plugin
Create a new file in [`alarmcode/sensors/`](file:///home/bkbilly/Documents/AlarmPI/alarmcode/sensors/) (e.g. `zigbee.py`):

```python
from alarmcode.sensors.base import BaseSensorPlugin, SensorField

class ZigbeeSensorPlugin(BaseSensorPlugin):
    sensor_type = "Zigbee"
    display_name = "Zigbee Device"
    description = "Monitor Zigbee door sensors and PIR detectors."

    @classmethod
    def define_fields(cls):
        return [
            SensorField("device_ieee", "Device IEEE Address", "string", required=True),
        ]
```

---

## Installation & Running

```bash
# Clone the repository
git clone https://github.com/bkbilly/AlarmPI.git
cd AlarmPI

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the server
python3 run.py
```

Open your browser at `http://localhost:5000` (Default credentials: `test1` / `secret`).
