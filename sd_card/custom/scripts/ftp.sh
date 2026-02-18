#!/bin/sh
SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/ftp.${DATETIME}.log"
CFG_FILE="${CUSTOM_DIR}/configs/hack.conf"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" >> "${LOG_FILE}"
}

mkdir -p "${SD_DIR}/logs" >/dev/null 2>&1 || true
touch "${LOG_FILE}"
exec >>"${LOG_FILE}" 2>&1

load_cfg() {
    # Defaults
    FTP=0
    FTP_PORT=21

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}

ensure_ftp() {
    if ps | grep -v grep | grep -q "tcpsvd 0 ${FTP_PORT}"; then
        return 0
    fi
    tcpsvd 0 "${FTP_PORT}" ftpd -a -w / -t 1800 &
    log "ftp started on port ${FTP_PORT}"
}

load_cfg
if [ "${FTP}" = "1" ]; then
    ensure_ftp
fi