#!/bin/sh

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DOCKER_DIR="${ROOT_DIR}/docker"

IMAGE_NAME="anyka-arm-builder:latest"
CONTAINER_NAME="anyka-arm-build"

echo "Building docker image: ${IMAGE_NAME}"
docker build --build-context="project=${ROOT_DIR}" -f "${DOCKER_DIR}/arm-builder.Dockerfile" -t "${IMAGE_NAME}" "${DOCKER_DIR}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

echo "Creating isolated build container: ${CONTAINER_NAME}"
CID="$(docker create --name "${CONTAINER_NAME}" "${IMAGE_NAME}" sleep infinity)"

cleanup() {
    docker rm -f "${CID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "Starting container and building binaries"
docker start "${CID}" >/dev/null
docker exec "${CID}" /work/build_ptzctl.sh

echo "Copying build artifacts back"
docker cp "${CID}:/work/dist/ptzctl" "${ROOT_DIR}/sd_card/custom/bin/ptzctl"

echo "Done. Artifacts:"
file "${ROOT_DIR}/sd_card/custom/bin/ptzctl"

docker stop "${CID}"
docker rm "${CID}"