#!/bin/sh
# Rebuild the ARM latch. End users run the committed sd_card/custom/bin/mqtt_latch.
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SRC="${ROOT_DIR}/latch/mqtt_latch.c"
OUTPUT_DIR="${LATCH_OUTPUT_DIR:-${ROOT_DIR}/sd_card/custom/bin}"
OUT="${OUTPUT_DIR}/mqtt_latch"
NOBIND_SRC="${ROOT_DIR}/latch/nobind.c"
NOBIND_OUT="${OUTPUT_DIR}/libnobind.so"
MBEDTLS_VER="${MBEDTLS_VER:-3.6.2}"
CACHE="${LATCH_CACHE_DIR:-${ROOT_DIR}/latch/.cache}"

pick_cc() {
    if [ -n "${LATCH_CC:-}" ]; then
        echo "${LATCH_CC}"
        return 0
    fi
    for cc in arm-linux-gnueabi-gcc arm-linux-uclibcgnueabi-gcc arm-linux-gnueabihf-gcc; do
        if command -v "$cc" >/dev/null 2>&1; then
            echo "$cc"
            return 0
        fi
    done
    return 1
}

build_with_cc() {
    CC_BIN="$1"
    PREFIX="${CACHE}/mbedtls-${MBEDTLS_VER}-arm"
    TAR="${CACHE}/mbedtls-${MBEDTLS_VER}.tar.bz2"
    SRC_DIR="${CACHE}/mbedtls-${MBEDTLS_VER}"

    mkdir -p "${CACHE}"
    if [ ! -f "${TAR}" ]; then
        curl -fsSL -o "${TAR}" "https://github.com/Mbed-TLS/mbedtls/releases/download/mbedtls-${MBEDTLS_VER}/mbedtls-${MBEDTLS_VER}.tar.bz2"
    fi
    if [ ! -d "${SRC_DIR}" ]; then
        tar -C "${CACHE}" -xf "${TAR}"
    fi
    if [ ! -f "${PREFIX}/lib/libmbedtls.a" ]; then
        cmake -S "${SRC_DIR}" -B "${CACHE}/mbedtls-build" \
            -DCMAKE_SYSTEM_NAME=Linux \
            -DCMAKE_C_COMPILER="${CC_BIN}" \
            -DCMAKE_BUILD_TYPE=MinSizeRel \
            -DCMAKE_C_FLAGS="-Os" \
            -DCMAKE_INSTALL_PREFIX="${PREFIX}" \
            -DENABLE_PROGRAMS=OFF \
            -DENABLE_TESTING=OFF \
            -DUSE_SHARED_MBEDTLS_LIBRARY=OFF
        cmake --build "${CACHE}/mbedtls-build" -j"$(nproc)"
        cmake --install "${CACHE}/mbedtls-build"
    fi

    mkdir -p "$(dirname "${OUT}")"
    "${CC_BIN}" -Os -s -static -fno-pie -no-pie \
        -I"${PREFIX}/include" \
        "${SRC}" \
        "${PREFIX}/lib/libmbedtls.a" \
        "${PREFIX}/lib/libmbedx509.a" \
        "${PREFIX}/lib/libmbedcrypto.a" \
        -o "${OUT}"
    chmod +x "${OUT}"

    # No libc at link time: the camera runs uClibc, this toolchain ships glibc.
    "${CC_BIN}" -Os -s -shared -fPIC -nostdlib -marm \
        -Wl,--hash-style=sysv -Wl,--allow-shlib-undefined \
        "${NOBIND_SRC}" -o "${NOBIND_OUT}"
}

verify_elf() {
    FILE_INFO="$(file "${OUT}")"
    echo "${FILE_INFO}"
    case "${FILE_INFO}" in
        *"ELF 32-bit"*"ARM"*) ;;
        *)
            echo "ERROR: ${OUT} is not an ARM 32-bit ELF" >&2
            exit 1
            ;;
    esac
    if readelf -l "${OUT}" 2>/dev/null | grep -q "Requesting program interpreter"; then
        echo "ERROR: latch is not static" >&2
        exit 1
    fi
}

if [ "${LATCH_INNER:-}" != "1" ]; then
    if ! pick_cc >/dev/null 2>&1; then
        mkdir -p "${OUTPUT_DIR}" "${CACHE}"
        OUTPUT_DIR="$(CDPATH= cd -- "${OUTPUT_DIR}" && pwd)"
        CACHE="$(CDPATH= cd -- "${CACHE}" && pwd)"
        docker build -t tuyha-latch-builder -f "${ROOT_DIR}/Dockerfile" "${ROOT_DIR}/latch"
        exec docker run --rm \
            --user "$(id -u):$(id -g)" \
            -v "${OUTPUT_DIR}:/out" -v "${CACHE}:/cache" \
            -e MBEDTLS_VER="${MBEDTLS_VER}" \
            -e LATCH_OUTPUT_DIR=/out -e LATCH_CACHE_DIR=/cache \
            tuyha-latch-builder
    fi
fi

CC_BIN="$(pick_cc)"
build_with_cc "${CC_BIN}"
verify_elf
echo "Built: ${OUT}"
