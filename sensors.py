#!/usr/bin/env python

import RPi.GPIO as GPIO
import threading
import time

import requests
import re


class Sensor():
    """docstring for Sensor"""

    def __init__(self, sensorType, autoStop, alertTime):
        self.sensorType = sensorType
        self.autoStop = autoStop
        self.alertTime = alertTime  # seconds
        self._event_alert = []
        self._event_alert_stop = []
        self.allSensors = {}
        self.activeSensorText = "active"
        self.inactiveSensorText = "inactive"

    def add_sensor(self, *sensors):
        pass

    def del_sensor(self, *sensors):
        pass

    def get_all_sensors(self):
        return self.allSensors

    def is_sensor_active(self, sensor):
        if self.allSensors[sensor]['state'] == self.activeSensorText:
            return True
        else:
            return False

    def on_alert(self, callback):
        self._event_alert.append(callback)

    def _notify_alert(self, sensorName):
        self.allSensors[sensorName]['state'] = self.activeSensorText
        if self.autoStop is True:
            threading.Thread(target=self._notify_alert_stop_later, args=[sensorName]).start()
        for callback in self._event_alert:
            callback(sensorName)

    def on_alert_stop(self, callback):
        self._event_alert_stop.append(callback)

    def _notify_alert_stop(self, sensorName):
        self.allSensors[sensorName]['state'] = self.inactiveSensorText
        for callback in self._event_alert_stop:
            callback(sensorName)

    def _notify_alert_stop_later(self, sensorName):
        time.sleep(self.alertTime)
        self._notify_alert_stop(sensorName)


class sensorGPIO(Sensor):
    def __init__(self):
        Sensor.__init__(self, 'GPIO', False, 0)
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Global Variables
        self.outputPins = {}

    def add_sensor(self, *sensors):
        for sensor in sensors:
            pin = int(sensor)
            if pin not in self.allSensors:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.remove_event_detect(pin)
                GPIO.add_event_detect(
                    pin, GPIO.BOTH,
                    callback=self._checkInputPinState,
                    bouncetime=500)
                state = GPIO.input(pin)
                self.allSensors[pin] = {'state': state, 'type': self.sensorType}

    def del_sensor(self, *sensors):
        for sensor in sensors:
            pin = int(sensor)
            if pin in self.allSensors:
                del self.allSensors[pin]
                GPIO.remove_event_detect(pin)

    def _checkInputPinState(self, inputPin):
        prevState = self.allSensors[inputPin]['state']
        nowState = GPIO.input(inputPin)
        if nowState != prevState:
            # print "Pin: {0} changed state to: {1}".format(inputPin, str(nowState))
            if nowState == 1:
                self._notify_alert(inputPin)
            else:
                self._notify_alert_stop(inputPin)
        else:
            print "Wrong state change. Ignoring!!!"

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


class sensorHikvision(Sensor):
    def __init__(self):
        Sensor.__init__(self, 'Hikvision', True, 8)

    def add_sensor(self, sensor, ip, username, password):
        if sensor not in self.allSensors:
            self.allSensors[sensor] = {'state': True, 'type': self.sensorType}
            threading.Thread(target=self.runInBackground, args=[sensor, ip, username, password]).start()

    def runInBackground(self, sensor, ip, username, password):
        print "RUNNIN NEW HIKVISION!!!"
        authorization = requests.auth.HTTPBasicAuth('admin', 'loco8Way')
        while True:
            response = requests.get('http://' + ip + '/ISAPI/Event/notification/alertStream',
                                    auth=authorization,
                                    stream=True)
            for chunk in response.iter_lines():
                if chunk:
                    match = re.match(r'<eventType>(.*)</eventType>', chunk)
                    if match:
                        if match.group(1) == 'linedetection':
                            if not self.is_sensor_active(sensor):
                                self._notify_alert(sensor)

    def del_sensor(self, *sensors):
        for sensor in sensors:
            if sensor in self.allSensors:
                del self.allSensors[sensor]
                pin = int(sensor)
                GPIO.remove_event_detect(pin)
                del self.allSensors[pin]
