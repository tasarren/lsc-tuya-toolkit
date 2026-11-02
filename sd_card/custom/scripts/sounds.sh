#!/bin/sh
# This script replaces audio files from the device with custom ones
LOG_FILENAME="sounds"
. "/tmp/sd/custom/env.sh"

# Defaults
MUTE_FACTORY_PROMPT=1
MUTE_ALL_SOUNDS=0
REPLACE_SOUNDS=0
SILENT_FILE="${AUDIO_DIR}/custom/silent.mp3"

load_cfg
log "Sounds script starting"

apply_factory_sound_mute() {
  if [ "${MUTE_FACTORY_PROMPT}" != "1" ]; then
    return
  fi
  for f in \
    /usr/share/hutong_sound2.mp3 \
    /usr/share/8k16_cn_factory_enter_factory_mode.mp3 \
    /usr/share/8k16_cn_factory_speaker_test_voice.mp3; do
    [ -e "${f}" ] || continue
    do_mount "${SILENT_FILE}" "${f}"
    log "Muted factory prompt file: ${f}"
  done
}

mute_all() {
  if [ "${MUTE_ALL_SOUNDS}" != "1" ]; then
    return
  fi
  for f in /usr/share/*.mp3; do
    [ -e "${f}" ] || continue
    do_mount "${SILENT_FILE}" "${f}"
    log "Muted audio file: ${f}"
  done
}

replace_all() {
  if [ "${REPLACE_SOUNDS}" != "1" ]; then
    return
  fi
  for f in "${AUDIO_DIR}"/*.mp3; do
    [ -e "${f}" ] || continue
    name=${f##*/}
    do_mount "${f}" "/usr/share/${name}"
    log "Replaced audio file: ${name}"
  done
}

mute_all
apply_factory_sound_mute
replace_all