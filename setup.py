from setuptools import setup, find_packages

REQUIRES = [
    'Flask==0.12.2',
    'Flask-SocketIO==2.9.2',
    'Flask-Login==0.4.0',
    'requests==2.18.4',
    'pytz==2017.2',
    'paho-mqtt==1.3.0',
    'RPi.GPIO==0.6.3',
]


setup(
    name='AlarmPI',
    version='1.5',
    description='Home Security System',
    author='bkbilly',
    author_email='bkbilly@hotmail.com',
    packages=find_packages(),
    install_requires=REQUIRES,
    # long_description=open('README.md').read()
)
