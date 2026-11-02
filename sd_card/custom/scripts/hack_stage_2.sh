#!/bin/sh
# Hack Stage 2!
# This stage bind mounts our payloads into the sytstem

LOG_FILENAME="stage2"
. "/tmp/sd/custom/env.sh"

log "Running Hack stage 2"


ensure_shadow() {
  src="${SD_DIR}/shadow"
  dst="/etc/config/shadow"
  done="${STATE_DIR}/shadow.done"

  [ -f "$done" ] && [ -f "$dst" ] && return 0

  touch "${dst}"
  do_mount "${src}" "${dst}"
  touch "${done}"
}


ensure_ini_flag() {
  ini="${STATE_DIR}/_ht_sw_settings.ini"
  key="$1"
  [ -f "$ini" ] || return 0
  if grep -q "^${key}" "$ini"; then
    sed -i "s/^${key}.*/${key} = 1/" "$ini"
  else
    printf '\n%s = 1\n' "${key}" >> "$ini"
  fi
}


ensure_bind_service() {
  # Skip Anyka QR (bind) and mark WiFi as configured so main() will decrypt
  # _ht_encrypt.bin slots 3/4 after Tuya tkl_wifi_station_connect persists them.
  # Empty slots are a no-op; do not overlay wpa_supplicant (MODE=none).
  ensure_ini_flag "bool_has_bind_service"
  ensure_ini_flag "bool_has_config_wifi"
  # Non-factory RTSP :88/:89 is started from ht_onvif_service_start() after MQTT,
  # only when this flag is 1. Default 0 leaves those ports closed.
  ensure_ini_flag "bool_onvif_switch"
}


ht_ini_get() {
  _file="$1"
  _key="$2"
  _line=$(grep "^${_key}[[:space:]]*=" "$_file" 2>/dev/null | tail -n 1)
  [ -n "$_line" ] || return 1
  echo "$_line" | sed 's/^[^=]*=[[:space:]]*//;s/[[:space:]]*;.*//;s/[[:space:]]*$//'
}


enc_to_onvif() {
  case "$1" in
    0) echo H264 ;;
    1) echo JPEG ;;
    2) echo H265 ;;
    *) echo H264 ;;
  esac
}


ensure_hw_settings() {
  dst="${STATE_DIR}/_ht_hw_settings.ini"
  src="/usr/local/_ht_hw_settings.ini"
  if [ -f "$dst" ]; then
    return 0
  fi
  if [ -f "$src" ]; then
    cp "$src" "$dst" || return 1
    log "Copied flash _ht_hw_settings.ini to state"
    return 0
  fi
  log "WARN missing _ht_hw_settings.ini"
  return 1
}


sync_onvif_from_hw_ini() {
  ini="${STATE_DIR}/_ht_hw_settings.ini"
  conf="${STATE_DIR}/onvif_simple_server.conf"
  if [ ! -f "$ini" ] || [ ! -f "$conf" ]; then
    log "WARN skip ONVIF profile sync"
    return 0
  fi

  mw=$(ht_ini_get "$ini" main_width) || mw=""
  mh=$(ht_ini_get "$ini" main_height) || mh=""
  mt=$(enc_to_onvif "$(ht_ini_get "$ini" main_enc_out_type)")
  sw=$(ht_ini_get "$ini" sub_width) || sw=""
  sh=$(ht_ini_get "$ini" sub_height) || sh=""
  st=$(enc_to_onvif "$(ht_ini_get "$ini" sub_enc_out_type)")

  if [ -z "$mw" ] || [ -z "$mh" ] || [ -z "$sw" ] || [ -z "$sh" ]; then
    log "WARN INI missing video size; skip ONVIF profile sync"
    return 0
  fi

  tmp="${conf}.tmp"
  awk -v mw="$mw" -v mh="$mh" -v mt="$mt" -v sw="$sw" -v sh="$sh" -v st="$st" '
    BEGIN { p = -1 }
    /^name=Profile_0/ { p = 0 }
    /^name=Profile_1/ { p = 1 }
    p == 0 && /^width=/ { print "width=" mw; next }
    p == 0 && /^height=/ { print "height=" mh; next }
    p == 0 && /^type=/ { print "type=" mt; next }
    p == 1 && /^width=/ { print "width=" sw; next }
    p == 1 && /^height=/ { print "height=" sh; next }
    p == 1 && /^type=/ { print "type=" st; next }
    { print }
  ' "$conf" > "$tmp" || return 1
  mv "$tmp" "$conf"
  log "ONVIF profiles from INI main=${mw}x${mh} ${mt} sub=${sw}x${sh} ${st}"
}


apply_overrides() {
  do_mount "${BIN_DIR}/busybox" /bin/busybox
  do_mount "${SCRIPTS_DIR}/anyka_ipc.sh" /usr/sbin/anyka_ipc.sh

  # Modified DB Files
  if [ -f "${DB_FILE_HACKED}" ]; then
    do_mount "${DB_FILE_HACKED}" /etc/config/tuya_user.db
    do_mount "${DB_KEY_HACKED}" /etc/config/tuya_enckey.db
  else
    do_mount "${DB_FILE_ORIGINAL}" /etc/config/tuya_user.db
    do_mount "${DB_KEY_ORIGINAL}" /etc/config/tuya_enckey.db
  fi

  ensure_hw_settings
  sync_onvif_from_hw_ini

  # Maybe tuned device settings
  do_mount "${STATE_DIR}/onvif_simple_server.conf" /usr/local/etc/onvif_simple_server.conf
  do_mount "${STATE_DIR}/lighttpd.conf" /usr/local/etc/lighttpd.conf
  if [ -f "${STATE_DIR}/_ht_hw_settings.ini" ]; then
    do_mount "${STATE_DIR}/_ht_hw_settings.ini" /usr/local/_ht_hw_settings.ini
  fi
  ensure_bind_service
  do_mount "${STATE_DIR}/_ht_sw_settings.ini" /etc/config/_ht_sw_settings.ini
  if [ -f "${STATE_DIR}/_ht_uuid.ini" ]; then
    do_mount "${STATE_DIR}/_ht_uuid.ini" /etc/config/_ht_uuid.ini
  fi

  ensure_shadow

  # Mute & replace sounds
  /bin/sh "${SCRIPTS_DIR}/sounds.sh" >/dev/null 2>&1

  sync
}

if [ "${STAGE_1_DONE}" != "1" ]; then
  log "Hack stage 1 not yet finished. Check logs for errors."
  exit 1
fi

apply_overrides
log "Hack Stage 2 done."