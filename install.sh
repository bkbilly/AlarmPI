#!/bin/bash

# Global
basedir=/opt/AlarmPI

# Installing with apt-get
echo -e "\e[35mLooking for GIT...\e[0m"
if [ -z $(which git) ]; then
    echo -e "\e[31mGit not found, installing from apt-get:\e[0m"
    sudo apt-get --yes --force-yes install git
fi

echo -e "\e[35mLooking for JSON processor...\e[0m"
if [ -z $(which jq) ]; then
    echo -e "\e[31mJQ not found, installing from apt-get:\e[0m"
    sudo apt-get --yes --force-yes install jq
fi

echo -e "\e[35mLooking for Python3...\e[0m"
if [ -z $(which python3) ]; then
    echo -e "\e[31mPython3 not found, installing from apt-get:\e[0m"
    sudo apt-get --yes --force-yes install python3
fi

echo -e "\e[35mLooking for PIP3...\e[0m"
if [ -z $(which pip3) ]; then
    echo -e "\e[31mPIP3 not found, installing from apt-get:\e[0m"
    sudo apt-get --yes --force-yes install python3-pip
fi


# Download from GitHub
if [ ! -d $basedir ]; then
    echo -e "\e[35mDownloading from GitHub...\e[0m"
    sudo git clone https://github.com/bkbilly/AlarmPI.git $basedir
else
    echo -e "\e[35mAlarmPI already exists, updating...\e[0m"
    sudo git -C $basedir pull origin master
fi



# User Configuration
echo -e "\e[35mUser configuration...\e[0m"
if [ ! -f $basedir/play.wav ]; then
    sudo cp $basedir/play_template.wav $basedir/play.wav
fi
if [ ! -f $basedir/config/settings.json ]; then
    sudo cp $basedir/config/settings_template.json $basedir/config/settings.json
fi
if [ ! -f $basedir/config/server.json ]; then
    sudo cp $basedir/config/server_template.json $basedir/config/server.json
fi
settingsJson=`cat $basedir/config/settings.json`
serverJson=`cat $basedir/config/server.json`
defport=`echo $serverJson | jq -r ".ui.port"`
defhttps=`echo $serverJson | jq -r ".ui.https"`
echo $defhttps
if [[ $defhttps == 'true' ]]; then
    defhttps='Y/n'
else
    defhttps='y/N'
fi
defusername=`echo $serverJson | jq -r ".users | keys[0]"`
defpassword=`echo $serverJson | jq -r ".users.$defusername.pw"`

read -p "Change port? [$defport] " port
if [[ ! $port =~ ^[0-9]+$ ]]; then
    port=$defport
fi
read -p "Want to use HTTPs? [$defhttps] " https
if [[ $https =~ ^[Nn]$ ]]; then
    https='false'
elif [[ $https =~ ^[Yy]$ ]]; then
    https='true'
elif [[ $defhttps == 'Y/n' ]]; then
    https='true'
else
    https='false'
fi
read -p "Username [$defusername]: " username
if [[ $username == "" ]]; then
    username=$defusername
fi
read -p "Password [$defpassword]: " password
if [[ $password == "" ]]; then
    password=$defpassword
fi
serverJson=`echo $serverJson | jq ".ui.port=$port"`
serverJson=`echo $serverJson | jq ".ui.https=$https"`
serverJson=`echo $serverJson | jq ".users.$defusername.pw=\"$password\""`
if [ "$defusername" != "$username" ]; then
    serverJson=`echo $serverJson | jq ".users.$username=.users.$defusername | del(.users.$defusername)"`
fi
echo $settingsJson | jq '.' | sudo tee $basedir/settings.json > /dev/null
echo $serverJson | jq '.' | sudo tee $basedir/server.json > /dev/null

if [[ $https == 'true' ]]; then
    httpsurl='https'
else
    httpsurl='http'
fi


# Install Python requirements
echo -e "\e[35mInstalling Python requirements...\e[0m"
sudo pip3 install -r $basedir/requirements.txt

# Install as a service
echo -e "\e[35mInstalling as a service...\e[0m"
#sudo chmod +x $basedir/autostart/alarmpi
#sudo ln -s $basedir/autostart/alarmpi /etc/init.d/alarmpi
#sudo update-rc.d alarmpi defaults
#sudo service alarmpi stop
#sudo service alarmpi start
sudo cp $basedir/autostart/alarmpi.service /etc/systemd/system/alarmpi.service
sudo chmod +x /etc/systemd/system/alarmpi.service
sudo systemctl enable alarmpi
sudo service alarmpi start


# Done
myURL="$httpsurl://$username:$password@localhost:$port"
echo -e "\n\n\nAll done!"
echo -e "\e[33mThis is your URL: $myURL\e[0m"
echo "Enjoy!!!"

