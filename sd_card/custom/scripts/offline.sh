#!/bin/sh
# This script replaces hosts with no addresses to avoid Tuya services
LOG_FILENAME="offline"
. "/tmp/sd/custom/env.sh"

# Defaults
OFFLINE=1
HOSTS_FILE="${STATE_DIR}/hosts"
load_cfg
log "Offline script starting"

ensure_offline_mode() {
  if [ "${OFFLINE}" != "1" ]; then
    return
  fi

  if [ ! -f "${HOSTS_FILE}" ]; then
      log "Hosts file missing: ${HOSTS_FILE}"
      exit 0
  fi

  if ! mount | grep -q " on /etc/hosts "; then
      do_mount "${HOSTS_FILE}" /etc/hosts
      log "Bound ${HOSTS_FILE} to /etc/hosts"
  fi
}

ensure_offline_mode