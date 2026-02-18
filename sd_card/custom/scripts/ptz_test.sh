#!/bin/sh

set -eu

PTZCTL="${PTZCTL:-/tmp/sd/custom/bin/ptzctl}"
CONF="${CONF:-/tmp/sd/custom/configs/onvif.conf}"
LOG_FILE="${LOG_FILE:-/tmp/sd/logs/ptz.log}"

DEFAULT_SPEED="${DEFAULT_SPEED:-0.60}"
MOVE_SECONDS="${MOVE_SECONDS:-1}"
PAUSE_SECONDS="${PAUSE_SECONDS:-1}"
SWEEP_SPEEDS="${SWEEP_SPEEDS:-0.25 0.50 0.75 0.95}"

usage() {
    cat <<'EOF'
Usage: /tmp/sd/custom/scripts/ptz_test.sh [command] [args]

Commands:
  smoke                    one quick pass: up/down/left/right
  sweep                    test all directions at multiple speeds
  calibrate                run guided low/high-speed calibration pattern
  tilt-probe               direct tilt motor probe using motor helper
  dir <direction> [speed]  move one direction (left|right|up|down)
  stop                     send stop
  home                     send home
  pos                      print current position
  log [lines]              show last lines from ptz log (default: 40)
  raw ...                  pass args directly to ptzctl

Environment overrides:
  PTZCTL, CONF, LOG_FILE
  DEFAULT_SPEED, MOVE_SECONDS, PAUSE_SECONDS, SWEEP_SPEEDS
EOF
}

need_ptzctl() {
    if [ ! -x "${PTZCTL}" ]; then
        echo "ptzctl not executable: ${PTZCTL}" >&2
        exit 1
    fi
}

run_ptz() {
    "${PTZCTL}" -c "${CONF}" "$@"
}

run_move() {
    direction="$1"
    speed="$2"
    run_ptz -m "${direction}" -s "${speed}"
    sleep "${MOVE_SECONDS}"
    run_ptz -m stop
    sleep "${PAUSE_SECONDS}"
}

smoke_test() {
    speed="$1"
    echo "smoke speed=${speed} move=${MOVE_SECONDS}s pause=${PAUSE_SECONDS}s"
    run_move up "${speed}"
    run_move down "${speed}"
    run_move left "${speed}"
    run_move right "${speed}"
    run_ptz --get-position
}

sweep_test() {
    for speed in ${SWEEP_SPEEDS}; do
        echo "sweep speed=${speed}"
        run_move up "${speed}"
        run_move down "${speed}"
        run_move left "${speed}"
        run_move right "${speed}"
    done
    run_ptz --get-position
}

cmd="${1:-smoke}"
case "${cmd}" in
    -h|--help|help)
        usage
        ;;
    smoke)
        need_ptzctl
        speed="${2:-${DEFAULT_SPEED}}"
        smoke_test "${speed}"
        ;;
    sweep)
        need_ptzctl
        sweep_test
        ;;
    calibrate)
        exec /tmp/sd/custom/scripts/ptz_calibrate.sh
        ;;
    tilt-probe)
        exec /tmp/sd/custom/scripts/ptz_tilt_probe.sh
        ;;
    dir)
        need_ptzctl
        direction="${2:-}"
        speed="${3:-${DEFAULT_SPEED}}"
        if [ -z "${direction}" ]; then
            echo "missing direction" >&2
            usage
            exit 1
        fi
        case "${direction}" in
            left|right|up|down)
                run_move "${direction}" "${speed}"
                ;;
            *)
                echo "invalid direction: ${direction}" >&2
                exit 1
                ;;
        esac
        ;;
    stop)
        need_ptzctl
        run_ptz -m stop
        ;;
    home)
        need_ptzctl
        run_ptz -h
        ;;
    pos)
        need_ptzctl
        run_ptz --get-position
        ;;
    log)
        lines="${2:-40}"
        if [ -f "${LOG_FILE}" ]; then
            tail -n "${lines}" "${LOG_FILE}"
        else
            echo "log file not found: ${LOG_FILE}" >&2
            exit 1
        fi
        ;;
    raw)
        need_ptzctl
        shift
        run_ptz "$@"
        ;;
    *)
        echo "unknown command: ${cmd}" >&2
        usage
        exit 1
        ;;
esac
