#!/usr/bin/env python

import re
import threading
import time
from datetime import datetime


class Notify():

    def __init__(self, optsUpdateUI=None):
        self.optsUpdateUI = optsUpdateUI

    def updateUI(self, event, data):
        """ Send changes to the UI """
        self.optsUpdateUI['obj'](event, data, room=self.optsUpdateUI['room'])
