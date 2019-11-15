# AlarmPI ![Build Status](https://github.com/bkbilly/AlarmPI/workflows/build/badge.svg)

AlarmPI is a home security system based on Raspberry PI. It supports wired sensors (PIR, Magnetic etc.) and wireless through MQTT or Hikvision. It is controlled with a Web UI, a Android Application, or through HTTP & MQTT messages. When the alarm detects movement, it supports the following events:
 * Enables the Serene
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

### MQTT
These are the possible mqtt messages. First you will have to setup the MQTT state_topc & command_topic.
  * `home/alarm/set` [ARM_HOME,ARM_AWAY,ARM_NIGHT,DISARM]
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


## Configuration
### Configuration Explained `server.json`
* `ui.https` (bool) Use HTTPs
* `ui.port` (bool) The port
* `users[user]` (str) The username for login
* `users[user].pw` (str) the password for login
* `users[user].logfile` (str) The name of the log file
* `users[user].settings` (str) The name of the settings file


### Configuration Explained `settings.json`
* `serene.enable` (bool) Enable serene activation
* `serene.pin` (int) Output pin of the serene
* `mail.enable` (bool) Enable mail alerts
* `mail.smtpServer` (str) SMTP of your mail
* `mail.smtpPort` (int) SMTP Port of your mail
* `mail.username` (str) Username of your mail
* `mail.password` (str) Password of your mail
* `mail.recipients` (list str) List of recipents. eg. ["mail1@example.com", "mail2@example.com"]
* `mail.messageSubject` (str) Subject of the sent mail
* `mail.messageBody` (str) Body message of the sent mail
* `voip.enable` (bool) Enable VoIP alerts
* `voip.domain` (str) VoIP server
* `voip.username` (str) VoIP username
* `voip.password` (str) VoIP password
* `voip.numbersToCall` (list str) List of numbers to call. eg. ["3849392849", "3582735872"]
* `voip.timesOfRepeat` (str) How many times the recorded message is played
* `sensors[uuid]` (str) The specific ID of the sensor (auto created)
* `sensors[uuid].name` (str) Name of the sensor
* `sensors[uuid].type` (str) The type of the sensor (GPIO, MQTT, Hikvision)
* `sensors[uuid].enabled` (bool) Set the sensor as Active/Inactive
* `sensors[uuid].online` (bool) The online status of the sensor
* `sensors[uuid].alert` (bool) Automatically created. Status of the sensor
* `sensors[uuid].pin` (str) [GPIO] Input pin of the sensor
* `sensors[uuid].ip` (str) [Hikvision] IP of the Hikvision camera
* `sensors[uuid].user` (str) [Hikvision] Username of the Hikvision camera
* `sensors[uuid].pass` (str) [Hikvision] Password of the Hikvision camera
* `sensors[uuid].state_topic` (str) [MQTT] The unique topic for the sensor
* `sensors[uuid].message_alert` (str) [MQTT] The message for alert
* `sensors[uuid].message_noalert` (str) [MQTT] The message for stop alert
* `sensors[uuid].zones` (list str) Set zones to massively activate the desired sensors
* `mqtt.enable` (bool) Enable the mqtt server
* `mqtt.authentication` (bool) Use authentication for the mqtt server
* `mqtt.state_topic` (str) The MQTT topic for the state (disarmed, triggered, armed_away)
* `mqtt.command_topic` (str) The MQTT topic for the commands (DISARM, ARM_AWAY)
* `mqtt.host` (str) IP Address of the mqtt server
* `mqtt.port` (int) Port of the mqtt server
* `mqtt.username` (str) Username of the mqtt server if authentication is true
* `mqtt.password` (str) Passwrd of the mqtt server if authentication is true
* `mqtt.homeassistant` (bool) Automatically create sensors on HomeAssistant
* `settings.alarmArmed` (bool) If true, activate the alarm
* `settings.alarmTriggered` (bool) If true, there is an intruder
* `settings.timezone` (str) The timezone for the log file based on pytz

## Contributing
1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request :D
