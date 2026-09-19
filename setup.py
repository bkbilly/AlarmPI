from setuptools import setup, find_packages

REQUIRES = [
    'Flask>=3.0.0',
    'Flask-SocketIO>=5.3.6',
    'Flask-Login>=0.6.3',
    'requests>=2.31.0',
    'pytz>=2024.1',
    'paho-mqtt>=2.0.0',
    'simple-websocket>=1.1.0',
    'Werkzeug>=3.0.0',
    'RPi.GPIO>=0.7.1; sys_platform == "linux" and (platform_machine == "armv7l" or platform_machine == "aarch64" or platform_machine == "armv6l")',
]

setup(
    name='AlarmPI',
    version='5.0',
    description='Modular Home Security & Automation System for Raspberry Pi and Modern Linux',
    author='bkbilly',
    author_email='bkbilly@hotmail.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=REQUIRES,
    python_requires='>=3.9',
)
