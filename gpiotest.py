import RPi.GPIO as GPIO
import time
import json
import signal
import threading


class DoorSensor():

    """docstring for DoorSensor"""

    def __init__(self, jsonfile, alertpins):
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        # Global Variables
        self.jsonfile = jsonfile
        self.alertpins = alertpins
        self.enabledPins = []
        self.settings = self.readSettings(self.jsonfile)

        # Stop execution on exit
        self.setAlert = False
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        # Init Alarm
        self.clearAlarmsFile()
        self.checkForAlarm(0)

        # Start checking for setting changes in a thread
        thr = threading.Thread(
            target=self.checkSettingsChanges, args=(self.checkForAlarm,))
        thr.start()

        # Start PC Speaker thread for Alert
        # outputPins = self.getOutputPins(self.settings)
        # download_thread = threading.Thread(target=self.alert, args=([outputPins]))
        # download_thread.start()

        # Run until killed
        while True and self.kill_now is False:
            time.sleep(1)

    def checkForAlarm(self, inputPin):
        pinActive = False
        alertSensors = []
        self.setAlert = False
        pinsStatus = {'sensors': []}
        for sensor in self.settings["sensors"]:
            if sensor["active"] is True:
                pinActive = True
                if sensor["pin"] not in self.enabledPins:
                    self.enabledPins.append(sensor["pin"])
                    GPIO.setup(sensor["pin"], GPIO.IN,
                               pull_up_down=GPIO.PUD_UP)
                    GPIO.remove_event_detect(sensor["pin"])
                    GPIO.add_event_detect(
                        sensor["pin"], GPIO.BOTH, callback=self.checkForAlarm)

                if GPIO.input(sensor["pin"]) == 1:
                    self.setAlert = True
                    pinAlert = True
                    alertSensors.append(sensor)
                else:
                    pinAlert = False
                pinsStatus["sensors"].append({
                    "pin": sensor["pin"],
                    "active": sensor["active"],
                    "alert": pinAlert
                })
        if pinActive is False and inputPin in self.enabledPins:
            GPIO.remove_event_detect(inputPin)
            self.enabledPins.remove(inputPin)

        print "------------"
        with open(self.alertpins, 'w') as f:
            f.write(json.dumps(pinsStatus))
        if self.setAlert is False:
            print "No alarm!"
        else:
            for alertSensor in alertSensors:
                print alertSensor  # ["name"]

    def clearAlarmsFile(self):
        with open(self.alertpins, 'w'):
            pass

    def exit_gracefully(self, signum, frame):
        self.kill_now = True
        self.clearAlarmsFile()

    def readSettings(self, jsonfile):
        with open(jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def getOutputPins(self, settings):
        outputPins = []
        for alarm in settings["alarms"]:
            if alarm["active"] is True:
                outputPins.append(alarm["pin"])
        return outputPins

    def alert(self, outputPins):
        while self.kill_now is False:
            if self.setAlert is True:
                for outputPin in outputPins:
                    GPIO.setup(outputPin, GPIO.OUT)

                    p = GPIO.PWM(outputPin, 10000)
                    p.start(0)
                    for dc in range(0, 101, 50):
                        p.ChangeDutyCycle(dc)
                        time.sleep(0.1)
                    # GPIO.output(outputPin, 0)
                    # time.sleep(.00001)
                    # GPIO.output(outputPin, 1)
                    # time.sleep(.00001)
            else:
                time.sleep(1)
                for outputPin in outputPins:
                    GPIO.setup(outputPin, GPIO.OUT, initial=GPIO.LOW)
                    GPIO.output(outputPin, GPIO.LOW)

    def checkSettingsChanges(self, callback):
        callback(0)
        while self.kill_now is False:
            prevSettings = self.settings
            nowSettings = self.readSettings(self.jsonfile)
            if prevSettings != nowSettings:
                self.settings = nowSettings
                callback(0)
            time.sleep(1)


door = DoorSensor("web/settings.json", "web/alertpins.json")

# GPIO.setmode(GPIO.BCM)
# GPIO.setup(4, GPIO.OUT)

# p = GPIO.PWM(4, 10000)  # channel=12 frequency=50Hz
# p.start(0)
# try:
#     while 1:
#         for dc in range(0, 101, 20):
#             p.ChangeDutyCycle(dc)
#             time.sleep(0.1)
# except KeyboardInterrupt:
#     pass
# p.stop()
# GPIO.cleanup()
