#!/bin/sh
# This script is run every time anyka_ipc.sh is called with start argument
# in order to re-run our payloads everytime anyka_ipc restarts
# This behaviour is controlled by the anyka daemon process.

LOG_FILENAME="entrypoint"
. "/tmp/sd/custom/env.sh"

# Defaults
SAVE_SYSLOG=0
SANDBOX_MODE=0

load_cfg
log "entrypoint starting"

save_syslog_tail() {
    if [ "${SAVE_SYSLOG}" != "1" ]; then
        return 0
    fi
    if [ ! -f /var/log/messages ]; then
        return 0
    fi
    # Once per boot.
    if [ -e /tmp/.ht_syslog_saved ]; then
        return 0
    fi
    tail -n 400 /var/log/messages > "${SD_DIR}/logs/messages_tail.txt" 2>/dev/null || true
    touch /tmp/.ht_syslog_saved 2>/dev/null || true
    log "Saved /var/log/messages tail to ${SD_DIR}/logs/messages_tail.txt"
}

set_cpus() {
  ulimit -c unlimited
  echo "1" > /proc/sys/kernel/core_uses_pid
  echo "/mnt/ht_log/core_%e_%p_%t" > /proc/sys/kernel/core_pattern
  rm /tmp/camera_start_times
}

wait_rtsp_listening() {
  PORTS="554 88 89 6667 6668 6669 7000 7001"
  MAX="${1:-30}"   # seconds
  i=0
  log "Wait for RTSP"

  while [ "$i" -lt "$MAX" ]; do
    for p in $PORTS; do
      # Prefer netstat if available
      if netstat -ltnp 2>/dev/null | grep -q "anyka_ipc" | grep -q ":$p "; then
        log "RTSP running"
        return 0
      fi
      # BusyBox netstat often lacks -p; fallback without process match
      if netstat -ltn 2>/dev/null | grep -q ":$p "; then
        log "RTSP running"
        return 0
      fi
    done
    sleep 1
    i=$((i+1))
  done
  log "Timeout waiting for RTSP"
}

wait_anyka() {
  # Wait untill anyka_ipc is running
  while ! pgrep anyka_ipc >/dev/null 2>&1; do
    sleep 1
  done
  log "anyka_ipc running"
  sleep 30
}

save_syslog_tail

log "DATE IS: $(date)"

if [ "${SANDBOX_MODE}" != "1" ]; then
  wait_anyka
fi

/bin/sh "${SCRIPTS_DIR}/wifi_apply.sh" >/dev/null 2>&1 &
/bin/sh "${SCRIPTS_DIR}/remote.sh" >/dev/null 2>&1 &
/bin/sh "${SCRIPTS_DIR}/offline.sh" >/dev/null 2>&1 &
/bin/sh "${SCRIPTS_DIR}/onvif.sh" >/dev/null 2>&1 &

if [ "${SANDBOX_MODE}" != "1" ]; then
  # Wait until any RTSP port is open
  wait_rtsp_listening 30
fi

log "entrypoint done"
