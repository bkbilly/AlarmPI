from setuptools import setup, find_packages

REQUIRES = [
    'Flask==1.0.2',
    'Flask-SocketIO==3.0.1',
    'Flask-Login==0.4.1',
    'requests==2.20.0',
    'pytz==2018.5',
    'paho-mqtt==1.3.1',
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
