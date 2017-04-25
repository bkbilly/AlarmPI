# AlarmPI

AlarmPI is a home alarm system based on Raspberry PI controlling PIR sensors, Door sensors or any other wired sensor. It is controlled with a Web UI, or a Android Application using HTTPS. When the alarm detects movement, it supports the following events:
 * Enables the Serene
 * Send Mail
 * VoIP Calls

## Usage

### Web UI
The Web Interface of the alarm has all the features that are needed to configure and use the home security. It supports real time events of the sensors, the logs and their status.
It also works as an smartphone application from the browser: _Add to Home screen_

### Mobile Application
The android application is very light and fast and it is recomended for the phone, but it has no real time updates.
You can download it from here: [Play Store](https://play.google.com/store/apps/details?id=bkbilly.alarmpi)

The source code for the application is here: https://github.com/bkbilly/AlarmPI-Android


### IFTTT
It can also be used with IFTTT using the Maker module like this:
`https://admin:secret@example.com:5000/activateAlarmOnline`
`https://admin:secret@example.com:5000/deactivateAlarmOnline`
>My personal favourite is to control it with Google Assistant.


## Installation
```bash
sudo git clone https://github.com/bkbilly/AlarmPI.git /opt/AlarmPI/
cd /opt/AlarmPI/
sudo cp settings_template.json settings.json
sudo cp play_template.wavplay.wav
sudo pip install -r requirements.txt
sudo chmod +x /opt/AlarmPI/alarmpi
sudo ln -s /opt/AlarmPI/alarmpi /etc/init.d/alarmpi
sudo update-rc.d alarmpi defaults
sudo service alarmpi start

```

### Run on Raspberry Pi Boot
Edit the `/etc/rc.local` and before exit 0 add this line: `python /opt/AlarmPI/alarmpi.py &`


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
* `sensors[pin]` (str) Input pin of the specific sensor
* `sensors[pin].active` (bool) Activate the specific sensor
* `sensors[pin].name` (str) Name of the specific sensor
* `sensors[pin].alert` (bool) Automatically created. Status of the sensor
* `settings.alarmArmed` (bool) If true, activate the alarm
* `ui.username` (str) Username for the Web UI
* `ui.password` (str) Password for the Web UI
* `ui.https` (bool) Use TLS encryption for the Web UI
* `ui.port` (int) TCP port for the Web UI
* `ui.timezone` (str) The timezone for the log file based on pytz

### SipCall (VoIP)

I have built the sipcall for the Raspberry Pi, so hopefully you will not have to build it yourself.
To test it, execute this replacing the (myserver, myusername, mypassword, mynumbertocall):

`./sipcall -sd myserver -su myusername -sp mypassword -pn mynumbertocall -s 1 -mr 2 -ttsf ../play.wav`

## Contributing

1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request :D
