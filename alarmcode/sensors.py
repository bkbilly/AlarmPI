#!/usr/bin/env python

import logging
try:
    import RPi.GPIO as GPIO
except Exception as e:
    print(e)
import threading
import time

import requests
import re

from alarmcode.colors import bcolors

logging = logging.getLogger('alarmpi')


class sensorGeneral():
    def __init__(self, sensorName):
        self.sensorName = sensorName
        self.online = None
        self.alert = None
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []

    def add_sensor(self, sensor, settings=None):
        self.sensor = sensor
        self.reload()

    def del_sensor(self):
        pass

    def reload(self, settings=None):
        pass

    def setAlertStatus(self, alertstate=None):
        self.alert = alertstate

    def on_alert(self, callback):
        self._event_alert.append(callback)

    def on_alert_stop(self, callback):
        self._event_alert_stop.append(callback)

    def on_error(self, callback):
        self._event_error.append(callback)

    def on_error_stop(self, callback):
        self._event_error_stop.append(callback)

    def _notify_alert(self, sensorName):
        self.setAlertStatus(alertstate=True)
        for callback in self._event_alert:
            callback(sensorName)

    def _notify_alert_stop(self, sensorName):
        self.setAlertStatus(alertstate=False)
        for callback in self._event_alert_stop:
            callback(sensorName)

    def _notify_error(self, sensorName):
        self.online = False
        for callback in self._event_error:
            callback(sensorName)

    def _notify_error_stop(self, sensorName):
        self.online = True
        for callback in self._event_error_stop:
            callback(sensorName)


class sensorGPIO(sensorGeneral):
    def __init__(self, sensorName):
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Global Required Variables
        self.sensorName = sensorName
        self.online = True
        self.alert = None
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []

        # Other Variables
        self.gpioState = None
        self.pin = None

    def setAlertStatus(self, alertstate=None):
        self.gpioState = GPIO.input(self.pin)
        self.alert = False
        if self.gpioState == 1:
            self.alert = True

    def add_sensor(self, sensor, settings=None):
        self.pin = int(sensor['pin'])
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.remove_event_detect(self.pin)
        GPIO.add_event_detect(
            self.pin, GPIO.BOTH,
            callback=self._checkInputPinState,
            bouncetime=600)
        self._checkInputPinState(self.pin)
        self.setAlertStatus()

    def del_sensor(self):
        GPIO.remove_event_detect(self.pin)

    def _checkInputPinState(self, inputPin):
        nowState = GPIO.input(self.pin)
        if nowState != self.gpioState:
            if nowState == 1:
                self._notify_alert(self.sensorName)
            else:
                self._notify_alert_stop(self.sensorName)
        else:
            logging.info("{0}GPIO {2}: Wrong state change. Ignoring!!!{1}".format(bcolors.STRIKE, bcolors.ENDC, str(inputPin)))


class sensorHikvision(sensorGeneral):
    def __init__(self, sensorName):
        # Global Required Variables
        self.sensorName = sensorName
        self.online = None
        self.alert = False
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []

        # Other Variables
        self.alertTime = 8
        self.threadRunforever = None
        self.runforever = None
        self.hasBeenNotified = False
        self.sensor = None

    def add_sensor(self, sensor, settings=None):
        self.sensor = sensor
        self.reload()

    def reload(self, settings=None):
        self.runforever = False
        ip = self.sensor['ip']
        username = self.sensor['user']
        password = self.sensor['pass']
        self.threadRunforever = threading.Thread(target=self.runInBackground,
                                                 args=[self.sensor,
                                                       ip,
                                                       username,
                                                       password])
        self.threadRunforever.daemon = True
        self.threadRunforever.start()
        self._notify_alert_stop(self.sensorName)

    def runInBackground(self, sensor, ip, username, password):
        self.runforever = True
        streamURL = 'http://' + ip + '/ISAPI/Event/notification/alertStream'
        authorization = requests.auth.HTTPBasicAuth(username, password)
        while self.runforever:
            try:
                response = requests.get(streamURL,
                                        auth=authorization,
                                        timeout=15,
                                        stream=True)
                if not self.online:
                    self._notify_error_stop(self.sensorName)
                for chunk in response.iter_lines():
                    if chunk:
                        chunk = chunk.decode("utf-8")
                        match = re.match(r'<eventType>(.*)</eventType>', chunk)
                        if match:
                            if match.group(1) == 'linedetection':
                                if not self.hasBeenNotified:
                                    self._notify_alert(self.sensorName)
            except Exception:
                logging.exception("Hikvision can't connect:")
                if self.online:
                    self._notify_error(self.sensorName)
                time.sleep(2)

    def del_sensor(self):
        self.runforever = False

    def setAlertStatus(self, alertstate=None):
        self.hasBeenNotified = True
        self.alert = True
        threading.Thread(target=self._notify_alert_stop_later).start()

    def _notify_alert_stop_later(self):
        time.sleep(self.alertTime)
        self._notify_alert_stop(self.sensorName)


class sensorMQTT(sensorGeneral):
    def __init__(self, sensorName):
        # Global Required Variables
        self.sensorName = sensorName
        self.online = None
        self.alert = False
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []

        # Other Variables
        self.sensor = None

    def add_sensor(self, sensor, settings=None):
        self._notify_error(self.sensorName)
        self.sensor = sensor


class Sensor(sensorGeneral):
    """docstring for Sensor"""

    def __init__(self, wd):
        self.wd = wd
        self.allSensors = {}
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []

    def add_sensors(self, settings):
        self.settings = settings
        sensors = settings['sensors']
        for sensor, sensorvalues in sensors.items():
            if sensor not in self.allSensors:
                sensorType = sensorvalues['type']
                sensorName = sensorvalues['name']
                logging.info(" {0}{2} {3} sensor with id: {4}{1}"
                      .format(bcolors.OKBLUE,
                              bcolors.ENDC,
                              sensorType,
                              sensorName,
                              sensor))

                sensorsettings = None
                if sensorType == 'GPIO':
                    try:
                        sensorobject = sensorGPIO(sensor)
                    except Exception:
                        logging.exception("Can't find GPIO:")
                        sensorobject = sensorGeneral(sensor)
                elif sensorType == 'Hikvision':
                    sensorobject = sensorHikvision(sensor)
                elif sensorType == 'MQTT':
                    sensorobject = sensorMQTT(sensor)
                    sensorsettings = settings['mqtt']
                else:
                    sensorobject = sensorGeneral(sensor)

                self.allSensors[sensor] = {
                    'values': sensorvalues,
                    'obj': sensorobject,
                    'settings': sensorsettings
                }
                self.allSensors[sensor]['obj'].on_alert(self._notify_alert)
                self.allSensors[sensor]['obj'].on_alert_stop(
                    self._notify_alert_stop)
                self.allSensors[sensor]['obj'].on_error(self._notify_error)
                self.allSensors[sensor]['obj'].on_error_stop(
                    self._notify_error_stop)
                self.allSensors[sensor]['obj'].add_sensor(
                    self.allSensors[sensor]['values'],
                    self.allSensors[sensor]['settings'])

    def del_sensor(self, sensor):
        self.allSensors[sensor]['obj'].del_sensor()
        del self.allSensors[sensor]

    def reload(self, sensortype=None, settings=None):
        for sensor in self.allSensors:
            if (sensortype is None or
                    sensortype == self.allSensors[sensor]['values']['type']):
                # logging.info(self.allSensors[sensor]['values']['name'])
                self.allSensors[sensor]['obj'].reload(settings)

    def get_all_sensors(self):
        return self.allSensors

