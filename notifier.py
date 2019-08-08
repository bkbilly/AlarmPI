#!/usr/bin/env python

import threading
from colors import bcolors
import paho.mqtt.client as mqtt
import random
import json
import os
import smtplib
from email.mime.text import MIMEText
from collections import OrderedDict
import subprocess
import sys
import re



class notifyGPIO():

    def __init__(self, settings, optsUpdateUI, mylogs, callbacks):
        self.settings = settings
        self.mylogs = mylogs
        try:
            import RPi.GPIO as GPIO
            self.connected = True
        except Exception as e:
            self.connected = False


    def enableSerene(self):
        """ This method enables the output pin for the serene """

        if self.settings['serene']['enable'] is True and self.connected:
            self.mylogs.writeLog("alarm", "Serene started")
            serenePin = int(self.settings['serene']['pin'])
            outputGPIO().enableOutputPin(serenePin)

    def stopSerene(self):
        """ This method disables the output pin for the serene """

        if self.settings['serene']['enable'] is True and self.connected:
            serenePin = self.settings['serene']['pin']
            outputGPIO().disableOutputPin(serenePin)

    def enableOutputPin(self, *pins):
        if self.connected:
            for pin in pins:
                GPIO.setup(pin, GPIO.OUT)
                state = GPIO.input(pin)
                if state == GPIO.LOW:
                    GPIO.output(pin, GPIO.HIGH)

    def disableOutputPin(self, *pins):
        if self.connected:
            for pin in pins:
                GPIO.setup(pin, GPIO.OUT)
                if GPIO.input(pin) == GPIO.HIGH:
                    GPIO.output(pin, GPIO.LOW)
                GPIO.setup(pin, GPIO.IN)

    def status(self):
        return self.connected


class notifyUI():

    def __init__(self, settings, optsUpdateUI, mylogs, callbacks):
        self.settings = settings
        self.optsUpdateUI = optsUpdateUI

    def updateUI(self, event, data):
        """ Send changes to the UI """
        self.optsUpdateUI['obj'](event, data, room=self.optsUpdateUI['room'])


