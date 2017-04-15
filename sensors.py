#!/usr/bin/env python

import RPi.GPIO as GPIO
import threading
import time


class Sensor():
    """docstring for Sensor"""

    def __init__(self, sensorType, autoStop):
        self.sensorType = sensorType
        self.autoStop = autoStop
        self.alertTime = 2  # seconds
        self._event_alert = []
        self._event_alert_stop = []
        self.allSensors = {}

    def get_all_sensors(self):
        return self.allSensors

    def get_sensor_state(self, sensor):
        return self.allSensors[int(sensor)]['state']

    def get_alert_sensors(self):
        alertSensors = {}
        for sensor, sensorvalue in self.allSensors.iteritems():
            if sensorvalue['state'] == 1:
                alertSensors[sensor] = sensorvalue
        return alertSensors

    def on_alert(self, callback):
        self._event_alert.append(callback)

    def clear_alert_events(self):
        self._event_alert = []

    def notify_alert(self, sensorName, sensorData):
        if self.autoStop is True:
            threading.Thread(target=self.notify_alert_stop_later, args=[sensorName, sensorData]).start()
        for callback in self._event_alert:
            callback(sensorName, sensorData)

    def on_alert_stop(self, callback):
        self._event_alert_stop.append(callback)

    def clear_alert_stop_events(self):
        self._event_alert_stop = []

    def notify_alert_stop(self, sensorName, sensorData):
        for callback in self._event_alert_stop:
            callback(sensorName, sensorData)

    def notify_alert_stop_later(self, sensorName, sensorData):
        time.sleep(self.alertTime)
        self.notify_alert_stop(sensorName, sensorData)


class sensorGPIO(Sensor):
    def __init__(self):
        Sensor.__init__(self, 'GPIO', False)
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Global Variables
        self.outputPins = {}

    def enableInputPin(self, *pins):
        for pin in pins:
            if pin not in self.allSensors:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.remove_event_detect(pin)
                GPIO.add_event_detect(
                    pin, GPIO.BOTH,
                    callback=self._checkInputPinState,
                    bouncetime=500)
                state = GPIO.input(pin)
                self.allSensors[pin] = {'state': state, 'type': self.sensorType}

    def disableInputPin(self, *pins):
        for pin in pins:
            if pin in self.allSensors:
                GPIO.remove_event_detect(pin)
                del self.allSensors[pin]

    def _checkInputPinState(self, inputPin):
        prevState = self.allSensors[inputPin]['state']
        nowState = GPIO.input(inputPin)
        if nowState != prevState:
            # print "Pin: {0} changed state to: {1}".format(inputPin, str(nowState))
            self.allSensors[inputPin]['state'] = nowState
            if nowState == 1:
                self.notify_alert(inputPin, self.allSensors[inputPin])
            else:
                self.notify_alert_stop(inputPin, self.allSensors[inputPin])
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


# def observer(name, values):
#     print name, values

# asdf = sensorGPIO()
# pinsToEnable = [17, 4, 18, 22]
# asdf.enableInputPin(*pinsToEnable)
# asdf.disableInputPin(4, 18, 22)
# asdf.enableInputPin(18, 22)

# asdf.on_alert(observer)
# asdf.on_alert_stop(observer)

# asdf.enableOutputPin(14)
# print asdf.getOutputPinStates()
# time.sleep(2)
# asdf.disableOutputPin(14)
# print asdf.getOutputPinStates()

# print asdf.get_all_sensors()

# while True:
#     time.sleep(2)  # 2 second delay
