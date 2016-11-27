import RPi.GPIO as GPIO
import time
import json
import threading

from flask import Flask, send_from_directory
from flask_socketio import SocketIO

import logging
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)


class DoorSensor():

    """docstring for DoorSensor"""

    def __init__(self, jsonfile):
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Global Variables
        self.jsonfile = jsonfile
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
        pinActive = False  # DELETE????
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
                    if self.settings['settings']['alarmArmed'] is True:
                        self.startSerene()
            # Create the list of the pins status
            self.sensorsStatus["sensors"].append(sensor)
        # ??????
        if inputPin is not None:
            if pinActive is False and inputPin in self.enabledPins:
                GPIO.remove_event_detect(inputPin)
                self.enabledPins.remove(inputPin)

        # Send to JS
        socketio.emit('pinsChanged', self.getPinsStatus())

        # Debug Print
        print "------------"
        for pinStatus in self.sensorsStatus['sensors']:
            if pinStatus['alert'] is True:
                print pinStatus['name']

    def ReadSettings(self, jsonfile):
        with open(jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def CheckSettingsChanges(self, callback):
        callback(None)
        while self.kill_now is False:
            prevSettings = self.settings
            nowSettings = self.ReadSettings(self.jsonfile)
            if prevSettings != nowSettings:
                self.settings = nowSettings
                callback(None)
            time.sleep(1)

    def startSerene(self):
        self.setAlert = True
        serenePin = self.settings['settings']['serenePin']
        GPIO.setup(serenePin, GPIO.OUT)
        GPIO.output(serenePin, GPIO.HIGH)
        socketio.emit('alarmStatus', self.getAlarmStatus())

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
        self.settings['settings']['alarmArmed'] = True

        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile)
        self.RefreshAlarmData(None)

    def deactivateAlarm(self):
        self.settings['settings']['alarmArmed'] = False
        self.stopSerene()

        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile)

    def getAlarmStatus(self):
        return {"alert": self.setAlert}

    def getSerenePin(self):
        pass

    def getSensorsLog(self):
        pass

    def setSerenePin(self, pin):
        pass

    def setSensorName(self, pin, name):
        for i, sensor in enumerate(self.settings["sensors"]):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['name'] = name

        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile)

    def setSensorState(self, pin, state):
        for i, sensor in enumerate(self.settings["sensors"]):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['active'] = state

        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile)

    def setSensorPin(self, pin, newpin):
        for i, sensor in enumerate(self.settings["sensors"]):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['pin'] = newpin

        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile)

    def addSensor(self, pin, name, active):
        pass

    def delSensor(self, pin):
        pass


app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
alarmSensors = DoorSensor("web/settings.json")


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


@app.route('/settings.json')
def settingsJson():
    return send_from_directory('web', 'settings.json')


@app.route('/alertpins.json')
def alertpinsJson():
    return json.dumps(alarmSensors.getPinsStatus())


@app.route('/alarmStatus.json')
def alarmStatus():
    return json.dumps(alarmSensors.getAlarmStatus())


@socketio.on('setSensorState')
def setSensorState(message):
    print(message)
    alarmSensors.setSensorState(message['pin'], message['active'])
    socketio.emit('pinsChanged', alarmSensors.getPinsStatus())


@socketio.on('activateAlarm')
def activateAlarm():
    alarmSensors.activateAlarm()
    socketio.emit('pinsChanged', alarmSensors.getPinsStatus())


@socketio.on('deactivateAlarm')
def deactivateAlarm():
    alarmSensors.deactivateAlarm()
    socketio.emit('pinsChanged', alarmSensors.getPinsStatus())


if __name__ == '__main__':
    socketio.run(app, host="", port=5000, debug=True)
