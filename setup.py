from setuptools import setup, find_packages

REQUIRES = [
<<<<<<< HEAD
    'Flask==1.1.1',
    'Flask-SocketIO==3.0.1',
=======
    'Flask==1.0.2',
    'Flask-SocketIO==4.2.1',
>>>>>>> eb370438a15247bcd778632064e44f15d3c58822
    'Flask-Login==0.4.1',
    'requests==2.22.0',
    'pytz==2019.2',
    'paho-mqtt==1.4.0',
    'RPi.GPIO==0.7.0',
]


setup(
    name='AlarmPI',
    version='4.0',
    description='Home Security System',
    author='bkbilly',
    author_email='bkbilly@hotmail.com',
    packages=find_packages(),
    install_requires=REQUIRES,
    # long_description=open('README.md').read()
)
