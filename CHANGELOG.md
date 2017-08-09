# Change Log
All notable changes to this project will be documented in this file.


## [[2.7]](https://github.com/bkbilly/AlarmPI/tree/v2.7) - Aug 9, 2017
#### CHANGED
  - Renamed active/inactive sensors to enabled/disabled
  - better sensors with callbacks, auto delete old logs, better developer friendly
  - filled the online and alert when creating new sensor

## [[2.6]](https://github.com/bkbilly/AlarmPI/tree/v2.6) - Jul 25, 2017
#### CHANGED
  - fixed hikvision sensor, added UI log filter, print accessed ipaddress

## [[2.5]](https://github.com/bkbilly/AlarmPI/tree/v2.5) - Jul 10, 2017
#### CHANGED
  - categorize logs and get them as json if required
  - Min size of css merged with Mobile version

## [[2.4]](https://github.com/bkbilly/AlarmPI/tree/v2.4) - Apr 27, 2017
#### CHANGED
  - Refactor the services

## [2.3] - Apr 26, 2017
#### CHANGED
  - Installation script, ask configuration questions.

## [2.2] - Apr 25, 2017
#### ADDED
  - Startup Script.
  - Python requirements.
  - Install Script.

## [[2.1]](https://github.com/bkbilly/AlarmPI/tree/v2.1) - Apr 24, 2017
#### ADDED
  - Add hikvision Sensor (from settings.json)
#### FIXED
  - Fixed the GPIO Sensors on the UI to select only the unused pins.

## [[2.0]](https://github.com/bkbilly/AlarmPI/tree/v2.0) - Apr 16, 2017
#### ADDED
  - Created API for the sensors.
#### CHANGED
  - Write LOGs even if the sensor is inactive with the appropriate message.
  - Sensors converted from lists of dictionaries to dictionary of dictionary.

## [[1.9]](https://github.com/bkbilly/AlarmPI/tree/v1.9) - Mar 5, 2017
#### ADDED
  - More HTTP Requests for use in the Android Application.
  - HTTP Request for how many logs to get.

## [1.8] - Feb 28, 2017
#### ADDED
  - Protect connection with HTTPS (SSL certificate)
#### CHANGED
  - Changes to WebInterface settings.
  - Change the settings.json hierarchy.
#### FIXED
  - Fixed multiple logs on sensors alert.

## [1.7] - Feb 16, 2017
#### ADDED
  - Change settings from the WebInterface.

## [1.6] - Feb 12, 2017
#### ADDED
  - Commented every class and method.
  - Authenticate with username and password.
  - Added helping methods.
  - Activate/Deactivate alarm from HTTP request (socket still works).
#### CHANGED
  - Removed unwanted methods.

## [1.5] - Feb 11, 2017
#### CHANGED
  - Split code into two files.
  - Write the desired time based on the timezone from settings.json using pytz.

## [1.4] - Dec 26, 2016
#### ADDED
  - More detailed LOGs.
#### FIXED
  - Run the intruderAlert method in a thread in order not to interfere with the rest of the events.

## [1.3] - Dec 1, 2016
#### ADDED
  - Make VoIP Calls using pjsua library in C.
#### FIXED
  - Right working directory paths.

## [1.2] - Nov 29, 2016
#### ADDED
  - Send Mail on alarm with settings read from settings.json
  - Add or Remove sensors from the WebInterface.

## [1.1] - Nov 28, 2016
#### ADDED
  - Write LOGs to a file

## [1.0] - Nov 27, 2016
#### ADDED
  - Enable/Disable serene based on alarm armed.
  - Change settings.json from the WebInterface.
  - Seperate view for the mobile WebInterface.

## [0.7] - Nov 26, 2016
#### ADDED
  - New buttons for the senosors in the WebInterface
#### CHANGED
  - Removed NodeJS, replaced by Flask.
#### REMOVED
  - Refreshing the application on settings.json change.

## [0.6] - Nov 23, 2016
#### ADDED
  - First WebInterface based on NodeJS.
  - Store alerted pins to alertpins.json file in order to be used by the NodeJS.

## [0.3] - Nov 12, 2016
#### ADDED
  - Refresh application on settings.json change.
  - Print the alerted pins.

## [0.2] - Oct 30, 2016
#### FIXED
  - Add the event listener only if it has not already been added.
#### ADDED
  - Call a function when a PIN changes state.


## [0.1] - Mar 8, 2016
#### ADDED
  - Read from settings.json and run the Alarm.
