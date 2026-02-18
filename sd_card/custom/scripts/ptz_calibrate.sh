#!/bin/sh

set -eu

PTZ_TEST="${PTZ_TEST:-/tmp/sd/custom/scripts/ptz_test.sh}"
PTZCTL="${PTZCTL:-/tmp/sd/custom/bin/ptzctl}"
CONF="${CONF:-/tmp/sd/custom/configs/onvif.conf}"
LOG_FILE="${LOG_FILE:-/tmp/sd/logs/ptz.log}"

LOW_SPEED="${LOW_SPEED:-0.35}"
HIGH_SPEED="${HIGH_SPEED:-0.85}"
MOVE_SECONDS="${MOVE_SECONDS:-1}"
PAUSE_SECONDS="${PAUSE_SECONDS:-1}"

run_step() {
    label="$1"
    shift
    echo "== ${label} =="
    "$@"
    "$PTZ_TEST" pos || true
}

if [ ! -x "${PTZ_TEST}" ]; then
    echo "missing executable test helper: ${PTZ_TEST}" >&2
    exit 1
fi

if [ ! -x "${PTZCTL}" ]; then
    echo "missing executable ptzctl: ${PTZCTL}" >&2
    exit 1
fi

echo "PTZ calibration run"
echo "conf=${CONF}"
echo "log=${LOG_FILE}"
echo "move=${MOVE_SECONDS}s pause=${PAUSE_SECONDS}s"
echo "low_speed=${LOW_SPEED} high_speed=${HIGH_SPEED}"

run_step "center/home" "$PTZ_TEST" home

run_step "tilt check (UP)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir up "${LOW_SPEED}"
run_step "tilt check (DOWN)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir down "${LOW_SPEED}"

run_step "pan check (LEFT)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir left "${LOW_SPEED}"
run_step "pan check (RIGHT)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir right "${LOW_SPEED}"

run_step "tilt magnitude (UP high)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir up "${HIGH_SPEED}"
run_step "tilt magnitude (DOWN high)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir down "${HIGH_SPEED}"

run_step "pan magnitude (LEFT high)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir left "${HIGH_SPEED}"
run_step "pan magnitude (RIGHT high)" env MOVE_SECONDS="${MOVE_SECONDS}" PAUSE_SECONDS="${PAUSE_SECONDS}" "$PTZ_TEST" dir right "${HIGH_SPEED}"

echo "Calibration sequence complete."
echo "If tilt direction is reversed, set TILT_INVERT=1 in ${CONF}."
echo "If pan direction is reversed, set PAN_INVERT=1 in ${CONF}."

if [ -f "${LOG_FILE}" ]; then
    echo "Recent PTZ log lines:"
    tail -n 40 "${LOG_FILE}" || true
fi
