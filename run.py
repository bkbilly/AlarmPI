#!/usr/bin/env python3

import os
import sys

import logging

from alarmcode.alarmpi import AlarmPiServer

if __name__ == '__main__':
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    if len(sys.argv) > 1:
        if ".pid" in sys.argv[1]:
            with open(sys.argv[1], "w") as f:
                f.write(str(os.getpid()))
    wd = os.path.dirname(os.path.realpath(__file__))
    myserver = AlarmPiServer(wd)
    myserver.setServerConfig('server.json')
    myserver.create_app()
    myserver.startMyApp()
    myserver.startServer()
