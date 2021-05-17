#!/usr/bin/bash

export LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib
export HOME=/data/data/com.termux/files/home
export PATH=/usr/local/bin:/data/data/com.termux/files/usr/bin:/data/data/com.termux/files/usr/sbin:/data/data/com.termux/files/usr/bin/applets:/bin:/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin:/data/data/com.termux/files/usr/bin/python
export PYTHONPATH=/sdcard/

cd /sdcard/
echo "downloading mixplorer apk"
wget https://raw.githubusercontent.com/dragonpilot-community/apps/com.mixplorer.apk/com.mixplorer.apk
echo "installing the apk"
pm install -r "/sdcard/com.mixplorer.apk";
echo "Going to sleep because i am tired."
sleep 5;
