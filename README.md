# AlarmPI ![Build Status](https://github.com/bkbilly/AlarmPI/workflows/build/badge.svg) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/bkbilly/AlarmPI)](https://github.com/bkbilly/AlarmPI/releases/latest)

AlarmPI is a home security system based on Raspberry Pi. It supports wired sensors (PIR, magnetic door/window contacts, smoke, vibration) and wireless sensors through MQTT or Hikvision smart cameras. It is controlled via a Web UI, an Android Application, or through HTTP & MQTT messages.

When the alarm detects movement or an emergency event, it supports:
 * 🔊 Enabling physical GPIO and HTTP sirens
 * 📱 Sending instant push notifications (Browser Web Push, Telegram, NTFY, Pushover, Webhooks)
 * ✉️ Sending email alerts
 * 📞 Automated VoIP phone calls (SIP)
 * 📡 Sending MQTT messages & Home Assistant state updates

Written in Python 3. It also supports multiple users by editing the `server.json` file.

---

## Installation

### Quick Install & Update
With this command on your terminal you can install and update the application with the latest release:
```bash
bash <(curl -s "https://raw.githubusercontent.com/bkbilly/AlarmPI/master/install.sh")
```

### Manual Installation
```bash
git clone https://github.com/bkbilly/AlarmPI.git
cd AlarmPI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```
Open your browser at `http://localhost:5000` (Default credentials: `test1` / `secret`).

---

## Usage

### Web UI
The Web Interface has all the features needed to configure and monitor your home security:
* Real-time sensor statuses, interactive zone arming/disarming, and activity logs.
* Visual timeline to analyze sensor event patterns over hours or days.
* Smart arming controls: exit/entry delays, door chimes, arm-after-closing, and automatic sensor bypass.
* Works directly as a smartphone app from your mobile browser: *Add to Home screen* (PWA).

### Push & Browser Notifications
AlarmPI supports instant alerts across multiple notification providers:
* **Browser Web Push**: Direct notifications to your phone, tablet, or PC browser with background delivery and vibration (one-click subscription in Settings).
* **Telegram Bot**: Instant rich alerts to your Telegram chat or group.
* **NTFY**: Free, open-source push alerts via `ntfy.sh` or self-hosted servers.
* **Pushover**: High-priority siren audio alerts directly on mobile devices.
* **Custom Webhooks**: Connect to Discord, Slack, or custom automation endpoints.

### Mobile Application
The Android application is lightweight and fast:
* **Google Play**: [Download on Play Store](https://play.google.com/store/apps/details?id=bkbilly.alarmpi)
* **Source Code**: [AlarmPI-Android on GitHub](https://github.com/bkbilly/AlarmPI-Android)

### Home-Assistant
AlarmPI seamlessly integrates with Home Assistant using **MQTT Auto-Discovery**. Simply enable the **Home Assistant Auto-Discovery** switch in the AlarmPI **MQTT** settings pane:
* 🛡️ **Alarm Control Panel**: Automatically creates the alarm entity in Home Assistant with Arm Home, Arm Away, Arm Night, Disarm, and optional PIN code support.
* 🔌 **Binary Sensors**: Automatically discovers all configured sensors with their appropriate device classes (doors, windows, motion, smoke, tamper, vibration).
* 🔊 **Siren Control**: Automatically creates a siren entity for triggering and silencing alarms directly from Home Assistant.

---

## Sensors

AlarmPI supports multiple sensor types:
* **Wired GPIO**: Connect physical PIR sensors, magnetic reed switches, and buttons to Raspberry Pi GPIO pins with configurable hardware debouncing and glitch filtering.
* **Hikvision Cameras**: Connect to Hikvision IP cameras or NVRs to automatically discover and trigger alerts from smart video analytics (Line Crossing, Field Intrusion, Motion Detection).
* **MQTT Sensors**: Subscribe to wireless sensor topics like Zigbee2MQTT with custom payload matching (e.g. `message['contact'] == False`).
* **Virtual Sensors**: Trigger sensor state updates remotely via HTTP requests.

---

## API

### HTTP
  * `https://test1:secret@example.com:5000/setSensorStatus?name=test1&state=off`
  * `https://test1:secret@example.com:5000/activateAlarmOnline`
  * `https://test1:secret@example.com:5000/deactivateAlarmOnline`
  * `https://test1:secret@example.com:5000/stopSiren`
  * `https://test1:secret@example.com:5000/startSiren`
  * `https://example.com:5000/login?username=test1&password=secret`

### MQTT
These are the MQTT topics used by AlarmPI:
  * `home/alarm/set` [`ARM_HOME`, `ARM_AWAY`, `ARM_NIGHT`, `DISARM`, `PENDING`]
  * `home/alarm/set/siren` `{"state": "ON"}` or `{"state": "OFF"}`
  * `home/alarm/sensor/<sensor_name>` [`off`, `on`, `error`]
  * `home/alarm` [`armed_away`, `armed_home`, `disarmed`, `pending`, `triggered`]

Supports custom message subscriptions on MQTT sensors by configuring the topic and payload condition (e.g. for Zigbee2MQTT):
 * `message['contact'] == False`

### IFTTT / Webhooks
You can trigger arm/disarm actions using webhooks:
* `https://test1:secret@example.com:5000/activateAlarmOnline`
* `https://test1:secret@example.com:5000/deactivateAlarmOnline`

### SipCall (VoIP)
AlarmPI includes a prebuilt `sipcall` binary for Raspberry Pi to place automated voice calls on alarm breach.
To test it from the command line:
```bash
./voip/sipcall -sd myserver -su myusername -sp mypassword -pn mynumbertocall -s 1 -mr 2 -ttsf play_template.wav
```
