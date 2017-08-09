#!/usr/bin/env python

import RPi.GPIO as GPIO
import threading
import time

import requests
import re


class outputGPIO():
    def enableOutputPin(self, *pins):
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            state = GPIO.input(pin)
            if state == GPIO.LOW:
                GPIO.output(pin, GPIO.HIGH)
            self.outputPins[pin] = {'state': state, 'type': 'GPIO.output'}

    def disableOutputPin(self, *pins):
        for pin in pins:
            if pin in self.outputPins:
                GPIO.setup(pin, GPIO.OUT)
                if GPIO.input(pin) == GPIO.HIGH:
                    GPIO.output(pin, GPIO.LOW)
                GPIO.setup(pin, GPIO.IN)
                del self.outputPins[pin]

    def getOutputPinStates(self):
        return self.outputPins


class sensorGPIO():
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

    def getOnlineStatus(self):
        return self.online

    def getAlertStatus(self):
        return self.alert

    def setAlertStatus(self):
        self.gpioState = GPIO.input(self.pin)
        self.alert = False
        if self.gpioState == 1:
            self.alert = True

    def add_sensor(self, sensor):
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
            # print "Pin: {0} changed state to: {1}".format(self.pin, str(nowState))
            if nowState == 1:
                self._notify_alert()
            else:
                self._notify_alert_stop()
        else:
            print "Wrong state change. Ignoring!!!"

    def forceNotify(self):
        if GPIO.input(self.pin) == 1:
            self._notify_alert()
        else:
            self._notify_alert_stop()

    # ------------------------------
    def on_alert(self, callback):
        self._event_alert.append(callback)

    def on_alert_stop(self, callback):
        self._event_alert_stop.append(callback)

    def on_error(self, callback):
        pass

    def on_error_stop(self, callback):
        pass

    def _notify_alert(self):
        self.setAlertStatus()
        for callback in self._event_alert:
            callback(self.sensorName)

    def _notify_alert_stop(self):
        self.setAlertStatus()
        for callback in self._event_alert_stop:
            callback(self.sensorName)

    def _notify_error(self):
        pass

    def _notify_error_stop(self):
        pass


class sensorHikvision():
    def __init__(self, sensorName):
        # Global Required Variables
        self.sensorName = sensorName
        self.online = False
        self.alert = False
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []

        # Other Variables
        self.alertTime = 8
        self.threadRunforever = None
        self.runforever = True

    def add_sensor(self, sensor):
        ip = sensor['ip']
        username = sensor['user']
        password = sensor['pass']
        # sensor_settings = {'ip': ip, 'username': username, 'password': password}
        # print sensor_settings
        try:
            self.threadRunforever._Thread__stop()
        except Exception as e:
            print e
        self.threadRunforever = threading.Thread(target=self.runInBackground, args=[sensor, ip, username, password])
        self.threadRunforever.daemon = True
        self.threadRunforever.start()

    def runInBackground(self, sensor, ip, username, password):
        print "RUNNIN NEW HIKVISION!!!"
        authorization = requests.auth.HTTPBasicAuth(username, password)
        while self.runforever:
            try:
                response = requests.get('http://' + ip + '/ISAPI/Event/notification/alertStream',
                                        auth=authorization,
                                        timeout=5,
                                        stream=True)
                self._notify_error_stop()
                for chunk in response.iter_lines():
                    if chunk:
                        match = re.match(r'<eventType>(.*)</eventType>', chunk)
                        if match:
                            if match.group(1) == 'linedetection':
                                self._notify_alert()
            except requests.exceptions.RequestException as e:
                self._notify_error()
                print e
                time.sleep(5)

    def del_sensor(self):
        self.runforever = False
        try:
            self.threadRunforever._Thread__stop()
        except Exception as e:
            print e

    def forceNotify(self):
        pass

    # ------------------------------
    def on_alert(self, callback):
        self._event_alert.append(callback)

    def on_alert_stop(self, callback):
        self._event_alert_stop.append(callback)

    def on_error(self, callback):
        self._event_error.append(callback)

    def on_error_stop(self, callback):
        self._event_error_stop.append(callback)

    def _notify_alert(self):
        self.alert = True
        threading.Thread(target=self._notify_alert_stop_later).start()
        for callback in self._event_alert:
            callback(self.sensorName)

    def _notify_alert_stop(self):
        self.alert = False
        for callback in self._event_alert_stop:
            callback(self.sensorName)

    def _notify_alert_stop_later(self):
        time.sleep(self.alertTime)
        self._notify_alert_stop(self.sensorName)

    def _notify_error(self):
        self.online = False
        for callback in self._event_error:
            callback(self.sensorName)

    def _notify_error_stop(self):
        self.online = True
        for callback in self._event_error_stop:
            callback(self.sensorName)


class Sensor():
    """docstring for Sensor"""

    def __init__(self):
        # self.sensorType = sensorType
        # self.autoStop = autoStop
        # self.alertTime = alertTime  # seconds
        self._event_alert = []
        self._event_alert_stop = []
        self._event_error = []
        self._event_error_stop = []
        self.allSensors = {}

    def add_sensors(self, sensors):
        for sensor, sensorvalues in sensors.iteritems():
            if sensor not in self.allSensors:
                print sensor
                sensorType = sensorvalues['type']
                if sensorType == 'GPIO':
                    sensorobject = sensorGPIO(sensor)
                    print 'GPIO', sensor
                elif sensorType == 'Hikvision':
                    sensorobject = sensorHikvision(sensor)
                    print 'Hikvision', sensor
                self.allSensors[sensor] = {'values': sensorvalues, 'obj': sensorobject}
                self.allSensors[sensor]['obj'].on_alert(self._notify_alert)
                self.allSensors[sensor]['obj'].on_alert_stop(self._notify_alert_stop)
                self.allSensors[sensor]['obj'].on_error(self._notify_error)
                self.allSensors[sensor]['obj'].on_error_stop(self._notify_error_stop)
                self.allSensors[sensor]['obj'].add_sensor(self.allSensors[sensor]['values'])
            self.allSensors[sensor]['obj'].forceNotify()

    def printTest1(self, hello):
        print "on_alert", hello

    def printTest2(self, hello):
        print "on_alert_stop", hello

    def printTest3(self, hello):
        print "on_error", hello

    def printTest4(self, hello):
        print "on_error_stop", hello

    def del_sensor(self, sensor):
        self.allSensors[sensor]['obj'].del_sensor()
        del self.allSensors[sensor]

    def get_all_sensors(self):
        return self.allSensors

    # ------------------------------
    def on_alert(self, callback):
        self._event_alert.append(callback)

    def on_alert_stop(self, callback):
        self._event_alert_stop.append(callback)

    def on_error(self, callback):
        self._event_error.append(callback)

    def on_error_stop(self, callback):
        self._event_error_stop.append(callback)

    def _notify_alert(self, sensorName):
        for callback in self._event_alert:
            callback(sensorName)

    def _notify_alert_stop(self, sensorName):
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