class notifyMQTT():

    def __init__(self, settings, optsUpdateUI, mylogs, callbacks):
        self.settings = settings
        self.optsUpdateUI = optsUpdateUI
        self.callbacks = callbacks
        self.isconnected = False
        self.version = self.getVersion()
        self.setupMQTT()

    def getVersion(self):
        version = 0
        wd = os.path.dirname(os.path.realpath(__file__))
        setupfile = os.path.join(wd, "setup.py")
        with open(setupfile) as setup:
            for line in setup:
                if 'version=' in line:
                    match = re.findall(r"\'(.*?)\'", line)
                    if len(match) > 0:
                        version = match[0]
        return version

    def setupMQTT(self):
        """ Start or Stop the MQTT connection based on the settings """

        # self.mqttclient = mqtt.Client("", True, None, mqtt.MQTTv311)
        if not hasattr(self, 'mqttclient'):
            self.mqttclient = mqtt.Client(client_id=str(random.randint(1,10000)), clean_session=False)


        self.mqttclient.disconnect()
        self.mqttclient.loop_stop(force=False)
        if self.settings['mqtt']['enable']:
            try:
                mqttHost = self.settings['mqtt']['host']
                mqttPort = self.settings['mqtt']['port']
                self.mqttclient.on_message = self.on_message_mqtt
                if (self.settings['mqtt']['password'] != ""):
                    self.mqttclient.username_pw_set(
                        username=self.settings['mqtt']['username'],
                        password=self.settings['mqtt']['password'])
                self.mqttclient.on_connect = self.on_connect
                self.mqttclient.on_disconnect = self.on_disconnect
                self.mqttclient.connect(mqttHost, mqttPort, 10)
                self.mqttclient.loop_start()
            except Exception as e:
                print("{0}MQTT: {2}{1}".format(
                    bcolors.FAIL, bcolors.ENDC, str(e)))
        else:
            self.mqttclient.disconnect()
            self.mqttclient.loop_stop(force=False)

        # return self.sendStateMQTT

    def on_connect(self, client, userdata, flags, rc):
        self.isconnected = True
        print('MQTT subscribing to: {0}'.format(self.settings['mqtt']['command_topic']))
        self.mqttclient.subscribe(self.settings['mqtt']['command_topic'])
        for sensor, sensorvalue in self.settings['sensors'].items():
            # Subscribe to mqtt sensors events
            setmqttsensor = '{0}{1}{2}'.format(
                self.settings['mqtt']['command_topic'],
                '/sensor/',
                sensorvalue['name'].lower().replace(' ', '_'))
            print('MQTT subscribing to: {0}'.format(setmqttsensor))
            self.mqttclient.subscribe(setmqttsensor)

            # Home assistant integration
            if self.settings['mqtt']['homeassistant']:
                statemqttsensor = '{0}/sensor/{1}'.format(
                    self.settings['mqtt']['state_topic'],
                    sensorvalue['name']
                )
                sensor_name = sensorvalue['name'].lower().replace(' ', '_')
                has_topic = "homeassistant/binary_sensor/{0}/config".format(sensor_name)
                print(has_topic)
                has_config = {
                    "payload_on": "on",
                    "payload_off": "off",
                    "device_class": "door",
                    "state_topic": statemqttsensor,
                    "name": "AlarmPI-{0}".format(sensorvalue['name']),
                    "unique_id": "alarmpi_{0}".format(sensor_name),
                    "device": {
                        "identifiers": "alarmpi-{0}".format(self.optsUpdateUI['room']),
                        "name": "AlarmPI-{0}".format(self.optsUpdateUI['room']),
                        "sw_version": "AlarmPI {0}".format(self.version),
                        "model": "Raspberry PI",
                        "manufacturer": "bkbilly"
                    }
                }
                has_payload = json.dumps(has_config)
                self.mqttclient.publish(has_topic, has_payload, retain=True, qos=2)

    def on_disconnect(self, client, userdata, flags, rc):
        self.isconnected = False
        if rc != 0:
            print("Unexpected disconnection.")
        client.reconnect()

    def on_message_mqtt(self, mqttclient, userdata, msg):
        """ Arm or Disarm on message from subscribed MQTT topics """

        message = msg.payload.decode("utf-8")
        topicArm = self.settings['mqtt']['command_topic']
        topicSensorSet = self.settings['mqtt']['command_topic'] + '/sensor/'
        print(msg.topic + " " + message)
        try:
            if msg.topic == self.settings['mqtt']['command_topic']:
                if message == "DISARM":
                    self.callbacks['deactivateAlarm']()
                elif message == "ARM_HOME":
                    self.callbacks['activateAlarm']('home')
                elif message == "ARM_AWAY":
                    self.callbacks['activateAlarm']('away')
                elif message == "ARM_NIGHT":
                    self.callbacks['activateAlarm']('night')
            elif topicSensorSet in msg.topic:
                sensorName = msg.topic.replace(topicSensorSet, '')
                for sensor, sensorvalue in self.settings['sensors'].items():
                    if sensorvalue['name'].lower().replace(' ', '_') == sensorName:
                        if message.lower() == 'on':
                            self.callbacks['sensorAlert'](sensor)
                        else:
                            self.callbacks['sensorStopAlert'](sensor)
        except Exception as e:
            raise e

    def sendStateMQTT(self):
        """ Send to the MQTT server the state of the alarm
            (disarmed, triggered, armed_away) """
        if self.settings['mqtt']['enable']:
            stateTopic = self.settings['mqtt']['state_topic']
            state = 'disarmed'
            if self.settings['settings']['alarmTriggered']:
                state = 'triggered'
            elif self.settings['settings']['alarmArmed']:
                state = 'armed_away'
            self.mqttclient.publish(stateTopic, state, retain=False, qos=2)

    def sendSensorMQTT(self, topic, state):
        if self.settings['mqtt']['enable']:
            self.mqttclient.publish(topic, state, retain=False, qos=2)

    def status(self):
        return self.isconnected

class notifyEmail():

    def __init__(self, settings, optsUpdateUI, mylogs, callbacks):
        self.settings = settings
        self.mylogs = mylogs

    def sendMail(self):
        """ This method sends an email to all recipients
            in the json settings file. """

        if self.settings['mail']['enable'] is True:
            mail_user = self.settings['mail']['username']
            mail_pwd = self.settings['mail']['password']
            smtp_server = self.settings['mail']['smtpServer']
            smtp_port = int(self.settings['mail']['smtpPort'])

            bodyMsg = self.settings['mail']['messageBody']
            LogsTriggered = self.mylogs.getSensorsLog(
                fromText='Alarm activated')['log']
            LogsTriggered.reverse()
            for logTriggered in LogsTriggered:
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

            self.mylogs.writeLog("alarm", "Mail sent to: " + ", ".join(recipients))

    def status(self):
        connected = False
        if self.settings['mail']['enable'] is True:
            try:
                mail_user = self.settings['mail']['username']
                mail_pwd = self.settings['mail']['password']
                smtp_server = self.settings['mail']['smtpServer']
                smtp_port = int(self.settings['mail']['smtpPort'])

                smtpserver = smtplib.SMTP(smtp_server, smtp_port)
                smtpserver.ehlo()
                smtpserver.starttls()
                smtpserver.login(mail_user, mail_pwd)
                smtpserver.close()
                connected = True
            except Exception as e:
                pass
        return connected


