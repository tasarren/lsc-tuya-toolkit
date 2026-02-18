#!/bin/sh

SD_DIR="/tmp/sd"
DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/recover.${DATETIME}.log"

mkdir -p "${SD_DIR}/logs"
exec >>"${LOG_FILE}" 2>&1
#recover factory config ini
echo "========= system reset start ==========="
#cp /usr/local/factory_cfg.ini /etc/config/anyka_cfg.ini
sync
#disable watchdog
killall -12 daemon
# recover tuya specific configure
rm -rf /etc/config/isp*.conf
rm -rf /etc/config/_ht_sw_settings.ini
rm -rf /etc/config/tuya_user.db*
rm -rf /etc/config/tuya_enckey.db

#killall -9 wpa_supplicant
killall -9 anyka_ipc
#ifconfig wlan0 down
# /etc/config/wifi_driver_new.sh stop
#rm -rf /etc/config/wifi_driver.sh
echo "========== system reset end============"
sleep 3
reboot -f
#after all done play tips
#play_recover_tip
