#!/usr/bin/env python

import json
import os

from flask import Flask, send_from_directory, request, Response
from flask_socketio import SocketIO
from functools import wraps

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


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not alarmSensors.check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route('/')
@requires_auth
def index():
    return send_from_directory(webDirectory, 'index.html')


@app.route('/main.css')
@requires_auth
def main():
    return send_from_directory(webDirectory, 'main.css')


@app.route('/icon.png')
@requires_auth
def icon():
    return send_from_directory(webDirectory, 'icon.png')


@app.route('/mycss.css')
@requires_auth
def mycss():
    return send_from_directory(webDirectory, 'mycss.css')


@app.route('/mycssMobile.css')
@requires_auth
def mycssMobile():
    return send_from_directory(webDirectory, 'mycssMobile.css')


@app.route('/myjs.js')
@requires_auth
def myjs():
    return send_from_directory(webDirectory, 'myjs.js')


@app.route('/alertpins.json')
@requires_auth
def alertpinsJson():
    return json.dumps(alarmSensors.getSensorsArmed())


@app.route('/alarmStatus.json')
@requires_auth
def alarmStatus():
    return json.dumps(alarmSensors.getAlarmStatus())


@app.route('/sensorsLog.json')
@requires_auth
def sensorsLog():
    return json.dumps(alarmSensors.getSensorsLog(10))


@app.route('/serenePin.json')
@requires_auth
def serenePin():
    return json.dumps(alarmSensors.getSerenePin())


@socketio.on('setSerenePin')
@requires_auth
def setSerenePin(message):
    alarmSensors.setSerenePin(int(message['pin']))
    socketio.emit('pinsChanged')


@socketio.on('setSensorState')
@requires_auth
def setSensorState(message):
    alarmSensors.setSensorState(message['pin'], message['active'])
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('setSensorName')
@requires_auth
def setSensorName(message):
    alarmSensors.setSensorName(message['pin'], message['name'])
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('setSensorPin')
@requires_auth
def setSensorPin(message):
    alarmSensors.setSensorPin(int(message['pin']), int(message['newpin']))
    socketio.emit('pinsChanged')


@socketio.on('activateAlarm')
@requires_auth
def activateAlarm():
    alarmSensors.activateAlarm()
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('deactivateAlarm')
@requires_auth
def deactivateAlarm():
    alarmSensors.deactivateAlarm()
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('addSensor')
@requires_auth
def addSensor(message):
    alarmSensors.addSensor(int(message['pin']), message['name'], message['active'])
    socketio.emit('pinsChanged')


@socketio.on('delSensor')
@requires_auth
def delSensor(message):
    alarmSensors.delSensor(int(message['pin']))
    socketio.emit('pinsChanged')


if __name__ == '__main__':
    socketio.run(app, host="", port=5000)
