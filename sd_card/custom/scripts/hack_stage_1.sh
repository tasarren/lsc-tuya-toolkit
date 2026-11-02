#!/bin/sh
# Hack Stage 1!
# This stage stores the necessary files in our $STATE_DIR
# so we can inject our payloads, tweak values and whatnot

LOG_FILENAME="stage1"
. "/tmp/sd/custom/env.sh"

log "Running Hack stage 1"

backup_files() {
  if [ "${STAGE_1_DONE}" = "1" ]; then
    log "Hack stage 1 already done."
    return
  fi

  # DB Files to be rewritten by our kvtool
  cp /etc/config/tuya_user.db "${DB_FILE_ORIGINAL}"
  cp /etc/config/tuya_enckey.db "${DB_KEY_ORIGINAL}"

  # Default device configs, tunable
  cp /usr/local/etc/onvif_simple_server.conf "${STATE_DIR}"
  cp /usr/local/etc/lighttpd.conf "${STATE_DIR}"
  cp /usr/local/_ht_hw_settings.ini "${STATE_DIR}"
  cp /etc/config/_ht_sw_settings.ini "${STATE_DIR}"

  # Default device audio files, to be override if wanted
  cp -r /usr/share/*.mp3 "${AUDIO_DIR}"

  touch "${STAGE_1_MARKER}"
}

backup_files

log "Hack Stage 1 done."
/bin/sh "${SCRIPTS_DIR}/hack_stage_2.sh" >/dev/null 2>&1