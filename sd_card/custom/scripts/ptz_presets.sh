#!/bin/sh

STATE_DIR="/tmp/sd/custom/state"
PRESETS_DB="${STATE_DIR}/ptz_presets.db"
POS_FILE="${STATE_DIR}/ptz_position"

mkdir -p "${STATE_DIR}" >/dev/null 2>&1 || true
[ -f "${PRESETS_DB}" ] || : > "${PRESETS_DB}"
[ -f "${POS_FILE}" ] || echo "180,98,0" > "${POS_FILE}"

ACTION=""
NAME=""
ID=""

while [ $# -gt 0 ]; do
    case "$1" in
        -a) ACTION="$2"; shift 2 ;;
        -m) NAME="$2"; shift 2 ;;
        -n) ID="$2"; shift 2 ;;
        *) shift 1 ;;
    esac
done

next_id() {
    if [ ! -s "${PRESETS_DB}" ]; then
        echo "1"
        return
    fi
    awk -F, 'BEGIN{m=0} {if ($1+0>m) m=$1+0} END{print m+1}' "${PRESETS_DB}"
}

case "$ACTION" in
    add_preset)
        [ -z "${NAME}" ] && NAME="Preset"
        CUR="$(cat "${POS_FILE}" 2>/dev/null || echo "180,98,0")"
        X="$(echo "${CUR}" | awk -F, '{print $1}')"
        Y="$(echo "${CUR}" | awk -F, '{print $2}')"
        Z="$(echo "${CUR}" | awk -F, '{print $3}')"
        NID="$(next_id)"
        echo "${NID},${NAME},${X},${Y},${Z}" >> "${PRESETS_DB}"
        echo "${NID}"
        ;;
    del_preset)
        if [ -n "${ID}" ]; then
            grep -Ev "^${ID}," "${PRESETS_DB}" > "${PRESETS_DB}.tmp" 2>/dev/null || true
            mv "${PRESETS_DB}.tmp" "${PRESETS_DB}"
        fi
        echo "OK"
        ;;
    set_home_position)
        cp "${POS_FILE}" "${STATE_DIR}/ptz_home" 2>/dev/null || true
        echo "OK"
        ;;
    get_presets)
        cat "${PRESETS_DB}"
        ;;
    *)
        echo ""
        ;;
esac
