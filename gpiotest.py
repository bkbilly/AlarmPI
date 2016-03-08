import RPi.GPIO as GPIO
import time
import json
import signal
import threading


class DoorSensor():
    """docstring for DoorSensor"""
    def __init__(self, jsonfile):
        # Global Variables
        self.setAlert = False
        self.kill_now = False
        self.outputPins = []

        # Stop execution on exit
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        # Infinite While that makes the Alarm work
        while True and self.kill_now == False:
            #Read the JSON File and get the Inut and Output Pins
            settings = self.readSettings(jsonfile)
            inputPins = self.getInputPins(settings)
            self.outputPins = self.getOutputPins(settings)

            alertPins = []
            for inputPin in inputPins:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(inputPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                input_state = GPIO.input(inputPin)
                if input_state == True:
                    alertPins.append(inputPin)

            if len(alertPins) == 0:
                self.setAlert = False
                print('...')
            else:
                if self.setAlert is False:
                    self.setAlert = True
                    download_thread = threading.Thread(target=self.alert, args=())
                    download_thread.start()
                print('ALERT!!!!')
            time.sleep(0.4)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True

    def readSettings(self, jsonfile):
        with open(jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def getInputPins(self, settings):
        inputPins = []
        for sensor in settings["sensors"]:
            if sensor["active"] is True:
                inputPins.append(sensor["pin"])
        return inputPins

    def getOutputPins(self, settings):
        outputPins = []
        for alarm in settings["alarms"]:
            if alarm["active"] == True:
                outputPins.append(alarm["pin"])
        return outputPins

    def alert(self):
        ''' 5V & GPIO(8) '''
        GPIO.setwarnings(False)

        while self.setAlert == True and self.kill_now == False:
            for outputPin in self.outputPins:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(outputPin, GPIO.OUT)
                GPIO.output(outputPin, 0)
                time.sleep(.0001)
                GPIO.output(outputPin, 1)
                time.sleep(.0001)


door = DoorSensor("settings.json")
