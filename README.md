# AlarmPI

AlarmPI is a home alarm system based on Raspberry PI controlling PIR and Door sensors. It uses a web interface which is able to activate or deactivate the alarm and also disable or enable sensors. You can also change some settings like changing name of sensor, adding sensors and changing pins of both the serene and sensors.

When the alarm is active and it detects change in the sensors, the application enables the Serene, sends Mail and calls through VoIP provider. All those events can be activated/deactivated through settings.json

## Installation
```
sudo git clone https://github.com/bkbilly/AlarmPI.git
cd AlarmPI/
sudo cp settings_template.json settings.json
sudo cp play_template.wavplay.wav
sudo pip install -r requirements.txt
```

## Run on Raspberry Pi Boot
Edit the `/etc/rc.local` and before exit 0 add this line: `python /home/pi/AlarmPI/alarmpi.py &`



## settings.json

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
* `sensors.active` (bool) Activate the specific sensor
* `sensors.name` (str) Name of the specific sensor
* `sensors.pin` (int) Input pin of the specific sensor
* `settings.alarmArmed` (bool) If true, activate the alarm
* `settings.timezone` (str) The timezone for the log file based on pytz

## SipCall (VoIP)

I have built the sipcall for the Raspberry Pi, so hopefully you will not have to build it yourself.
To test it, execute this replacing the (myserver, myusername, mypassword, mynumbertocall):

`./sipcall -sd myserver -su myusername -sp mypassword -pn mynumbertocall -s 1 -mr 2 -ttsf ../play.wav`

## Contributing

1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request :D
