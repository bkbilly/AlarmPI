#!/usr/bin/env python

import re
import threading
import time
from datetime import datetime
from colors import bcolors
import paho.mqtt.client as mqtt


class Notify():

    def __init__(self, settings):
        self.settings = settings

    def setupUpdateUI(self, optsUpdateUI):
        self.optsUpdateUI = optsUpdateUI
        return self.updateUI

    def updateUI(self, event, data):
        """ Send changes to the UI """
        self.optsUpdateUI['obj'](event, data, room=self.optsUpdateUI['room'])

    def setupSendStateMQTT(self):
        """ Start or Stop the MQTT connection based on the settings """

        # self.mqttclient = mqtt.Client("", True, None, mqtt.MQTTv311)
        if not hasattr(self, 'mqttclient'):
            self.mqttclient = mqtt.Client("")


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
                self.mqttclient.connect(mqttHost, mqttPort, 60)
                self.mqttclient.loop_start()
                print('subscribing to: ', self.settings['mqtt']['command_topic'])
                self.mqttclient.subscribe(self.settings['mqtt']['command_topic'])
            except Exception as e:
                print("{0}MQTT: {2}{1}".format(
                    bcolors.FAIL, bcolors.ENDC, str(e)))
        else:
            self.mqttclient.disconnect()
            self.mqttclient.loop_stop(force=False)

        # return self.sendStateMQTT

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
            self.mqttclient.publish(stateTopic, state, retain=True, qos=2)

    def sendSensorMQTT(self, topic, state):
        if self.settings['mqtt']['enable']:
            self.mqttclient.publish(topic, state, retain=True, qos=2)

    def updateSettings(self, settings):
        self.settings = settings

    def on_message_mqtt(self, mqttclient, userdata, msg):
        """ Arm or Disarm on message from subscribed MQTT topics """

        message = msg.payload.decode("utf-8")
        try:
            print(msg.topic + " " + message)
            if message == "DISARM":
                self.deactivateAlarm()
            elif message == "ARM_HOME":
                self.activateAlarm('home')
            elif message == "ARM_AWAY":
                self.activateAlarm('away')
        except Exception as e:
            raise e

    def on_disarm_mqtt(self, callback):
        self.deactivateAlarm = callback

    def on_arm_mqtt(self, callback):
        self.activateAlarm = callback
