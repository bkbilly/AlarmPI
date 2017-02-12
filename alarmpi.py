#!/usr/bin/env python

import json
import os

from flask import Flask, send_from_directory
from flask_socketio import SocketIO

from DoorSensor import DoorSensor

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


class myDoorSensor(DoorSensor):
    def updateUI(self, event, data):
        ''' Send changes to the UI '''
        socketio.emit(event, data)


app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
wd = os.path.dirname(os.path.realpath(__file__))
webDirectory = os.path.join(wd, 'web')
jsonfile = os.path.join(wd, "settings.json")
logfile = os.path.join(wd, "alert.log")
sipcallfile = os.path.join(os.path.join(wd, "voip"), "sipcall")
alarmSensors = myDoorSensor(jsonfile, logfile, sipcallfile)


@app.route('/')
def index():
    return send_from_directory(webDirectory, 'index.html')


@app.route('/main.css')
def main():
    return send_from_directory(webDirectory, 'main.css')


@app.route('/icon.png')
def icon():
    return send_from_directory(webDirectory, 'icon.png')


@app.route('/mycss.css')
def mycss():
    return send_from_directory(webDirectory, 'mycss.css')


@app.route('/mycssMobile.css')
def mycssMobile():
    return send_from_directory(webDirectory, 'mycssMobile.css')


@app.route('/myjs.js')
def myjs():
    return send_from_directory(webDirectory, 'myjs.js')


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
    alarmSensors.setSerenePin(int(message['pin']))
    socketio.emit('pinsChanged')


@socketio.on('setSensorState')
def setSensorState(message):
    alarmSensors.setSensorState(message['pin'], message['active'])
    socketio.emit('settingsChanged', alarmSensors.getPinsStatus())


@socketio.on('setSensorName')
def setSensorName(message):
    alarmSensors.setSensorName(message['pin'], message['name'])
    socketio.emit('settingsChanged', alarmSensors.getPinsStatus())


@socketio.on('setSensorPin')
def setSensorPin(message):
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
    alarmSensors.addSensor(int(message['pin']), message['name'], message['active'])
    socketio.emit('pinsChanged')


@socketio.on('delSensor')
def delSensor(message):
    alarmSensors.delSensor(int(message['pin']))
    socketio.emit('pinsChanged')


if __name__ == '__main__':
    socketio.run(app, host="", port=5000)
