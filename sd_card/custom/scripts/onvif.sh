#!/bin/sh

SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
DATETIME="$(date +%Y%m%d_%H%M%S)"
CFG_FILE="${CUSTOM_DIR}/configs/hack.conf"
LOG_FILE="${SD_DIR}/logs/onvif.${DATETIME}.log"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*"
}

mkdir -p "${SD_DIR}/logs" >/dev/null 2>&1 || true
exec >>"${LOG_FILE}" 2>&1

load_cfg() {
    # Defaults
    ONVIF=1
    ONVIF_PTZ=1
    ONVIF_PTZCTL="${CUSTOM_DIR}/bin/ptzctl"

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}

mount_onvif_ptz_helpers() {
    if [ "${ONVIF_PTZ}" != "1" ]; then
        return 0
    fi

    for helper in ptz_move get_position is_moving ptz_presets.sh; do
        src="${CUSTOM_DIR}/scripts/${helper}"
        if [ ! -x "${src}" ]; then
            log "WARN ONVIF PTZ helper missing: ${src}"
            continue
        fi
        chmod +x "${src}" >/dev/null 2>&1 || true
    done

    if [ ! -x "${ONVIF_PTZCTL}" ]; then
        log "WARN ONVIF PTZ controller missing: ${ONVIF_PTZCTL}"
    fi
}

ensure_onvif() {
    mount_onvif_ptz_helpers

    if ps | grep -v grep | grep -q "lighttpd -f /usr/local/etc/lighttpd.conf"; then
        return 0
    fi

    if [ -x /usr/local/bin/mini_onvif_service.sh ]; then
        /usr/local/bin/mini_onvif_service.sh start || true
        log "ONVIF started (mini_onvif_service.sh)"
    else
        log "ONVIF requested but missing: /usr/local/bin/mini_onvif_service.sh"
    fi
}

log_onvif_status() {
    if [ "${ONVIF}" != "1" ]; then
        return 0
    fi
    # Once per boot.
    if [ -e /tmp/.ht_onvif_status_logged ]; then
        return 0
    fi

    {
        echo "[${SD_DIR}] ONVIF status $(date +%Y-%m-%dT%H:%M:%S)"
        echo ""
        echo "## ps"
        ps w | grep -v grep | grep -E "lighttpd|wsd_simple_server|onvif_notify_server|events_service" || true
        echo ""
        echo "## netstat"
        netstat -lntp 2>/dev/null | grep -E ":80\b|:8080\b|:3702\b|:8899\b" || true
        netstat -lnt 2>/dev/null | grep -E ":80\b|:8080\b|:3702\b|:8899\b" || true
        echo ""
        echo "## http probe"
        if command -v wget >/dev/null 2>&1; then
            wget -qO- http://127.0.0.1:8080/ 2>/dev/null | head -c 200 || true
            echo ""
            wget -qO- http://127.0.0.1:8080/onvif/device_service 2>/dev/null | head -c 200 || true
            echo ""
        fi
    } > "${SD_DIR}/logs/onvif_status.txt" 2>&1

    touch /tmp/.ht_onvif_status_logged 2>/dev/null || true
    log "Wrote ${SD_DIR}/logs/onvif_status.txt"
}

load_cfg
if [ "${ONVIF}" = "1" ]; then
  ensure_onvif
  log_onvif_status
fi