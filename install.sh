#!/bin/bash

echo -e "\e[35mLooking for GIT...\e[0m"
if [ -z $(which git) ]; then
	echo -e "\e[31mGit not found, installing from apt-get:\e[0m"
	sudo apt-get install git
fi

echo -e "\e[35mLooking for Python...\e[0m"
if [ -z $(which python) ]; then
	echo -e "\e[31mPython not found, installing from apt-get:\e[0m"
	sudo apt-get install python
fi

echo -e "\e[35mLooking for PIP...\e[0m"
if [ -z $(which pip) ]; then
	echo -e "\e[31mPIP not found, installing from apt-get:\e[0m"
	sudo apt-get install python-pip
fi


echo -e "\e[35mDownloading from GitHub...\e[0m"
sudo git clone https://github.com/bkbilly/AlarmPI.git /opt/AlarmPI/

echo -e "\e[35mInstalling Python requirements...\e[0m"
cd /opt/AlarmPI/
sudo cp settings_template.json settings.json
sudo cp play_template.wav play.wav
sudo pip install -r requirements.txt

echo -e "\e[35mInstalling as a service...\e[0m"
sudo chmod +x /opt/AlarmPI/alarmpi
sudo ln -s /opt/AlarmPI/alarmpi /etc/init.d/alarmpi
sudo update-rc.d alarmpi defaults
sudo service alarmpi start


echo -e "\n\n\nAll done!\n\n"
echo "Enjoy!!!"

