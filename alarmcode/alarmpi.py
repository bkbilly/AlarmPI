#!/usr/bin/env python3
"""AlarmPI Server - REST and Socket.IO API Backend."""

from copy import deepcopy
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

from flask import Flask, redirect, render_template, request, Response, send_from_directory
from flask_socketio import join_room, SocketIO
import flask_login

from alarmcode.notifiers import NotifierManager
from alarmcode.sensors import get_available_sensor_types
from alarmcode.utils import parse_bool, parse_int
from alarmcode.Worker import Worker

logger = logging.getLogger('alarmpi')


class User(flask_login.UserMixin):
    """User representation for Flask-Login."""
    pass


class AlarmPiServer:
    """Initialize the AlarmPI Server, REST services, WebSocket handlers, and User Workers."""

    def __init__(self, wd: str):
        self.wd = wd
        self.webDirectory = os.path.join(self.wd, 'web')
        self.staticDirectory = os.path.join(self.webDirectory, 'static')
        self.templateDirectory = os.path.join(self.webDirectory, 'template')
        self.serverfile = ""
        self.serverJson: Dict[str, Any] = {}
        self.users: Dict[str, Any] = {}
        self.app: Optional[Flask] = None
        self.socketio: Optional[SocketIO] = None
        self.login_manager: Optional[flask_login.LoginManager] = None

    def setServerConfig(self, jsonfile: str) -> None:
        """Set server configuration file and load users."""
        self.serverfile = os.path.join(self.wd, jsonfile)
        if not os.path.exists(self.serverfile):
            # Fallback to server_template.json if server.json doesn't exist yet
            template_file = os.path.join(self.wd, 'config', 'server_template.json')
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    self.serverJson = json.load(f)
            else:
                self.serverJson = {
                    "ui": {"https": False, "port": 5000},
                    "users": {"admin": {"pw": "admin", "admin": True, "logfile": "alert.log", "settings": "settings.json"}}
                }
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.serverfile)), exist_ok=True)
                with open(self.serverfile, 'w') as f:
                    json.dump(self.serverJson, f, sort_keys=True, indent=4)
            except Exception:
                pass
        else:
            with open(self.serverfile, 'r') as data_file:
                self.serverJson = json.load(data_file)
        self.users = deepcopy(self.serverJson.get('users', {}))

    def create_app(self) -> Flask:
        """Define RESTful services and Socket.IO events."""
        self.app = Flask(
            __name__,
            template_folder=self.templateDirectory,
            static_folder=self.staticDirectory
        )
        self.app.secret_key = self.serverJson.get('secret_key', 'alarmpi-super-secret-key-2026')
        self.login_manager = flask_login.LoginManager()
        self.login_manager.init_app(self.app)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        @self.login_manager.user_loader
        def user_loader(email: str):
            if email not in self.users:
                return None
            user = User()
            user.id = email
            return user

        @self.login_manager.request_loader
        def request_loader(req):
            username = None
            password = None
            if len(req.form) > 0:
                username = req.form.get('email')
                password = req.form.get('pw')
            elif req.authorization:
                username = req.authorization.username
                password = req.authorization.password
            elif len(req.args) > 0:
                username = req.args.get('username')
                password = req.args.get('password')

            if username and username in self.users:
                if password == self.users[username].get('pw'):
                    user = User()
                    user.id = username
                    flask_login.login_user(user)
                    return user
            return None

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if flask_login.current_user.is_authenticated:
                return redirect('/')
            if request.method == 'GET':
                return render_template('login.html')
            request_loader(request)
            return redirect('/')

        @self.app.route('/logout')
        def logout():
            flask_login.logout_user()
            return json.dumps("done")

        @self.login_manager.unauthorized_handler
        def unauthorized_handler():
            if request.path.endswith('.json') or request.is_json:
                return Response(
                    '{"error": "Unauthorized"}',
                    status=401,
                    mimetype='application/json',
                    headers={'WWW-Authenticate': 'Basic realm="Login Required"'}
                )
            return redirect('/login')

        @self.app.route('/switchUser', methods=['GET', 'POST'])
        @flask_login.login_required
        def switchUser():
            newuser = request.args.get('newuser')
            if newuser in self.users:
                user = User()
                user.id = newuser
                flask_login.login_user(user)
            return json.dumps("done")

        @self.app.route('/getUsers', methods=['GET', 'POST'])
        @flask_login.login_required
        def getUsers():
            user = flask_login.current_user.id
            is_admin = self.serverJson.get('users', {}).get(user, {}).get('admin', False)
            allusers = list(self.users.keys()) if is_admin else [user]
            return json.dumps({'current': user, 'allusers': allusers})

        @self.app.route('/restart')
        @flask_login.login_required
        def restart():
            os.system("sudo systemctl restart alarmpi.service &")
            return json.dumps("done")

        @self.app.route('/')
        @self.app.route('/index')
        @flask_login.login_required
        def index():
            user = flask_login.current_user.id
            sensorClass = self.users[user].get('obj')
            return render_template('index.html', sensorClass=sensorClass)

        # Services
        @self.app.route('/getSensors.json')
        @flask_login.login_required
        def getSensors():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            return json.dumps(worker.getSensorsArmed())

        @self.app.route('/getAlarmStatus.json')
        @flask_login.login_required
        def getAlarmStatus():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            return json.dumps(worker.getAlarmState())

        @self.app.route('/getSensorsLog.json', methods=['GET', 'POST'])
        @flask_login.login_required
        def getSensorsLog():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            if request.args.get('saveLimit') == 'True':
                worker.setLogFilters(request.args.get('limit'), request.args.get('type'))
            returnedLogs = worker.getSensorsLog(
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
            worker: Worker = self.users[user]['obj']
            return json.dumps(worker.getNotifiersStatus())

        @self.app.route('/getSereneSettings.json')
        @flask_login.login_required
        def getSereneSettings():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            return json.dumps(worker.getSettings('serene'))

        @self.app.route('/getSensorTypes.json')
        @self.app.route('/api/sensors/types')
        @flask_login.login_required
        def getSensorTypes():
            return json.dumps(get_available_sensor_types())

        @self.app.route('/getAllSettings.json')
        @self.app.route('/api/settings/schema')
        @flask_login.login_required
        def getAllSettings():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']

            system_section = {
                "id": "system",
                "title": "System",
                "description": "Configure system parameters, smart arming delays, operator credentials, web server security, and service controls.",
                "icon": "settings",
                "has_enable": False,
                "fields": [
                    {"name": "timezone", "label": "Timezone", "type": "string", "default": "Europe/Athens", "section": "settings"},
                    {"name": "trim", "label": "Log History Max Lines", "type": "number", "default": 1000, "section": "settings"},
                    {"name": "exit_delay", "label": "Exit Delay (seconds)", "type": "number", "default": 0, "section": "settings"},
                    {"name": "entry_delay", "label": "Entry Delay (seconds)", "type": "number", "default": 30, "section": "settings"},
                    {"name": "arm_after_closing", "label": "Arm After Closing", "type": "boolean", "default": True, "section": "settings"},
                    {"name": "auto_bypass_open", "label": "Auto-Bypass Open Sensors", "type": "boolean", "default": False, "section": "settings"},
                    {"name": "door_chime", "label": "Door Chime when Disarmed", "type": "boolean", "default": False, "section": "settings"},
                    {"name": "siren_duration", "label": "Siren Duration (seconds)", "type": "number", "default": 180, "section": "settings"},
                    {"name": "username", "label": "Username", "type": "string", "readonly": True, "section": "ui"},
                    {"name": "password", "label": "Password", "type": "password", "section": "ui"},
                    {"name": "port", "label": "Web Port", "type": "number", "default": 5000, "section": "ui"},
                    {"name": "https", "label": "Enable HTTPS", "type": "boolean", "default": False, "section": "ui"},
                ]
            }

            notifier_sections = NotifierManager.get_registered_schemas()
            all_sections = [system_section] + notifier_sections

            ui_values = {
                'username': user,
                'password': self.serverJson.get('users', {}).get(user, {}).get('pw', ''),
                'timezone': worker.getSettings('settings').get('timezone', 'Europe/Athens'),
                'https': self.serverJson.get('ui', {}).get('https', False),
                'port': self.serverJson.get('ui', {}).get('port', 5000),
            }

            response_data = {
                "sections": all_sections,
                "sensor_types": get_available_sensor_types(),
                "values": {
                    "ui": ui_values,
                    "settings": worker.getSettings('settings'),
                    **{s["id"]: worker.getSettings(s["id"]) for s in notifier_sections}
                },
                "statuses": worker.getNotifiersStatus(),
                # Legacy top-level keys for backward compatibility
                "mail": worker.getSettings('mail'),
                "voip": worker.getSettings('voip'),
                "ui": ui_values,
                "mqtt": worker.getSettings('mqtt'),
                "http": worker.getSettings('http'),
                "serene": worker.getSettings('serene'),
                "settings": worker.getSettings('settings')
            }

            return json.dumps(response_data)

        @self.app.route('/activateAlarmOnline', methods=['GET', 'POST'])
        @flask_login.login_required
        def activateAlarmOnline():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            force = parse_bool(request.args.get('force', False))
            worker.activateAlarm(force=force)
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/activateAlarmZone', methods=['GET', 'POST'])
        @flask_login.login_required
        def activateAlarmZone():
            zones_arg = request.args.get('zones', '')
            zones = [z.strip().lower() for z in zones_arg.split(',') if z.strip()]
            force = parse_bool(request.args.get('force', False))
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.activateAlarm(zones=zones, force=force)
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/deactivateAlarmOnline', methods=['GET', 'POST'])
        @flask_login.login_required
        def deactivateAlarmOnline():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.deactivateAlarm()
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/setSensorStateOnline', methods=['GET', 'POST'])
        @flask_login.login_required
        def setSensorStateOnline():
            sensor_id = request.args.get('sensor')
            enabled_val = parse_bool(request.args.get('enabled'))
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.setSensorState(sensor_id, enabled_val)
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/startSiren', methods=['GET', 'POST'])
        @flask_login.login_required
        def startSiren():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.startSiren()
            return json.dumps("done")

        @self.app.route('/stopSiren', methods=['GET', 'POST'])
        @flask_login.login_required
        def stopSiren():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.stopSiren()
            return json.dumps("done")

        @self.app.route('/addSensor', methods=['GET', 'POST'])
        @flask_login.login_required
        def addSensor():
            message = request.get_json(force=True)
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.addSensor(message)
            self.socketio.emit('sensorsChanged', worker.getSensorsArmed(), room=user)
            return json.dumps("done")

        @self.app.route('/setSensorStatus', methods=['GET', 'POST'])
        @flask_login.login_required
        def setSensorStatus():
            name = request.args.get('name', '')
            state = request.args.get('state', '')
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            result = worker.setSensorStatus(name, state)
            return json.dumps(result)

        @self.app.route('/api/settings', methods=['POST'])
        @flask_login.login_required
        def apiSetSettings():
            message = request.get_json(force=True)
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            self._apply_settings(user, worker, message)
            return json.dumps("done")

        # Socket.IO Handlers
        @self.socketio.on('setSensorState')
        @flask_login.login_required
        def handleSetSensorState(message):
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.setSensorState(message['sensor'], parse_bool(message['enabled']))
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)

        @self.socketio.on('activateAlarm')
        @flask_login.login_required
        def handleActivateAlarm(message=None):
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            zones = None
            force = False
            if isinstance(message, dict):
                zones = message.get('zones')
                force = parse_bool(message.get('force', False))
            worker.activateAlarm(zones=zones, force=force)
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)

        @self.socketio.on('deactivateAlarm')
        @flask_login.login_required
        def handleDeactivateAlarm():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.deactivateAlarm()
            self.socketio.emit('settingsChanged', worker.getSensorsArmed(), room=user)

        @self.socketio.on('delSensor')
        @flask_login.login_required
        def handleDelSensor(message):
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            worker.delSensor(str(message['sensor']))
            self.socketio.emit('sensorsChanged', worker.getSensorsArmed(), room=user)

        @self.socketio.on('setSettings')
        @flask_login.login_required
        def handleSetSettings(message):
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            self._apply_settings(user, worker, message)

        @self.socketio.on('join')
        @flask_login.login_required
        def on_join(data):
            join_room(flask_login.current_user.id)

        return self.app

    def _apply_settings(self, user: str, worker: Worker, message: Dict[str, Any]) -> None:
        """Apply and persist updated settings across worker and serverJson."""
        if 'ui' in message:
            ui_msg = message['ui']
            if 'password' in ui_msg and ui_msg['password']:
                self.serverJson.setdefault('users', {}).setdefault(user, {})['pw'] = ui_msg['password']
                self.users[user]['pw'] = ui_msg['password']
            if 'port' in ui_msg:
                self.serverJson.setdefault('ui', {})['port'] = parse_int(ui_msg['port'], 5000)
            if 'https' in ui_msg:
                self.serverJson.setdefault('ui', {})['https'] = parse_bool(ui_msg['https'])

            with open(self.serverfile, 'w') as f:
                json.dump(self.serverJson, f, sort_keys=True, indent=4)

        worker.setSettings(message)

    def startMyApp(self) -> None:
        """Instantiate Worker for each configured user."""
        for user, properties in self.users.items():
            jsonfile = os.path.join(self.wd, 'config', properties.get('settings', 'settings.json'))
            logfile = os.path.join(self.wd, properties.get('logfile', 'alert.log'))
            optsUpdateUI = {'obj': self.socketio.emit, 'room': user}
            self.users[user]['obj'] = Worker(
                self.wd,
                jsonfile,
                logfile,
                optsUpdateUI
            )

    def startServer(self) -> None:
        """Start the Flask + Socket.IO server."""
        port = parse_int(self.serverJson.get('ui', {}).get('port'), 5000)
        use_https = parse_bool(self.serverJson.get('ui', {}).get('https'), False)
        scheme = "https" if use_https else "http"

        logger.info("AlarmPI Web Server listening on %s://0.0.0.0:%d", scheme, port)

        if use_https:
            key_path = self.serverJson.get('ui', {}).get('key', 'config/my.cert.key')
            crt_path = self.serverJson.get('ui', {}).get('cert', 'config/my.cert.crt')

            if not os.path.isabs(key_path):
                key_path = os.path.join(self.wd, key_path)
            if not os.path.isabs(crt_path):
                crt_path = os.path.join(self.wd, crt_path)

            try:
                self.socketio.run(
                    self.app,
                    host="0.0.0.0",
                    port=port,
                    certfile=crt_path,
                    keyfile=key_path,
                    allow_unsafe_werkzeug=True
                )
            except Exception:
                logger.exception("Falling back to ssl_context for HTTPS:")
                context = (crt_path, key_path)
                self.socketio.run(
                    self.app,
                    host="0.0.0.0",
                    port=port,
                    ssl_context=context,
                    allow_unsafe_werkzeug=True
                )
        else:
            self.socketio.run(
                self.app,
                host="0.0.0.0",
                port=port,
                allow_unsafe_werkzeug=True
            )
