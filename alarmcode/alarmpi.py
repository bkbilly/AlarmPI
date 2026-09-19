#!/usr/bin/env python3
"""AlarmPI Server - REST and Socket.IO API Backend."""

from copy import deepcopy
from datetime import datetime
import json
import logging
import os
import secrets
import sys
from typing import Any, Dict, Optional

from flask import Flask, make_response, redirect, render_template, request, Response, send_from_directory
from flask_socketio import join_room, SocketIO
import flask_login

from alarmcode.notifiers import NotifierManager
from alarmcode.sensors import get_available_sensor_types
from alarmcode.utils import parse_bool, parse_int
from alarmcode.webpush_helper import get_or_create_vapid_keys
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
        save_needed = False

        template_file = os.path.join(self.wd, 'config', 'server_template.json')
        template_json = {}
        if os.path.exists(template_file):
            try:
                with open(template_file, 'r') as f:
                    template_json = json.load(f)
            except Exception:
                pass

        if not os.path.exists(self.serverfile):
            self.serverJson = deepcopy(template_json) if template_json else {
                "ui": {"https": False, "port": 5000},
                "users": {"test1": {"pw": "secret", "admin": True, "logfile": "alert.log", "settings": "settings.json"}}
            }
            save_needed = True
        else:
            with open(self.serverfile, 'r') as data_file:
                self.serverJson = json.load(data_file)

        # Ensure UI configuration exists
        if not self.serverJson.get('ui'):
            self.serverJson['ui'] = template_json.get('ui', {"https": False, "port": 5000})
            save_needed = True

        # Ensure users configuration exists and is not empty
        if not self.serverJson.get('users'):
            self.serverJson['users'] = template_json.get('users', {
                "test1": {"pw": "secret", "admin": True, "logfile": "alert.log", "settings": "settings.json"}
            })
            save_needed = True

        # Auto-generate cryptographically secure secret_key if not already present
        if not self.serverJson.get('secret_key'):
            self.serverJson['secret_key'] = secrets.token_hex(32)
            save_needed = True

        # Auto-generate VAPID keypair for Browser Web Push if needed
        try:
            get_or_create_vapid_keys(self.wd, self.serverJson)
        except Exception:
            pass

        if save_needed:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.serverfile)), exist_ok=True)
                with open(self.serverfile, 'w') as f:
                    json.dump(self.serverJson, f, sort_keys=True, indent=4)
            except Exception:
                pass

        self.users = deepcopy(self.serverJson.get('users', {}))

    def create_app(self) -> Flask:
        """Define RESTful services and Socket.IO events."""
        self.app = Flask(
            __name__,
            template_folder=self.templateDirectory,
            static_folder=self.staticDirectory
        )
        self.app.secret_key = self.serverJson.get('secret_key') or secrets.token_hex(32)
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
            if req.authorization:
                username = req.authorization.username
                password = req.authorization.password
            elif len(req.args) > 0 and 'username' in req.args and 'password' in req.args:
                username = req.args.get('username')
                password = req.args.get('password')

            if username and username in self.users:
                if password == self.users[username].get('pw'):
                    user = User()
                    user.id = username
                    return user
            return None

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if flask_login.current_user.is_authenticated:
                return redirect('/')
            error = None
            if request.method == 'POST':
                username = request.form.get('email', '').strip()
                password = request.form.get('pw', '')
                if username in self.users and self.users[username].get('pw') == password:
                    user = User()
                    user.id = username
                    flask_login.login_user(user, remember=True)
                    logger.info("User '%s' logged in successfully.", username)
                    next_url = request.args.get('next') or '/'
                    return redirect(next_url)
                else:
                    logger.warning("Failed login attempt for username: '%s'", username)
                    error = "Invalid username or password. Please try again."
            return render_template('login.html', error=error)

        @self.app.route('/logout')
        def logout():
            flask_login.logout_user()
            if request.is_json or request.path.endswith('.json'):
                return json.dumps("done")
            return redirect('/login')

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

        @self.app.route('/api/hikvision/discover', methods=['POST'])
        @flask_login.login_required
        def apiHikvisionDiscover():
            data = request.get_json(force=True) or {}
            ip = str(data.get('ip', '')).strip()
            user = str(data.get('user', '')).strip()
            pwd = str(data.get('pass', '')).strip()
            from alarmcode.sensors.hikvision import discover_hikvision
            result = discover_hikvision(ip, user, pwd)
            return json.dumps(result)

        @self.app.route('/sw.js')
        def serviceWorker():
            resp = make_response(send_from_directory(self.staticDirectory, 'sw.js'))
            resp.headers['Content-Type'] = 'application/javascript'
            resp.headers['Service-Worker-Allowed'] = '/'
            return resp

        @self.app.route('/api/push/vapid-public-key', methods=['GET'])
        @flask_login.login_required
        def apiPushVapidPublicKey():
            _, pub_key = get_or_create_vapid_keys(self.wd, self.serverJson)
            if not pub_key:
                return json.dumps({"status": "error", "message": "VAPID key generation not available."})
            return json.dumps({"status": "success", "public_key": pub_key})

        @self.app.route('/api/push/subscribe', methods=['POST'])
        @flask_login.login_required
        def apiPushSubscribe():
            data = request.get_json(force=True) or {}
            sub = data.get('subscription')
            if not sub or not isinstance(sub, dict) or not sub.get('endpoint'):
                return json.dumps({"status": "error", "message": "Invalid subscription object."})

            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            push_cfg = worker.settings.setdefault('push', {})
            subs = push_cfg.setdefault('subscriptions', [])

            endpoint = sub.get('endpoint')
            existing_idx = None
            for idx, item in enumerate(subs):
                item_sub = item.get('subscription', item) if isinstance(item, dict) else {}
                if item_sub.get('endpoint') == endpoint:
                    existing_idx = idx
                    break

            device_entry = {
                "subscription": sub,
                "user_agent": request.headers.get('User-Agent', 'Unknown Browser'),
                "device_name": data.get('device_name', 'Web Browser'),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if 'datetime' in globals() else str(request.date or 'now'),
            }

            if existing_idx is not None:
                subs[existing_idx] = device_entry
            else:
                subs.append(device_entry)

            worker.saveSettings()
            logger.info("Registered Web Push subscription for user '%s' (%s). Total: %d", user, device_entry.get('device_name'), len(subs))
            return json.dumps({"status": "success", "message": "Device subscribed successfully!", "total_devices": len(subs)})

        @self.app.route('/api/push/unsubscribe', methods=['POST'])
        @flask_login.login_required
        def apiPushUnsubscribe():
            data = request.get_json(force=True) or {}
            endpoint = data.get('endpoint')
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            push_cfg = worker.settings.get('push', {})
            subs = push_cfg.get('subscriptions', [])

            if endpoint:
                new_subs = []
                for item in subs:
                    item_sub = item.get('subscription', item) if isinstance(item, dict) else {}
                    if item_sub.get('endpoint') != endpoint:
                        new_subs.append(item)
                push_cfg['subscriptions'] = new_subs
                worker.saveSettings()
                return json.dumps({"status": "success", "message": "Device unsubscribed.", "total_devices": len(new_subs)})
            return json.dumps({"status": "error", "message": "No endpoint provided."})

        @self.app.route('/api/push/subscriptions', methods=['GET'])
        @flask_login.login_required
        def apiPushSubscriptions():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            push_cfg = worker.settings.get('push', {})
            subs = push_cfg.get('subscriptions', [])
            sanitized = []
            for s in subs:
                sub_dict = s if isinstance(s, dict) else {}
                sub_info = sub_dict.get('subscription', sub_dict)
                ep = sub_info.get('endpoint', '')
                sanitized.append({
                    "device_name": sub_dict.get('device_name', 'Web Browser'),
                    "user_agent": sub_dict.get('user_agent', ''),
                    "endpoint_preview": ep[:35] + '...' if len(ep) > 35 else ep,
                    "created_at": sub_dict.get('created_at', '')
                })
            return json.dumps({"status": "success", "subscriptions": sanitized, "count": len(sanitized)})

        @self.app.route('/api/push/subscriptions/clear', methods=['POST'])
        @flask_login.login_required
        def apiPushClearSubscriptions():
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']
            push_cfg = worker.settings.setdefault('push', {})
            push_cfg['subscriptions'] = []
            worker.saveSettings()
            return json.dumps({"status": "success", "message": "All device subscriptions cleared."})

        @self.app.route('/api/notifiers/test', methods=['POST'])
        @flask_login.login_required
        def apiTestNotifier():
            data = request.get_json(force=True) or {}
            notifier_id = str(data.get('notifier', '')).strip()
            custom_cfg = data.get('config')
            user = flask_login.current_user.id
            worker: Worker = self.users[user]['obj']

            plugin = worker.mynotify.plugins.get(notifier_id)
            if not plugin:
                return json.dumps({"status": "error", "message": f"Notifier '{notifier_id}' not found."})

            test_cfg = custom_cfg if isinstance(custom_cfg, dict) else deepcopy(worker.settings.get(notifier_id, {}))

            try:
                if notifier_id == "push":
                    # Ensure subscriptions from worker settings are available for webpush test if not in test_cfg
                    if not test_cfg.get("subscriptions"):
                        test_cfg["subscriptions"] = worker.settings.get("push", {}).get("subscriptions", [])
                    success = plugin._send_push_payload(
                        cfg=test_cfg,
                        title="🔔 AlarmPI Test Push",
                        message="✅ <b>AlarmPI Test Alert</b>\n\nYour push notifications are configured and working properly!",
                        priority="normal",
                        is_alarm=False
                    )
                    if success:
                        return json.dumps({"status": "success", "message": "Test push notification sent successfully!"})
                    else:
                        svc = test_cfg.get("service", "push")
                        err_hint = "Ensure at least one device is subscribed above." if svc == "webpush" else "Verify provider credentials and settings."
                        return json.dumps({"status": "error", "message": f"Failed to deliver push notification via {svc}. {err_hint}"})
                else:
                    return json.dumps({"status": "success", "message": f"Test executed for {plugin.display_name}."})
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})

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
