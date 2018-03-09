#!/usr/bin/env python

import json
import os
import sys

from flask import Flask, send_from_directory, request, Response, redirect
from flask_socketio import SocketIO, join_room
import flask_login
from distutils.util import strtobool
from copy import deepcopy
import logging

from Worker import Worker


class User(flask_login.UserMixin):
    pass


class AlarmPiServer(object):
    """Initialize the AlarmPI Server by defying the files to use,
    the RESTful Services and calling the class (Worker)"""

    def __init__(self):
        """ Initialize the global variables for AlarmPIServer """
        self.wd = os.path.dirname(os.path.realpath(__file__))
        self.certkeyfile = os.path.join(self.wd, 'my.cert.key')
        self.certcrtfile = os.path.join(self.wd, 'my.cert.crt')
        self.webDirectory = os.path.join(self.wd, 'web')
        self.sipcallfile = os.path.join(
            os.path.join(self.wd, "voip"), "sipcall")

    def setServerConfig(self, jsonfile):
        """ Set the server file to use and initialize the users """

        self.serverfile = os.path.join(self.wd, jsonfile)
        with open(self.serverfile) as data_file:
            self.serverJson = json.load(data_file)
        self.users = deepcopy(self.serverJson['users'])

    def create_app(self):
        """ Define the RESTfull Services and call the
            accordingly method in the Worker class """

        # some_queue = None
        self.app = Flask(__name__, static_url_path='')
        self.app.secret_key = 'super secret string'
        self.login_manager = flask_login.LoginManager()
        self.login_manager.init_app(self.app)
        self.socketio = SocketIO(self.app)

        @self.login_manager.user_loader
        def user_loader(email):
            if email not in self.users:
                return
            user = User()
            user.id = email
            return user

        @self.login_manager.request_loader
        def request_loader(request):
            username = None
            password = None
            if len(request.form) > 0:
                username = request.form.get('email')
                password = request.form.get('pw')
            elif request.authorization:
                username = request.authorization['username']
                password = request.authorization['password']
            if username not in self.users:
                return
            user = User()
            user.id = username
            if password == self.users[username]['pw']:
                flask_login.login_user(user)
            return user

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if flask_login.current_user.is_authenticated:
                return redirect('/')
            if request.method == 'GET':
                return send_from_directory(self.webDirectory, 'login.html')
            request_loader(request)
            return redirect('/')

        @self.app.route('/logout')
        def logout():
            flask_login.logout_user()
            return redirect('/login')

        @self.login_manager.unauthorized_handler
        def unauthorized_handler():
            return redirect('/login')
            return Response(
                'Could not verify your access level for that URL.', 401,
                {'WWWAuthenticate': 'Basic realm="Login Required"'}
            )

        # **********************************

        # # Start/Stop Application
        # def shutdownServer():
        #     func = request.environ.get('werkzeug.server.shutdown')
        #     if func is None:
        #         raise RuntimeError('Not running with the Werkzeug Server')
        #     func()
        # @self.app.route('/restart')
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

        @self.app.route('/')
        @flask_login.login_required
        def index():
            return send_from_directory(self.webDirectory, 'index.html')

        @self.app.route('/main.css')
        @flask_login.login_required
        def main():
            return send_from_directory(self.webDirectory, 'main.css')

        @self.app.route('/icon.png')
        @flask_login.login_required
        def icon():
            return send_from_directory(self.webDirectory, 'icon.png')

        @self.app.route('/mycss.css')
        @flask_login.login_required
        def mycss():
            return send_from_directory(self.webDirectory, 'mycss.css')

        @self.app.route('/mycssMobile.css')
        @flask_login.login_required
        def mycssMobile():
            return send_from_directory(self.webDirectory, 'mycssMobile.css')

        @self.app.route('/myjs.js')
        @flask_login.login_required
        def myjs():
            return send_from_directory(self.webDirectory, 'myjs.js')

        @self.app.route('/jquery.js')
        @flask_login.login_required
        def jqueryfile():
            return send_from_directory(self.webDirectory, 'jquery.js')

        @self.app.route('/socket.io.js')
        @flask_login.login_required
        def socketiofile():
            return send_from_directory(self.webDirectory, 'socket.io.js')

        @self.app.route('/play_alert.mp3')
        @flask_login.login_required
        def play_alert():
            return send_from_directory(self.webDirectory, 'play_alert.mp3')

        @self.app.route('/getSensors.json')
        @flask_login.login_required
        def getSensors():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            return json.dumps(sensorClass.getSensorsArmed())

        @self.app.route('/getAlarmStatus.json')
        @flask_login.login_required
        def getAlarmStatus():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            return json.dumps(sensorClass.getTriggeredStatus())

        @self.app.route('/getSensorsLog.json', methods=['Get', 'POST'])
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
            sensorClass = self.users[user]['obj']
            sensorClass.setLogFilters(limit, logtype)
            returnedLogs = sensorClass.getSensorsLog(limit, logtype, logformat)
            return json.dumps(returnedLogs)

        @self.app.route('/getSereneSettings.json')
        @flask_login.login_required
        def getSereneSettings():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            return json.dumps(sensorClass.getSereneSettings())

        @self.app.route('/getAllSettings.json')
        @flask_login.login_required
        def getAllSettings():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            uisettings = {
                'username': user,
                'password': self.serverJson['users'][user]['pw'],
                'timezone': sensorClass.getTimezoneSettings(),
                'https': self.serverJson['ui']['https'],
                'port': self.serverJson['ui']['port']
            }
            return json.dumps({
                "mail": sensorClass.getMailSettings(),
                "voip": sensorClass.getVoipSettings(),
                "ui": uisettings,
                "mqtt": sensorClass.getMQTTSettings()
            })

        @self.app.route('/activateAlarmOnline')
        @flask_login.login_required
        def activateAlarmOnline():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.activateAlarm()
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/activateAlarmZone', methods=['GET', 'POST'])
        @flask_login.login_required
        def activateAlarmZone():
            zones = request.args.get('zones').lower().split(',')
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setSensorsZone(zones)
            sensorClass.activateAlarm()
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/deactivateAlarmOnline')
        @flask_login.login_required
        def deactivateAlarmOnline():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.deactivateAlarm()
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/setSensorStateOnline', methods=['GET', 'POST'])
        @flask_login.login_required
        def setSensorStateOnline():
            message = {
                "sensor": request.args.get('sensor'),
                "enabled": strtobool(request.args.get('enabled').lower())
            }
            message['enabled'] = True if message['enabled'] else False
            # print(message)
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setSensorState(message['sensor'], message['enabled'])
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.socketio.on('setSensorState')
        @flask_login.login_required
        def setSensorState(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setSensorState(message['sensor'], message['enabled'])
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('activateAlarm')
        @flask_login.login_required
        def activateAlarm():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.activateAlarm()
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('deactivateAlarm')
        @flask_login.login_required
        def deactivateAlarm():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            self.users[user]['obj'].deactivateAlarm()
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        # @self.socketio.on('addSensor')
        # @flask_login.login_required
        # def addSensor(message):
        #     user = flask_login.current_user.id
        #     sensorClass = self.users[user]['obj']
        #     sensorClass.addSensor(message)
        #     self.socketio.emit('sensorsChanged', room=user)

        @self.app.route('/addSensor', methods=['GET', 'POST'])
        @flask_login.login_required
        def addSensor():
            message = request.get_json()
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.addSensor(message)
            self.socketio.emit('sensorsChanged', room=user)
            return json.dumps("done")

        @self.socketio.on('delSensor')
        @flask_login.login_required
        def delSensor(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.delSensor(str(message['sensor']))
            self.socketio.emit('sensorsChanged', room=user)

        @self.socketio.on('setSereneSettings')
        @flask_login.login_required
        def setSereneSettings(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setSereneSettings(message)
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('setMailSettings')
        @flask_login.login_required
        def setMailSettings(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setMailSettings(message)
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('setVoipSettings')
        @flask_login.login_required
        def setVoipSettings(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setVoipSettings(message)
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('setUISettings')
        @flask_login.login_required
        def setUISettings(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setTimezoneSettings(message['timezone'])
            self.serverJson['users'][user]['pw'] = message['password']
            self.serverJson['ui']['port'] = message['port']
            self.serverJson['ui']['https'] = message['https']
            with open(self.serverfile, 'w') as outfile:
                json.dump(self.serverJson, outfile, sort_keys=True,
                          indent=4, separators=(',', ': '))
            print("You might want to restart...")
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('setMQTTSettings')
        @flask_login.login_required
        def setMQTTSettings(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setMQTTSettings(message)
            self.socketio.emit('settingsChanged',
                               sensorClass.getSensorsArmed(), room=user)

        @self.socketio.on('join')
        @flask_login.login_required
        def on_join(data):
            # print('joining room:', flask_login.current_user.id)
            join_room(flask_login.current_user.id)

        return self.app

    def startMyApp(self):
        """ Call the Worker class for each user """

        mysocket = self.socketio
        for user, properties in self.users.items():
            class myWorker(Worker):
                myuser = user

                def updateUI(self, event, data):
                    """ Send changes to the UI """
                    mysocket.emit(event, data, room=self.myuser)
            jsonfile = os.path.join(self.wd, properties['settings'])
            logfile = os.path.join(self.wd, properties['logfile'])
            self.users[user]['obj'] = myWorker(
                jsonfile, logfile, self.sipcallfile)

    def startServer(self):
        """ Start the Flask App """
        if self.serverJson['ui']['https'] is True:
            try:
                self.socketio.run(self.app, host="0.0.0.0",
                                  port=self.serverJson['ui']['port'],
                                  certfile=self.certcrtfile,
                                  keyfile=self.certkeyfile)
            except Exception:
                context = (self.certcrtfile, self.certkeyfile)
                self.socketio.run(self.app, host="0.0.0.0",
                                  port=self.serverJson['ui']['port'],
                                  ssl_context=context)

        else:
            self.socketio.run(self.app, host="0.0.0.0",
                              port=self.serverJson['ui']['port'])


if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    # log.setLevel(logging.ERROR)

    if len(sys.argv) > 1:
        if ".pid" in sys.argv[1]:
            with open(sys.argv[1], "w") as f:
                f.write(str(os.getpid()))
    myserver = AlarmPiServer()
    myserver.setServerConfig('server.json')
    myserver.create_app()
    myserver.startMyApp()
    myserver.startServer()
