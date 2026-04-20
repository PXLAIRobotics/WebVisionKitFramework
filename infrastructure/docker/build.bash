#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DOCKERFILE_RELATIVE="infrastructure/docker/Dockerfile"
DOCKERFILE_PATH="${ROOT_DIR}/${DOCKERFILE_RELATIVE}"
IMAGE_NAME="${IMAGE_NAME:-chromium-opencv-stream}"

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

detect_hash_tool() {
  if command_exists "sha256sum"; then
    printf '%s\n' "sha256sum"
    return 0
  fi
  if command_exists "shasum"; then
    printf '%s\n' "shasum"
    return 0
  fi
  return 1
}

hash_file_sha256() {
  local path="$1"
  local tool

  tool="$(detect_hash_tool)" || {
    echo "[error] No SHA-256 tool is available. Install sha256sum or shasum before building the image." >&2
    exit 1
  }

  if [[ "${tool}" == "sha256sum" ]]; then
    sha256sum "${path}" | awk '{print $1}'
    return 0
  fi

  shasum -a 256 "${path}" | awk '{print $1}'
}

compute_source_hash() {
  (
    cd "${ROOT_DIR}"
    {
      printf '%s\n' "${DOCKERFILE_RELATIVE}"
      find "api/webvisionkit" -type f ! -path '*/__pycache__/*' | LC_ALL=C sort
    } | while IFS= read -r path; do
      hash_file_sha256 "${path}"
    done | hash_file_sha256 "/dev/stdin"
  ) | hash_file_sha256 "/dev/stdin"
}

SOURCE_HASH="$(compute_source_hash)"

echo "[info] Building ${IMAGE_NAME} with source hash ${SOURCE_HASH}"

if ! command_exists "docker"; then
  echo "[error] docker is required to build ${IMAGE_NAME}." >&2
  exit 1
fi

docker build \
  --build-arg "SOURCE_HASH=${SOURCE_HASH}" \
  -f "${DOCKERFILE_PATH}" \
  -t "${IMAGE_NAME}" \
  "${ROOT_DIR}"
