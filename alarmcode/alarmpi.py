#!/usr/bin/env python3

import json
import os
import sys

from flask import Flask, send_from_directory, request, Response, redirect
from flask_socketio import SocketIO, join_room
import flask_login
from distutils.util import strtobool
from copy import deepcopy
import logging

from alarmcode.Worker import Worker

logging = logging.getLogger('alarmpi')


class User(flask_login.UserMixin):
    pass


class AlarmPiServer(object):
    """Initialize the AlarmPI Server by defying the files to use,
    the RESTful Services and calling the class (Worker)"""

    def __init__(self, wd):
        """ Initialize the global variables for AlarmPIServer """
        self.wd = wd
        self.webDirectory = os.path.join(self.wd, 'web')

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
            return json.dumps("done")

        @self.login_manager.unauthorized_handler
        def unauthorized_handler():
            return redirect('/login')
            return Response(
                'Could not verify your access level for that URL.', 401,
                {'WWWAuthenticate': 'Basic realm="Login Required"'}
            )

        @self.app.route('/switchUser', methods=['Get', 'POST'])
        @flask_login.login_required
        def switchUser():
            newuser = request.args.get('newuser')
            user = User()
            user.id = newuser
            flask_login.login_user(user)
            return json.dumps("done")

        @self.app.route('/getUsers', methods=['Get', 'POST'])
        @flask_login.login_required
        def getUsers():
            user = flask_login.current_user.id
            admin = self.serverJson['users'][user].get('admin')
            allusers = [user]
            if admin:
                allusers = list(self.users.keys())
            usersdict = {
                'current': user,
                'allusers': allusers
            }
            return json.dumps(usersdict)

        # **********************************
        @self.app.route('/restart')
        @flask_login.login_required
        def restart():
            os.system("sudo systemctl restart alarmpi.service &")
            return json.dumps("done")


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
        #         logging.WARNING("Restarted successfully")
        #         return "Quit"
        #     except Exception:
        #         logging.WARNING("Failed in restart")
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
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            if request.args.get('saveLimit') == 'True':
                sensorClass.setLogFilters(
                    request.args.get('limit'),
                    request.args.get('type'))
            returnedLogs = sensorClass.getSensorsLog(
                limit=request.args.get('limit'),
                fromText=request.args.get('fromText'),
                selectTypes=request.args.get('type'),
                filterText=request.args.get('filterText'),
                getFormat=request.args.get('format'),
                combineSensors=request.args.get('combineSensors')
            )
            return json.dumps(returnedLogs)

        @self.app.route('/getNotifiersStatus.json')
        @flask_login.login_required
        def getNotifiersStatus():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            return json.dumps(sensorClass.getNotifiersStatus())

        @self.app.route('/getSereneSettings.json')
        @flask_login.login_required
        def getSereneSettings():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            return json.dumps(sensorClass.getSettings('serene'))

        @self.app.route('/getAllSettings.json')
        @flask_login.login_required
        def getAllSettings():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            uisettings = {
                'username': user,
                'password': self.serverJson['users'][user]['pw'],
                'timezone': sensorClass.getSettings('settings')['timezone'],
                'https': self.serverJson['ui']['https'],
                'port': self.serverJson['ui']['port']
            }
            return json.dumps({
                "mail": sensorClass.getSettings('mail'),
                "voip": sensorClass.getSettings('voip'),
                "ui": uisettings,
                "mqtt": sensorClass.getSettings('mqtt'),
                "http": sensorClass.getSettings('http'),
                "serene": sensorClass.getSettings('serene'),
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
            # logging.INFO(message)
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

        @self.app.route('/startSiren', methods=['GET', 'POST'])
        @flask_login.login_required
        def startSiren():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.startSiren()
            return json.dumps("done")

        @self.app.route('/stopSiren', methods=['GET', 'POST'])
        @flask_login.login_required
        def stopSiren():
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.stopSiren()
            return json.dumps("done")

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

        @self.app.route('/setSensorStatus', methods=['GET', 'POST'])
        @flask_login.login_required
        def setSensorStatus():
            message = request.get_json()
            name = request.args.get('name')
            state = request.args.get('state')
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            result = sensorClass.setSensorStatus(name, state)
            return json.dumps(result)

        @self.socketio.on('setSettings')
        @flask_login.login_required
        def setSettings(message):
            user = flask_login.current_user.id
            sensorClass = self.users[user]['obj']
            sensorClass.setSettings(message)

        @self.socketio.on('join')
        @flask_login.login_required
        def on_join(data):
            # logging.INFO('joining room:', flask_login.current_user.id)
            join_room(flask_login.current_user.id)

        return self.app

    def startMyApp(self):
        """ Call the Worker class for each user """

        mysocket = self.socketio
        for user, properties in self.users.items():
            jsonfile = os.path.join(self.wd, 'config')
            jsonfile = os.path.join(jsonfile, properties['settings'])
            logfile = os.path.join(self.wd, properties['logfile'])
            optsUpdateUI = {'obj': mysocket.emit, 'room': user}
            self.users[user]['obj'] = Worker(
                self.wd,
                jsonfile,
                logfile,
                optsUpdateUI
            )


    def startServer(self):
        """ Start the Flask App """
        if self.serverJson['ui']['https'] is True:
            if 'key' in self.serverJson['ui'] and 'key' in self.serverJson['ui']:
                self.certkeyfile = self.serverJson['ui']['key']
                self.certcrtfile = self.serverJson['ui']['cert']
            else:
                self.certkeyfile = os.path.join(self.wd, 'config')
                self.certkeyfile = os.path.join(self.certkeyfile, 'my.cert.key')
                self.certcrtfile = os.path.join(self.wd, 'config')
                self.certcrtfile = os.path.join(self.certcrtfile, 'my.cert.crt')
            try:
                self.socketio.run(self.app, host="0.0.0.0",
                                  port=self.serverJson['ui']['port'],
                                  certfile=self.certcrtfile,
                                  keyfile=self.certkeyfile)
            except Exception:
                logging.exception("Can't run server with HTTPS:")
                context = (self.certcrtfile, self.certkeyfile)
                self.socketio.run(self.app, host="0.0.0.0",
                                  port=self.serverJson['ui']['port'],
                                  ssl_context=context)

        else:
            self.socketio.run(self.app, host="0.0.0.0",
                              port=self.serverJson['ui']['port'])


if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    if len(sys.argv) > 1:
        if ".pid" in sys.argv[1]:
            with open(sys.argv[1], "w") as f:
                f.write(str(os.getpid()))
    myserver = AlarmPiServer()
    myserver.setServerConfig('config/server.json')
    myserver.create_app()
    myserver.startMyApp()
    myserver.startServer()
