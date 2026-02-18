#!/bin/sh

SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
SCRIPTS_DIR="${CUSTOM_DIR}/scripts"
CONFIG_DIR="${CUSTOM_DIR}/configs"
STATE_DIR="${CUSTOM_DIR}/state"

DATETIME="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${SD_DIR}/logs/run.${DATETIME}.log"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*"
}

load_cfg() {
    # Defaults
    OVERRIDE_HW_SETTINGS=1
    OVERRIDE_SW_SETTINGS=1

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}

kill_processes() {
  kill -9 "$(ps | grep -F 'drop_caches' | grep -v grep | awk '{print $1}')" || true
  rm /tmp/drop_caches.sh || true
  kill -TERM "$(pidof anyka_ipc)" || true
}

ensure_shadow() {
  src="${SD_DIR}/shadow"
  dst="/etc/config/shadow"
  done="${STATE_DIR}/shadow.done"

  [ -f "$done" ] && [ -f "$dst" ] && return 0

  log "Copying shadow"
  touch "${dst}"
  mount --bind "${src}" "${dst}" || true

  : > "$done"
  log "Shadow copied."
}

apply_overrides() {
  mount --bind "${SCRIPTS_DIR}/recover_cfg.sh" /usr/sbin/recover_cfg.sh || true
  mount --bind "${SCRIPTS_DIR}/anyka_ipc.sh" /usr/sbin/anyka_ipc.sh || true
  if [ "${OVERRIDE_HW_SETTINGS}" = "1" ]; then
    mount --bind "${CONFIG_DIR}/_ht_hw_settings.ini" /usr/local/_ht_hw_settings.ini || true
  fi
  if [ "${OVERRIDE_SW_SETTINGS}" = "1" ]; then
    mount --bind "${CONFIG_DIR}/_ht_sw_settings.ini" /etc/config/_ht_sw_settings.ini || true
  fi
  # mount --bind "${CONFIG_DIR}/factory_cfg.ini" /usr/local/factory_cfg.ini || true
  mount --bind "${CONFIG_DIR}/onvif_simple_server.conf" /usr/local/etc/onvif_simple_server.conf || true
  touch "${SD_DIR}/logs/anyka_debug.${DATETIME}.log"
  touch /etc/config/log_debug
  mount --bind "${SD_DIR}/logs/anyka_debug.${DATETIME}.log" /etc/config/log_debug || true

  ensure_shadow
  sync
}


show_info() {
  log "===================="
  log "------------ process"
  ps aux
  log "------------ /tmp"
  ls -a /tmp
  log "------------ netstat"
  netstat -tulpn
  log "===================="
}

main() {
  log "Checkin stuff pre-hack"
  show_info
  if [ ! -x "${SCRIPTS_DIR}/dump_fs.sh" ]; then
      log "ERROR dump_fs.sh missing or not executable: ${SCRIPTS_DIR}/dump_fs.sh"
      return 1
  fi

  /bin/sh "${SCRIPTS_DIR}/dump_fs.sh" >/dev/null 2>&1

  apply_overrides || true
  kill_processes || true

  log "Checkin stuff post-hack"
  show_info
}

mkdir -p "${SD_DIR}"
mount /dev/mmcblk0p1 "${SD_DIR}" || mount /dev/mmcblk0 "${SD_DIR}" || true

mkdir -p "${SD_DIR}/logs"
load_cfg
exec >>"${LOG_FILE}" 2>&1

/bin/sh "${SCRIPTS_DIR}/sounds.sh" >/dev/null 2>&1

log "hack.sh starting"
log "DATE IS: $(date)"

main
log "hack.sh done"