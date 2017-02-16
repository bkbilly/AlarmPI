#!/usr/bin/env python

import RPi.GPIO as GPIO
from datetime import datetime
import pytz
import json
import threading
import subprocess
import sys
import smtplib
from email.mime.text import MIMEText


class DoorSensor():

    ''' This class runs on the background using GPIO Events Changes.
    It uses a json file to store the settings and a log file to store the logs.
    When a GPIO input changes state after the alarm is activated it can enable
    the Serene, send Mail, call through VoIP.
    Also there is the updateUI method wich it has to be overridden in
    the main application.
    '''

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
        self.hiddenUIPassword = "**************"

        # Stop execution on exit
        self.setAlert = False
        self.kill_now = False

        # Init Alarm
        self.writeLog("Alarm Booted")
        self.RefreshAlarmData(None)

    def RefreshAlarmData(self, inputPin):
        ''' This method adds event listener on enabled sensors and removes them for
        the disabled sensors.
        After each call it checks for an alert and calls the method responsible
        for the alert.
        '''
        enabledSensors, disabledSensors = self.getEnabledDisabledSensors()
        self.sensorsStatus = {'sensors': []}

        # Enable pin events, check for their status and append result to sensorsStatus
        for sensor in enabledSensors:
            if sensor['pin'] not in self.enabledPins:
                print "enabling pin: ", sensor['pin']
                self.enabledPins.append(sensor['pin'])
                GPIO.setup(sensor['pin'], GPIO.IN,
                           pull_up_down=GPIO.PUD_UP)
                GPIO.remove_event_detect(sensor['pin'])
                GPIO.add_event_detect(
                    sensor['pin'], GPIO.BOTH, callback=self.RefreshAlarmData)
            sensor['alert'] = False
            if GPIO.input(sensor['pin']) == 1:
                sensor['alert'] = True
            self.sensorsStatus['sensors'].append(sensor)

        # Remove pin events and append result to sensorsStatus
        for sensor in disabledSensors:
            if sensor['pin'] in self.enabledPins:
                print "disabling pin: ", sensor['pin']
                GPIO.remove_event_detect(sensor['pin'])
                self.enabledPins.remove(sensor['pin'])
            sensor['alert'] = False
            self.sensorsStatus['sensors'].append(sensor)

        # Send to JS
        self.updateUI('settingsChanged', self.getSensorsArmed())

        # Write Alerted Sensors Log and call IntruderAlert when alarm is activated
        for sensor in self.sensorsStatus['sensors']:
            if sensor['alert'] is True:
                self.writeLog(sensor['name'])
                if self.settings['settings']['alarmArmed'] is True and self.setAlert is False:
                    threading.Thread(target=self.intruderAlert).start()

        # TODO REMOVE PRINT
        print "\n\n\ncalled RefreshAlarmData"
        print inputPin
        print self.enabledPins

    def getEnabledDisabledSensors(self):
        ''' Gets a list of the enabled and the disabled sensors '''
        enabledSensors = []
        disabledSensors = []
        self.settings = self.ReadSettings()
        for sensor in self.settings['sensors']:
            if sensor['active'] is True:
                enabledSensors.append(sensor)
            else:
                disabledSensors.append(sensor)
        return enabledSensors, disabledSensors

    def ReadSettings(self):
        ''' Reads the json settings file and returns it '''
        with open(self.jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def writeNewSettingsToFile(self):
        ''' Write the new settings to the json file '''
        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def updateUI(self, event, data):
        ''' Override this method to send changes to the UI '''
        pass

    def writeLog(self, message):
        ''' Write log events into a file and send the last to UI.
        It also uses the timezone from json file to get the local time.
        '''
        try:
            mytimezone = pytz.timezone(self.settings['ui']['timezone'])
        except:
            mytimezone = pytz.utc

        myTimeLog = datetime.now(tz=mytimezone).strftime("[%Y-%m-%d %H:%M:%S] ")
        with open(self.logfile, "a") as myfile:
            myfile.write(myTimeLog + message + "\n")
        self.updateUI('sensorsLog', self.getSensorsLog(1))

    def intruderAlert(self):
        ''' This method is called when an intruder is detected. It calls
        all the methods whith the actions that we want to do.
        '''
        self.setAlert = True
        self.enableSerene()
        self.updateUI('alarmStatus', self.getAlarmStatus())
        self.sendMail()
        self.callVoip()

    def callVoip(self):
        ''' This method uses a prebuild application in C to connect to the SIP provider
        and call all the numbers in the json settings file.
        '''
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
        ''' This method sends an email to all recipients in the json settings file. '''
        if self.settings['mail']['enable'] is True:
            mail_user = self.settings['mail']['username']
            mail_pwd = self.settings['mail']['password']
            smtp_server = self.settings['mail']['smtpServer']
            smtp_port = int(self.settings['mail']['smtpPort'])

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

            self.writeLog("Mail sent to: " + ", ".join(recipients))

    def enableSerene(self):
        ''' This method enables the output pin for the serene '''
        if self.settings['serene']['enable'] is True:
            self.writeLog("Serene started")
            serenePin = int(self.settings['serene']['pin'])
            GPIO.setup(serenePin, GPIO.OUT)
            GPIO.output(serenePin, GPIO.HIGH)

    def stopSerene(self):
        ''' This method disables the output pin for the serene '''
        if self.settings['serene']['enable'] is True:
            serenePin = self.settings['serene']['pin']
            GPIO.setup(serenePin, GPIO.OUT)
            GPIO.output(serenePin, GPIO.LOW)

    def activateAlarm(self):
        ''' Activates the alarm '''
        self.writeLog("Alarm activated")
        self.settings = self.ReadSettings()
        self.settings['settings']['alarmArmed'] = True
        self.writeNewSettingsToFile()

    def deactivateAlarm(self):
        ''' Deactivates the alarm '''
        self.setAlert = False
        self.writeLog("Alarm deactivated")
        self.settings['settings']['alarmArmed'] = False
        self.stopSerene()
        self.updateUI('alarmStatus', self.getAlarmStatus())
        self.writeNewSettingsToFile()

    def getSensorsArmed(self):
        ''' Returns the sensors and alarm status as a json to use it to the UI '''
        sensorsArmed = {}
        sensorsArmed['sensors'] = self.sensorsStatus['sensors']
        sensorsArmed['alarmArmed'] = self.settings['settings']['alarmArmed']
        return sensorsArmed

    def getAlarmStatus(self):
        ''' Returns the status of the alert for the UI '''
        return {"alert": self.setAlert}

    def getSensorsLog(self, limit):
        ''' Returns the last n lines if the log file '''
        with open(self.logfile, "r") as f:
            lines = f.readlines()
        return {"log": lines[-limit:]}

    def getSerenePin(self):
        ''' Returns the output pin for the serene '''
        return {'serenePin': self.settings['serene']['pin']}

    def setSerenePin(self, pin):
        ''' Changes the input serene pin '''
        self.settings['serene']['pin'] = pin
        self.writeNewSettingsToFile()
        self.RefreshAlarmData(pin)

    def setSensorName(self, pin, name):
        ''' Changes the Sensor Name '''
        for i, sensor in enumerate(self.settings['sensors']):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['name'] = name
        self.writeNewSettingsToFile()

    def setSensorState(self, pin, state):
        ''' Activate or Deactivate a sensor '''
        for i, sensor in enumerate(self.settings['sensors']):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['active'] = state
        self.writeNewSettingsToFile()
        self.RefreshAlarmData(pin)

    def setSensorPin(self, pin, newpin):
        ''' Changes the Sensor Pin '''
        for i, sensor in enumerate(self.settings['sensors']):
            if sensor['pin'] == pin:
                self.settings['sensors'][i]['pin'] = newpin
        self.writeNewSettingsToFile()
        self.RefreshAlarmData(pin)

    def addSensor(self, pin, name, active):
        ''' Add a new sensor '''
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
        self.RefreshAlarmData(pin)

    def delSensor(self, pin):
        ''' Delete a sensor '''
        tmpSensors = []
        for sensor in self.settings['sensors']:
            if sensor['pin'] != pin:
                tmpSensors.append(sensor)

        self.settings['sensors'] = tmpSensors
        self.sensorsStatus['sensors'] = tmpSensors

        self.writeNewSettingsToFile()
        self.RefreshAlarmData(pin)

    def check_auth(self, username, password):
        """This function is called to check if a
        username / password combination is valid.
        """
        myuser = self.settings['ui']['username']
        mypass = self.settings['ui']['password']
        return username == myuser and password == mypass

    def getPortUI(self):
        ''' Returns the port for the UI '''
        return self.settings['ui']['port']

    def getSereneSettings(self):
        return self.settings['serene']

    def setSereneSettings(self, message):
        self.settings['serene']['enable'] = message['enable']
        self.settings['serene']['pin'] = message['pin']
        self.writeNewSettingsToFile()

    def getMailSettings(self):
        return self.settings['mail']

    def setMailSettings(self, message):
        self.settings['mail']['enable'] = message['enable']
        self.settings['mail']['smtpServer'] = message['smtpServer']
        self.settings['mail']['smtpPort'] = message['smtpPort']
        self.settings['mail']['recipients'] = message['recipients']
        self.settings['mail']['messageSubject'] = message['messageSubject']
        self.settings['mail']['messageBody'] = message['messageBody']
        self.settings['mail']['username'] = message['username']
        self.settings['mail']['password'] = message['password']
        self.writeNewSettingsToFile()

    def getVoipSettings(self):
        return self.settings['voip']

    def setVoipSettings(self, message):
        self.settings['voip']['enable'] = message['enable']
        self.settings['voip']['domain'] = message['domain']
        self.settings['voip']['numbersToCall'] = message['numbersToCall']
        self.settings['voip']['timesOfRepeat'] = message['timesOfRepeat']
        self.settings['voip']['username'] = message['username']
        self.settings['voip']['password'] = message['password']
        self.writeNewSettingsToFile()

    def getUISettings(self):
        return self.settings['ui']

    def setUISettings(self, message):
        self.settings['ui']['timezone'] = message['timezone']
        self.settings['ui']['username'] = message['username']
        self.settings['ui']['password'] = message['password']
        self.writeNewSettingsToFile()
