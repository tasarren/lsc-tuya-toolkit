#!/bin/sh
# This script ensures telnet is always running on port 24
# When anyka_ipc restarts, it kills any active telnetd process

LOG_FILENAME="telnet"
. "/tmp/sd/custom/env.sh"

# Defaults
TELNET=0
TELNET_PORT=24
LOCK="/tmp/telnet.sh.pid"

load_cfg
log "Telnet script starting"

run_telnet() {
  telnetd -p "${TELNET_PORT}" -l /bin/sh || true
  log "telnetd started on port ${TELNET_PORT}"
}

ensure_telnet() {
  if [ "${TELNET}" != "1" ]; then
    return
  fi

  if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
    exit 0
  fi
  echo $$ >"$LOCK"
  while :; do
    if ps | grep -v grep | grep -q "telnetd -p ${TELNET_PORT}"; then
      sleep 2
      continue
    fi
    run_telnet
    sleep 1
  done
}

ensure_telnet