#!/usr/bin/env python

from sensors import Sensor, outputGPIO
from logs import Logs
from notifier import Notify
from colors import bcolors
from datetime import datetime
import pytz
import json
import threading
import time
import subprocess
import sys
import smtplib
import re
from email.mime.text import MIMEText
import uuid
import paho.mqtt.client as mqtt
from collections import OrderedDict


class Worker():

    """ This class runs on the background using GPIO Events Changes.
    It uses a json file to store the settings and a log file to store the logs.
    When a sensor changes state after the alarm is activated it can enable
    the Serene, send Mail, call through VoIP.
    Also there is the updateUI method wich it has to be overridden in
    the main application.
    """

    def __init__(self, jsonfile, logfile, sipcallfile, optsUpdateUI=None):
        """ Init for the Worker class """

        print("{0}------------ INIT FOR DOOR SENSOR CLASS! ----------------{1}"
              .format(bcolors.HEADER, bcolors.ENDC))
        # Global Variables
        self.jsonfile = jsonfile
        self.logfile = logfile
        self.sipcallfile = sipcallfile
        self.settings = self.ReadSettings()
        self.mqttclient = mqtt.Client("", True, None, mqtt.MQTTv31)
        self.limit = 10
        self.logtypes = 'all'

        # Stop execution on exit
        self.alarmTriggered = False
        self.kill_now = False

        # Init Alarm
        self.mynotify = Notify(self.settings)
        self.mynotify.setupUpdateUI(optsUpdateUI)
        self.mynotify.setupSendStateMQTT(self.mqttclient.publish)
        mylogs = Logs(self.logfile)
        self.getSensorsLog = mylogs.getSensorsLog
        self.writeLog("system", "Alarm Booted")
        mylogs.startTrimThread()

        # Event Listeners
        self.sensors = Sensor()
        self.sensors.on_alert(self.sensorAlert)
        self.sensors.on_alert_stop(self.sensorStopAlert)
        self.sensors.on_error(self.sensorError)
        self.sensors.on_error_stop(self.sensorStopError)
        self.sensors.add_sensors(self.settings)
        self.mqttclient.on_connect_mqtt = self.on_connect_mqtt
        self.mqttclient.on_message_mqtt = self.on_message_mqtt

        # Init MQTT Messages
        self.startstopMQTT()
        self.mynotify.sendStateMQTT(self.getTriggeredStatus())


    def startstopMQTT(self):
        """ Start or Stop the MQTT connection based on the settings """

        self.mqttclient.disconnect()
        self.mqttclient.loop_stop(force=False)
        if self.settings['mqtt']['enable']:
            try:
                mqttHost = self.settings['mqtt']['host']
                mqttPort = self.settings['mqtt']['port']
                self.mqttclient.connect(mqttHost, mqttPort, 60)
                self.mqttclient.loop_start()
            except Exception as e:
                print("{0}MQTT: {2}{1}".format(
                    bcolors.FAIL, bcolors.ENDC, str(e)))
        else:
            self.mqttclient.disconnect()
            self.mqttclient.loop_stop(force=False)

    def on_connect_mqtt(self, mqttclient, userdata, flags, rc):
        """ Subscribe to MQTT commands """

        print("{0}Connected to MQTT with result code {2}{1}".format(
            bcolors.WARNING, bcolors.ENDC, str(rc)))
        mqttclient.subscribe(self.settings['mqtt']['command_topic'])

    def on_message_mqtt(self, mqttclient, userdata, msg):
        """ Arm or Disarm on message from subscribed MQTT topics """

        message = msg.payload.decode("utf-8")
        # print(msg.topic + " " + message)
        if message == "DISARM":
            self.deactivateAlarm()
        elif message == "ARM_AWAY":
            self.activateAlarm()

    def sensorAlert(self, sensorUUID):
        """ On Sensor Alert, write logs and check for intruder """

        name = self.settings['sensors'][sensorUUID]['name']
        print("{0}-> Alert Sensor: {2}{1}".format(
            bcolors.OKGREEN, bcolors.ENDC, name))
        self.settings['sensors'][sensorUUID]['alert'] = True
        self.settings['sensors'][sensorUUID]['online'] = True
        self.writeNewSettingsToFile(self.settings)
        stateTopic = 'home/sensor/' + name
        self.mynotify.sendSensorMQTT(stateTopic, 'on')
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())
        self.writeLog("sensor,start," + sensorUUID, name)
        self.checkIntruderAlert()

    def sensorStopAlert(self, sensorUUID):
        """ On Sensor Alert Stop, write logs """

        name = self.settings['sensors'][sensorUUID]['name']
        print("{0}<- Stop Alert Sensor: {2}{1}".format(
            bcolors.OKGREEN, bcolors.ENDC, name))
        self.settings['sensors'][sensorUUID]['alert'] = False
        self.settings['sensors'][sensorUUID]['online'] = True
        self.writeNewSettingsToFile(self.settings)
        stateTopic = 'home/sensor/' + name
        self.mynotify.sendSensorMQTT(stateTopic, 'off')
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())
        self.writeLog("sensor,stop," + sensorUUID, name)

    def sensorError(self, sensorUUID):
        """ On Sensor Error, write logs """

        name = self.settings['sensors'][sensorUUID]['name']
        print("{0}!- Error Sensor: {2}{1}".format(
            bcolors.FAIL, bcolors.ENDC, name))
        # print("Error Sensor", sensorUUID)
        name = self.settings['sensors'][sensorUUID]['name']
        self.settings['sensors'][sensorUUID]['alert'] = True
        self.settings['sensors'][sensorUUID]['online'] = False
        self.writeNewSettingsToFile(self.settings)
        self.writeLog("error", "Lost connection to: " + name)
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())

    def sensorStopError(self, sensorUUID):
        """ On Sensor Stop Error, write logs """

        name = self.settings['sensors'][sensorUUID]['name']
        print("{0}-- Error Stop Sensor: {2}{1}".format(
            bcolors.FAIL, bcolors.ENDC, name))
        name = self.settings['sensors'][sensorUUID]['name']
        self.settings['sensors'][sensorUUID]['online'] = True
        self.writeNewSettingsToFile(self.settings)
        self.writeLog("error", "Restored connection to: " + name)
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())

    def checkIntruderAlert(self):
        """ Checks if the alarm is armed and if it finds an active
            sensor then it calls the intruderAlert method """

        if (self.settings['settings']['alarmArmed'] is True and
                self.alarmTriggered is False):
            for sensor, sensorvalue in self.settings['sensors'].items():
                if (sensorvalue['alert'] is True and
                        sensorvalue['enabled'] is True):
                    self.alarmTriggered = True
                    threadIntruderAlert = threading.Thread(
                        target=self.intruderAlert)
                    threadIntruderAlert.daemon = True
                    threadIntruderAlert.start()

    def ReadSettings(self):
        """ Reads the json settings file and returns it """

        with open(self.jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def writeNewSettingsToFile(self, settings):
        """ Write the new settings to the json file """
        self.mynotify.updateSettings(settings)
        with open(self.jsonfile, 'w') as outfile:
            json.dump(settings, outfile, sort_keys=True,
                      indent=4, separators=(',', ': '))


    def writeLog(self, logType, message):
        """ Write log events into a file and send the last to UI.
            It also uses the timezone from json file to get the local time.
        """
        try:
            mytimezone = pytz.timezone(self.settings['settings']['timezone'])
        except Exception:
            mytimezone = pytz.utc

        myTimeLog = datetime.now(tz=mytimezone).strftime("%Y-%m-%d %H:%M:%S")
        logmsg = '({0}) [{1}] {2}\n'.format(logType, myTimeLog, message)
        with open(self.logfile, "a") as myfile:
            myfile.write(logmsg)
        self.mynotify.updateUI('sensorsLog', self.getSensorsLog(
            self.limit, selectTypes=self.logtypes))

    def intruderAlert(self):
        """ This method is called when an intruder is detected. It calls
            all the methods whith the actions that we want to do.
            Sends MQTT message, enables serene, Send mail, Call Voip.
        """
        self.writeLog("alarm", "Intruder Alert")
        self.enableSerene()
        self.mynotify.sendStateMQTT(self.getTriggeredStatus())
        self.mynotify.updateUI('alarmStatus', self.getTriggeredStatus())
        threadSendMail = threading.Thread(target=self.sendMail)
        threadSendMail.daemon = True
        threadSendMail.start()
        threadCallVoip = threading.Thread(target=self.callVoip)
        threadCallVoip.daemon = True
        threadCallVoip.start()

    def callVoip(self):
        """ This method uses a prebuild application in C to connect to the SIP provider
            and call all the numbers in the json settings file.
        """

        sip_domain = str(self.settings['voip']['domain'])
        sip_user = str(self.settings['voip']['username'])
        sip_password = str(self.settings['voip']['password'])
        sip_repeat = str(self.settings['voip']['timesOfRepeat'])
        if self.settings['voip']['enable'] is True:
            for phone_number in self.settings['voip']['numbersToCall']:
                phone_number = str(phone_number)
                if self.alarmTriggered is True:
                    self.writeLog("alarm", "Calling " + phone_number)
                    cmd = (self.sipcallfile, '-sd', sip_domain,
                           '-su', sip_user, '-sp', sip_password,
                           '-pn', phone_number, '-s', '1', '-mr', sip_repeat)
                    print("{0}Voip command: {2}{1}".format(
                        bcolors.FADE, bcolors.ENDC, " ".join(cmd)))
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                    for line in proc.stderr:
                        sys.stderr.write(line)
                    proc.wait()
                    self.writeLog("alarm", "Call to " +
                                  phone_number + " endend")
                    print("{0}Call Ended{1}".format(
                        bcolors.FADE, bcolors.ENDC))

    def sendMail(self):
        """ This method sends an email to all recipients
            in the json settings file. """

        if self.settings['mail']['enable'] is True:
            mail_user = self.settings['mail']['username']
            mail_pwd = self.settings['mail']['password']
            smtp_server = self.settings['mail']['smtpServer']
            smtp_port = int(self.settings['mail']['smtpPort'])

            bodyMsg = self.settings['mail']['messageBody']
            LogsTriggered = self.getSensorsLog(
                fromText='Alarm activated')['log']
            for logTriggered in LogsTriggered.reversed():
                bodyMsg += '<br>' + logTriggered
            msg = MIMEText(bodyMsg, 'html')
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
        """ This method enables the output pin for the serene """

        if self.settings['serene']['enable'] is True:
            self.writeLog("alarm", "Serene started")
            serenePin = int(self.settings['serene']['pin'])
            outputGPIO().enableOutputPin(serenePin)

    def stopSerene(self):
        """ This method disables the output pin for the serene """

        if self.settings['serene']['enable'] is True:
            serenePin = self.settings['serene']['pin']
            outputGPIO().disableOutputPin(serenePin)

    def activateAlarm(self):
        """ Activates the alarm """

        self.writeLog("user_action", "Alarm activated")
        self.settings['settings']['alarmArmed'] = True
        self.mynotify.sendStateMQTT(self.getTriggeredStatus())
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())
        self.writeNewSettingsToFile(self.settings)

    def deactivateAlarm(self):
        """ Deactivates the alarm """

        self.alarmTriggered = False
        self.writeLog("user_action", "Alarm deactivated")
        self.settings['settings']['alarmArmed'] = False
        self.stopSerene()
        self.mynotify.sendStateMQTT(self.getTriggeredStatus())
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())
        self.writeNewSettingsToFile(self.settings)

    def getSensorsArmed(self):
        """ Returns the sensors and alarm status
            as a json to use it to the UI """

        sensorsArmed = {}
        sensors = self.settings['sensors']
        orderedSensors = OrderedDict(
            sorted(sensors.items(), key=lambda k_v: k_v[1]['name']))
        sensorsArmed['sensors'] = orderedSensors
        sensorsArmed['triggered'] = self.alarmTriggered
        sensorsArmed['alarmArmed'] = self.settings['settings']['alarmArmed']
        return sensorsArmed

    def getTriggeredStatus(self):
        """ Returns the status of the alert for the UI """

        return {"alert": self.alarmTriggered}

    def setLogFilters(self, limit, logtypes):
        """ Sets the global filters for the getSensorsLog method """

        self.limit = limit
        self.logtypes = logtypes

    def getSereneSettings(self):
        """ Gets the Serene Settings """
        return self.settings['serene']

    def getMailSettings(self):
        return self.settings['mail']

    def getVoipSettings(self):
        """ Gets the Voip Settings """
        return self.settings['voip']

    def getTimezoneSettings(self):
        """ Get the Timezone Settings """
        return self.settings['settings']['timezone']

    def getMQTTSettings(self):
        """ Gets the MQTT Settings """
        return self.settings['mqtt']

    def setSereneSettings(self, message):
        """ set Serene Settings """
        if self.settings['serene'] != message:
            self.settings['serene'] = message
            self.writeLog("user_action", "Settings for Serene changed")
            self.writeNewSettingsToFile(self.settings)

    def setMailSettings(self, message):
        """ Set Mail Settings """
        if self.settings['mail'] != message:
            self.settings['mail'] = message
            self.writeLog("user_action", "Settings for Mail changed")
            self.writeNewSettingsToFile(self.settings)

    def setVoipSettings(self, message):
        """ Set Voip Settings """
        if self.settings['voip'] != message:
            self.settings['voip'] = message
            self.writeLog("user_action", "Settings for VoIP changed")
            self.writeNewSettingsToFile(self.settings)

    def setTimezoneSettings(self, message):
        """ Set the Timezone """
        if self.settings['settings']['timezone'] != message:
            self.settings['settings']['timezone'] = message
            self.writeLog("user_action", "Settings for UI changed")
            self.writeNewSettingsToFile(self.settings)

    def setMQTTSettings(self, message):
        """ Set MQTT Settings """
        if self.settings['mqtt'] != message:
            self.settings['mqtt'] = message
            self.writeLog("user_action", "Settings for MQTT changed")
            self.writeNewSettingsToFile(self.settings)
            self.startstopMQTT()
            self.sensors.reload('MQTT', message)

    def setSensorState(self, sensorUUID, state):
        """ Activate or Deactivate a sensor """
        self.settings['sensors'][sensorUUID]['enabled'] = state
        self.writeNewSettingsToFile(self.settings)

        logState = "Deactivated"
        if state is True:
            logState = "Activated"
        logSensorName = self.settings['sensors'][sensorUUID]['name']
        self.writeLog("user_action", "{0} sensor: {1}".format(
            logState, logSensorName))
        self.writeNewSettingsToFile(self.settings)

    def setSensorsZone(self, zones):
        for sensor, sensorvalue in self.settings['sensors'].items():
            sensorZones = sensorvalue.get('zones', [])
            sensorZones = [item.lower() for item in sensorZones]
            if not set(sensorZones).isdisjoint(zones):
                sensorvalue['enabled'] = True
            else:
                sensorvalue['enabled'] = False
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())
        self.writeNewSettingsToFile(self.settings)

    def addSensor(self, sensorValues):
        """ Add a new sensor """
        print("{0}New Sensor: {2}{1}".format(
            bcolors.WARNING, bcolors.ENDC, sensorValues))
        key = next(iter(sensorValues))
        sensorValues[key]['enabled'] = True
        sensorValues[key]['online'] = False
        sensorValues[key]['alert'] = True
        if 'undefined' in sensorValues:
            sensorUUID = str(uuid.uuid4())
            sensorValues[sensorUUID] = sensorValues.pop('undefined')
        else:
            self.sensors.del_sensor(key)
        self.settings['sensors'].update(sensorValues)
        self.writeNewSettingsToFile(self.settings)
        self.sensors.add_sensors(self.settings)

    def delSensor(self, sensorUUID):
        """ Delete a sensor """
        self.sensors.del_sensor(sensorUUID)
        del self.settings['sensors'][sensorUUID]
        self.writeNewSettingsToFile(self.settings)
