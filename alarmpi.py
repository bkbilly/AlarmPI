#!/usr/bin/env python

import json
import os
import sys

from flask import Flask, send_from_directory, request, Response, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room
import flask_login
from functools import wraps
from distutils.util import strtobool
from copy import deepcopy

# import time
# import subprocess
from multiprocessing import Process, Queue

from DoorSensor import DoorSensor
from colors import bcolors

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


# some_queue = None
app = Flask(__name__, static_url_path='')
app.secret_key = 'super secret string'
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

socketio = SocketIO(app)
wd = os.path.dirname(os.path.realpath(__file__))
webDirectory = os.path.join(wd, 'web')

certkeyfile = os.path.join(wd, 'my.cert.key')
certcrtfile = os.path.join(wd, 'my.cert.crt')
sipcallfile = os.path.join(os.path.join(wd, "voip"), "sipcall")
serverfile = os.path.join(wd, 'server.json')
with open(serverfile) as data_file:
    serverJson = json.load(data_file)

users = deepcopy(serverJson['users'])
for user, properties in users.items():
    class myDoorSensor(DoorSensor):
        myuser = user

        def updateUI(self, event, data):
            ''' Send changes to the UI '''
            socketio.emit(event, data, room=self.myuser)
    jsonfile = os.path.join(wd, properties['settings'])
    logfile = os.path.join(wd, properties['logfile'])
    users[user]['obj'] = myDoorSensor(jsonfile, logfile, sipcallfile)
print("\n{0}============= AlarmPI Has started! ============={1}".format(
    bcolors.HEADER, bcolors.ENDC))


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return
    user = User()
    user.id = email
    return user


@login_manager.request_loader
def request_loader(request):
    username = None
    password = None
    if len(request.form) > 0:
        username = request.form.get('email')
        password = request.form.get('pw')
    elif request.authorization:
        username = request.authorization['username']
        password = request.authorization['password']
    if username not in users:
        return
    user = User()
    user.id = username
    if password == users[username]['pw']:
        flask_login.login_user(user)
    return user


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return send_from_directory(webDirectory, 'login.html')
    request_loader(request)
    return redirect('/')
    # email = request.form['email']
    # if email not in users:
    #     return 'Bad login'
    # if request.form['pw'] == users[email]['pw']:
    #     user = User()
    #     user.id = email
    #     flask_login.login_user(user)
    #     return redirect('/')
    # return 'Bad login'


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect('/login')


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect('/login')


# **********************************

# # Start/Stop Application
# def shutdownServer():
#     func = request.environ.get('werkzeug.server.shutdown')
#     if func is None:
#         raise RuntimeError('Not running with the Werkzeug Server')
#     func()


# def startServer(queue):
def startServer():
    # global some_queue
    # some_queue = queue
    # Save the PID to a file
    if len(sys.argv) > 1:
        if ".pid" in sys.argv[1]:
            with open(sys.argv[1], "w") as f:
                f.write(str(os.getpid()))
    if serverJson['ui']['https'] is True:
        context = (certcrtfile, certkeyfile)
    else:
        context = None
    socketio.run(app, host="", port=serverJson['ui']['port'], ssl_context=context)


# @app.route('/restart')
# @flask_login.login_required
# def restart():
#     try:
#         some_queue.put("something")
#         print("Restarted successfully")
#         return "Quit"
#     except Exception:
#         print("Failed in restart")
#         return "Failed"


# Get the required files for the UI

@app.route('/')
@flask_login.login_required
def index():
    return send_from_directory(webDirectory, 'index.html')


@app.route('/main.css')
@flask_login.login_required
def main():
    return send_from_directory(webDirectory, 'main.css')


@app.route('/icon.png')
@flask_login.login_required
def icon():
    return send_from_directory(webDirectory, 'icon.png')


@app.route('/mycss.css')
@flask_login.login_required
def mycss():
    return send_from_directory(webDirectory, 'mycss.css')


@app.route('/mycssMobile.css')
@flask_login.login_required
def mycssMobile():
    return send_from_directory(webDirectory, 'mycssMobile.css')


@app.route('/myjs.js')
@flask_login.login_required
def myjs():
    return send_from_directory(webDirectory, 'myjs.js')


@app.route('/jquery.js')
@flask_login.login_required
def jqueryfile():
    return send_from_directory(webDirectory, 'jquery.js')


@app.route('/socket.io.js')
@flask_login.login_required
def socketiofile():
    return send_from_directory(webDirectory, 'socket.io.js')


# Get the required data from the AlarmPI

@app.route('/getSensors.json')
@flask_login.login_required
def getSensors():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    return json.dumps(sensorClass.getSensorsArmed())


@app.route('/getAlarmStatus.json')
@flask_login.login_required
def getAlarmStatus():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    return json.dumps(sensorClass.getTriggeredStatus())


@app.route('/getSensorsLog.json', methods=['Get', 'POST'])
@flask_login.login_required
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
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    return json.dumps(sensorClass.getSensorsLog(limit, logtype, logformat))


@app.route('/serenePin.json')
@flask_login.login_required
def serenePin():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    return json.dumps(sensorClass.getSerenePin())


@app.route('/getSereneSettings.json')
@flask_login.login_required
def getSereneSettings():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    return json.dumps(sensorClass.getSereneSettings())


