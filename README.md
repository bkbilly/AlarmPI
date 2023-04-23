# AlarmPI ![Build Status](https://github.com/bkbilly/AlarmPI/workflows/build/badge.svg) [![GitHub release (latest by date)](https://img.shields.io/github/v/release/bkbilly/AlarmPI)](https://github.com/bkbilly/AlarmPI/releases/latest)

AlarmPI is a home security system based on Raspberry PI. It supports wired sensors (PIR, Magnetic etc.) and wireless through MQTT or Hikvision. It is controlled with a Web UI, a Android Application, or through HTTP & MQTT messages. When the alarm detects movement, it supports the following events:
 * Enables the Siren
 * Send Mail
 * VoIP Calls
 * Send MQTT message

It is written in python and supports both python 2.7 & python 3.6. There is also the option of having more than one user by editing the server.json file accordingly.


## Installation
With this command on your terminal you can install and update the application with my latest commit.
```bash
bash <(curl -s "https://raw.githubusercontent.com/bkbilly/AlarmPI/master/install.sh")
```

## Usage
### Web UI
The Web Interface of the alarm has all the features that are needed to configure and use the home security. It supports real time events of the sensors, the logs and their status.
It also works as an smartphone application from the browser: _Add to Home screen_

### Mobile Application
The android application is very light and fast and it is recomended for the phone, but it has no real time updates.
You can download it from here: [Play Store](https://play.google.com/store/apps/details?id=bkbilly.alarmpi)

The source code for the application is here: https://github.com/bkbilly/AlarmPI-Android

### Snips
Through voice commands from Snips platform using this application: [snips console](https://console.snips.ai/store/en/skill_G4V82q5rb2)

### Home-Assistant
It is also controlled with MQTT commands with the Home-Assistant component: 'MQTT Alarm Control Panel'.
On Home-Assistant the configuration is like so:
```yaml
alarm_control_panel:
  - platform: mqtt
    name: "AlarmPI"
    state_topic: "home/alarm"        # The State Topic from AlarmPI
    command_topic: "home/alarm/set"  # The Command Topic from AlarmPI
    payload_arm_home: "ARM_HOME"     # This is not used
    payload_arm_away: "ARM_AWAY"
```

## API
### HTTP
  * `https://admin:secret@example.com:5000/setSensorStatus?name=test1&state=off`
  * `https://admin:secret@example.com:5000/activateAlarmZone?zones=home,away`
  * `https://admin:secret@example.com:5000/activateAlarmOnline`
  * `https://admin:secret@example.com:5000/deactivateAlarmOnline`
  * `https://admin:secret@example.com:5000/stopSiren`
  * `https://admin:secret@example.com:5000/startSiren`
  * `https://example.com:5000/login?username=admin&password=secret`

### MQTT
These are the possible mqtt messages. First you will have to setup the MQTT state_topc & command_topic.
  * `home/alarm/set` [ARM_HOME,ARM_AWAY,ARM_NIGHT,DISARM,PENDING]
  * `home/alarm/set/siren` {"state": "ON"}
  * `home/alarm/set/sensor/test1` [off,online]
  * `home/alarm/sensor/test1` [off,on,error]
  * `home/alarm` [armed_away,disarmed,triggered]

Supports custom messages subscriptions on MQTT Sensors by filling the appropriate information about topic and payload on sensor settings. This can be used for cases like zigbee2mqtt so that zigbee devices can be used. The payload must be a python function with the payload stored as `message` like this:
 * message['contact'] == 'ON'

### IFTTT
It can also be used with IFTTT using the Webhooks module like this:
`https://admin:secret@example.com:5000/activateAlarmOnline`
`https://admin:secret@example.com:5000/deactivateAlarmOnline`
>My personal favourite is to control it with Google Assistant.

## SipCall (VoIP)
I have built the sipcall for the Raspberry Pi, so hopefully you will not have to build it yourself.
To test it, execute this replacing the (myserver, myusername, mypassword, mynumbertocall):

`./sipcall -sd myserver -su myusername -sp mypassword -pn mynumbertocall -s 1 -mr 2 -ttsf ../play.wav`
