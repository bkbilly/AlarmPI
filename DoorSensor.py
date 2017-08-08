#!/usr/bin/env python

from sensors import sensorGPIO, sensorHikvision
from datetime import datetime
import pytz
import json
import threading
import subprocess
import sys
import smtplib
import re
from email.mime.text import MIMEText


class DoorSensor(sensorGPIO):

    ''' This class runs on the background using GPIO Events Changes.
    It uses a json file to store the settings and a log file to store the logs.
    When a GPIO input changes state after the alarm is activated it can enable
    the Serene, send Mail, call through VoIP.
    Also there is the updateUI method wich it has to be overridden in
    the main application.
    '''

    def __init__(self, jsonfile, logfile, sipcallfile):
        # Global Variables
        self.jsonfile = jsonfile
        self.logfile = logfile
        self.sipcallfile = sipcallfile
        self.settings = self.ReadSettings()
        self.allSensors = {}

        # Stop execution on exit
        self.setAlert = False
        self.kill_now = False

        # Init Alarm
        self.sensorsGPIO = sensorGPIO()
        self.sensorsHikvision = sensorHikvision()
        self.writeLog("system", "Alarm Booted")
        self.RefreshAlarmData()

        # Event Listeners
        self.sensorsGPIO.on_alert(self.sensorAlert)
        self.sensorsGPIO.on_alert_stop(self.sensorStopAlert)
        # Event Listeners
        self.sensorsHikvision.on_alert(self.sensorAlert)
        self.sensorsHikvision.on_alert_stop(self.sensorStopAlert)

    def sensorAlert(self, sensorName):
        self.settings['sensors'][str(sensorName)]['alert'] = True
        self.RefreshAlarmData()
        name = self.settings['sensors'][str(sensorName)]['name']
        enabled = self.settings['sensors'][str(sensorName)]['enabled']
        enabledText = "enabled sensor: "
        sensorLogType = "enabled_sensor"
        if enabled is False:
            enabledText = "Disabled sensor: "
            sensorLogType = "disabled_sensor"
        self.writeLog(sensorLogType, enabledText + name)
        self.checkIntruderAlert()

    def sensorStopAlert(self, sensorName):
        self.settings['sensors'][str(sensorName)]['alert'] = False
        self.RefreshAlarmData()

    def checkIntruderAlert(self):
        # Write Alerted Sensors Log and call IntruderAlert when alarm is activated
        if self.settings['settings']['alarmArmed'] is True and self.setAlert is False:
            for sensor, sensorvalue in self.settings['sensors'].iteritems():
                if sensorvalue['alert'] is True:
                    threading.Thread(target=self.intruderAlert).start()

    def RefreshAlarmData(self):
        ''' This method adds event listener on enabled sensors and removes them for
        the disabled sensors.
        After each call it checks for an alert and calls the method responsible
        for the alert.
        '''
        self.allSensors = {}

        # Get a list of the enabled and the disabled sensors
        for sensor, sensorvalue in self.settings['sensors'].iteritems():
            print sensorvalue
            if sensorvalue['type'] == 'GPIO':
                self.sensorsGPIO.add_sensor(sensor)
                self.allSensors[sensor] = sensorvalue
                sensor_alert = False
                if sensorvalue['enabled'] is True:
                    if self.sensorsGPIO.is_sensor_active(int(sensor)):
                        sensor_alert = True
                self.allSensors[sensor]['alert'] = sensor_alert
            if sensorvalue['type'] == 'Hikvision':
                ip = sensorvalue['ip']
                password = sensorvalue['pass']
                username = sensorvalue['user']
                self.sensorsHikvision.add_sensor(sensor, ip, username, password)
                self.allSensors[sensor] = sensorvalue
                sensor_alert = False
                if sensorvalue['enabled'] is True:
                    if self.sensorsHikvision.is_sensor_active(sensor):
                        sensor_alert = True
                self.allSensors[sensor]['alert'] = sensor_alert

        # Send to JS
        self.updateUI('settingsChanged', self.getSensorsArmed())

    def ReadSettings(self):
        ''' Reads the json settings file and returns it '''
        with open(self.jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def writeNewSettingsToFile(self):
        ''' Write the new settings to the json file '''
        self.RefreshAlarmData()
        with open(self.jsonfile, 'w') as outfile:
            json.dump(self.settings, outfile, sort_keys=True, indent=4, separators=(',', ': '))

    def updateUI(self, event, data):
        ''' Override this method to send changes to the UI '''
        pass

    def writeLog(self, logType, message):
        ''' Write log events into a file and send the last to UI.
        It also uses the timezone from json file to get the local time.
        '''
        try:
            mytimezone = pytz.timezone(self.settings['ui']['timezone'])
        except:
            mytimezone = pytz.utc

        myTimeLog = datetime.now(tz=mytimezone).strftime("%Y-%m-%d %H:%M:%S")
        with open(self.logfile, "a") as myfile:
            myfile.write('({0}) [{1}] {2}\n'.format(logType, myTimeLog, message))
        self.updateUI('sensorsLog', self.getSensorsLog(1))

    def intruderAlert(self):
        ''' This method is called when an intruder is detected. It calls
        all the methods whith the actions that we want to do.
        '''
        self.setAlert = True
        self.writeLog("alarm", "Intruder Alert")
        self.enableSerene()
        self.updateUI('alarmStatus', self.getAlarmStatus())
        threading.Thread(target=self.sendMail).start()
        threading.Thread(target=self.callVoip).start()

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
                    self.writeLog("alarm", "Calling " + phone_number)
                    cmd = self.sipcallfile, '-sd', sip_domain, '-su', sip_user, '-sp', sip_password, '-pn', phone_number, '-s', '1', '-mr', sip_repeat
                    print cmd
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                    for line in proc.stderr:
                        sys.stderr.write(line)
                    proc.wait()
                    self.writeLog("alarm", "Call to " + phone_number + " endend")
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

            self.writeLog("alarm", "Mail sent to: " + ", ".join(recipients))

    def enableSerene(self):
        ''' This method enables the output pin for the serene '''
        if self.settings['serene']['enable'] is True:
            self.writeLog("alarm", "Serene started")
            serenePin = int(self.settings['serene']['pin'])
            self.sensorsGPIO.enableOutputPin(serenePin)

    def stopSerene(self):
        ''' This method disables the output pin for the serene '''
        if self.settings['serene']['enable'] is True:
            serenePin = self.settings['serene']['pin']
            self.sensorsGPIO.disableOutputPin(serenePin)

    def activateAlarm(self):
        ''' Activates the alarm '''
        self.writeLog("user_action", "Alarm activated")
        self.settings['settings']['alarmArmed'] = True
        self.writeNewSettingsToFile()

    def deactivateAlarm(self):
        ''' Deactivates the alarm '''
        self.setAlert = False
        self.writeLog("user_action", "Alarm deactivated")
        self.settings['settings']['alarmArmed'] = False
        self.stopSerene()
        self.updateUI('alarmStatus', self.getAlarmStatus())
        self.writeNewSettingsToFile()

    def getSensorsArmed(self):
        ''' Returns the sensors and alarm status as a json to use it to the UI '''
        sensorsArmed = {}
        sensorsArmed['sensors'] = self.settings['sensors']
        sensorsArmed['alarmArmed'] = self.settings['settings']['alarmArmed']
        return sensorsArmed

    def getAlarmStatus(self):
        ''' Returns the status of the alert for the UI '''
        return {"alert": self.setAlert}

    def getSensorsLog(self, limit=100, selectTypes='all', getFormat='text'):
        ''' Returns the last n lines if the log file. 
        If selectTypes is specified, then it returns only this type of logs.
        Available types: user_action, disabled_sensor, enabled_sensor, system, alarm
        If the getFormat is specified as json, then it returns it in a 
        json format (programmer friendly) '''
        with open(self.logfile, "r") as f:
            lines = f.readlines()
        logTypes = []
        for line in lines:
            try:
                mymatch = re.match(r'^\((.*)\) \[(.*)\] (.*)', line)
                logType = mymatch.group(1)
                logTime = mymatch.group(2)
                logText = mymatch.group(3)
            except:
                mymatch = re.match(r'^\[(.*)\] (.*)', line)
                logType = "unknown"
                logTime = mymatch.group(1)
                logText = mymatch.group(2)
            if (logType in selectTypes or 'all' in selectTypes):
                if getFormat == 'json':
                    logTypes.append({
                        'type': logType,
                        'event': logText,
                        'time': logTime
                    })
                else:
                    logTypes.append('[{0}] {1}'.format(logTime, logText))
        return {"log": logTypes[-limit:]}

    def getSerenePin(self):
        ''' Returns the output pin for the serene '''
        return {'serenePin': self.settings['serene']['pin']}

    def getPortUI(self):
        ''' Returns the port for the UI '''
        return self.settings['ui']['port']

    def getSereneSettings(self):
        return self.settings['serene']

    def getMailSettings(self):
        return self.settings['mail']

    def getVoipSettings(self):
        return self.settings['voip']

    def getUISettings(self):
        return self.settings['ui']

    def setSereneSettings(self, message):
        if self.settings['serene'] != message:
            self.settings['serene'] = message
            self.writeLog("user_action", "Settings for Serene changed")
            self.writeNewSettingsToFile()

    def setMailSettings(self, message):
        if self.settings['mail'] != message:
            self.settings['mail'] = message
            self.writeLog("user_action", "Settings for Mail changed")
            self.writeNewSettingsToFile()

    def setVoipSettings(self, message):
        if self.settings['voip'] != message:
            self.settings['voip'] = message
            self.writeLog("user_action", "Settings for VoIP changed")
            self.writeNewSettingsToFile()

    def setUISettings(self, message):
        if self.settings['ui'] != message:
            self.settings['ui'] = message
            self.writeLog("user_action", "Settings for UI changed")
            self.writeNewSettingsToFile()

    def setSensorName(self, sensor, name):
        ''' Changes the Sensor Name '''
        self.settings['sensors'][str(sensor)]['name'] = name
        self.writeNewSettingsToFile()

    def setSensorState(self, sensor, state):
        ''' Activate or Deactivate a sensor '''
        self.settings['sensors'][str(sensor)]['enabled'] = state
        self.writeNewSettingsToFile()

        logState = "Deactivated"
        if state is True:
            logState = "Activated"
        logSensorName = self.settings['sensors'][str(sensor)]['name']
        self.writeLog("user_action", "{0} sensor: {1}".format(logState, logSensorName))
        self.writeNewSettingsToFile()

    def setSensorPin(self, pin, newpin):
        ''' Changes the Sensor Pin '''
        self.settings['sensors'][str(newpin)] = self.settings['sensors'][str(pin)]
        del self.settings['sensors'][str(pin)]
        self.sensorsGPIO.del_sensor(pin)
        self.writeNewSettingsToFile()

    def addSensor(self, sensor, name, sensorType, enabled):
        ''' Add a new sensor '''
        self.settings['sensors'][str(sensor)] = {
            'name': name,
            'enabled': enabled,
            'type': sensorType
        }
        self.writeNewSettingsToFile()

    def delSensor(self, sensor):
        ''' Delete a sensor '''
        del self.settings['sensors'][str(sensor)]
        self.sensorsGPIO.del_sensor(sensor)

        self.writeNewSettingsToFile()

    def check_auth(self, username, password):
        """This function is called to check if a
        username / password combination is valid.
        """
        myuser = self.settings['ui']['username']
        mypass = self.settings['ui']['password']
        return username == myuser and password == mypass
