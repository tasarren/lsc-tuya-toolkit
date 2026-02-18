#!/bin/sh

SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
HOSTS_FILE_DEFAULT="${CUSTOM_DIR}/configs/hosts"
DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/offline.${DATETIME}.log"
HOSTS_FILE="${HOSTS_FILE_DEFAULT}"
CFG_FILE="${CUSTOM_DIR}/configs/hack.conf"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" >> "${LOG_FILE}"
}

mkdir -p "${SD_DIR}/logs" >/dev/null 2>&1 || true
exec >>"${LOG_FILE}" 2>&1

load_cfg() {
    # Defaults
    OFFLINE=1

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}


ensure_offline_mode() {
  log "offline.sh starting (hosts=${HOSTS_FILE})"

  if [ ! -f "${HOSTS_FILE}" ]; then
      log "Hosts file missing: ${HOSTS_FILE}"
      exit 0
  fi

  if ! mount | grep -q " on /etc/hosts "; then
      mount --bind "${HOSTS_FILE}" /etc/hosts || true
      log "Bound ${HOSTS_FILE} to /etc/hosts"
  fi
}

load_cfg

if [ "${OFFLINE}" = "1" ]; then
    ensure_offline_mode
fi