class notifyVoip():

    def __init__(self, settings, optsUpdateUI, mylogs, callbacks):
        self.settings = settings
        self.mylogs = mylogs
        self.wd = os.path.dirname(os.path.realpath(__file__))
        self.sipcallfile = os.path.join(
            os.path.join(self.wd, "voip"), "sipcall")

    def callNotify(self):
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
                if self.settings['settings']['alarmTriggered'] is True:
                    self.mylogs.writeLog("alarm", "Calling " + phone_number)
                    cmd = (self.sipcallfile, '-sd', sip_domain,
                           '-su', sip_user, '-sp', sip_password,
                           '-pn', phone_number, '-s', '1', '-mr', sip_repeat)
                    print("{0}Voip command: {2}{1}".format(
                        bcolors.FADE, bcolors.ENDC, " ".join(cmd)))
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                    for line in proc.stderr:
                        sys.stderr.write(str(line))
                    proc.wait()
                    self.mylogs.writeLog("alarm", "Call to " +
                                  phone_number + " endend")
                    print("{0}Call Ended{1}".format(
                        bcolors.FADE, bcolors.ENDC))


class Notify():

    def __init__(self, settings, optsUpdateUI, mylogs):
        self.mylogs = mylogs
        self.callbacks = {}
        self.callbacks['deactivateAlarm'] = lambda:0
        self.callbacks['activateAlarm'] = lambda:0
        self.callbacks['sensorAlert'] = lambda:0
        self.callbacks['sensorStopAlert'] = lambda:0
        self.room = 'initial'
        self.optsUpdateUI = optsUpdateUI
        self.room = self.optsUpdateUI['room']

        print("{0}------------ INIT FOR DOOR SENSOR CLASS! ----------------{1}"
              .format(bcolors.HEADER, bcolors.ENDC))
        self.gpio = notifyGPIO(settings, optsUpdateUI, mylogs, self.callbacks)
        self.ui = notifyUI(settings, optsUpdateUI, mylogs, self.callbacks)
        self.mqtt = notifyMQTT(settings, optsUpdateUI, mylogs, self.callbacks)
        self.email = notifyEmail(settings, optsUpdateUI, mylogs, self.callbacks)
        self.voip = notifyVoip(settings, optsUpdateUI, mylogs, self.callbacks)

    def status(self):
        return {
            'email': self.email.status(),
            'gpio': self.gpio.status(),
            'mqtt': self.mqtt.status(),
        }

    def intruderAlert(self):
        """ This method is called when an intruder is detected. It calls
            all the methods whith the actions that we want to do.
            Sends MQTT message, enables serene, Send mail, Call Voip.
        """
        self.mylogs.writeLog("alarm", "Intruder Alert")
        self.gpio.enableSerene()
        self.mqtt.sendStateMQTT()
        self.ui.updateUI('alarmStatus', {"alert": self.settings['settings']['alarmTriggered']})
        threadSendMail = threading.Thread(target=self.email.sendMail)
        threadSendMail.daemon = True
        threadSendMail.start()
        threadCallVoip = threading.Thread(target=self.voip.callNotify)
        threadCallVoip.daemon = True
        threadCallVoip.start()

    def update_sensor(self, sensorUUID):
        #Define
        name = self.settings['sensors'][sensorUUID]['name']
        stateTopic = self.settings['mqtt']['state_topic'] + '/sensor/' + name
        if self.settings['sensors'][sensorUUID]['online'] == False:
            sensorState = 'error'
        elif self.settings['sensors'][sensorUUID]['alert'] == True:
            sensorState = 'on'
        elif self.settings['sensors'][sensorUUID]['alert'] == False:
            sensorState = 'off'

        self.mylogs.writeLog("{0},{1},{2}".format('sensor', sensorState, sensorUUID), name)
        self.ui.updateUI('settingsChanged', self.getSensorsArmed())
        self.mqtt.sendSensorMQTT(stateTopic, sensorState)

    def update_alarmstate(self):
        if self.settings['settings']['alarmArmed']:
            self.mylogs.writeLog("user_action", "Alarm activated")
        else:
            self.mylogs.writeLog("user_action", "Alarm deactivated")

        self.gpio.stopSerene()
        self.mqtt.sendStateMQTT()
        self.ui.updateUI('settingsChanged', self.getSensorsArmed())


    def updateUI(self, event, data):
        self.ui.updateUI(event, data)

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

    def settings_update(self, settings):
        self.settings = settings

    def on_disarm(self, callback):
        self.callbacks['deactivateAlarm'] = callback

    def on_arm(self, callback):
        self.callbacks['activateAlarm'] = callback

    def on_sensor_set_alert(self, callback):
        self.callbacks['sensorAlert'] = callback

    def on_sensor_set_stopalert(self, callback):
        self.callbacks['sensorStopAlert'] = callback
