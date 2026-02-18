#!/bin/sh

SD_DIR="/tmp/sd"
CUSTOM_DIR="${SD_DIR}/custom"
CONFIG_DIR="${CUSTOM_DIR}/configs"
DUMP_ROOT_DIR="${SD_DIR}/dump"
DATETIME="$(date +%Y%m%d_%H%M%S)"
DUMP_DIR="${DUMP_ROOT_DIR}/${DATETIME}"
LOG_FILE="${SD_DIR}/logs/dump.${DATETIME}.log"
STATE_DIR="${CUSTOM_DIR}/state"
DUMP_MARKER="${STATE_DIR}/dump.done"
CFG_FILE="${CONFIG_DIR}/hack.conf"

log() {
    echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*"
}

load_cfg() {
    # Defaults
    DUMP_FORCE=0

    if [ -f "${CFG_FILE}" ]; then
        # shellcheck disable=SC1090
        . "${CFG_FILE}"
    fi
}

copy_item() {
    src="$1"

    if [ ! -e "${src}" ]; then
        log "SKIP missing: ${src}"
        return 0
    fi

    log "COPY ${src} -> ${DUMP_DIR}/"
    cp -a "${src}" "${DUMP_DIR}/" || log "WARN copy failed: ${src}"
}

run_dump() {
  log "Starting filesystem dump"
  log "SD_DIR=${SD_DIR}"
  log "DUMP_ROOT_DIR=${DUMP_ROOT_DIR}"

  for src in /*; do
      name="${src#/}"
      case "${name}" in
          tmp|proc|dev|sys|mount|mnt|media|run)
              log "SKIP excluded: ${src}"
              continue
              ;;
      esac
      copy_item "${src}"
  done
}

run_dump_once() {
    if [ "${DUMP_FORCE}" = "1" ]; then
        log "DUMP_FORCE=1: running dump_fs.sh"
    else
        if [ -f "${DUMP_MARKER}" ]; then
            log "DUMP_FORCE=1 but dump already done (${DUMP_MARKER}); skipping"
            return 0
        fi
        log "DUMP_FORCE=1: running dump_fs.sh (first time)"
    fi
    run_dump
    rc=$?
    if [ $rc -eq 0 ]; then
        mkdir -p "${STATE_DIR}" >/dev/null 2>&1 || true
        date > "${DUMP_MARKER}" 2>/dev/null || true
        log "Dump succeeded, wrote ${DUMP_MARKER}"
        return 0
    fi

    log "Dump failed (rc=${rc}); not writing done flag"
    return $rc
}

mkdir -p "${SD_DIR}"
mount /dev/mmcblk0p1 "${SD_DIR}" || mount /dev/mmcblk0 "${SD_DIR}" || true

mkdir -p "${SD_DIR}/logs"
mkdir -p "${DUMP_DIR}"
exec >>"${LOG_FILE}" 2>&1

load_cfg
run_dump_once
