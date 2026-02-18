#!/bin/sh

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Usage:
#   build_ptzctl.sh [PROJECT_DIR] [OUT_FILE]

PROJECT_DIR="${1:-${ROOT_DIR}/ptzlib}"
OUT_FILE="${2:-${ROOT_DIR}/dist/ptzctl}"
STATIC_BUILD="${PTZCTL_STATIC:-1}"

pick_cc() {
    if [ -n "${PTZCTL_CC:-}" ]; then
        echo "${PTZCTL_CC}"
        return 0
    fi

    if [ -n "${CROSS_COMPILE:-}" ] && command -v "${CROSS_COMPILE}gcc" >/dev/null 2>&1; then
        echo "${CROSS_COMPILE}gcc"
        return 0
    fi

    for cc in arm-linux-gnueabi-gcc arm-linux-uclibcgnueabi-gcc arm-buildroot-linux-uclibcgnueabihf-gcc gcc; do
        if command -v "$cc" >/dev/null 2>&1; then
            echo "$cc"
            return 0
        fi
    done

    return 1
}

build_cflags() {
    if [ -n "${PTZCTL_CFLAGS:-}" ]; then
        echo "${PTZCTL_CFLAGS}"
        return 0
    fi

    CFLAGS="-Os -s"

    # keep old default: non-PIE (common on older toolchains/firmwares)
    if [ "${PTZCTL_NO_PIE:-1}" = "1" ]; then
        CFLAGS="${CFLAGS} -fno-pie"
    fi

    echo "${CFLAGS}"
}

build_ldflags() {
    if [ -n "${PTZCTL_LDFLAGS:-}" ]; then
        echo "${PTZCTL_LDFLAGS}"
        return 0
    fi

    LDFLAGS=""

    if [ "${STATIC_BUILD}" = "1" ]; then
        LDFLAGS="${LDFLAGS} -static"
    fi

    if [ "${PTZCTL_NO_PIE:-1}" = "1" ]; then
        LDFLAGS="${LDFLAGS} -no-pie"
    fi

    echo "${LDFLAGS}"
}

ensure_out_dir() {
    mkdir -p "$(dirname -- "${OUT_FILE}")"
}

verify_elf() {
    if command -v file >/dev/null 2>&1; then
        FILE_INFO="$(file "${OUT_FILE}")"
        echo "${FILE_INFO}"

        case "${FILE_INFO}" in
            *"ELF 32-bit"*"ARM"*)
                ;;
            *)
                echo "ERROR: built ptzctl is not an ARM 32-bit ELF binary." >&2
                echo "Set PTZCTL_CC or CROSS_COMPILE to your ARM toolchain." >&2
                exit 1
                ;;
        esac
    fi

    if command -v readelf >/dev/null 2>&1; then
        if [ "${STATIC_BUILD}" = "1" ]; then
            ELF_PROG_HEADERS="$(readelf -l "${OUT_FILE}" 2>/dev/null || true)"
            ELF_DYNAMIC="$(readelf -d "${OUT_FILE}" 2>/dev/null || true)"

            case "${ELF_PROG_HEADERS}" in
                *"Requesting program interpreter"*)
                    echo "ERROR: static build unexpectedly requests a dynamic loader." >&2
                    exit 1
                    ;;
            esac

            case "${ELF_DYNAMIC}" in
                *"(NEEDED)"*)
                    echo "ERROR: static build unexpectedly depends on shared libraries." >&2
                    exit 1
                    ;;
            esac
        fi
    fi
}

find_built_binary() {
    SRC_DIR="$1"

    # Preferred conventional locations
    if [ -x "${SRC_DIR}/ptzctl" ]; then
        echo "${SRC_DIR}/ptzctl"
        return 0
    fi
    if [ -x "${SRC_DIR}/bin/ptzctl" ]; then
        echo "${SRC_DIR}/bin/ptzctl"
        return 0
    fi

    # Fallback search
    FOUND="$(find "${SRC_DIR}" -maxdepth 3 -type f -name ptzctl -perm -111 2>/dev/null | head -n 1 || true)"
    if [ -n "${FOUND}" ]; then
        echo "${FOUND}"
        return 0
    fi

    return 1
}

build_directory() {
    SRC_DIR="${PROJECT_DIR}/src"

    if [ ! -d "${SRC_DIR}" ]; then
        echo "Source directory not found: ${SRC_DIR}" >&2
        exit 1
    fi
    if [ ! -f "${PROJECT_DIR}/Makefile" ] && [ ! -f "${PROJECT_DIR}/makefile" ]; then
        echo "No Makefile found in: ${PROJECT_DIR}" >&2
        exit 1
    fi

    CC_BIN="$(pick_cc || true)"
    if [ -z "${CC_BIN}" ]; then
        echo "No compiler found. Set PTZCTL_CC or CROSS_COMPILE." >&2
        exit 1
    fi

    CFLAGS="$(build_cflags)"
    LDFLAGS="$(build_ldflags)"

    echo "Building (directory) in: ${PROJECT_DIR}"
    echo "CC:      ${CC_BIN}"
    echo "CFLAGS:  ${CFLAGS}"
    echo "LDFLAGS: ${LDFLAGS}"

    make -C "${PROJECT_DIR}" \
        CC="${CC_BIN}" \
        CFLAGS="${CFLAGS}" \
        LDFLAGS="${LDFLAGS}" \
        PTZCTL_STATIC="${STATIC_BUILD}" \
        PTZCTL_NO_PIE="${PTZCTL_NO_PIE:-1}"

    BUILT_BIN="$(find_built_binary "${PROJECT_DIR}" || true)"
    if [ -z "${BUILT_BIN}" ]; then
        echo "Build succeeded but couldn't locate the built 'ptzctl' executable under: ${PROJECT_DIR}" >&2
        echo "Expected: ${PROJECT_DIR}/ptzctl or ${PROJECT_DIR}/bin/ptzctl" >&2
        exit 1
    fi

    ensure_out_dir
    cp -f "${BUILT_BIN}" "${OUT_FILE}"
    chmod +x "${OUT_FILE}"
}

build_directory
echo "Built: ${OUT_FILE}"
verify_elf
