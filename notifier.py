#!/usr/bin/env python

import re
import threading
import time
from datetime import datetime


class Notify():

    def __init__(self, settings):
        self.settings = settings

    def setupUpdateUI(self, optsUpdateUI):
        self.optsUpdateUI = optsUpdateUI
        return self.updateUI

    def updateUI(self, event, data):
        """ Send changes to the UI """
        self.optsUpdateUI['obj'](event, data, room=self.optsUpdateUI['room'])

    def setupSendStateMQTT(self, optsMQTTpublish):
        self.optsMQTTpublish = optsMQTTpublish
        return self.sendStateMQTT

    def sendStateMQTT(self):
        """ Send to the MQTT server the state of the alarm
            (disarmed, triggered, armed_away) """

        stateTopic = self.settings['mqtt']['state_topic']
        state = 'disarmed'
        if self.settings['settings']['alarmArmed']:
            state = 'triggered'
        elif self.settings['settings']['alarmArmed']:
            state = 'armed_away'
        self.optsMQTTpublish(stateTopic, state, retain=True, qos=2)

    def sendSensorMQTT(self, topic, state):
        self.optsMQTTpublish(topic, state, retain=True, qos=2)

    def updateSettings(self, settings):
        self.settings = settings

