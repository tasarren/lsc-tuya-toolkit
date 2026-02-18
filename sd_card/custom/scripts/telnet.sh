#!/bin/sh
SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/telnet.${DATETIME}.log"
CFG_FILE="${CUSTOM_DIR}/configs/hack.conf"
LOCK="/tmp/telnet.sh.pid"


log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" >> "${LOG_FILE}"
}

mkdir -p "${SD_DIR}/logs" >/dev/null 2>&1 || true
exec >>"${LOG_FILE}" 2>&1

load_cfg() {
    # Defaults
    TELNET=0
    TELNET_PORT=24

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}

run_telnet() {
  telnetd -p "${TELNET_PORT}" -l /bin/sh || true
  log "telnetd started on port ${TELNET_PORT}"
}

ensure_telnet() {
  while :; do
    if ps | grep -v grep | grep -q "telnetd -p ${TELNET_PORT}"; then
      sleep 2
      continue
    fi
    run_telnet
    sleep 1
  done
}

load_cfg

if [ "${TELNET}" = "1" ]; then
    if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
      exit 0
    fi
    echo $$ >"$LOCK"
    ensure_telnet
fi