#!/usr/bin/env python

import RPi.GPIO as GPIO
import time
from datetime import datetime
import pytz
import json
import threading
import subprocess
import sys
import smtplib
from email.mime.text import MIMEText


class ReadSettings():
    def __init__(self, jsonfile):
        self.jsonfile = jsonfile
        self.settings = None

    def getNewSettings(self):
        with open(self.jsonfile) as data_file:
            settings = json.load(data_file)
        self.settings = settings
        return self.settings

    def getSettings(self):
        return self.settings

    def updateSettingsFile(self, settings):
        with open(self.jsonfile, 'w') as outfile:
            json.dump(settings, outfile, sort_keys=True, indent=4, separators=(',', ': '))


class DoorSensor():

    """docstring for DoorSensor"""

    def __init__(self, jsonfile, logfile, sipcallfile):
        # GPIO Setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Global Variables
        self.jsonfile = jsonfile
        self.logfile = logfile
        self.sipcallfile = sipcallfile
        self.enabledPins = []
        self.settings = self.ReadSettings()
        self.sensorsStatus = {'sensors': []}

        # Stop execution on exit
        self.setAlert = False
        self.kill_now = False

        # Init Alarm
        self.writeLog("Alarm Booted")
        self.RefreshAlarmData(None)

    def RefreshAlarmData(self, inputPin):
        self.settings = self.ReadSettings()
        pinActive = False
        self.sensorsStatus = {'sensors': []}
        for sensor in self.settings['sensors']:
            sensor['alert'] = False
            if sensor['active'] is True:
                pinActive = True
                # Enable the event change of the pin
                if sensor['pin'] not in self.enabledPins:
                    self.enabledPins.append(sensor['pin'])
                    GPIO.setup(sensor['pin'], GPIO.IN,
                               pull_up_down=GPIO.PUD_UP)
                    GPIO.remove_event_detect(sensor['pin'])
                    GPIO.add_event_detect(
                        sensor['pin'], GPIO.BOTH, callback=self.RefreshAlarmData)
                # Check for the pin status
                if GPIO.input(sensor['pin']) == 1:
                    sensor['alert'] = True
            # Create the list of the pins status
            self.sensorsStatus['sensors'].append(sensor)
        # Clean pin when it becomes inactive
        if inputPin is not None and pinActive is False:
            self.clearUnusedPin(inputPin)

        # Send to JS
        self.sendUpdatesToUI('settingsChanged', self.getPinsStatus())

        # Write Alerted Sensors Log
        for sensor in self.sensorsStatus['sensors']:
            if sensor['alert'] is True:
                self.writeLog(sensor['name'])

        # Call IntruderAlert
        for sensor in self.sensorsStatus['sensors']:
            if sensor['alert'] is True:
                if self.settings['settings']['alarmArmed'] is True and self.setAlert is False:
                    threading.Thread(target=self.intruderAlert).start()
                    # self.intruderAlert()

    def clearUnusedPin(self, pin):
        if pin in self.enabledPins:
            GPIO.remove_event_detect(pin)
            self.enabledPins.remove(pin)

    def ReadSettings(self):
        with open(self.jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def writeNewSettingsToFile(self):
        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def CheckSettingsChanges(self, callback):
        callback(None)
        while self.kill_now is False:
            prevSettings = self.settings
            nowSettings = self.ReadSettings()
            if prevSettings != nowSettings:
                self.settings = nowSettings
                callback(None)
            time.sleep(1)

    def sendUpdatesToUI(self, event, data):
        try:
            # socketio.emit(event, data)
            pass
        except Exception as e:
            raise e

    def writeLog(self, message):
        try:
            mytimezone = pytz.timezone(self.settings['settings']['timezone'])
        except:
            mytimezone = pytz.utc

        myTimeLog = datetime.now(tz=mytimezone).strftime("[%Y-%m-%d %H:%M:%S] ")
        with open(self.logfile, "a") as myfile:
            myfile.write(myTimeLog + message + "\n")
        self.sendUpdatesToUI('sensorsLog', self.getSensorsLog(1))

    def callVoip(self):
        sip_domain = str(self.settings['voip']['domain'])
        sip_user = str(self.settings['voip']['username'])
        sip_password = str(self.settings['voip']['password'])
        sip_repeat = str(self.settings['voip']['timesOfRepeat'])
        if self.settings['voip']['enable'] is True:
            for phone_number in self.settings['voip']['numbersToCall']:
                phone_number = str(phone_number)
                if self.setAlert is True:
                    self.writeLog("Calling " + phone_number)
                    cmd = self.sipcallfile, '-sd', sip_domain, '-su', sip_user, '-sp', sip_password, '-pn', phone_number, '-s', '1', '-mr', sip_repeat
                    print cmd
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                    for line in proc.stderr:
                        sys.stderr.write(line)
                    proc.wait()
                    self.writeLog("Call to " + phone_number + " endend")
                    print "Call Ended"

    def sendMail(self):
        if self.settings['mail']['enable'] is True:
            mail_user = self.settings['mail']['username']
            mail_pwd = self.settings['mail']['password']
            smtp_server = self.settings['mail']['smtpServer']
            smtp_port = self.settings['mail']['smtpPort']

            msg = MIMEText(self.settings['mail']['messageBody'])
            sender = mail_user
            recipients = self.settings['mail']['recipients']
            msg['Subject'] = self.settings['mail']['messageSubject']
            msg['From'] = sender
            msg['To'] = ", ".join(recipients)

            smtpserver = smtplib.SMTP(smtp_server, smtp_port)
            smtpserver.ehlo()
            smtpserver.starttls()
            smtpserver.login(mail_user, mail_pwd)
            smtpserver.sendmail(sender, recipients, msg.as_string())
            smtpserver.close()

            json.dumps(alarmSensors.getPinsStatus())
            self.writeLog("Mail sent to: " + ", ".join(recipients))

    def enableSerene(self):
        if self.settings['serene']['enable'] is True:
            self.writeLog("Serene started")
            serenePin = self.settings['serene']['pin']
            GPIO.setup(serenePin, GPIO.OUT)
            GPIO.output(serenePin, GPIO.HIGH)

    def intruderAlert(self):
        self.setAlert = True
        self.enableSerene()
        self.sendUpdatesToUI('alarmStatus', self.getAlarmStatus())

        self.sendMail()
        self.callVoip()

    def stopSerene(self):
        self.setAlert = False
        serenePin = self.settings['serene']['pin']
        GPIO.setup(serenePin, GPIO.OUT)
        GPIO.output(serenePin, GPIO.LOW)
        self.sendUpdatesToUI('alarmStatus', self.getAlarmStatus())

    def getPinsStatus(self):
        settings = {}
        settings['sensors'] = self.sensorsStatus['sensors']
        settings['settings'] = self.settings['settings']
        return settings

    def activateAlarm(self):
        self.writeLog("Alarm activated")
        self.settings = self.ReadSettings()
        self.settings['settings']['alarmArmed'] = True
        self.writeNewSettingsToFile()
        self.RefreshAlarmData(None)

    def deactivateAlarm(self):
        self.writeLog("Alarm deactivated")
        self.settings['settings']['alarmArmed'] = False
        self.stopSerene()
        self.writeNewSettingsToFile()

    def getAlarmStatus(self):
        return {"alert": self.setAlert}

    def getSerenePin(self):
        return {'serenePin': self.settings['serene']['pin']}

    def getSensorsLog(self, limit):
        with open(self.logfile, "r") as f:
            lines = f.readlines()
        return {"log": lines[-limit:]}

    def setSerenePin(self, pin):
        self.clearUnusedPin(pin)
        self.settings['serene']['pin'] = pin
        self.writeNewSettingsToFile()

    def setSensorName(self, pin, name):
        for i, sensor in enumerate(self.settings['sensors']):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['name'] = name
        self.writeNewSettingsToFile()

    def setSensorState(self, pin, state):
        for i, sensor in enumerate(self.settings['sensors']):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['active'] = state
        self.writeNewSettingsToFile()

    def setSensorPin(self, pin, newpin):
        self.clearUnusedPin(pin)
        for i, sensor in enumerate(self.settings['sensors']):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['pin'] = newpin
        self.writeNewSettingsToFile()

    def addSensor(self, pin, name, active):
        self.settings['sensors'].append({
            "pin": pin,
            "name": name,
            "active": active
        })
        self.sensorsStatus['sensors'].append({
            "pin": pin,
            "name": name,
            "active": active
        })
        self.writeNewSettingsToFile()

    def delSensor(self, pin):
        tmpSensors = []
        for sensor in self.settings['sensors']:
            if sensor['pin'] != pin:
                tmpSensors.append(sensor)

        self.settings['sensors'] = tmpSensors
        self.sensorsStatus['sensors'] = tmpSensors

        self.writeNewSettingsToFile()
