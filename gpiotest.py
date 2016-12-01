import RPi.GPIO as GPIO
import time
import json
import threading
import time
import os

from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import smtplib
from email.mime.text import MIMEText

import logging
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)


class DoorSensor():

    """docstring for DoorSensor"""

    def __init__(self, jsonfile, logfile):
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Global Variables
        wd = os.path.dirname(os.path.realpath(__file__))
        self.jsonfile = os.path.join(wd, jsonfile)
        self.logfile = os.path.join(wd, logfile)
        self.enabledPins = []
        self.settings = self.ReadSettings(self.jsonfile)
        self.sensorsStatus = {'sensors': []}

        # Stop execution on exit
        self.setAlert = False
        self.kill_now = False

        # Init Alarm
        self.RefreshAlarmData(None)

        # Start checking for setting changes in a thread
        # thr = threading.Thread(
        #     target=self.CheckSettingsChanges, args=(self.RefreshAlarmData,))
        # thr.start()

    def RefreshAlarmData(self, inputPin):
        self.settings = self.ReadSettings(self.jsonfile)
        pinActive = False
        self.sensorsStatus = {'sensors': []}
        for sensor in self.settings["sensors"]:
            sensor["alert"] = False
            if sensor["active"] is True:
                pinActive = True
                # Enable the event change of the pin
                if sensor["pin"] not in self.enabledPins:
                    self.enabledPins.append(sensor["pin"])
                    GPIO.setup(sensor["pin"], GPIO.IN,
                               pull_up_down=GPIO.PUD_UP)
                    GPIO.remove_event_detect(sensor["pin"])
                    GPIO.add_event_detect(
                        sensor["pin"], GPIO.BOTH, callback=self.RefreshAlarmData)
                # Check for the pin status
                if GPIO.input(sensor["pin"]) == 1:
                    sensor["alert"] = True
                    if self.settings['settings']['alarmArmed'] is True and self.setAlert is False:
                        self.startSerene()
            # Create the list of the pins status
            self.sensorsStatus["sensors"].append(sensor)
        # Clean pin when it becomes inactive
        if inputPin is not None and pinActive is False:
            self.clearUnusedPin(inputPin)

        # Send to JS
        socketio.emit('settingsChanged', self.getPinsStatus())

        # Write Log
        for pinStatus in self.sensorsStatus['sensors']:
            if pinStatus['alert'] is True:
                self.writeLog(pinStatus['name'])

    def clearUnusedPin(self, pin):
        if pin in self.enabledPins:
            GPIO.remove_event_detect(pin)
            self.enabledPins.remove(pin)

    def ReadSettings(self, jsonfile):
        with open(jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def writeNewSettingsToFile(self):
        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def CheckSettingsChanges(self, callback):
        callback(None)
        while self.kill_now is False:
            prevSettings = self.settings
            nowSettings = self.ReadSettings(self.jsonfile)
            if prevSettings != nowSettings:
                self.settings = nowSettings
                callback(None)
            time.sleep(1)

    def writeLog(self, message):
        myTimeLog = time.strftime("[%Y-%m-%d %H:%M:%S] ")
        with open(self.logfile, "a") as myfile:
            myfile.write(myTimeLog + message + "\n")
        socketio.emit('sensorsLog', self.getSensorsLog(1))

    def sendMail(self):
        mail_user = self.settings['mail']['username']
        mail_pwd = self.settings['mail']['password']
        smtp_server = self.settings['mail']['smtpServer']
        smtp_port = self.settings['mail']['smtpPort']

        msg = MIMEText(self.settings['mail']['messageBody'])
        sender = mail_user
        recipients = self.settings['mail']['recipients']
        msg['Subject'] = self.settings['mail']['messageSubject']
        msg['From'] = sender
        msg['To'] = ", ".join(recipients)

        smtpserver = smtplib.SMTP(smtp_server, smtp_port)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.login(mail_user, mail_pwd)
        smtpserver.sendmail(sender, recipients, msg.as_string())
        smtpserver.close()

    def startSerene(self):
        self.setAlert = True
        self.writeLog("Serene started")
        serenePin = self.settings['settings']['serenePin']
        GPIO.setup(serenePin, GPIO.OUT)
        GPIO.output(serenePin, GPIO.HIGH)
        socketio.emit('alarmStatus', self.getAlarmStatus())
        self.sendMail()

    def stopSerene(self):
        self.setAlert = False
        serenePin = self.settings['settings']['serenePin']
        GPIO.setup(serenePin, GPIO.OUT)
        GPIO.output(serenePin, GPIO.LOW)
        socketio.emit('alarmStatus', self.getAlarmStatus())

    def getPinsStatus(self):
        settings = {}
        settings['sensors'] = self.sensorsStatus['sensors']
        settings['settings'] = self.settings["settings"]
        return settings

    def activateAlarm(self):
        self.writeLog("Alarm activated")
        self.settings['settings']['alarmArmed'] = True
        self.writeNewSettingsToFile()
        self.RefreshAlarmData(None)

    def deactivateAlarm(self):
        self.writeLog("Alarm deactivated")
        self.settings['settings']['alarmArmed'] = False
        self.stopSerene()
        self.writeNewSettingsToFile()

    def getAlarmStatus(self):
        return {"alert": self.setAlert}

    def getSerenePin(self):
        return {'serenePin': self.settings['settings']['serenePin']}

    def getSensorsLog(self, limit):
        with open(self.logfile, "r") as f:
            lines = f.readlines()
        return {"log": lines[-limit:]}

    def setSerenePin(self, pin):
        self.clearUnusedPin(pin)
        self.settings['settings']['serenePin'] = pin
        self.writeNewSettingsToFile()

    def setSensorName(self, pin, name):
        for i, sensor in enumerate(self.settings["sensors"]):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['name'] = name
        self.writeNewSettingsToFile()

    def setSensorState(self, pin, state):
        for i, sensor in enumerate(self.settings["sensors"]):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['active'] = state
        self.writeNewSettingsToFile()

    def setSensorPin(self, pin, newpin):
        self.clearUnusedPin(pin)
        for i, sensor in enumerate(self.settings["sensors"]):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['pin'] = newpin
        self.writeNewSettingsToFile()

    def addSensor(self, pin, name, active):
        self.settings['sensors'].append({
            "pin": pin,
            "name": name,
            "active": active
        })
        self.sensorsStatus['sensors'].append({
            "pin": pin,
            "name": name,
            "active": active
        })
        self.writeNewSettingsToFile()

    def delSensor(self, pin):
        tmpSensors = []
        for sensor in self.settings["sensors"]:
            if sensor['pin'] != pin:
                tmpSensors.append(sensor)

        self.settings['sensors'] = tmpSensors
        self.sensorsStatus['sensors'] = tmpSensors

        self.writeNewSettingsToFile()


app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
alarmSensors = DoorSensor("settings.json", "alert.log")


@app.route('/')
def index():
    return send_from_directory('web', 'index.html')


@app.route('/main.css')
def main():
    return send_from_directory('web', 'main.css')


@app.route('/icon.png')
def icon():
    return send_from_directory('web', 'icon.png')


@app.route('/mycss.css')
def mycss():
    return send_from_directory('web', 'mycss.css')


@app.route('/mycssMobile.css')
def mycssMobile():
    return send_from_directory('web', 'mycssMobile.css')


@app.route('/myjs.js')
def myjs():
    return send_from_directory('web', 'myjs.js')


@app.route('/alertpins.json')
def alertpinsJson():
    return json.dumps(alarmSensors.getPinsStatus())


@app.route('/alarmStatus.json')
def alarmStatus():
    return json.dumps(alarmSensors.getAlarmStatus())


@app.route('/sensorsLog.json')
def sensorsLog():
    return json.dumps(alarmSensors.getSensorsLog(10))


@app.route('/serenePin.json')
def serenePin():
    return json.dumps(alarmSensors.getSerenePin())


@socketio.on('setSerenePin')
def setSerenePin(message):
    print(message)
    alarmSensors.setSerenePin(int(message['pin']))
    socketio.emit('pinsChanged')


@socketio.on('setSensorState')
def setSensorState(message):
    print(message)
    alarmSensors.setSensorState(message['pin'], message['active'])
    socketio.emit('settingsChanged', alarmSensors.getPinsStatus())


@socketio.on('setSensorName')
def setSensorName(message):
    print(message)
    alarmSensors.setSensorName(message['pin'], message['name'])
    socketio.emit('settingsChanged', alarmSensors.getPinsStatus())


@socketio.on('setSensorPin')
def setSensorPin(message):
    print(message)
    alarmSensors.setSensorPin(int(message['pin']), int(message['newpin']))
    socketio.emit('pinsChanged')


@socketio.on('activateAlarm')
def activateAlarm():
    alarmSensors.activateAlarm()
    socketio.emit('settingsChanged', alarmSensors.getPinsStatus())


@socketio.on('deactivateAlarm')
def deactivateAlarm():
    alarmSensors.deactivateAlarm()
    socketio.emit('settingsChanged', alarmSensors.getPinsStatus())


@socketio.on('addSensor')
def addSensor(message):
    print(message)
    alarmSensors.addSensor(int(message['pin']), message['name'], message['active'])
    socketio.emit('pinsChanged')


@socketio.on('delSensor')
def delSensor(message):
    print(message)
    alarmSensors.delSensor(int(message['pin']))
    socketio.emit('pinsChanged')


if __name__ == '__main__':
    socketio.run(app, host="", port=5000)
