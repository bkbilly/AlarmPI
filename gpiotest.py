import RPi.GPIO as GPIO
import time
import json
import signal
import threading

class DoorSensor():
    """docstring for DoorSensor"""
    def __init__(self, jsonfile):
        self.jsonfile = jsonfile
        self.setAlert = False
        self.kill_now = False

        # Stop execution on exit
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.myCallBack(0)

        outputPins = self.getOutputPins(self.settings)
        download_thread = threading.Thread(target=self.alert, args=([outputPins]))
        download_thread.start()

        while True and self.kill_now == False:
            time.sleep(1)

    def myCallBack(self, inputPin):
        foundInputPin = False
        self.settings = self.readSettings(self.jsonfile)
        self.setAlert = False
        for sensor in self.settings["sensors"]:
            if sensor["active"] == True:
                foundInputPin = True
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(sensor["pin"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.remove_event_detect(inputPin)
                GPIO.add_event_detect(sensor["pin"], GPIO.BOTH, callback=self.myCallBack)
                if GPIO.input(sensor["pin"]) == 1:
                    print sensor["name"]
                    self.setAlert = True
        if foundInputPin == False:
            GPIO.remove_event_detect(inputPin)
        if self.setAlert == False:
            print "No alarm!"


    def exit_gracefully(self, signum, frame):
        self.kill_now = True

    def readSettings(self, jsonfile):
        with open(jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def getOutputPins(self, settings):
        outputPins = []
        for alarm in settings["alarms"]:
            if alarm["active"] == True:
                outputPins.append(alarm["pin"])
        return outputPins

    def alert(self, outputPins):
        ''' 5V & GPIO(8) '''
        GPIO.setwarnings(False)

        while self.kill_now == False:
            if self.setAlert == True:
                for outputPin in outputPins:
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(outputPin, GPIO.OUT)
                    GPIO.output(outputPin, 0)
                    time.sleep(.00001)
                    GPIO.output(outputPin, 1)
                    time.sleep(.00001)


door = DoorSensor("settings.json")

