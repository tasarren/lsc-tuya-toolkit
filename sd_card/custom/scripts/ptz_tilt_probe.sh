#!/bin/sh

set -eu

CONF="${CONF:-/tmp/sd/custom/configs/onvif.conf}"
MOTOR_BIN="${MOTOR_BIN:-/tmp/sd/custom/bin/motor}"
ANYKA_PROC="${ANYKA_PROC:-anyka_ipc}"
TILT_ADDR="${TILT_ADDR:-}"
IOCTL_MOVE="${IOCTL_MOVE:-}"
IOCTL_STOP="${IOCTL_STOP:-}"
IOCTL_SET_SPEED="${IOCTL_SET_SPEED:-}"
TILT_SPEED_STEP="${TILT_SPEED_STEP:-}"
COUNT="${COUNT:-8}"
PAUSE_SECONDS="${PAUSE_SECONDS:-1}"
STEPS="${STEPS:--64 64 -128 128 -256 256 -512 512}"
USE_STOP="${USE_STOP:-0}"

read_conf() {
    key="$1"
    if [ ! -f "${CONF}" ]; then
        return 1
    fi
    awk -F= -v k="${key}" '$1==k {v=$2} END{if(v!="") print v}' "${CONF}"
}

if [ -z "${TILT_ADDR}" ]; then
    TILT_ADDR="$(read_conf TILT_FD_ADDR || true)"
fi
if [ -z "${IOCTL_MOVE}" ]; then
    IOCTL_MOVE="$(read_conf IOCTL_MOVE || true)"
fi
if [ -z "${IOCTL_STOP}" ]; then
    IOCTL_STOP="$(read_conf IOCTL_STOP || true)"
fi
if [ -z "${IOCTL_SET_SPEED}" ]; then
    IOCTL_SET_SPEED="$(read_conf IOCTL_SET_SPEED || true)"
fi
if [ -z "${TILT_SPEED_STEP}" ]; then
    TILT_SPEED_STEP="$(read_conf TILT_SPEED_STEP || true)"
fi

if [ -z "${TILT_ADDR}" ]; then
    TILT_ADDR="0x5377d0"
fi
if [ -z "${IOCTL_MOVE}" ]; then
    IOCTL_MOVE="0x40046d40"
fi
if [ -z "${IOCTL_STOP}" ]; then
    IOCTL_STOP="0x40046d41"
fi
if [ -z "${IOCTL_SET_SPEED}" ]; then
    IOCTL_SET_SPEED="0x40046d20"
fi

if [ ! -x "${MOTOR_BIN}" ]; then
    echo "motor binary not executable: ${MOTOR_BIN}" >&2
    exit 1
fi

find_pid() {
    for d in /proc/[0-9]*; do
        [ -r "${d}/comm" ] || continue
        name="$(cat "${d}/comm" 2>/dev/null || true)"
        if [ "${name}" = "${ANYKA_PROC}" ]; then
            basename "${d}"
            return 0
        fi
    done
    return 1
}

to_u32_hex() {
    n="$1"
    if [ "${n}" -lt 0 ]; then
        printf "0x%08x" $(( (n + 4294967296) & 4294967295 ))
    else
        printf "0x%08x" "$n"
    fi
}

PID="$(find_pid || true)"
if [ -z "${PID}" ]; then
    echo "could not find process: ${ANYKA_PROC}" >&2
    exit 1
fi

echo "Tilt probe"
echo "pid=${PID} proc=${ANYKA_PROC}"
echo "addr=${TILT_ADDR} move=${IOCTL_MOVE} stop=${IOCTL_STOP} set_speed=${IOCTL_SET_SPEED} count=${COUNT} pause=${PAUSE_SECONDS}s use_stop=${USE_STOP}"
echo "steps=${STEPS}"
if [ -n "${TILT_SPEED_STEP}" ]; then
    echo "tilt_speed_step=${TILT_SPEED_STEP}"
fi
echo
echo "Watch camera physically and note which step signs move UP vs DOWN."
echo

if [ -n "${TILT_SPEED_STEP}" ]; then
    speed_hex="$(to_u32_hex "${TILT_SPEED_STEP}")"
    echo "--- set speed step=${TILT_SPEED_STEP} value=${speed_hex} ---"
    "${MOTOR_BIN}" "${PID}" "${TILT_ADDR}" "${IOCTL_SET_SPEED}" "${speed_hex}" "1" || true
    sleep "${PAUSE_SECONDS}"
fi

for step in ${STEPS}; do
    value="$(to_u32_hex "${step}")"
    echo "--- step=${step} value=${value} ---"
    "${MOTOR_BIN}" "${PID}" "${TILT_ADDR}" "${IOCTL_MOVE}" "${value}" "${COUNT}" || true
    if [ "${USE_STOP}" = "1" ]; then
        "${MOTOR_BIN}" "${PID}" "${TILT_ADDR}" "${IOCTL_STOP}" "0x00000000" "1" || true
    fi
    sleep "${PAUSE_SECONDS}"
done

echo
echo "Done. If only larger steps move, increase TILT_STEP_REPEAT and/or TILT_STEP_MULT in ${CONF}."
