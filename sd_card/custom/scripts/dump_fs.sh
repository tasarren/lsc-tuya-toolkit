#!/bin/sh

LOG_FILENAME="dump"
. "/tmp/sd/custom/env.sh"

# Defaults
DUMP_FORCE=0

load_cfg

log "Running dump script"

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

  mkdir -p "${DUMP_DIR}"
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

run_dump_once
