#!/usr/bin/env python

import json
import os
import sys

from flask import Flask, send_from_directory, request, Response
from flask_socketio import SocketIO
from functools import wraps
from distutils.util import strtobool

import time
import subprocess
from multiprocessing import Process, Queue

from DoorSensor import DoorSensor

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


class myDoorSensor(DoorSensor):
    def updateUI(self, event, data):
        ''' Send changes to the UI '''
        socketio.emit(event, data)


# some_queue = None
app = Flask(__name__, static_url_path='')
socketio = SocketIO(app)
wd = os.path.dirname(os.path.realpath(__file__))
webDirectory = os.path.join(wd, 'web')
jsonfile = os.path.join(wd, "settings.json")
logfile = os.path.join(wd, "alert.log")
sipcallfile = os.path.join(os.path.join(wd, "voip"), "sipcall")
certkeyfile = os.path.join(wd, 'my.cert.key')
certcrtfile = os.path.join(wd, 'my.cert.crt')
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
        ipaddr = request.remote_addr
        if not auth or not alarmSensors.check_auth(auth.username, auth.password):
            if not auth:
                print("Trying to login with IP:", ipaddr)
            else:
                print("Unauthorized login:", ipaddr)
            return authenticate()
        return f(*args, **kwargs)
    return decorated


# Start/Stop Application
def shutdownServer():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


def startServer(queue):
# def startServer():
    global some_queue
    some_queue = queue
    # Save the PID to a file
    if len(sys.argv) > 1:
        if ".pid" in sys.argv[1]:
            with open(sys.argv[1], "w") as f:
                f.write(str(os.getpid()))
    if alarmSensors.getUISettings()['https'] is True:
        context = (certcrtfile, certkeyfile)
    else:
        context = None
    socketio.run(app, host="", port=alarmSensors.getPortUI(), ssl_context=context)


@app.route('/restart')
@requires_auth
def restart():
    try:
        some_queue.put("something")
        print("Restarted successfully")
        return "Quit"
    except Exception:
        print("Failed in restart")
        return "Failed"


# Get the required files for the UI

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


@app.route('/jquery.js')
@requires_auth
def jqueryfile():
    return send_from_directory(webDirectory, 'jquery.js')


@app.route('/socket.io.js')
@requires_auth
def socketiofile():
    return send_from_directory(webDirectory, 'socket.io.js')


# Get the required data from the AlarmPI

@app.route('/getSensors.json')
@requires_auth
def getSensors():
    return json.dumps(alarmSensors.getSensorsArmed())


@app.route('/getAlarmStatus.json')
@requires_auth
def getAlarmStatus():
    return json.dumps(alarmSensors.getAlarmStatus())


@app.route('/getSensorsLog.json', methods=['Get', 'POST'])
@requires_auth
def getSensorsLog():
    limit = 10
    logtype = 'all'
    logformat = 'text'
    requestLimit = request.args.get('limit')
    requestType = request.args.get('type')
    requestFormat = request.args.get('format')
    if requestLimit is not None:
        if requestLimit.isdigit():
            limit = int(request.args.get('limit'))
    if requestType is not None:
        logtype = request.args.get('type').split(',')
    if requestFormat is not None:
        logformat = request.args.get('format')
    return json.dumps(alarmSensors.getSensorsLog(limit, logtype, logformat))


@app.route('/serenePin.json')
@requires_auth
def serenePin():
    return json.dumps(alarmSensors.getSerenePin())


@app.route('/getSereneSettings.json')
@requires_auth
def getSereneSettings():
    return json.dumps(alarmSensors.getSereneSettings())


@app.route('/getMailSettings.json')
@requires_auth
def getMailSettings():
    return json.dumps(alarmSensors.getMailSettings())


@app.route('/getVoipSettings.json')
@requires_auth
def getVoipSettings():
    return json.dumps(alarmSensors.getVoipSettings())


@app.route('/getUISettings.json')
@requires_auth
def getUISettings():
    return json.dumps(alarmSensors.getUISettings())


# Change settings to the AlarmPI

@app.route('/activateAlarmOnline')
@requires_auth
def activateAlarmOnline():
    alarmSensors.activateAlarm()
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@app.route('/deactivateAlarmOnline')
@requires_auth
def deactivateAlarmOnline():
    alarmSensors.deactivateAlarm()
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@app.route('/setSensorStateOnline', methods=['GET', 'POST'])
@requires_auth
def setSensorStateOnline():
    message = {
        "sensor": request.args.get('sensor'),
        "enabled": strtobool(request.args.get('enabled').lower())
    }
    message['enabled'] = True if message['enabled'] else False
    print(message)
    alarmSensors.setSensorState(message['sensor'], message['enabled'])
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


# @socketio.on('setSerenePin')
# @requires_auth
# def setSerenePin(message):
#     alarmSensors.setSerenePin(str(message['pin']))
#     socketio.emit('sensorsChanged')


@socketio.on('setSensorState')
@requires_auth
def setSensorState(message):
    alarmSensors.setSensorState(message['sensor'], message['enabled'])
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


# @socketio.on('setSensorName')
# @requires_auth
# def setSensorName(message):
#     alarmSensors.setSensorName(message['sensor'], message['name'])
#     socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('setSensorPin')
@requires_auth
def setSensorPin(message):
    alarmSensors.setSensorPin(str(message['sensor']), str(message['newpin']))
    socketio.emit('sensorsChanged')


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
    alarmSensors.addSensor(message)
    socketio.emit('sensorsChanged')


@app.route('/addSensor2', methods=['GET', 'POST'])
@requires_auth
def addSensor2():
    message = request.get_json()
    alarmSensors.addSensor(message)
    socketio.emit('sensorsChanged')
    return json.dumps("done")


@socketio.on('delSensor')
@requires_auth
def delSensor(message):
    alarmSensors.delSensor(str(message['sensor']))
    socketio.emit('sensorsChanged')


@socketio.on('setSereneSettings')
@requires_auth
def setSereneSettings(message):
    alarmSensors.setSereneSettings(message)
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('setMailSettings')
@requires_auth
def setMailSettings(message):
    alarmSensors.setMailSettings(message)
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('setVoipSettings')
@requires_auth
def setVoipSettings(message):
    alarmSensors.setVoipSettings(message)
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


@socketio.on('setUISettings')
@requires_auth
def setUISettings(message):
    alarmSensors.setUISettings(message)
    socketio.emit('settingsChanged', alarmSensors.getSensorsArmed())


# Run
if __name__ == '__main__':
    # startServer()
    q = Queue()
    p = Process(target=startServer, args=[q, ])
    p.start()
    while True:  # wathing queue, if there is no call than sleep, otherwise break
        if q.empty():
            time.sleep(1)
        else:
            break
    subprocess.call('service alarmpi stop', shell=True)
    p.terminate()  # terminate flaskapp and then restart the app on subprocess
    args = [sys.executable] + [sys.argv[0]]
    subprocess.call(args)
