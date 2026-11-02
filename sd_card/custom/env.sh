#!/bin/sh

export SD_DIR="/tmp/sd"
export CUSTOM_DIR="${SD_DIR}/custom"
export BIN_DIR="${CUSTOM_DIR}/bin"
export SCRIPTS_DIR="${CUSTOM_DIR}/scripts"
export CONFIG_DIR="${CUSTOM_DIR}/configs"
export STATE_DIR="${CUSTOM_DIR}/state"
export AUDIO_DIR="${STATE_DIR}/audio"
export DUMP_ROOT_DIR="${SD_DIR}/dump"
export DUMP_DIR="${DUMP_ROOT_DIR}/${DATETIME}"
export DUMP_MARKER="${STATE_DIR}/dump.done"

export LOGS_DIR="${SD_DIR}/logs"

DATETIME="$(date +%Y%m%d_%H%M%S)"
export DATETIME
export LOG_FILENAME="${LOG_FILENAME:-hack}"
export LOG_FILE="${LOGS_DIR}/${LOG_FILENAME}.${DATETIME}.log"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

exec >>"${LOG_FILE}" 2>&1

load_cfg() {
  cfg_file="${1:-${CONFIG_DIR}/hack.conf}"
  if [ -f "${cfg_file}" ]; then
      # shellcheck disable=SC1090
      . "${cfg_file}"
  fi
}

kill_anyka() {
  kill -TERM "$(pidof anyka_ipc)" || true
}

kill_caches() {
  kill -9 "$(ps | grep -F 'drop_caches' | grep -v grep | awk '{print $1}')" || true
  rm /tmp/drop_caches.sh || true
}

do_mount() {
  src="$1"
  dst="$2"

  log "mount start: $src -> $dst"
  result=$(mount --verbose --bind "$src" "$dst" 2>&1)
  status=$?

  log "$result"

  if [ "$status" -ne 0 ]; then
    log "mount failed: $src -> $dst"
  fi

  return "$status"
}

ensure_dirs() {
  mkdir -p "${AUDIO_DIR}" || true
  mkdir -p "${LOGS_DIR}" || true
}

ensure_dirs

# Hack stages state
STAGE_1_MARKER="${STATE_DIR}/.stage1"
STAGE_1_DONE=0
if [ -f "${STAGE_1_MARKER}" ]; then
  STAGE_1_DONE=1
fi

export STAGE_1_DONE
export DB_FILE_ORIGINAL="${STATE_DIR}/tuya_user.original.db"
export DB_KEY_ORIGINAL="${STATE_DIR}/tuya_enckey.original.db"
export DB_FILE_HACKED="${STATE_DIR}/tuya_user.hacked.db"
export DB_KEY_HACKED="${STATE_DIR}/tuya_enckey.hacked.db"