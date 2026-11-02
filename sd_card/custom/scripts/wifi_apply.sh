#!/bin/sh
# This scripts enables WiFi by manually connecting to the interface
# anyka_ipc should handle connection correctly if using the kvtool
# but this script is useful if you want full sandbox mode
LOG_FILENAME="wifi"
. "/tmp/sd/custom/env.sh"

# Defaults
MODE=none
SSID=""
PASS=""
SECURITY=0
DHCP=1
load_cfg
log "wifi_apply starting (MODE=${MODE})"

stop_wifi_stack() {
    log "Stop network stack"
    killall wpa_supplicant >>"${LOG_FILE}" 2>&1 || true
    killall udhcpd >>"${LOG_FILE}" 2>&1 || true
    # killall hostapd  >>"${LOG_FILE}" 2>&1 || true
    ifconfig wlan0 0.0.0.0  >>"${LOG_FILE}" 2>&1 || true
}

start_sta() {
    if [ -z "${SSID}" ]; then
        log "STA: SSID is empty, skipping"
        return 1
    fi

    stop_wifi_stack
    ifconfig wlan0 up  >>"${LOG_FILE}" 2>&1 || true

    mkdir -p /var/run/wpa_supplicant  >>"${LOG_FILE}" 2>&1 || true

    cat > /tmp/wpa_supplicant.conf <<'EOF'
ctrl_interface=/var/run/wpa_supplicant
update_config=1
EOF

    log "STA: starting wpa_supplicant"
    wpa_supplicant -B -iwlan0 -Dnl80211 -c /tmp/wpa_supplicant.conf >>"${LOG_FILE}" 2>&1 || true

    log "STA: connecting ssid='${SSID}' security=${SECURITY}"
    /usr/sbin/station_connect.sh "${SECURITY}" "${SSID}" "${PASS}" >>"${LOG_FILE}" 2>&1 || true

    if [ "${DHCP}" = "0" ]; then
        log "STA: DHCP disabled by config"
        return 0
    fi

    log "STA: starting udhcpc"
    if [ -x /usr/share/udhcpc/default.script ]; then
        udhcpc -i wlan0 -s /usr/share/udhcpc/default.script >>"${LOG_FILE}" 2>&1 || true
    else
        udhcpc -i wlan0 >>"${LOG_FILE}" 2>&1 || true
    fi

    iwpriv wlan0 common get_conn_state > /tmp/wpa_status.txt

    return 0
}

drop_factory_ap() {
    # Firmware starts wlan0 as AP (udhcpd + 172.16.10.1) before this hijack.
    # Drop only that AP DHCP/address. Never kill wpa_supplicant or zero a live STA IP.
    killall udhcpd >>"${LOG_FILE}" 2>&1 || true
    if ifconfig wlan0 2>/dev/null | grep -q "inet addr:172.16.10.1"; then
        log "Drop factory AP address 172.16.10.1"
        ifconfig wlan0 0.0.0.0 >>"${LOG_FILE}" 2>&1 || true
    else
        log "MODE=none: leave STA addressing unchanged"
    fi
}

case "${MODE}" in
    none|"")
        log "MODE=none, leaving wifi unchanged (set WIFI_MODE=sta in wifi.conf)"
        drop_factory_ap
        exit 0
        ;;
    sta)
        start_sta
        exit $?
        ;;
    *)
        log "Unknown MODE='${MODE}', doing nothing"
        exit 1
        ;;
esac
