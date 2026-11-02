#! /bin/sh

MODE="$1"
PATH="$PATH:/bin:/sbin:/usr/bin:/usr/sbin"

LOG_FILENAME="anyka_ipc"
. "/tmp/sd/custom/env.sh"

# Defaults
LOG_ANYKA=0
load_cfg
log "anyka_ipc.sh script starting"

usage() {
  echo "Usage: $0 start|stop|restart"
  exit 3
}

entrypoint() {
  if [ -x "${SCRIPTS_DIR}/entrypoint.sh" ]; then
      /bin/sh "${SCRIPTS_DIR}/entrypoint.sh" >/dev/null 2>&1 &
  else
      log "ERROR entrypoint missing: ${SCRIPTS_DIR}/entrypoint.sh"
  fi

}

start_latch() {
  latch="${BIN_DIR}/mqtt_latch"
  cert="${STATE_DIR}/mqtt/server.crt"
  key="${STATE_DIR}/mqtt/server.key"
  i=0
  [ -x "$latch" ] && [ -f "$cert" ] && [ -f "$key" ] || return 0
  killall mqtt_latch >/dev/null 2>&1 || true
  "$latch" "$cert" "$key" >/dev/null 2>&1 &
  while [ "$i" -lt 15 ]; do
    if netstat -ltn 2>/dev/null | grep -q ':8883 '; then
      log "mqtt_latch listening"
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  log "mqtt_latch did not listen on :8883"
}

start() {
  if pgrep anyka_ipc >/dev/null 2>&1; then
    log "anyka_ipc already running"
    exit 0
  fi

  start_latch
  # anyka_ipc pins its MQTT socket to wlan0 (SO_BINDTODEVICE), which makes
  # 127.0.0.1 unreachable. The preload drops that option.
  preload=""
  if [ -f "${BIN_DIR}/libnobind.so" ]; then
    preload="${BIN_DIR}/libnobind.so"
  fi
  log "start ipc service..."
  if [ "${LOG_ANYKA}" = "1" ]; then
    LD_PRELOAD="$preload" anyka_ipc >>"$LOG_FILE" 2>&1 &
  else
		LD_PRELOAD="$preload" anyka_ipc > /dev/null &
  fi
  log "log: $LOG_FILE"
  entrypoint
}

stop() {
  log "stopping ipc service..."
  killall anyka_ipc >/dev/null 2>&1 || true
  killall mqtt_latch >/dev/null 2>&1 || true
  sleep 1
  killall -9 anyka_ipc >/dev/null 2>&1 || true
  killall -9 mqtt_latch >/dev/null 2>&1 || true
}

restart() {
  log "restart ipc service..."
  stop
  start
}

case "$MODE" in
  start) start ;;
  stop) stop ;;
  restart) restart ;;
  *) usage ;;
esac

exit 0