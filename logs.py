#!/usr/bin/env python

import re
import threading
import time
from datetime import datetime


class Logs():

    def __init__(self, logfile):
        self.logfile = logfile

    def startTrimThread(self):
        threadTrimLogFile = threading.Thread(target=self.trimLogFile)
        threadTrimLogFile.daemon = True
        threadTrimLogFile.start()


    def _convert_timedelta(self, duration):
        """ Converts a time difference into human readable format """

        days, seconds = duration.days, duration.seconds
        hours = days * 24 + seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = (seconds % 60)
        diffTxt = ""
        if days > 0:
            diffTxt = "{days} days, {hours} hour, {minutes} min, {seconds} sec"
        elif hours > 0:
            diffTxt = "{hours} hour, {minutes} min, {seconds} sec"
        elif minutes > 0:
            diffTxt = "{minutes} min, {seconds} sec"
        else:
            diffTxt = "{seconds} sec"
        diffTxt = diffTxt.format(
            days=days, hours=hours, minutes=minutes, seconds=seconds)
        return diffTxt


    def trimLogFile(self):
        """ Trims the log file in an interval of 24 hours to 1000 lines """

        lines = 1000  # Number of lines of logs to keep
        repeat_every_n_sec = 86400  # 24 Hours
        while True:
            with open(self.logfile, 'r') as f:
                data = f.readlines()
            with open(self.logfile, 'w') as f:
                f.writelines(data[-lines:])
            time.sleep(repeat_every_n_sec)


    def getSensorsLog(self, limit=100, fromText=None,
                      selectTypes='all', filterText=None,
                      getFormat='text', combineSensors=True):
        """ Returns the last n lines if the log file.
        If selectTypes is specified, then it returns only this type of logs.
        Available types: user_action, sensor,
                         system, alarm
        If the getFormat is specified as json, then it returns it in a
        json format (programmer friendly)
        """

        # Fix inputs
        if (type(limit) != int and limit is not None):
            if (limit.isdigit()):
                limit = int(limit)
        else:
            limit = 100
        if (type(selectTypes) == str):
            selectTypes = selectTypes.split(',')
        elif selectTypes is None:
            selectTypes = 'all'.split(',')
        if (type(combineSensors) != bool and combineSensors is not None):
            if (combineSensors.lower() == 'true'):
                combineSensors = True
            elif (combineSensors.lower() == 'false'):
                combineSensors = False
        else:
            combineSensors = True
        if getFormat is None:
            getFormat = 'text'

        # Read from File the Logs
        logs = []
        with open(self.logfile, "r") as f:
            lines = f.readlines()
        startedSensors = {}
        for line in lines:
            logType = None
            logTime = None
            logText = None

            # Analyze log line for each category
            try:
                mymatch = re.match(r'^\((.*)\) \[(.*)\] (.*)', line)
                if mymatch:
                    logType = mymatch.group(1).split(',')
                    logTime = mymatch.group(2)
                    logText = mymatch.group(3)
            except Exception:
                mymatch = re.match(r'^\[(.*)\] (.*)', line)
                if mymatch:
                    logType = ["unknown", "unknown"]
                    logTime = mymatch.group(1)
                    logText = mymatch.group(2)

            # append them to a list
            if logType is not None and logTime is not None and logText is not None:
                logs.append({
                    'type': logType,
                    'event': logText,
                    'time': logTime
                })

        # Add endtime to the sensors
        if (combineSensors):
            tmplogs = []
            index = 0
            startedSensors = {}
            for log in logs:
                if 'sensor' in log['type'][0].lower():
                    status, uuid = log['type'][1], log['type'][2]
                    if status == 'start':
                        startedSensors[uuid] = {
                            'start': log['time'],
                            'ind': index
                        }
                        index += 1
                        tmplogs.append(log)
                    elif status == 'stop':
                        try:
                            info = startedSensors.pop(uuid, None)
                            if info is not None:
                                starttime = datetime.strptime(
                                    info['start'], "%Y-%m-%d %H:%M:%S")
                                endtime = datetime.strptime(
                                    log['time'], "%Y-%m-%d %H:%M:%S")
                                timediff = self._convert_timedelta(endtime - starttime)
                                tmplogs[info['ind']]['timediff'] = timediff
                                tmplogs[info['ind']]['timeend'] = log['time']
                        except Exception, e:
                            print(e)
                            print(info)
                            print(log)
                            pass
                else:
                    index += 1
                    tmplogs.append(log)
            logs = tmplogs

        # Filter from last found text till the end (e.g. Alarm activated)
        if (fromText not in (None, 'all')):
            tmplogs = []
            index = 0
            for log in reversed(logs):
                index += 1
                if (fromText.lower() in log['event'].lower()):
                    break
            logs = logs[-index:]

        # Filter by Types (e.g. sensor, user_action, ...)
        if (selectTypes is not None):
            if ('all' not in selectTypes):
                tmplogs = []
                for log in logs:
                    if (log['type'][0].lower() in selectTypes):
                        tmplogs.append(log)
                logs = tmplogs

        # Filter by text (e.g. pir, ...)
        if (filterText not in (None, 'all')):
            tmplogs = []
            for log in logs:
                if (filterText.lower() in log['event'].lower()):
                    tmplogs.append(log)
            logs = tmplogs


        # Convert to Human format
        if (getFormat == 'text'):
            tmplogs = []
            for log in logs:
                if ('timediff' in log):
                    tmplogs.append('[{0}] ({1}) {2}'.format(log['time'], log['timediff'], log['event']))
                else:
                    tmplogs.append('[{0}] {1}'.format(log['time'], log['event']))
            logs = tmplogs

        return {"log": logs[-limit:]}


