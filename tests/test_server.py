import alarmcode
from alarmcode.alarmpi import AlarmPiServer
import unittest
from base64 import b64encode
import json
import os


class FlaskBookshelfTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        # creates a test client
        wd = os.path.dirname(os.path.dirname(alarmcode.__file__))
        myserver = AlarmPiServer(wd)
        myserver.setServerConfig('config/server.json')
        app = myserver.create_app()
        myserver.startMyApp()

        self.client = app.test_client()
        # propagate the exceptions to the test client
        self.client.testing = True
        self.headers = {'Authorization': 'Basic %s' % b64encode(
            b"test1:secret").decode("ascii")}

    def tearDown(self):
        pass

    def test_sensors(self):
        response = self.client.get(
            '/getSensors.json',
            headers=self.headers,
            follow_redirects=True
        )
        mydata = json.loads(response.data.decode('ascii'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue('sensors' in mydata)
        self.assertTrue('triggered' in mydata)
        self.assertTrue('alarmArmed' in mydata)

    def test_logs(self):
        response = self.client.get(
            '/getSensorsLog.json',
            headers=self.headers,
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

# getAlarmStatus.json
# getSensorsLog.json
# getSereneSettings.json
# getAllSettings.json
# activateAlarmOnline
# deactivateAlarmOnline
# setSensorStateOnline
# addSensor