@app.route('/getAllSettings.json')
@flask_login.login_required
def getAllSettings():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    uisettings = {
        'username': user,
        'password': serverJson['users'][user]['pw'],
        'timezone': sensorClass.getTimezoneSettings(),
        'https': serverJson['ui']['https'],
        'port': serverJson['ui']['port']
    }
    return json.dumps({
        "mail": sensorClass.getMailSettings(),
        "voip": sensorClass.getVoipSettings(),
        "ui": uisettings,
        "mqtt": sensorClass.getMQTTSettings()
    })

# @app.route('/getMailSettings.json')
# @flask_login.login_required
# def getMailSettings():
#     return json.dumps(sensorClass.getMailSettings())


# @app.route('/getVoipSettings.json')
# @flask_login.login_required
# def getVoipSettings():
#     return json.dumps(sensorClass.getVoipSettings())


# @app.route('/getUISettings.json')
# @flask_login.login_required
# def getUISettings():
#     return json.dumps(sensorClass.getUISettings())


# @app.route('/getMQTTSettings.json')
# @flask_login.login_required
# def getMQTTSettings():
#     return json.dumps(sensorClass.getMQTTSettings())


# Change settings to the AlarmPI

@app.route('/activateAlarmOnline')
@flask_login.login_required
def activateAlarmOnline():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.activateAlarm()
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)
    return json.dumps("done")


@app.route('/deactivateAlarmOnline')
@flask_login.login_required
def deactivateAlarmOnline():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.deactivateAlarm()
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)
    return json.dumps("done")


@app.route('/setSensorStateOnline', methods=['GET', 'POST'])
@flask_login.login_required
def setSensorStateOnline():
    message = {
        "sensor": request.args.get('sensor'),
        "enabled": strtobool(request.args.get('enabled').lower())
    }
    message['enabled'] = True if message['enabled'] else False
    # print(message)
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setSensorState(message['sensor'], message['enabled'])
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)
    return json.dumps("done")


# @socketio.on('setSerenePin')
# @flask_login.login_required
# def setSerenePin(message):
#     users[flask_login.current_user.id]['obj'].setSerenePin(str(message['pin']))
#     socketio.emit('sensorsChanged', room=user)


@socketio.on('setSensorState')
@flask_login.login_required
def setSensorState(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setSensorState(message['sensor'], message['enabled'])
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


# @socketio.on('setSensorName')
# @flask_login.login_required
# def setSensorName(message):
#     users[flask_login.current_user.id]['obj'].setSensorName(message['sensor'], message['name'])
#     socketio.emit('settingsChanged', users[flask_login.current_user.id]['obj'].getSensorsArmed(), room=user)


# @socketio.on('setSensorPin')
# @flask_login.login_required
# def setSensorPin(message):
#     user = flask_login.current_user.id
#     sensorClass = users[user]['obj']
#     sensorClass.setSensorPin(str(message['sensor']), str(message['newpin']))
#     socketio.emit('sensorsChanged', room=user)


@socketio.on('activateAlarm')
@flask_login.login_required
def activateAlarm():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.activateAlarm()
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


@socketio.on('deactivateAlarm')
@flask_login.login_required
def deactivateAlarm():
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    users[user]['obj'].deactivateAlarm()
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


# @socketio.on('addSensor')
# @flask_login.login_required
# def addSensor(message):
#     user = flask_login.current_user.id
#     sensorClass = users[user]['obj']
#     sensorClass.addSensor(message)
#     socketio.emit('sensorsChanged', room=user)


@app.route('/addSensor', methods=['GET', 'POST'])
@flask_login.login_required
def addSensor():
    message = request.get_json()
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.addSensor(message)
    socketio.emit('sensorsChanged', room=user)
    return json.dumps("done")


@socketio.on('delSensor')
@flask_login.login_required
def delSensor(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.delSensor(str(message['sensor']))
    socketio.emit('sensorsChanged', room=user)


@socketio.on('setSereneSettings')
@flask_login.login_required
def setSereneSettings(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setSereneSettings(message)
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


@socketio.on('setMailSettings')
@flask_login.login_required
def setMailSettings(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setMailSettings(message)
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


@socketio.on('setVoipSettings')
@flask_login.login_required
def setVoipSettings(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setVoipSettings(message)
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


@socketio.on('setUISettings')
@flask_login.login_required
def setUISettings(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setTimezoneSettings(message['timezone'])
    serverJson['users'][user]['pw'] = message['password']
    serverJson['ui']['port'] = message['port']
    serverJson['ui']['https'] = message['https']
    with open(serverfile, 'w') as outfile:
        json.dump(serverJson, outfile, sort_keys=True,
                  indent=4, separators=(',', ': '))
    print("You might want to restart...")
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


@socketio.on('setMQTTSettings')
@flask_login.login_required
def setMQTTSettings(message):
    user = flask_login.current_user.id
    sensorClass = users[user]['obj']
    sensorClass.setMQTTSettings(message)
    socketio.emit('settingsChanged', sensorClass.getSensorsArmed(), room=user)


@socketio.on('join')
@flask_login.login_required
def on_join(data):
    # print('joining room:', flask_login.current_user.id)
    join_room(flask_login.current_user.id)


# Run
if __name__ == '__main__':
    startServer()
    # q = Queue()
    # p = Process(target=startServer, args=[q, ])
    # p.start()
    # while True:  # wathing queue, if there is no call than sleep, otherwise break
    #     if q.empty():
    #         time.sleep(1)
    #     else:
    #         break
    # subprocess.call('service alarmpi stop', shell=True)
    # p.terminate()  # terminate flaskapp and then restart the app on subprocess
    # args = [sys.executable] + [sys.argv[0]]
    # subprocess.call(args)
