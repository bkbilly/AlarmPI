#!/usr/bin/env python

from alarmcode.sensors import Sensor
from alarmcode.logs import Logs
from alarmcode.notifier import Notify
from alarmcode.colors import bcolors
import json
import threading
import uuid
from collections import OrderedDict
from shutil import copyfile
import os
import logging

logging = logging.getLogger('alarmpi')


class Worker():

    """ This class runs on the background using GPIO Events Changes.
    It uses a json file to store the settings and a log file to store the logs.
    When a sensor changes state after the alarm is activated it can enable
    the Serene, send Mail, call through VoIP.
    Also there is the updateUI method wich it has to be overridden in
    the main application.
    """

    def __init__(self, wd, jsonfile, logfile, optsUpdateUI=None):
        """ Init for the Worker class """

        # Global Variables
        self.wd = wd
        self.jsonfile = jsonfile
        self.logfile = logfile
        self.settings = self.ReadSettings()
        self.optsUpdateUI = optsUpdateUI

        # Stop execution on exit
        self.kill_now = False

        # Init Alarm
        self.mylogs = Logs(self.wd, self.logfile, self.settings['settings']['timezone'])
        self.mylogs.startTrimThread(self.settings['settings'].get('trim', 0))
        self.mynotify = Notify(self.wd, self.settings, self.optsUpdateUI, self.mylogs)
        self.mylogs.setCallbackUpdateUI(self.mynotify.updateUI)
        self.mylogs.writeLog("system", "Alarm Booted")

        # Event Listeners
        self.sensors = Sensor(self.wd)
        self.sensors.on_alert(self.sensorAlert)
        self.sensors.on_alert_stop(self.sensorStopAlert)
        self.sensors.on_error(self.sensorError)
        self.sensors.on_error_stop(self.sensorStopError)
        self.sensors.add_sensors(self.settings)

        # Init MQTT Messages
        self.mynotify.on_arm(self.activateAlarm)
        self.mynotify.on_disarm(self.deactivateAlarm)
        self.mynotify.on_sensor_set_alert(self.sensorAlert)
        self.mynotify.on_sensor_set_stopalert(self.sensorStopAlert)

    def sensorAlert(self, sensorUUID):
        """ On Sensor Alert, write logs and check for intruder """

        logging.info("{0}-> Alert Sensor: {2}{1}".format(
            bcolors.OKGREEN,
            bcolors.ENDC,
            self.settings['sensors'][sensorUUID]['name']
        ))
        self.settings['sensors'][sensorUUID]['alert'] = True
        self.settings['sensors'][sensorUUID]['online'] = True
        if (self.settings['sensors'][sensorUUID].get('behavior') == '24hours' and
                self.settings['sensors'][sensorUUID]['alert'] is True and
                self.settings['sensors'][sensorUUID]['enabled'] is True and
                self.settings['sensors'][sensorUUID]['online'] is True):
            self.settings['settings']['alarmArmed'] = True
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.update_sensor(sensorUUID)
        self.checkIntruderAlert()

    def sensorStopAlert(self, sensorUUID):
        """ On Sensor Alert Stop, write logs """

        logging.info("{0}<- Stop Alert Sensor: {2}{1}".format(
            bcolors.OKGREEN,
            bcolors.ENDC,
            self.settings['sensors'][sensorUUID]['name']
        ))
        self.settings['sensors'][sensorUUID]['alert'] = False
        self.settings['sensors'][sensorUUID]['online'] = True
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.update_sensor(sensorUUID)

    def sensorError(self, sensorUUID):
        """ On Sensor Error, write logs """

        logging.info("{0}!- Error Sensor: {2}{1}".format(
            bcolors.FAIL,
            bcolors.ENDC,
            self.settings['sensors'][sensorUUID]['name']
        ))
        self.settings['sensors'][sensorUUID]['alert'] = True
        self.settings['sensors'][sensorUUID]['online'] = False
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.update_sensor(sensorUUID)

    def sensorStopError(self, sensorUUID):
        """ On Sensor Stop Error, write logs """

        logging.info("{0}-- Error Stop Sensor: {2}{1}".format(
            bcolors.FAIL,
            bcolors.ENDC,
            self.settings['sensors'][sensorUUID]['name']
        ))
        self.settings['sensors'][sensorUUID]['online'] = True
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.update_sensor(sensorUUID)

    def checkIntruderAlert(self):
        """ Checks if the alarm is armed and if it finds an active
            sensor then it calls the intruderAlert method """

        if (self.settings['settings']['alarmArmed'] is True):
            for sensor, sensorvalue in self.settings['sensors'].items():
                if (sensorvalue['alert'] is True and
                        sensorvalue['enabled'] is True and
                        sensorvalue['online'] is True and
                        self.settings['settings']['alarmTriggered'] is False):
                    self.settings['settings']['alarmTriggered'] = True
                    threadIntruderAlert = threading.Thread(
                        target=self.mynotify.intruderAlert)
                    threadIntruderAlert.daemon = True
                    threadIntruderAlert.start()

    def ReadSettings(self):
        """ Reads the json settings file and returns it """

        if not os.path.exists(self.jsonfile):
            copyfile(os.path.join(self.wd, 'config/settings_template.json'), self.jsonfile)

        with open(self.jsonfile) as data_file:
            settings = json.load(data_file)
        return settings

    def writeNewSettingsToFile(self, settings):
        """ Write the new settings to the json file """
        self.mynotify.settings_update(settings)
        with open(self.jsonfile, 'w') as outfile:
            json.dump(settings, outfile, sort_keys=True,
                      indent=4, separators=(',', ': '))

    def activateAlarm(self, zones=None):
        """ Activates the alarm """

        if zones is not None:
            if type(zones) == str:
                zones = [zones]
            self.setSensorsZone(zones)

        self.settings['settings']['alarmArmed'] = True
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.update_alarmstate()
        self.checkIntruderAlert()

    def deactivateAlarm(self):
        """ Deactivates the alarm """

        self.settings['settings']['alarmTriggered'] = False
        self.settings['settings']['alarmArmed'] = False
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.update_alarmstate()

    def startSiren(self, zones=None):
        """ Activates the Siren """
        self.mynotify.startSiren()

    def stopSiren(self):
        """ Deactivates the Siren """
        self.mynotify.stopSiren()

    def getSensorsArmed(self):
        """ Returns the sensors and alarm status
            as a json to use it to the UI """

        sensorsArmed = {}
        sensors = self.settings['sensors']
        orderedSensors = OrderedDict(
            sorted(sensors.items(), key=lambda k_v: k_v[1]['name']))
        sensorsArmed['sensors'] = orderedSensors
        sensorsArmed['triggered'] = self.settings['settings']['alarmTriggered']
        sensorsArmed['alarmArmed'] = self.settings['settings']['alarmArmed']
        return sensorsArmed

    def getTriggeredStatus(self):
        """ Returns the status of the alert for the UI """

        return {"alert": self.settings['settings']['alarmTriggered']}

    def getSensorsLog(self, **args):
        return self.mylogs.getSensorsLog(**args)

    def setLogFilters(self, limit, logtypes):
        """ Sets the global filters for the getSensorsLog method """
        self.mylogs.setLogFilters(limit, logtypes)

    def getNotifiersStatus(self):
        return self.mynotify.status()

    def getSettings(self, set_topic):
        """ Gets the Settings """
        return self.settings[set_topic]

    def setSettings(self, message):
        """ set Settings """
        for msg_topic, msg_values in message.items():
            changedValue = False
            for val_topic, set_value in msg_values.items():
                if val_topic not in self.settings[msg_topic]:
                    self.settings[msg_topic][val_topic] = None
                if self.settings[msg_topic][val_topic] != set_value:
                    changedValue = True
                    self.settings[msg_topic][val_topic] = set_value
            if changedValue:
                self.mylogs.writeLog("user_action", "Settings for %s changed" % (msg_topic))
        self.writeNewSettingsToFile(self.settings)

    def setSensorState(self, sensorUUID, state):
        """ Activate or Deactivate a sensor """
        self.settings['sensors'][sensorUUID]['enabled'] = state
        self.writeNewSettingsToFile(self.settings)

        logState = "Deactivated"
        if state is True:
            logState = "Activated"
        logSensorName = self.settings['sensors'][sensorUUID]['name']
        self.mylogs.writeLog("user_action", "{0} sensor: {1}".format(
            logState, logSensorName))
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.updateUI('settingsChanged', self.getSensorsArmed())

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
        logging.info("{0}New Sensor: {2}{1}".format(
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
        self.mynotify.updateMQTT()

    def delSensor(self, sensorUUID):
        """ Delete a sensor """
        self.sensors.del_sensor(sensorUUID)
        del self.settings['sensors'][sensorUUID]
        self.writeNewSettingsToFile(self.settings)
        self.mynotify.updateMQTT()

    def setSensorStatus(self, name, status):
        """ Add a new sensor """
        found = False
        logging.info(name, status)
        for sensor, sensorvalue in self.settings['sensors'].items():
            if sensorvalue['name'].lower().replace(' ', '_') == name.lower().replace(' ', '_'):
                found = True
                if status == 'on':
                    self.sensorAlert(sensor)
                elif status == 'off':
                    self.sensorStopAlert(sensor)
                elif status == 'error':
                    self.sensorError(sensor)
        return found
