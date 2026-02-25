#!/bin/sh

SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
CFG_FILE="${CUSTOM_DIR}/configs/wifi.conf"
DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/wifi.${DATETIME}.log"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" >> "${LOG_FILE}"
}
exec >>"${LOG_FILE}" 2>&1

load_cfg() {
    # Defaults
    MODE=none
    SSID=""
    PASS=""
    SECURITY=0
    DHCP=1

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}

stop_wifi_stack() {
    killall udhcpd >/dev/null 2>&1 || true
    killall udhcpc >/dev/null 2>&1 || true
    killall wpa_supplicant >/dev/null 2>&1 || true
    killall hostapd >/dev/null 2>&1 || true
}

start_sta() {
    if [ -z "${SSID}" ]; then
        log "STA: SSID is empty, skipping"
        return 1
    fi

    stop_wifi_stack
    ifconfig wlan0 0.0.0.0 >/dev/null 2>&1 || true
    ifconfig wlan0 up >/dev/null 2>&1 || true

    mkdir -p /var/run/wpa_supplicant >/dev/null 2>&1 || true

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

    return 0
}

load_cfg
log "wifi_apply starting (MODE=${MODE})"

case "${MODE}" in
    none|"")
        log "MODE=none, leaving wifi unchanged (set WIFI_MODE=sta in wifi.conf)"
        # Try to put wifi back into station mode after AP hijack.
        killall udhcpd >/dev/null 2>&1 || true
        ifconfig wlan0 0.0.0.0 >/dev/null 2>&1 || true
        # touch /tmp/wifi_is_8188 >/dev/null 2>&1 || true
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
