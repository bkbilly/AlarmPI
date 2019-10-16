#!/usr/bin/env python3

import os
import sys

import logging
from alarmcode.alarmpi import AlarmPiServer
import alarmcode

if __name__ == '__main__':
    # log = logging.getLogger('werkzeug')
    # log.setLevel(logging.ERROR)

    def get_logger(self):
        return logging


    if len(sys.argv) > 1:
        if ".pid" in sys.argv[1]:
            with open(sys.argv[1], "w") as f:
                f.write(str(os.getpid()))

    wd = os.path.dirname(os.path.dirname(alarmcode.__file__))

    # Logging setup
    rootLogger = logging.getLogger('socketio')
    rootLogger.setLevel(logging.ERROR)
    rootLogger = logging.getLogger('engineio')
    rootLogger.setLevel(logging.ERROR)
    rootLogger = logging.getLogger('werkzeug')
    rootLogger.setLevel(logging.ERROR)

    logFormatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)s]  %(message)s", "%Y-%m-%d %H:%M:%S")
    rootLogger = logging.getLogger('alarmpi')
    rootLogger.setLevel(logging.DEBUG)

    fileHandler = logging.FileHandler("{0}/{1}.log".format(wd, 'sysrun'))
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    # Run App
    try:
        myserver = AlarmPiServer(wd)
        myserver.setServerConfig('config/server.json')
        myserver.create_app()
        myserver.startMyApp()
        myserver.startServer()
    except Exception:
        rootLogger.exception("Unknown error has occured Contact Author:")
