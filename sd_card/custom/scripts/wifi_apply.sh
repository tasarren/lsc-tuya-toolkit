#!/bin/sh

SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
CFG_FILE="${CUSTOM_DIR}/configs/hack.conf"
DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/wifi.${DATETIME}.log"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" >> "${LOG_FILE}"
}

trim() {
    # usage: trim "  value  " -> "value"
    echo "$1" | sed 's/^ *//; s/ *$//'
}

get_cfg() {
    key="$1"
    # Accept either strict KEY=value or KEY = value (whitespace tolerated).
    # Ignores commented lines.
    awk -v k="$key" -F= '
        /^[[:space:]]*#/ { next }
        /^[[:space:]]*$/ { next }
        {
            kk=$1
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", kk)
            if (kk == k) {
                vv=$2
                sub(/^[[:space:]]+/, "", vv)
                sub(/[[:space:]]+$/, "", vv)
                print vv
                exit
            }
        }
    ' "${CFG_FILE}" 2>/dev/null
}

stop_wifi_stack() {
    killall udhcpd >/dev/null 2>&1 || true
    killall udhcpc >/dev/null 2>&1 || true
    killall wpa_supplicant >/dev/null 2>&1 || true
    killall hostapd >/dev/null 2>&1 || true
}

start_sta() {
    ssid="$1"
    pass="$2"
    sec="$3"
    dhcp="$4"

    if [ -z "${ssid}" ]; then
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

    if [ -z "${sec}" ]; then
        sec=3
    fi

    log "STA: connecting ssid='${ssid}' security=${sec}"
    /usr/sbin/station_connect.sh "${sec}" "${ssid}" "${pass}" >>"${LOG_FILE}" 2>&1 || true

    if [ "${dhcp}" = "0" ]; then
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

if [ ! -f "${CFG_FILE}" ]; then
    mkdir -p "${SD_DIR}/logs" >/dev/null 2>&1 || true
    log "No config file: ${CFG_FILE}"
    exit 0
fi

mkdir -p "${SD_DIR}/logs" >/dev/null 2>&1 || true

MODE="$(get_cfg MODE)"
# Some firmwares don't ship coreutils tr; avoid dependency.
MODE="$(echo "${MODE}" | sed 'y/ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklmnopqrstuvwxyz/')"

log "wifi_apply starting (MODE=${MODE})"

case "${MODE}" in
    none|"")
        log "MODE=none, leaving wifi unchanged (set WIFI_MODE=sta in hack.conf)"
        # Try to put wifi back into station mode after AP hijack.
        killall udhcpd >/dev/null 2>&1 || true
        ifconfig wlan0 0.0.0.0 >/dev/null 2>&1 || true
        # touch /tmp/wifi_is_8188 >/dev/null 2>&1 || true
        exit 0
        ;;
    sta)
        SSID="$(get_cfg SSID)"
        PASS="$(get_cfg PASS)"
        SECURITY="$(get_cfg SECURITY)"
        DHCP="$(get_cfg DHCP)"
        if [ -z "${DHCP}" ]; then
            DHCP=1
        fi
        start_sta "${SSID}" "${PASS}" "${SECURITY}" "${DHCP}"
        exit $?
        ;;
    *)
        log "Unknown MODE='${MODE}', doing nothing"
        exit 1
        ;;
esac
