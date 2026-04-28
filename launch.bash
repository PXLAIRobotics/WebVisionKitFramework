#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/infrastructure/docker"
DOCKER_BUILD_SCRIPT="${DOCKER_DIR}/build.bash"
DOCKERFILE_RELATIVE="infrastructure/docker/Dockerfile"

IMAGE_NAME="${IMAGE_NAME:-chromium-opencv-stream}"
CHROME_APP="${CHROME_APP:-}"
WSL_CHROME_BACKEND="${WSL_CHROME_BACKEND:-auto}"
CHROME_PORT="${CHROME_PORT:-9222}"
CHROME_PROFILE_DIR_RAW="${CHROME_PROFILE_DIR:-}"
CHROME_PROFILE_DIR=""
CHROME_REMOTE_ALLOW_ORIGINS="${CHROME_REMOTE_ALLOW_ORIGINS:-*}"
CHROME_VERSION_URL="${CHROME_VERSION_URL:-http://127.0.0.1:${CHROME_PORT}/json/version}"
CHROME_LIST_URL="${CHROME_LIST_URL:-http://127.0.0.1:${CHROME_PORT}/json}"
CHROME_HOST_IN_CONTAINER_RAW="${CHROME_HOST_IN_CONTAINER:-}"
CHROME_HOST_IN_CONTAINER="${CHROME_HOST_IN_CONTAINER_RAW:-host.docker.internal}"
CHROME_STARTUP_RETRIES="${CHROME_STARTUP_RETRIES:-30}"
CHROME_STARTUP_DELAY_SECONDS="${CHROME_STARTUP_DELAY_SECONDS:-1}"
CHROME_HTTP_CONNECT_TIMEOUT_SECONDS="${CHROME_HTTP_CONNECT_TIMEOUT_SECONDS:-1}"
CHROME_HTTP_MAX_TIME_SECONDS="${CHROME_HTTP_MAX_TIME_SECONDS:-2}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
GAMES_DIR="${GAMES_DIR:-${SCRIPT_DIR}/games}"
APPS_DIR="${APPS_DIR:-${SCRIPT_DIR}/apps}"
APPS_DIR_IN_CONTAINER="${APPS_DIR_IN_CONTAINER:-/workspace/apps}"
APP_NAME="${APP_NAME:-}"
APP_DEFAULT_TARGET_URL="${APP_DEFAULT_TARGET_URL:-}"
TARGET_URL_OVERRIDE="${TARGET_URL_OVERRIDE:-}"
TARGET_URL_OVERRIDE_INPUT="${TARGET_URL_OVERRIDE}"
TARGET_MATCH="${TARGET_MATCH:-}"
TARGET_CLOSE_ACTION="${TARGET_CLOSE_ACTION:-exit}"
STARTUP_TARGET_MODE="${STARTUP_TARGET_MODE:-new-target}"
OUTPUT_DIR_RAW="${OUTPUT_DIR:-}"
SCREENSHOT_DIR_RAW="${SCREENSHOT_DIR:-}"
SAVE_INTERVAL_SECONDS="${SAVE_INTERVAL_SECONDS:-10}"

FRAME_FORMAT="${FRAME_FORMAT:-jpeg}"
FRAME_QUALITY="${FRAME_QUALITY:-70}"
EVERY_NTH_FRAME="${EVERY_NTH_FRAME:-1}"
MAX_WIDTH="${MAX_WIDTH:-1280}"
MAX_HEIGHT="${MAX_HEIGHT:-720}"
LIVE_PREVIEW="${LIVE_PREVIEW:-0}"
VIDEO_OUTPUT="${VIDEO_OUTPUT:-}"
METADATA_OUTPUT="${METADATA_OUTPUT:-}"
PROCESSORS="${PROCESSORS:-}"
RECONNECT_ATTEMPTS="${RECONNECT_ATTEMPTS:-10}"
RECONNECT_DELAY_SECONDS="${RECONNECT_DELAY_SECONDS:-2}"
RECEIVE_TIMEOUT_SECONDS="${RECEIVE_TIMEOUT_SECONDS:-5}"
IDLE_TIMEOUT_SECONDS="${IDLE_TIMEOUT_SECONDS:-20}"
LOG_INTERVAL_SECONDS="${LOG_INTERVAL_SECONDS:-1}"
VIDEO_FPS="${VIDEO_FPS:-12}"
MAX_FRAMES="${MAX_FRAMES:-0}"
ACTION_MODE="${ACTION_MODE:-auto}"
ACTION_DEFAULT_COOLDOWN_MS="${ACTION_DEFAULT_COOLDOWN_MS:-250}"
ACTION_MAX_PER_FRAME="${ACTION_MAX_PER_FRAME:-0}"
ACTION_DRAG_STEP_COUNT="${ACTION_DRAG_STEP_COUNT:-8}"
ACTION_DRAG_STEP_DELAY_MS="${ACTION_DRAG_STEP_DELAY_MS:-16}"
DOCKER_EXTRA_ARGS="${DOCKER_EXTRA_ARGS:-}"
DOCKER_RUN_USER_MODE="${DOCKER_RUN_USER_MODE:-auto}"
SMOKE_MAX_FRAMES="${SMOKE_MAX_FRAMES:-6}"
SMOKE_EXTERNAL_MAX_FRAMES="${SMOKE_EXTERNAL_MAX_FRAMES:-1}"
SMOKE_INTERACTION_MAX_FRAMES="${SMOKE_INTERACTION_MAX_FRAMES:-40}"
SMOKE_EXTERNAL_URL="${SMOKE_EXTERNAL_URL:-https://example.com}"
SMOKE_OUTPUT_DIR_RAW="${SMOKE_OUTPUT_DIR:-}"

GAME_SLUGS=()
APP_NAMES=()
SELECTED_APP_NAME=""
APP_INSPECTION_JSON=""
APP_DEFAULT_START_TARGET=""
APP_DEFAULT_START_FPS=""
RESOLVED_APP_DEFAULT_TARGET=""
SELECTED_TARGET_OVERRIDE=""
SELECTED_EFFECTIVE_TARGET=""
TARGET_SELECTION_MODE="app-default"
TARGET_SELECTION_LABEL="app default"
TARGET_SELECTION_VALUE=""
INTERRUPTED=0
DOCKER_TTY_ARGS=()
HOST_OUTPUT_DIR=""
HOST_SCREENSHOT_DIR=""
SCREENSHOT_SUBPATH="screenshots"
CONTAINER_OUTPUT_DIR="/data/output"
CONTAINER_SAVE_DIR=""
DOCKER_HOST_ARGS=()
WSL_CHROME_LAUNCH_BACKEND=""
WSL_CHROME_LAST_ERROR=""
CHROME_PROFILE_KIND="unresolved"
WSL_HOST_ROUTE_MODE="default"
POWERSHELL_LAST_ERROR=""
WSL_HOST_ROUTE_TRIED=""
WSL_WINDOWS_CHROME_PATH=""
HOST_DEVTOOLS_SOURCE_LABEL="${CHROME_VERSION_URL}"
HOST_BROWSER_WS_URL_OVERRIDE=""
HOST_DEVTOOLS_VERSION_JSON=""
COMMAND="up"
LAUNCH_POSITIONAL_ARGS=()

stop_with_interrupt() {
  if [[ "${INTERRUPTED}" != "1" ]]; then
    INTERRUPTED=1
    echo
    echo "[info] Stopping."
  fi
  exit 130
}

trap stop_with_interrupt INT TERM

error_exit() {
  echo "[error] $*" >&2
  exit 1
}

validate_wsl_chrome_backend_value() {
  case "${WSL_CHROME_BACKEND}" in
    auto | linux | windows)
      return 0
      ;;
    *)
      error_exit "Invalid --chrome-backend value '${WSL_CHROME_BACKEND}'. Valid values are: auto, linux, windows."
      ;;
  esac
}

parse_launch_args() {
  local arg
  local command_seen=0

  COMMAND="up"
  LAUNCH_POSITIONAL_ARGS=()

  while [[ "$#" -gt 0 ]]; do
    arg="$1"
    case "${arg}" in
      --chrome-backend)
        shift
        if [[ "$#" -eq 0 ]]; then
          error_exit "--chrome-backend requires a value: auto, linux, or windows."
        fi
        WSL_CHROME_BACKEND="$1"
        ;;
      --chrome-backend=*)
        WSL_CHROME_BACKEND="${arg#--chrome-backend=}"
        ;;
      --help | -h)
        if [[ "${command_seen}" == "0" ]]; then
          COMMAND="${arg}"
          command_seen=1
        else
          LAUNCH_POSITIONAL_ARGS+=( "${arg}" )
        fi
        ;;
      --*)
        error_exit "Unknown option: ${arg}"
        ;;
      *)
        if [[ "${command_seen}" == "0" ]]; then
          COMMAND="${arg}"
          command_seen=1
        else
          LAUNCH_POSITIONAL_ARGS+=( "${arg}" )
        fi
        ;;
    esac
    shift
  done

  validate_wsl_chrome_backend_value
}

print_usage() {
  cat <<'EOF'
Usage:
  ./launch.bash [up] [--chrome-backend auto|linux|windows]
  ./launch.bash chrome [--chrome-backend auto|linux|windows]
  ./launch.bash doctor [--chrome-backend auto|linux|windows]
  ./launch.bash smoke [--chrome-backend auto|linux|windows]
  ./launch.bash container [--chrome-backend auto|linux|windows]
  ./launch.bash help

Commands:
  up         Run the full launcher flow: build/reuse the image, choose a target and app, ensure Chrome, then run the container.
  chrome     Start or reuse Google Chrome with DevTools remote debugging enabled.
  doctor     Run prerequisite and connectivity checks for Docker, Chrome, and the DevTools endpoint.
  smoke      Run bounded non-interactive smoke checks against one local target, one external target, and one dry-run action flow.
  container  Run the Docker container directly using the current environment variables.
  help       Show this help text.

Options:
  --chrome-backend VALUE
             WSL-only Chrome backend selection: auto, linux, or windows.
             auto keeps the default Windows-first behavior.

Examples:
  ./launch.bash
  ./launch.bash doctor
  ./launch.bash doctor --chrome-backend linux
  ./launch.bash smoke
  APP_NAME=screenshot_capture TARGET_URL_OVERRIDE=game://input-lab ./launch.bash
  ./launch.bash chrome
  APP_NAME=screenshot_capture ./launch.bash container
  ./infrastructure/docker/build.bash
EOF
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_command() {
  local command_name="$1"
  local remediation="$2"
  if command_exists "${command_name}"; then
    return 0
  fi
  error_exit "${command_name} is required. ${remediation}"
}

trim_carriage_return() {
  local value="$1"
  value="${value%$'\r'}"
  printf '%s\n' "${value}"
}

powershell_quote_literal() {
  local value="$1"
  value="${value//\'/\'\'}"
  printf '%s\n' "${value}"
}

windows_path_to_file_url() {
  local windows_path="$1"
  local normalized

  windows_path="$(trim_carriage_return "${windows_path}")"
  if [[ -z "${windows_path}" ]]; then
    printf '\n'
    return 0
  fi

  if [[ "${windows_path}" == \\\\* ]]; then
    normalized="${windows_path#\\\\}"
    normalized="${normalized//\\//}"
    printf 'file://%s\n' "${normalized}"
    return 0
  fi

  normalized="${windows_path//\\//}"
  printf 'file:///%s\n' "${normalized}"
}

normalize_target_url_for_wsl_windows_chrome() {
  local raw_url="$1"
  local wsl_path
  local windows_path

  if [[ -z "${raw_url}" ]]; then
    printf '\n'
    return 0
  fi

  if ! is_wsl || [[ "${WSL_CHROME_LAUNCH_BACKEND:-}" != "wsl-windows" ]]; then
    printf '%s\n' "${raw_url}"
    return 0
  fi

  if [[ "${raw_url}" != file://* ]]; then
    printf '%s\n' "${raw_url}"
    return 0
  fi

  wsl_path="${raw_url#file://}"
  if [[ "${wsl_path}" != /* ]]; then
    printf '%s\n' "${raw_url}"
    return 0
  fi

  if ! command_exists "wslpath"; then
    printf '%s\n' "${raw_url}"
    return 0
  fi

  if ! windows_path="$(wslpath -w "${wsl_path}" 2>/dev/null)"; then
    printf '%s\n' "${raw_url}"
    return 0
  fi

  windows_path="$(trim_carriage_return "${windows_path}")"
  if [[ -z "${windows_path}" ]]; then
    printf '%s\n' "${raw_url}"
    return 0
  fi

  windows_path_to_file_url "${windows_path}"
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

ensure_hash_tool() {
  if detect_hash_tool >/dev/null 2>&1; then
    return 0
  fi
  error_exit "No SHA-256 tool is available. Install sha256sum or shasum before running WebVisionKit."
}

hash_file_sha256() {
  local path="$1"
  local tool

  tool="$(detect_hash_tool)" || error_exit "No SHA-256 tool is available. Install sha256sum or shasum before running WebVisionKit."

  if [[ "${tool}" == "sha256sum" ]]; then
    sha256sum "${path}" | awk '{print $1}'
    return 0
  fi

  shasum -a 256 "${path}" | awk '{print $1}'
}

json_extract_string_field() {
  local json="$1"
  local key="$2"

  printf '%s\n' "${json}" | sed -nE "s/.*\"${key}\":[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\".*/\\1/p" | head -n 1
}

json_extract_number_field() {
  local json="$1"
  local key="$2"

  printf '%s\n' "${json}" | sed -nE "s/.*\"${key}\":[[:space:]]*([-0-9.]+).*/\\1/p" | head -n 1
}

is_wsl() {
  [[ "$(uname -s)" == "Linux" ]] && { [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null; }
}

is_wsl2() {
  is_wsl && uname -r | grep -qi 'wsl2'
}

is_macos() {
  [[ "$(uname -s)" == "Darwin" ]]
}

is_native_linux() {
  [[ "$(uname -s)" == "Linux" ]] && ! is_wsl
}

powershell_is_operational() {
  local output

  if ! command_exists "powershell.exe"; then
    POWERSHELL_LAST_ERROR="powershell.exe is not available on PATH."
    return 1
  fi

  if ! output="$(powershell.exe -NoProfile -Command '[Console]::Out.Write("webvisionkit-ok")' 2>&1)"; then
    POWERSHELL_LAST_ERROR="$(trim_carriage_return "${output}")"
    return 1
  fi

  output="$(trim_carriage_return "${output}")"
  if [[ "${output}" != *"webvisionkit-ok"* ]]; then
    POWERSHELL_LAST_ERROR="PowerShell probe returned unexpected output: ${output}"
    return 1
  fi

  POWERSHELL_LAST_ERROR=""
}

powershell_env_passthrough_works() {
  local output

  if ! output="$(
    WEBVISIONKIT_ENV_CHECK="webvisionkit-env-ok" \
      powershell.exe -NoProfile -Command '$value = $env:WEBVISIONKIT_ENV_CHECK; if ($null -eq $value) { [Console]::Out.Write("missing") } else { [Console]::Out.Write($value) }' \
      2>&1
  )"; then
    POWERSHELL_LAST_ERROR="$(trim_carriage_return "${output}")"
    return 1
  fi

  output="$(trim_carriage_return "${output}")"
  if [[ "${output}" != "webvisionkit-env-ok" ]]; then
    POWERSHELL_LAST_ERROR="PowerShell environment passthrough probe returned '${output}'."
    return 1
  fi

  POWERSHELL_LAST_ERROR=""
}

resolve_windows_local_app_data_dir() {
  local output

  if ! output="$(powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("LocalApplicationData")' 2>&1)"; then
    POWERSHELL_LAST_ERROR="$(trim_carriage_return "${output}")"
    return 1
  fi

  output="$(trim_carriage_return "${output}")"
  if [[ -z "${output}" ]]; then
    POWERSHELL_LAST_ERROR="PowerShell returned an empty LocalApplicationData path."
    return 1
  fi

  printf '%s\n' "${output}"
}

fetch_windows_local_devtools_version_json_via_powershell() {
  local output

  if ! output="$(
    powershell.exe -NoProfile -Command "\$uri = 'http://127.0.0.1:${CHROME_PORT}/json/version'; try { [Console]::Out.Write((Invoke-WebRequest -UseBasicParsing -Uri \$uri -TimeoutSec 2).Content) } catch { exit 1 }" \
      2>&1
  )"; then
    POWERSHELL_LAST_ERROR="$(trim_carriage_return "${output}")"
    return 1
  fi

  output="$(trim_carriage_return "${output}")"
  if [[ -z "${output}" ]]; then
    POWERSHELL_LAST_ERROR="PowerShell returned an empty DevTools version payload."
    return 1
  fi

  printf '%s\n' "${output}"
}

fetch_devtools_version_json_from_url() {
  local url="$1"

  curl \
    -fsSL \
    --connect-timeout "${CHROME_HTTP_CONNECT_TIMEOUT_SECONDS}" \
    --max-time "${CHROME_HTTP_MAX_TIME_SECONDS}" \
    "${url}" \
    2>/dev/null
}

fetch_host_devtools_version_json_into_state() {
  local version_json

  HOST_DEVTOOLS_VERSION_JSON=""

  if is_wsl && [[ "${WSL_CHROME_LAUNCH_BACKEND:-}" == "wsl-windows" ]] && powershell_is_operational; then
    if version_json="$(fetch_windows_local_devtools_version_json_via_powershell)"; then
      HOST_DEVTOOLS_SOURCE_LABEL="windows-local-powershell://127.0.0.1:${CHROME_PORT}/json/version"
      HOST_DEVTOOLS_VERSION_JSON="${version_json}"
      return 0
    fi
  fi

  if version_json="$(fetch_devtools_version_json_from_url "${CHROME_VERSION_URL}")"; then
    HOST_DEVTOOLS_SOURCE_LABEL="${CHROME_VERSION_URL}"
    HOST_DEVTOOLS_VERSION_JSON="${version_json}"
    return 0
  fi

  return 1
}

fetch_host_devtools_version_json() {
  if ! fetch_host_devtools_version_json_into_state; then
    return 1
  fi

  printf '%s\n' "${HOST_DEVTOOLS_VERSION_JSON}"
}

resolve_default_chrome_profile_dir_for_backend() {
  local backend="${1:-}"

  if is_wsl && [[ "${backend}" == "wsl-windows" ]]; then
    if ! powershell_is_operational; then
      return 1
    fi

    local windows_local_app_data
    if ! windows_local_app_data="$(resolve_windows_local_app_data_dir)"; then
      return 1
    fi
    printf '%s\n' "${windows_local_app_data}\\WebVisionKit\\chrome-cdp-profile"
    return 0
  fi

  printf '%s\n' "/tmp/webvisionkit-chrome-cdp-profile"
}

resolve_default_chrome_profile_dir() {
  resolve_default_chrome_profile_dir_for_backend ""
}

ensure_chrome_profile_dir_resolved_for_backend() {
  local backend="${1:-}"

  if [[ -n "${CHROME_PROFILE_DIR}" ]]; then
    return 0
  fi

  if [[ -n "${CHROME_PROFILE_DIR_RAW}" ]]; then
    CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR_RAW}"
    CHROME_PROFILE_KIND="explicit-env"
    return 0
  fi

  if ! CHROME_PROFILE_DIR="$(resolve_default_chrome_profile_dir_for_backend "${backend}")"; then
    return 1
  fi

  if is_wsl && [[ "${backend}" == "wsl-windows" ]]; then
    CHROME_PROFILE_KIND="wsl-windows-default"
  else
    CHROME_PROFILE_KIND="local-default"
  fi
}

ensure_chrome_profile_dir_resolved() {
  ensure_chrome_profile_dir_resolved_for_backend ""
}

compute_source_hash() {
  (
    cd "${SCRIPT_DIR}"
    {
      printf '%s\n' "${DOCKERFILE_RELATIVE}"
      find "api/webvisionkit" -type f ! -path '*/__pycache__/*' | LC_ALL=C sort
    } | while IFS= read -r path; do
      hash_file_sha256 "${path}"
    done | hash_file_sha256 "/dev/stdin"
  ) | hash_file_sha256 "/dev/stdin"
}

get_image_source_hash() {
  docker image inspect "${IMAGE_NAME}" \
    --format '{{ index .Config.Labels "webvisionkit.source-hash" }}' \
    2>/dev/null || true
}

sort_into_array() {
  local -a unsorted=("$@")
  local value

  if [[ "${#unsorted[@]}" -eq 0 ]]; then
    return 0
  fi

  while IFS= read -r value; do
    [[ -n "${value}" ]] && printf '%s\0' "${value}"
  done < <(printf '%s\n' "${unsorted[@]}" | LC_ALL=C sort -u)
}

discover_game_slugs() {
  local -a found=()
  local path

  shopt -s nullglob
  for path in "${GAMES_DIR}"/*/index.html; do
    found+=( "$(basename "$(dirname "${path}")")" )
  done
  shopt -u nullglob

  GAME_SLUGS=()
  if [[ "${#found[@]}" -eq 0 ]]; then
    return 0
  fi

  while IFS= read -r -d '' path; do
    GAME_SLUGS+=( "${path}" )
  done < <(sort_into_array "${found[@]}")
}

discover_app_names() {
  local -a found=()
  local path

  shopt -s nullglob
  for path in "${APPS_DIR}"/*/app.py; do
    found+=( "$(basename "$(dirname "${path}")")" )
  done
  shopt -u nullglob

  APP_NAMES=()
  if [[ "${#found[@]}" -eq 0 ]]; then
    return 0
  fi

  while IFS= read -r -d '' path; do
    APP_NAMES+=( "${path}" )
  done < <(sort_into_array "${found[@]}")
}

array_contains() {
  local needle="$1"
  shift

  local item
  for item in "$@"; do
    if [[ "${item}" == "${needle}" ]]; then
      return 0
    fi
  done

  return 1
}

require_interactive_input() {
  if [[ ! -t 0 ]]; then
    error_exit "Interactive selection requires a TTY. Set APP_NAME and optional TARGET_URL_OVERRIDE to run non-interactively."
  fi
}

ensure_curl_access() {
  require_command "curl" "Install curl so the launcher can query the Chrome DevTools endpoints."
}

ensure_wsl_prerequisites() {
  if ! is_wsl; then
    return 0
  fi

  if ! is_wsl2; then
    error_exit "WSL1 is not supported. Use WSL2 with Docker Desktop integration for WebVisionKit."
  fi
}

ensure_wsl_chrome_backend_scope() {
  validate_wsl_chrome_backend_value

  if [[ "${WSL_CHROME_BACKEND}" == "auto" ]]; then
    return 0
  fi

  if ! is_wsl; then
    error_exit "--chrome-backend is only supported on WSL. Use the default Chrome launcher behavior on macOS or native Linux."
  fi
}

ensure_browser_launch_prerequisites() {
  ensure_wsl_chrome_backend_scope
  ensure_curl_access
  ensure_wsl_prerequisites

  case "$(resolve_platform)" in
    wsl)
      resolve_wsl_launch_backend >/dev/null
      ;;
    macos)
      ensure_chrome_profile_dir_resolved_for_backend "macos" >/dev/null
      resolve_macos_chrome_app >/dev/null
      ;;
    linux)
      ensure_chrome_profile_dir_resolved_for_backend "linux" >/dev/null
      resolve_linux_chrome_app >/dev/null
      ;;
  esac
}

ensure_catalogs() {
  discover_game_slugs
  discover_app_names

  if [[ "${#APP_NAMES[@]}" -eq 0 ]]; then
    error_exit "No apps found in ${APPS_DIR}. Add subdirectories containing app.py."
  fi
}

ensure_docker_access() {
  require_command "docker" "Install Docker Desktop or a compatible Docker engine."
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  error_exit "Docker is unavailable or inaccessible. Start Docker Desktop or fix Docker permissions, then retry."
}

ensure_image() {
  local expected_hash
  local image_hash

  expected_hash="$(compute_source_hash)"
  image_hash="$(get_image_source_hash)"

  if [[ "${FORCE_REBUILD}" == "1" ]]; then
    echo "[info] FORCE_REBUILD=1, rebuilding Docker image ${IMAGE_NAME}"
    if ! IMAGE_NAME="${IMAGE_NAME}" bash "${DOCKER_BUILD_SCRIPT}"; then
      error_exit "Docker image build failed for ${IMAGE_NAME}. Check Docker access and the build output above."
    fi
    return 0
  fi

  if [[ -z "${image_hash}" ]]; then
    echo "[info] Docker image ${IMAGE_NAME} is missing or unversioned. Building it now."
    if ! IMAGE_NAME="${IMAGE_NAME}" bash "${DOCKER_BUILD_SCRIPT}"; then
      error_exit "Docker image build failed for ${IMAGE_NAME}. Check Docker access and the build output above."
    fi
    return 0
  fi

  if [[ "${image_hash}" != "${expected_hash}" ]]; then
    echo "[info] Docker image ${IMAGE_NAME} is stale."
    echo "[info] Expected source hash ${expected_hash}, found ${image_hash}."
    echo "[info] Rebuilding Docker image ${IMAGE_NAME}."
    if ! IMAGE_NAME="${IMAGE_NAME}" bash "${DOCKER_BUILD_SCRIPT}"; then
      error_exit "Docker image build failed for ${IMAGE_NAME}. Check Docker access and the build output above."
    fi
    return 0
  fi

  echo "[info] Reusing Docker image ${IMAGE_NAME}"
}

resolve_game_url() {
  local slug="$1"
  if ! array_contains "${slug}" "${GAME_SLUGS[@]}"; then
    error_exit "Unknown game slug ${slug}. Valid values: ${GAME_SLUGS[*]}"
  fi
  printf 'file://%s/%s/index.html\n' "${GAMES_DIR}" "${slug}"
}

resolve_target_value() {
  local raw="$1"
  if [[ -z "${raw}" ]]; then
    printf '\n'
    return 0
  fi
  if [[ "${raw}" == "free" ]]; then
    printf 'about:blank\n'
    return 0
  fi
  if [[ "${raw}" == game://* ]]; then
    resolve_game_url "${raw#game://}"
    return 0
  fi
  if array_contains "${raw}" "${GAME_SLUGS[@]}"; then
    resolve_game_url "${raw}"
    return 0
  fi
  printf '%s\n' "${raw}"
}

set_explicit_target_selection() {
  local label="$1"
  local raw_value="$2"

  TARGET_SELECTION_MODE="explicit"
  TARGET_SELECTION_LABEL="${label}"
  TARGET_SELECTION_VALUE="$(resolve_target_value "${raw_value}")"
  if [[ -z "${TARGET_SELECTION_VALUE}" ]]; then
    error_exit "Target selection ${label} did not resolve to a usable URL."
  fi
}

prompt_custom_url() {
  local input

  while true; do
    read -r -p "Custom URL: " input
    if [[ -z "${input}" ]]; then
      echo "[warn] Enter a non-empty URL, about:blank, game://slug, or a game slug." >&2
      continue
    fi
    set_explicit_target_selection "custom URL" "${input}"
    return 0
  done
}

choose_target_selection() {
  local selection
  local index
  local custom_index

  if [[ -n "${TARGET_URL_OVERRIDE_INPUT}" ]]; then
    set_explicit_target_selection "${TARGET_URL_OVERRIDE_INPUT}" "${TARGET_URL_OVERRIDE_INPUT}"
    return 0
  fi

  if [[ ! -t 0 ]]; then
    TARGET_SELECTION_MODE="app-default"
    TARGET_SELECTION_LABEL="app default"
    TARGET_SELECTION_VALUE=""
    return 0
  fi

  echo "[info] Choose what Chrome should open:"
  echo "  0) app default"
  echo "  1) free browse"

  index=2
  if [[ "${#GAME_SLUGS[@]}" -eq 0 ]]; then
    echo "[info] No local games found in ${GAMES_DIR}. Only app default, free browse, and custom URL are available."
  else
    for selection in "${GAME_SLUGS[@]}"; do
      echo "  ${index}) ${selection}"
      index=$((index + 1))
    done
  fi
  custom_index="${index}"
  echo "  ${custom_index}) custom URL"

  while true; do
    read -r -p "Launch target: " selection
    if [[ "${selection}" == "0" ]] || [[ "${selection}" == "default" ]]; then
      TARGET_SELECTION_MODE="app-default"
      TARGET_SELECTION_LABEL="app default"
      TARGET_SELECTION_VALUE=""
      return 0
    fi
    if [[ "${selection}" == "1" ]] || [[ "${selection}" == "free" ]]; then
      set_explicit_target_selection "free browse" "about:blank"
      return 0
    fi
    if [[ "${selection}" =~ ^[0-9]+$ ]]; then
      if [[ "${selection}" == "${custom_index}" ]]; then
        prompt_custom_url
        return 0
      fi
      index=$((selection - 2))
      if (( index >= 0 && index < ${#GAME_SLUGS[@]} )); then
        set_explicit_target_selection "${GAME_SLUGS[index]}" "${GAME_SLUGS[index]}"
        return 0
      fi
    elif [[ "${selection}" == "custom" ]]; then
      prompt_custom_url
      return 0
    elif [[ "${selection}" == game://* ]] || array_contains "${selection}" "${GAME_SLUGS[@]}"; then
      set_explicit_target_selection "${selection}" "${selection}"
      return 0
    elif [[ "${selection}" == "about:blank" ]] || [[ "${selection}" == http://* ]] || [[ "${selection}" == https://* ]] || [[ "${selection}" == file://* ]]; then
      set_explicit_target_selection "${selection}" "${selection}"
      return 0
    fi

    echo "[warn] Invalid selection. Choose app default, free browse, a game, or custom URL." >&2
  done
}

choose_app() {
  local selection
  local index

  if [[ -n "${APP_NAME}" ]]; then
    if array_contains "${APP_NAME}" "${APP_NAMES[@]}"; then
      SELECTED_APP_NAME="${APP_NAME}"
      return 0
    fi

    error_exit "Invalid APP_NAME=${APP_NAME}. Valid values: ${APP_NAMES[*]}"
  fi

  require_interactive_input
  echo "[info] Choose the student app to run:"
  index=1
  for selection in "${APP_NAMES[@]}"; do
    echo "  ${index}) ${selection}"
    index=$((index + 1))
  done

  while true; do
    read -r -p "App: " selection
    if [[ "${selection}" =~ ^[0-9]+$ ]]; then
      index=$((selection - 1))
      if (( index >= 0 && index < ${#APP_NAMES[@]} )); then
        SELECTED_APP_NAME="${APP_NAMES[index]}"
        return 0
      fi
    elif array_contains "${selection}" "${APP_NAMES[@]}"; then
      SELECTED_APP_NAME="${selection}"
      return 0
    fi

    echo "[warn] Invalid selection. Choose one of: ${APP_NAMES[*]}" >&2
  done
}

inspect_app() {
  if ! APP_INSPECTION_JSON="$(
    docker run --rm \
      -v "${APPS_DIR}:${APPS_DIR_IN_CONTAINER}:ro" \
      -e "APPS_DIR=${APPS_DIR_IN_CONTAINER}" \
      -e "APP_NAME=${SELECTED_APP_NAME}" \
      "${IMAGE_NAME}" \
      python -m webvisionkit.runner --inspect-app
  )"; then
    error_exit "Failed to inspect app ${SELECTED_APP_NAME} inside Docker. Check Docker access and the app definition."
  fi

  if [[ -z "${APP_INSPECTION_JSON}" ]]; then
    error_exit "Failed to inspect app ${SELECTED_APP_NAME} inside Docker."
  fi

  APP_DEFAULT_START_TARGET="$(json_extract_string_field "${APP_INSPECTION_JSON}" "start_target")"
  APP_DEFAULT_START_FPS="$(json_extract_number_field "${APP_INSPECTION_JSON}" "fps")"

  if [[ -z "${APP_DEFAULT_START_TARGET}" ]]; then
    error_exit "Could not extract start_target from Docker app inspection output."
  fi

  if [[ -z "${APP_DEFAULT_START_FPS}" ]]; then
    error_exit "Could not extract fps from Docker app inspection output."
  fi
}

resolve_effective_target() {
  RESOLVED_APP_DEFAULT_TARGET="$(resolve_target_value "${APP_DEFAULT_START_TARGET}")"
  if [[ -z "${RESOLVED_APP_DEFAULT_TARGET}" ]]; then
    error_exit "App ${SELECTED_APP_NAME} did not provide a usable default start target."
  fi

  if [[ "${TARGET_SELECTION_MODE}" == "app-default" ]]; then
    SELECTED_TARGET_OVERRIDE=""
    SELECTED_EFFECTIVE_TARGET="${RESOLVED_APP_DEFAULT_TARGET}"
    return 0
  fi

  SELECTED_TARGET_OVERRIDE="${TARGET_SELECTION_VALUE}"
  SELECTED_EFFECTIVE_TARGET="${TARGET_SELECTION_VALUE}"
}

ensure_profile_dir() {
  local path="$1"
  local ps_output
  local escaped_path

  if [[ -z "${path}" ]]; then
    echo "[error] Chrome profile directory path is empty." >&2
    return 1
  fi

  if [[ "${path}" == [A-Za-z]:\\* ]] || [[ "${path}" == \\\\* ]]; then
    if ! is_wsl; then
      return 0
    fi
    if ! command_exists "powershell.exe"; then
      echo "[error] powershell.exe is required in WSL to create Windows-native Chrome profile directories." >&2
      return 1
    fi

    escaped_path="$(powershell_quote_literal "${path}")"
    if ! ps_output="$(
      powershell.exe -NoProfile -Command "New-Item -ItemType Directory -Force -Path '${escaped_path}' | Out-Null" \
        2>&1
    )"; then
      ps_output="$(trim_carriage_return "${ps_output}")"
      echo "[error] Could not create Chrome profile directory ${path} via PowerShell: ${ps_output}" >&2
      return 1
    fi
    return 0
  fi
  mkdir -p "${path}"
}

resolve_platform() {
  if is_wsl; then
    printf 'wsl\n'
    return 0
  fi
  if is_macos; then
    printf 'macos\n'
    return 0
  fi
  if is_native_linux; then
    printf 'linux\n'
    return 0
  fi
  error_exit "launch.bash chrome supports macOS, Linux, and WSL only."
}

resolve_macos_chrome_app() {
  local app_path="${CHROME_APP:-/Applications/Google Chrome.app}"
  if [[ ! -d "${app_path}" ]]; then
    error_exit "Chrome app not found at ${app_path}. Set CHROME_APP to a valid macOS Chrome app bundle."
  fi
  printf '%s\n' "${app_path}"
}

try_resolve_linux_chrome_app() {
  local candidate
  local resolved

  if [[ -n "${CHROME_APP}" ]]; then
    if resolved="$(command -v "${CHROME_APP}" 2>/dev/null)"; then
      printf '%s\n' "${resolved}"
      return 0
    fi
    if [[ -x "${CHROME_APP}" ]]; then
      printf '%s\n' "${CHROME_APP}"
      return 0
    fi
    return 1
  fi

  for candidate in google-chrome google-chrome-stable chromium chromium-browser; do
    if resolved="$(command -v "${candidate}" 2>/dev/null)"; then
      printf '%s\n' "${resolved}"
      return 0
    fi
  done

  return 1
}

resolve_linux_chrome_app() {
  local resolved

  if resolved="$(try_resolve_linux_chrome_app)"; then
    printf '%s\n' "${resolved}"
    return 0
  fi

  if [[ -n "${CHROME_APP}" ]]; then
    error_exit "Chrome executable not found at ${CHROME_APP}. Set CHROME_APP to a valid Chrome or Chromium executable."
  fi

  error_exit "Chrome or Chromium was not found on Linux. Install one of them or set CHROME_APP."
}

try_resolve_wsl_chrome_app() {
  resolve_wsl_windows_chrome_path
}

resolve_wsl_chrome_app() {
  local resolved

  if resolved="$(try_resolve_wsl_chrome_app)"; then
    printf '%s\n' "${resolved}"
    return 0
  fi

  error_exit "Windows Chrome was not found from WSL. Install Chrome on Windows or set CHROME_APP to chrome.exe."
}

resolve_windows_local_chrome_path_via_powershell() {
  local output

  if ! output="$(
    powershell.exe -NoProfile -Command '$path = Join-Path $env:LOCALAPPDATA "Google\\Chrome\\Application\\chrome.exe"; if (Test-Path $path) { [Console]::Out.Write($path) }' \
      2>&1
  )"; then
    POWERSHELL_LAST_ERROR="$(trim_carriage_return "${output}")"
    return 1
  fi

  output="$(trim_carriage_return "${output}")"
  if [[ -z "${output}" ]]; then
    return 1
  fi

  printf '%s\n' "${output}"
}

is_valid_wsl_windows_chrome_candidate() {
  local candidate="$1"
  local wsl_candidate

  if [[ -z "${candidate}" ]]; then
    return 1
  fi

  if [[ "${candidate}" == [A-Za-z]:\\* ]]; then
    if ! command_exists "wslpath"; then
      return 1
    fi
    if ! wsl_candidate="$(wslpath -u "${candidate}" 2>/dev/null)"; then
      return 1
    fi
  else
    wsl_candidate="${candidate}"
  fi

  [[ -f "${wsl_candidate}" ]]
}

resolve_wsl_windows_chrome_path() {
  local candidate
  local local_appdata_candidate=""

  if ! is_wsl; then
    return 1
  fi

  if [[ -n "${WSL_WINDOWS_CHROME_PATH}" ]]; then
    printf '%s\n' "${WSL_WINDOWS_CHROME_PATH}"
    return 0
  fi

  if [[ -n "${CHROME_APP}" ]]; then
    echo "[info] Windows Chrome discovery: checking CHROME_APP override (${CHROME_APP})"
    if is_valid_wsl_windows_chrome_candidate "${CHROME_APP}"; then
      WSL_WINDOWS_CHROME_PATH="${CHROME_APP}"
      echo "[info] Windows Chrome discovery: CHROME_APP override is valid."
      printf '%s\n' "${WSL_WINDOWS_CHROME_PATH}"
      return 0
    fi
    echo "[warn] Windows Chrome discovery: CHROME_APP override did not resolve to an existing chrome.exe."
    return 1
  fi

  for candidate in \
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
  do
    echo "[info] Windows Chrome discovery: checking ${candidate}"
    if is_valid_wsl_windows_chrome_candidate "${candidate}"; then
      WSL_WINDOWS_CHROME_PATH="${candidate}"
      echo "[info] Windows Chrome discovery: found ${candidate}"
      printf '%s\n' "${WSL_WINDOWS_CHROME_PATH}"
      return 0
    fi
  done

  if command_exists "powershell.exe"; then
    if local_appdata_candidate="$(resolve_windows_local_chrome_path_via_powershell)"; then
      echo "[info] Windows Chrome discovery: checking LocalAppData candidate ${local_appdata_candidate}"
      if is_valid_wsl_windows_chrome_candidate "${local_appdata_candidate}"; then
        WSL_WINDOWS_CHROME_PATH="${local_appdata_candidate}"
        echo "[info] Windows Chrome discovery: found LocalAppData Chrome path."
        printf '%s\n' "${WSL_WINDOWS_CHROME_PATH}"
        return 0
      fi
      echo "[warn] Windows Chrome discovery: LocalAppData candidate did not validate from WSL."
    fi
  fi

  echo "[warn] Windows Chrome discovery: no native Windows chrome.exe candidate found."
  return 1
}

run_with_optional_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return $?
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return $?
  fi

  "$@"
}

install_wsl_linux_chrome() {
  local chrome_deb_url="https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
  local chrome_deb_path="/tmp/google-chrome-stable_current_amd64.deb"

  if ! is_wsl; then
    error_exit "WSL Chrome installer was invoked outside WSL."
  fi

  if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
    return 0
  fi

  require_command "wget" "Install wget or install google-chrome-stable manually."
  require_command "dpkg" "Install dpkg so WebVisionKit can install Google Chrome in WSL."
  require_command "apt-get" "Install apt-get or install google-chrome-stable manually."

  echo "[info] Linux Chrome fallback is missing in WSL. Installing Google Chrome."
  if ! wget -q -O "${chrome_deb_path}" "${chrome_deb_url}"; then
    error_exit "Failed to download Chrome from ${chrome_deb_url}. Check WSL network access and retry."
  fi

  if ! run_with_optional_sudo dpkg -i "${chrome_deb_path}"; then
    echo "[info] Resolving Chrome package dependencies via apt-get."
    if ! run_with_optional_sudo apt-get install -f -y; then
      error_exit "Could not install Chrome dependencies in WSL. Run 'sudo apt-get install -f -y' and retry."
    fi
    if ! run_with_optional_sudo dpkg -i "${chrome_deb_path}"; then
      error_exit "Failed to install Google Chrome package in WSL."
    fi
  fi
}

to_windows_path() {
  local input="$1"

  if [[ "${input}" == [A-Za-z]:\\* ]]; then
    printf '%s\n' "${input}"
    return 0
  fi

  if ! command -v wslpath >/dev/null 2>&1; then
    error_exit "wslpath is required to convert WSL paths for Windows Chrome."
  fi

  wslpath -w "${input}"
}

detect_wsl_gateway_ip() {
  local gateway_ip=""
  gateway_ip="$(ip route show default 2>/dev/null | awk '{print $3; exit}' || true)"
  printf '%s\n' "${gateway_ip}"
}

resolve_wsl_linux_fallback_host_candidates() {
  local gateway_ip

  gateway_ip="$(detect_wsl_gateway_ip)"
  if [[ -n "${gateway_ip}" ]]; then
    printf '%s\n' "${gateway_ip}"
  fi
  if [[ "${gateway_ip}" != "host.docker.internal" ]]; then
    printf '%s\n' "host.docker.internal"
  fi
}

resolve_wsl_windows_host_candidates() {
  local gateway_ip
  local -a candidates=()
  local candidate

  candidates+=( "host.docker.internal" )
  gateway_ip="$(detect_wsl_gateway_ip)"
  if [[ -n "${gateway_ip}" ]]; then
    candidates+=( "${gateway_ip}" )
  fi
  candidates+=( "localhost" "127.0.0.1" )

  for candidate in "${candidates[@]}"; do
    [[ -n "${candidate}" ]] && printf '%s\n' "${candidate}"
  done | awk '!seen[$0]++'
}

probe_chrome_host_from_container() {
  local host="$1"
  local probe_code
  local -a docker_args=( --rm )

  probe_code=$'import os\nimport socket\n\nhost = os.environ["WEBVISIONKIT_PROBE_HOST"]\nport = int(os.environ["WEBVISIONKIT_PROBE_PORT"])\ntimeout = float(os.environ.get("WEBVISIONKIT_PROBE_TIMEOUT_SECONDS", "1.5"))\n\nsock = socket.create_connection((host, port), timeout=timeout)\nsock.close()\n'

  if is_native_linux && [[ "${host}" == "host.docker.internal" ]]; then
    docker_args+=( --add-host=host.docker.internal:host-gateway )
  fi

  docker run \
    "${docker_args[@]}" \
    -e "WEBVISIONKIT_PROBE_HOST=${host}" \
    -e "WEBVISIONKIT_PROBE_PORT=${CHROME_PORT}" \
    -e "WEBVISIONKIT_PROBE_TIMEOUT_SECONDS=1.5" \
    "${IMAGE_NAME}" \
    python -c "${probe_code}" \
    >/dev/null 2>&1
}

resolve_wsl_linux_fallback_host_route() {
  local candidate
  local candidate_list=""
  local -a candidates=()
  local -a tried=()

  if ! is_wsl; then
    return 0
  fi

  if [[ "${WSL_CHROME_LAUNCH_BACKEND}" != "wsl-linux-fallback" ]]; then
    return 0
  fi

  WSL_HOST_ROUTE_TRIED=""

  if [[ -n "${CHROME_HOST_IN_CONTAINER_RAW}" ]]; then
    WSL_HOST_ROUTE_MODE="explicit-user"
    echo "[info] Using explicit CHROME_HOST_IN_CONTAINER=${CHROME_HOST_IN_CONTAINER}."
    return 0
  fi

  while IFS= read -r candidate; do
    [[ -n "${candidate}" ]] && candidates+=( "${candidate}" )
  done < <(resolve_wsl_linux_fallback_host_candidates)

  if (( ${#candidates[@]} == 0 )); then
    error_exit "Could not determine any WSL fallback host candidates. Set CHROME_HOST_IN_CONTAINER explicitly."
  fi

  candidate_list="$(IFS=', '; echo "${candidates[*]}")"
  echo "[info] WSL fallback host candidates (gateway first): ${candidate_list}"

  for candidate in "${candidates[@]}"; do
    tried+=( "${candidate}" )
    echo "[info] Probing container reachability to ${candidate}:${CHROME_PORT}"
    if probe_chrome_host_from_container "${candidate}"; then
      CHROME_HOST_IN_CONTAINER="${candidate}"
      WSL_HOST_ROUTE_MODE="wsl-fallback-probed"
      echo "[info] Selected CHROME_HOST_IN_CONTAINER=${candidate} after successful container probe."
      return 0
    fi
    echo "[warn] Candidate ${candidate}:${CHROME_PORT} is not reachable from the container."
  done

  WSL_HOST_ROUTE_TRIED="$(IFS=', '; echo "${tried[*]}")"
  error_exit "Could not reach Chrome from the container on any WSL fallback host candidate (${WSL_HOST_ROUTE_TRIED}) at port ${CHROME_PORT}. Set CHROME_HOST_IN_CONTAINER explicitly."
}

resolve_wsl_windows_host_route() {
  local candidate
  local candidate_list=""
  local -a candidates=()
  local -a tried=()

  if ! is_wsl; then
    return 0
  fi

  if [[ "${WSL_CHROME_LAUNCH_BACKEND}" != "wsl-windows" ]]; then
    return 0
  fi

  WSL_HOST_ROUTE_TRIED=""

  if [[ -n "${CHROME_HOST_IN_CONTAINER_RAW}" ]]; then
    WSL_HOST_ROUTE_MODE="explicit-user"
    echo "[info] Using explicit CHROME_HOST_IN_CONTAINER=${CHROME_HOST_IN_CONTAINER}."
    return 0
  fi

  while IFS= read -r candidate; do
    [[ -n "${candidate}" ]] && candidates+=( "${candidate}" )
  done < <(resolve_wsl_windows_host_candidates)

  if (( ${#candidates[@]} == 0 )); then
    error_exit "Could not determine any WSL Windows host candidates. Set CHROME_HOST_IN_CONTAINER explicitly."
  fi

  candidate_list="$(IFS=', '; echo "${candidates[*]}")"
  echo "[info] WSL Windows host candidates (host.docker.internal first): ${candidate_list}"

  for candidate in "${candidates[@]}"; do
    tried+=( "${candidate}" )
    echo "[info] Probing container reachability to ${candidate}:${CHROME_PORT}"
    if probe_chrome_host_from_container "${candidate}"; then
      CHROME_HOST_IN_CONTAINER="${candidate}"
      WSL_HOST_ROUTE_MODE="wsl-windows-probed"
      echo "[info] Selected CHROME_HOST_IN_CONTAINER=${candidate} after successful container probe."
      return 0
    fi
    echo "[warn] Candidate ${candidate}:${CHROME_PORT} is not reachable from the container."
  done

  WSL_HOST_ROUTE_TRIED="$(IFS=', '; echo "${tried[*]}")"
  return 1
}

resolve_container_chrome_host_route() {
  if [[ -n "${CHROME_HOST_IN_CONTAINER_RAW}" ]]; then
    CHROME_HOST_IN_CONTAINER="${CHROME_HOST_IN_CONTAINER_RAW}"
    WSL_HOST_ROUTE_MODE="explicit-user"
    return 0
  fi

  if ! is_wsl; then
    return 0
  fi

  case "${WSL_CHROME_LAUNCH_BACKEND:-}" in
    wsl-windows)
      resolve_wsl_windows_host_route
      return $?
      ;;
    wsl-linux-fallback)
      resolve_wsl_linux_fallback_host_route
      return $?
      ;;
  esac

  return 0
}

apply_wsl_linux_fallback_host_override() {
  # Backward-compatible wrapper for existing call sites and tests.
  resolve_wsl_linux_fallback_host_route
}

resolve_wsl_launch_backend() {
  if [[ -n "${WSL_CHROME_LAUNCH_BACKEND}" ]]; then
    printf '%s\n' "${WSL_CHROME_LAUNCH_BACKEND}"
    return 0
  fi

  local windows_reason=""

  validate_wsl_chrome_backend_value

  case "${WSL_CHROME_BACKEND}" in
    linux)
      WSL_CHROME_LAUNCH_BACKEND="wsl-linux-fallback"
      WSL_CHROME_LAST_ERROR=""
      echo "[info] WSL backend selection: choosing wsl-linux-fallback because --chrome-backend linux was requested."
      printf '%s\n' "${WSL_CHROME_LAUNCH_BACKEND}"
      return 0
      ;;
    windows)
      if ! command_exists "powershell.exe"; then
        error_exit "--chrome-backend windows requires powershell.exe on PATH."
      fi
      if ! powershell_is_operational; then
        error_exit "--chrome-backend windows requires working PowerShell interop: ${POWERSHELL_LAST_ERROR}"
      fi
      if ! command_exists "wslpath"; then
        error_exit "--chrome-backend windows requires wslpath on PATH."
      fi
      if ! resolve_wsl_windows_chrome_path >/dev/null 2>&1; then
        error_exit "--chrome-backend windows requires native Windows Chrome. Install Chrome on Windows or set CHROME_APP to chrome.exe."
      fi
      WSL_CHROME_LAUNCH_BACKEND="wsl-windows"
      WSL_CHROME_LAST_ERROR=""
      echo "[info] WSL backend selection: choosing wsl-windows because --chrome-backend windows was requested."
      printf '%s\n' "${WSL_CHROME_LAUNCH_BACKEND}"
      return 0
      ;;
  esac

  if ! command_exists "powershell.exe"; then
    windows_reason="powershell.exe is unavailable."
  elif ! powershell_is_operational; then
    windows_reason="PowerShell probe failed: ${POWERSHELL_LAST_ERROR}"
  elif ! command_exists "wslpath"; then
    windows_reason="wslpath is unavailable."
  elif ! resolve_wsl_windows_chrome_path >/dev/null 2>&1; then
    windows_reason="Windows Chrome was not found (set CHROME_APP if needed)."
  else
    WSL_CHROME_LAUNCH_BACKEND="wsl-windows"
    WSL_CHROME_LAST_ERROR=""
    echo "[info] WSL backend selection: choosing wsl-windows because native Windows Chrome was found."
    printf '%s\n' "${WSL_CHROME_LAUNCH_BACKEND}"
    return 0
  fi

  WSL_CHROME_LAUNCH_BACKEND="wsl-linux-fallback"
  WSL_CHROME_LAST_ERROR="${windows_reason}"
  echo "[info] WSL backend selection: choosing wsl-linux-fallback because ${windows_reason}"
  printf '%s\n' "${WSL_CHROME_LAUNCH_BACKEND}"
  return 0
}

launch_macos() {
  local app_path
  app_path="$(resolve_macos_chrome_app)"

  ensure_chrome_profile_dir_resolved_for_backend "macos"
  ensure_profile_dir "${CHROME_PROFILE_DIR}"
  echo "[info] Launching Chrome with remote debugging on port ${CHROME_PORT} on macOS"
  open -na "${app_path}" --args \
    --user-data-dir="${CHROME_PROFILE_DIR}" \
    --remote-debugging-port="${CHROME_PORT}" \
    --remote-allow-origins="${CHROME_REMOTE_ALLOW_ORIGINS}" \
    --start-maximized
}

launch_linux() {
  local chrome_bin
  chrome_bin="$(resolve_linux_chrome_app)"

  ensure_chrome_profile_dir_resolved_for_backend "linux"
  ensure_profile_dir "${CHROME_PROFILE_DIR}"
  echo "[info] Launching Chrome with remote debugging on port ${CHROME_PORT} on Linux"
  nohup "${chrome_bin}" \
    --user-data-dir="${CHROME_PROFILE_DIR}" \
    --remote-debugging-port="${CHROME_PORT}" \
    --remote-allow-origins="${CHROME_REMOTE_ALLOW_ORIGINS}" \
    --start-maximized \
    >/dev/null 2>&1 &
}

launch_wsl_windows() {
  local chrome_app_path
  local chrome_app_windows
  local profile_windows
  local ps_output
  local escaped_chrome_app_windows
  local escaped_profile_windows
  local escaped_chrome_port
  local escaped_remote_allow_origins
  local escaped_remote_debugging_address

  if ! chrome_app_path="$(resolve_wsl_windows_chrome_path)"; then
    WSL_CHROME_LAST_ERROR="Windows Chrome path could not be resolved."
    return 1
  fi
  if ! ensure_chrome_profile_dir_resolved_for_backend "wsl-windows"; then
    WSL_CHROME_LAST_ERROR="Could not resolve a Windows profile path: ${POWERSHELL_LAST_ERROR}"
    return 1
  fi
  if ! chrome_app_windows="$(to_windows_path "${chrome_app_path}" 2>/dev/null)"; then
    WSL_CHROME_LAST_ERROR="Could not convert Chrome path for Windows launch."
    return 1
  fi
  if ! ensure_profile_dir "${CHROME_PROFILE_DIR}"; then
    WSL_CHROME_LAST_ERROR="Could not create Windows profile path ${CHROME_PROFILE_DIR}."
    return 1
  fi
  if ! profile_windows="$(to_windows_path "${CHROME_PROFILE_DIR}" 2>/dev/null)"; then
    WSL_CHROME_LAST_ERROR="Could not convert profile path for Windows launch."
    return 1
  fi

  escaped_chrome_app_windows="$(powershell_quote_literal "${chrome_app_windows}")"
  escaped_profile_windows="$(powershell_quote_literal "${profile_windows}")"
  escaped_chrome_port="$(powershell_quote_literal "${CHROME_PORT}")"
  escaped_remote_allow_origins="$(powershell_quote_literal "${CHROME_REMOTE_ALLOW_ORIGINS}")"
  escaped_remote_debugging_address="$(powershell_quote_literal "0.0.0.0")"

  echo "[info] Launching Windows Chrome from WSL with remote debugging on port ${CHROME_PORT}"
  echo "[info] Windows Chrome executable: ${chrome_app_path}"
  if ! ps_output="$(
    powershell.exe -NoProfile -Command "\$args = @('--user-data-dir=${escaped_profile_windows}', '--remote-debugging-port=${escaped_chrome_port}', '--remote-debugging-address=${escaped_remote_debugging_address}', '--remote-allow-origins=${escaped_remote_allow_origins}', '--start-maximized'); Start-Process -FilePath '${escaped_chrome_app_windows}' -ArgumentList \$args | Out-Null" \
      2>&1
  )"; then
    ps_output="$(trim_carriage_return "${ps_output}")"
    WSL_CHROME_LAST_ERROR="PowerShell Start-Process failed: ${ps_output}"
    return 1
  fi

  CHROME_PROFILE_KIND="${CHROME_PROFILE_KIND:-wsl-windows-default}"
  return 0
}

launch_wsl_linux_fallback() {
  local chrome_bin

  if [[ -z "${CHROME_PROFILE_DIR_RAW}" ]]; then
    CHROME_PROFILE_DIR=""
    CHROME_PROFILE_KIND="unresolved"
  fi

  if ! chrome_bin="$(try_resolve_linux_chrome_app)"; then
    install_wsl_linux_chrome
    if ! chrome_bin="$(try_resolve_linux_chrome_app)"; then
      WSL_CHROME_LAST_ERROR="Linux Chrome fallback is unavailable."
      return 1
    fi
  fi

  if ! ensure_chrome_profile_dir_resolved_for_backend "wsl-linux-fallback"; then
    WSL_CHROME_LAST_ERROR="Could not resolve a Linux profile path for fallback mode."
    return 1
  fi
  if ! ensure_profile_dir "${CHROME_PROFILE_DIR}"; then
    WSL_CHROME_LAST_ERROR="Could not create Linux fallback profile path ${CHROME_PROFILE_DIR}."
    return 1
  fi

  echo "[info] Launching Linux Chrome fallback in WSL with remote debugging on port ${CHROME_PORT}"
  nohup "${chrome_bin}" \
    --user-data-dir="${CHROME_PROFILE_DIR}" \
    --remote-debugging-port="${CHROME_PORT}" \
    --remote-allow-origins="${CHROME_REMOTE_ALLOW_ORIGINS}" \
    --start-maximized \
    >/dev/null 2>&1 &
  return 0
}

launch_wsl() {
  local backend

  backend="$(resolve_wsl_launch_backend)"
  WSL_CHROME_LAUNCH_BACKEND="${backend}"

  if [[ "${backend}" == "wsl-windows" ]]; then
    echo "[info] Selected WSL Chrome backend: wsl-windows"
    if launch_wsl_windows; then
      return 0
    fi
    echo "[warn] Windows backend launch failed: ${WSL_CHROME_LAST_ERROR}"

    if [[ "${WSL_CHROME_BACKEND}" == "windows" ]]; then
      error_exit "Failed to launch Chrome from WSL with --chrome-backend windows: ${WSL_CHROME_LAST_ERROR}"
    fi

    if ! try_resolve_linux_chrome_app >/dev/null 2>&1; then
      error_exit "Failed to launch Chrome from WSL. Windows backend failed (${WSL_CHROME_LAST_ERROR}) and Linux fallback is unavailable."
    fi

    WSL_CHROME_LAUNCH_BACKEND="wsl-linux-fallback"
    echo "[info] Falling back to Linux Chrome in WSL."
  else
    echo "[info] Selected WSL Chrome backend: wsl-linux-fallback"
    if [[ -n "${WSL_CHROME_LAST_ERROR}" ]]; then
      echo "[warn] Windows backend unavailable: ${WSL_CHROME_LAST_ERROR}"
    fi
  fi

  if ! launch_wsl_linux_fallback; then
    error_exit "Failed to launch Linux Chrome fallback from WSL: ${WSL_CHROME_LAST_ERROR}"
  fi
}

cmd_chrome() {
  local print_endpoint="${1:-1}"

  ensure_browser_launch_prerequisites

  if fetch_host_devtools_version_json_into_state; then
    HOST_BROWSER_WS_URL_OVERRIDE="$(json_extract_string_field "${HOST_DEVTOOLS_VERSION_JSON}" "webSocketDebuggerUrl")"
    echo "[info] Reusing existing DevTools endpoint via ${HOST_DEVTOOLS_SOURCE_LABEL}"
    if [[ "${print_endpoint}" == "1" ]]; then
      printf '%s\n' "${HOST_DEVTOOLS_SOURCE_LABEL}"
    fi
    return 0
  fi

  echo "[info] Chrome DevTools endpoint is not up. Starting Chrome."

  case "$(resolve_platform)" in
    wsl)
      launch_wsl
      echo "[info] WSL launch backend in use: ${WSL_CHROME_LAUNCH_BACKEND}"
      ;;
    macos)
      launch_macos
      ;;
    linux)
      launch_linux
      ;;
  esac

  echo "[info] Chrome profile kind: ${CHROME_PROFILE_KIND}"
  echo "[info] Container-side DevTools host hint: ${CHROME_HOST_IN_CONTAINER} (${WSL_HOST_ROUTE_MODE})"

  if [[ "${print_endpoint}" == "1" ]]; then
    printf '%s\n' "${CHROME_VERSION_URL}"
  fi
}

wait_for_chrome() {
  local -a candidates=()
  local -a unique_candidates=()
  local candidate
  local existing_candidate
  local gateway_ip
  local attempt
  local version_json
  local use_windows_local_probe=0
  local already_present

  candidates+=( "${CHROME_VERSION_URL}" )
  if is_wsl && [[ "${WSL_CHROME_LAUNCH_BACKEND:-}" == "wsl-windows" ]]; then
    use_windows_local_probe=1
    candidates+=( "http://127.0.0.1:${CHROME_PORT}/json/version" )
    candidates+=( "http://localhost:${CHROME_PORT}/json/version" )
    gateway_ip="$(detect_wsl_gateway_ip)"
    if [[ -n "${gateway_ip}" ]]; then
      candidates+=( "http://${gateway_ip}:${CHROME_PORT}/json/version" )
    fi
  fi

  for candidate in "${candidates[@]}"; do
    [[ -z "${candidate}" ]] && continue
    already_present=0
    if (( ${#unique_candidates[@]} > 0 )); then
      for existing_candidate in "${unique_candidates[@]}"; do
        if [[ "${existing_candidate}" == "${candidate}" ]]; then
          already_present=1
          break
        fi
      done
    fi
    if (( already_present == 0 )); then
      unique_candidates+=( "${candidate}" )
    fi
  done

  if (( ${#unique_candidates[@]} > 1 )); then
    echo "[info] Waiting for Chrome DevTools endpoint on candidates: ${unique_candidates[*]}"
  fi

  HOST_BROWSER_WS_URL_OVERRIDE=""
  HOST_DEVTOOLS_SOURCE_LABEL="${CHROME_VERSION_URL}"

  for (( attempt=1; attempt<=CHROME_STARTUP_RETRIES; attempt++ )); do
    if [[ "${use_windows_local_probe}" == "1" ]] && powershell_is_operational; then
      if version_json="$(fetch_windows_local_devtools_version_json_via_powershell)"; then
        HOST_DEVTOOLS_SOURCE_LABEL="windows-local-powershell://127.0.0.1:${CHROME_PORT}/json/version"
        HOST_BROWSER_WS_URL_OVERRIDE="$(json_extract_string_field "${version_json}" "webSocketDebuggerUrl")"
        echo "[info] Chrome DevTools endpoint is ready on attempt ${attempt} via ${HOST_DEVTOOLS_SOURCE_LABEL}"
        return 0
      fi
    fi

    for candidate in "${unique_candidates[@]}"; do
      if version_json="$(fetch_devtools_version_json_from_url "${candidate}")"; then
        CHROME_VERSION_URL="${candidate}"
        CHROME_LIST_URL="${candidate%/version}"
        HOST_DEVTOOLS_SOURCE_LABEL="${candidate}"
        HOST_BROWSER_WS_URL_OVERRIDE="$(json_extract_string_field "${version_json}" "webSocketDebuggerUrl")"
        echo "[info] Chrome DevTools endpoint is ready on attempt ${attempt} at ${candidate}"
        return 0
      fi
    done

    sleep "${CHROME_STARTUP_DELAY_SECONDS}"
  done

  error_exit "Chrome DevTools endpoint did not become ready at ${CHROME_VERSION_URL}"
}

resolve_output_layout() {
  if [[ -n "${OUTPUT_DIR_RAW}" ]]; then
    HOST_OUTPUT_DIR="${OUTPUT_DIR_RAW}"
  else
    HOST_OUTPUT_DIR="${SCRIPT_DIR}/output"
  fi

  if [[ -n "${SCREENSHOT_DIR_RAW}" ]]; then
    HOST_SCREENSHOT_DIR="${SCREENSHOT_DIR_RAW}"
    if [[ -n "${OUTPUT_DIR_RAW}" ]]; then
      case "${HOST_SCREENSHOT_DIR}" in
        "${HOST_OUTPUT_DIR}"/*)
          SCREENSHOT_SUBPATH="${HOST_SCREENSHOT_DIR#${HOST_OUTPUT_DIR}/}"
          ;;
        *)
          error_exit "SCREENSHOT_DIR must be inside OUTPUT_DIR when both are set."
          ;;
      esac
    else
      HOST_OUTPUT_DIR="$(dirname "${HOST_SCREENSHOT_DIR}")"
      SCREENSHOT_SUBPATH="$(basename "${HOST_SCREENSHOT_DIR}")"
    fi
  else
    HOST_SCREENSHOT_DIR="${HOST_OUTPUT_DIR}/screenshots"
    SCREENSHOT_SUBPATH="screenshots"
  fi

  CONTAINER_SAVE_DIR="${CONTAINER_OUTPUT_DIR}/${SCREENSHOT_SUBPATH}"
}

build_docker_host_args() {
  local uid
  local gid

  DOCKER_HOST_ARGS=()
  if ! resolve_container_chrome_host_route; then
    return 1
  fi

  if is_native_linux && [[ "${CHROME_HOST_IN_CONTAINER}" == "host.docker.internal" ]]; then
    DOCKER_HOST_ARGS+=( --add-host=host.docker.internal:host-gateway )
  fi

  if [[ "${DOCKER_RUN_USER_MODE}" == "off" ]]; then
    return 0
  fi

  if is_native_linux || is_wsl; then
    uid="$(id -u)"
    gid="$(id -g)"
    if [[ -n "${uid}" ]] && [[ -n "${gid}" ]]; then
      DOCKER_HOST_ARGS+=( --user "${uid}:${gid}" )
    fi
  fi
}

rewrite_url_host_port() {
  local raw_url="$1"
  local new_host="$2"
  local new_port="$3"
  local normalized
  local prefix
  local remainder
  local host_port
  local path=""

  normalized="${raw_url//\\//}"
  if [[ -z "${normalized}" ]]; then
    printf '\n'
    return 0
  fi

  if [[ "${normalized}" != *"://"* ]]; then
    printf '%s\n' "${normalized}"
    return 0
  fi

  prefix="${normalized%%://*}"
  remainder="${normalized#*://}"
  if [[ "${remainder}" == */* ]]; then
    host_port="${remainder%%/*}"
    path="/${remainder#*/}"
  else
    host_port="${remainder}"
  fi

  if [[ -z "${host_port}" ]]; then
    printf '%s\n' "${normalized}"
    return 0
  fi

  printf '%s://%s:%s%s\n' "${prefix}" "${new_host}" "${new_port}" "${path}"
}

rewrite_ws_url_for_container() {
  local ws_url="$1"
  rewrite_url_host_port "${ws_url}" "${CHROME_HOST_IN_CONTAINER}" "${CHROME_PORT}"
}

resolve_browser_ws_url() {
  if [[ -n "${BROWSER_BROWSER_WS_URL:-}" ]]; then
    printf '%s\n' "${BROWSER_BROWSER_WS_URL}"
    return 0
  fi

  if [[ -n "${HOST_BROWSER_WS_URL_OVERRIDE:-}" ]]; then
    printf '%s\n' "${HOST_BROWSER_WS_URL_OVERRIDE}"
    return 0
  fi

  echo "[info] Fetching browser websocket from: ${HOST_DEVTOOLS_SOURCE_LABEL}" >&2

  if ! fetch_host_devtools_version_json_into_state; then
    echo "[error] Could not reach ${HOST_DEVTOOLS_SOURCE_LABEL}" >&2
    echo "[hint] Start Chrome with remote debugging first, or use ./launch.bash." >&2
    return 1
  fi

  local browser_ws_url
  browser_ws_url="$(json_extract_string_field "${HOST_DEVTOOLS_VERSION_JSON}" "webSocketDebuggerUrl")"

  if [[ -z "${browser_ws_url}" ]]; then
    echo "[error] Could not extract browser webSocketDebuggerUrl from ${HOST_DEVTOOLS_SOURCE_LABEL}" >&2
    return 1
  fi

  printf '%s\n' "${browser_ws_url}"
}

resolve_ws_url() {
  if [[ -n "${BROWSER_WS_URL:-}" ]]; then
    printf '%s\n' "${BROWSER_WS_URL}"
    return 0
  fi

  echo "[info] No host page websocket hint provided. The container runtime will create or discover a page target." >&2
  printf '\n'
}

resolve_container_targets() {
  discover_game_slugs

  if [[ -n "${APP_DEFAULT_TARGET_URL}" ]]; then
    APP_DEFAULT_TARGET_URL="$(resolve_target_value "${APP_DEFAULT_TARGET_URL}")"
  fi

  if [[ -n "${TARGET_URL_OVERRIDE}" ]]; then
    TARGET_URL_OVERRIDE="$(resolve_target_value "${TARGET_URL_OVERRIDE}")"
  fi
}

run_container_devtools_probe() {
  local -a docker_args=( --rm )
  local browser_browser_ws_url_host
  local browser_browser_ws_url_for_container
  local probe_code

  if ! build_docker_host_args; then
    return 1
  fi
  if (( ${#DOCKER_HOST_ARGS[@]} > 0 )); then
    docker_args+=( "${DOCKER_HOST_ARGS[@]}" )
  fi

  browser_browser_ws_url_host="$(resolve_browser_ws_url)"
  browser_browser_ws_url_for_container="$(rewrite_ws_url_for_container "${browser_browser_ws_url_host}")"
  probe_code=$'import json\nimport os\n\nimport websocket\n\nws_url = os.environ["BROWSER_BROWSER_WS_URL"]\nws = websocket.create_connection(ws_url, timeout=5)\ntry:\n    ws.send(json.dumps({"id": 1, "method": "Target.getTargets", "params": {}}))\n    payload = json.loads(ws.recv())\nfinally:\n    ws.close()\nif "result" not in payload:\n    raise RuntimeError(f"Browser websocket probe failed: {payload}")\ntarget_infos = payload["result"].get("targetInfos", [])\nprint(ws_url)\nprint(f"targets={len(target_infos)}")\n'

  docker run \
    "${docker_args[@]}" \
    -e "CHROME_HOST=${CHROME_HOST_IN_CONTAINER}" \
    -e "CHROME_PORT=${CHROME_PORT}" \
    -e "BROWSER_BROWSER_WS_URL=${browser_browser_ws_url_for_container}" \
    "${IMAGE_NAME}" \
    python -c "${probe_code}"
}

cmd_container() {
  local browser_browser_ws_url_host
  local browser_browser_ws_url_for_container
  local ws_url
  local ws_url_for_container

  DOCKER_TTY_ARGS=()
  HOST_OUTPUT_DIR=""
  HOST_SCREENSHOT_DIR=""
  SCREENSHOT_SUBPATH="screenshots"
  CONTAINER_SAVE_DIR=""

  ensure_curl_access
  ensure_docker_access
  resolve_output_layout
  resolve_container_targets

  APP_DEFAULT_TARGET_URL="$(normalize_target_url_for_wsl_windows_chrome "${APP_DEFAULT_TARGET_URL}")"
  TARGET_URL_OVERRIDE="$(normalize_target_url_for_wsl_windows_chrome "${TARGET_URL_OVERRIDE}")"

  if ! build_docker_host_args; then
    return 1
  fi

  mkdir -p "${HOST_OUTPUT_DIR}"
  mkdir -p "${HOST_SCREENSHOT_DIR}"

  if [[ ! -d "${APPS_DIR}" ]]; then
    error_exit "Apps directory not found at ${APPS_DIR}"
  fi

  if [[ -z "${APP_NAME}" ]]; then
    error_exit "APP_NAME must be set before running the container."
  fi

  if [[ -t 0 && -t 1 ]]; then
    DOCKER_TTY_ARGS+=( -it )
  elif [[ -t 0 ]]; then
    DOCKER_TTY_ARGS+=( -i )
  fi

  browser_browser_ws_url_host="$(resolve_browser_ws_url)"
  ws_url="$(resolve_ws_url)"
  browser_browser_ws_url_for_container="$(rewrite_ws_url_for_container "${browser_browser_ws_url_host}")"
  ws_url_for_container="$(rewrite_ws_url_for_container "${ws_url}")"

  echo "[info] Host-side DevTools endpoint:   ${HOST_DEVTOOLS_SOURCE_LABEL}"
  echo "[info] Container-side DevTools host:  ${CHROME_HOST_IN_CONTAINER} (${WSL_HOST_ROUTE_MODE})"
  echo "[info] Host browser websocket URL:   ${browser_browser_ws_url_host}"
  echo "[info] Container browser websocket:  ${browser_browser_ws_url_for_container}"
  echo "[info] Host page websocket URL:      ${ws_url:-<none>}"
  echo "[info] Container page websocket URL: ${ws_url_for_container:-<none>}"
  echo "[info] Output dir on host:           ${HOST_OUTPUT_DIR}"
  echo "[info] Screenshot dir on host:       ${HOST_SCREENSHOT_DIR}"
  echo "[info] Apps dir on host:             ${APPS_DIR}"
  echo "[info] Running app:                  ${APP_NAME}"
  if [[ -n "${APP_DEFAULT_TARGET_URL}" ]]; then
    echo "[info] App default target URL:       ${APP_DEFAULT_TARGET_URL}"
  fi
  if [[ -n "${TARGET_URL_OVERRIDE}" ]]; then
    echo "[info] Target override URL:          ${TARGET_URL_OVERRIDE}"
  fi
  echo "[info] Starting container: ${IMAGE_NAME}"

  local -a docker_args=(
    --rm
    -v "${HOST_OUTPUT_DIR}:${CONTAINER_OUTPUT_DIR}"
    -v "${APPS_DIR}:${APPS_DIR_IN_CONTAINER}:ro"
    -e "CHROME_HOST=${CHROME_HOST_IN_CONTAINER}"
    -e "CHROME_PORT=${CHROME_PORT}"
    -e "APPS_DIR=${APPS_DIR_IN_CONTAINER}"
    -e "APP_NAME=${APP_NAME}"
    -e "APP_DEFAULT_TARGET_URL=${APP_DEFAULT_TARGET_URL}"
    -e "TARGET_URL_OVERRIDE=${TARGET_URL_OVERRIDE}"
    -e "BROWSER_BROWSER_WS_URL=${browser_browser_ws_url_for_container}"
    -e "BROWSER_WS_URL=${ws_url_for_container}"
    -e "STARTUP_TARGET_MODE=${STARTUP_TARGET_MODE}"
    -e "TARGET_MATCH=${TARGET_MATCH}"
    -e "TARGET_CLOSE_ACTION=${TARGET_CLOSE_ACTION}"
    -e "SAVE_DIR=${CONTAINER_SAVE_DIR}"
    -e "SAVE_INTERVAL_SECONDS=${SAVE_INTERVAL_SECONDS}"
    -e "FRAME_FORMAT=${FRAME_FORMAT}"
    -e "FRAME_QUALITY=${FRAME_QUALITY}"
    -e "EVERY_NTH_FRAME=${EVERY_NTH_FRAME}"
    -e "MAX_WIDTH=${MAX_WIDTH}"
    -e "MAX_HEIGHT=${MAX_HEIGHT}"
    -e "LIVE_PREVIEW=${LIVE_PREVIEW}"
    -e "VIDEO_OUTPUT=${VIDEO_OUTPUT}"
    -e "METADATA_OUTPUT=${METADATA_OUTPUT}"
    -e "PROCESSORS=${PROCESSORS}"
    -e "RECONNECT_ATTEMPTS=${RECONNECT_ATTEMPTS}"
    -e "RECONNECT_DELAY_SECONDS=${RECONNECT_DELAY_SECONDS}"
    -e "RECEIVE_TIMEOUT_SECONDS=${RECEIVE_TIMEOUT_SECONDS}"
    -e "IDLE_TIMEOUT_SECONDS=${IDLE_TIMEOUT_SECONDS}"
    -e "LOG_INTERVAL_SECONDS=${LOG_INTERVAL_SECONDS}"
    -e "VIDEO_FPS=${VIDEO_FPS}"
    -e "MAX_FRAMES=${MAX_FRAMES}"
    -e "ACTION_MODE=${ACTION_MODE}"
    -e "ACTION_DEFAULT_COOLDOWN_MS=${ACTION_DEFAULT_COOLDOWN_MS}"
    -e "ACTION_MAX_PER_FRAME=${ACTION_MAX_PER_FRAME}"
    -e "ACTION_DRAG_STEP_COUNT=${ACTION_DRAG_STEP_COUNT}"
    -e "ACTION_DRAG_STEP_DELAY_MS=${ACTION_DRAG_STEP_DELAY_MS}"
  )

  if (( ${#DOCKER_TTY_ARGS[@]} > 0 )); then
    docker_args=( "${docker_args[0]}" "${DOCKER_TTY_ARGS[@]}" "${docker_args[@]:1}" )
  fi

  if (( ${#DOCKER_HOST_ARGS[@]} > 0 )); then
    docker_args+=( "${DOCKER_HOST_ARGS[@]}" )
  fi

  if [[ -n "${DOCKER_EXTRA_ARGS}" ]]; then
    # shellcheck disable=SC2206
    local -a extra_args=( ${DOCKER_EXTRA_ARGS} )
    docker_args+=( "${extra_args[@]}" )
  fi

  echo "[info] Container process started (foreground)."
  if ! docker run "${docker_args[@]}" "${IMAGE_NAME}"; then
    return 1
  fi
  return 0
}

cmd_doctor() {
  local probe_output

  echo "[info] Running WebVisionKit doctor"
  ensure_hash_tool
  ensure_curl_access
  ensure_docker_access
  ensure_browser_launch_prerequisites

  echo "[info] Hash tool: $(detect_hash_tool)"
  echo "[info] Docker: available"
  echo "[info] Chrome platform: $(resolve_platform)"

  cmd_chrome 0
  wait_for_chrome

  echo "[info] Chrome launch backend: ${WSL_CHROME_LAUNCH_BACKEND:-n/a}"
  echo "[info] Chrome profile dir: ${CHROME_PROFILE_DIR}"
  echo "[info] Chrome profile kind: ${CHROME_PROFILE_KIND}"
  echo "[info] Container-side DevTools host hint: ${CHROME_HOST_IN_CONTAINER} (${WSL_HOST_ROUTE_MODE})"

  if ! fetch_host_devtools_version_json_into_state; then
    error_exit "Chrome DevTools responded during startup but ${HOST_DEVTOOLS_SOURCE_LABEL} could not be fetched afterward."
  fi
  echo "[info] Host DevTools version endpoint is reachable."
  echo "[info] Host browser websocket: $(json_extract_string_field "${HOST_DEVTOOLS_VERSION_JSON}" "webSocketDebuggerUrl")"

  ensure_image
  if ! build_docker_host_args; then
    error_exit "Could not resolve a container-side Chrome DevTools route. Tried: ${WSL_HOST_ROUTE_TRIED:-unknown}."
  fi
  echo "[info] Host-side DevTools endpoint: ${HOST_DEVTOOLS_SOURCE_LABEL}"
  echo "[info] Container-side DevTools host: ${CHROME_HOST_IN_CONTAINER} (${WSL_HOST_ROUTE_MODE})"

  if ! probe_output="$(run_container_devtools_probe)"; then
    if is_wsl && [[ "${WSL_CHROME_LAUNCH_BACKEND}" == "wsl-linux-fallback" ]]; then
      error_exit "The container could not reach the host Chrome DevTools endpoint at ${CHROME_HOST_IN_CONTAINER}:${CHROME_PORT}. In WSL Linux fallback mode, set CHROME_HOST_IN_CONTAINER explicitly to a reachable route."
    fi
    error_exit "The container could not reach the host Chrome DevTools endpoint at ${CHROME_HOST_IN_CONTAINER}:${CHROME_PORT}."
  fi

  echo "[info] Container DevTools probe succeeded:"
  printf '%s\n' "${probe_output}"
  echo "[info] Doctor checks passed."
}

run_smoke_case() {
  local label="$1"
  local app_name="$2"
  local target_url="$3"
  local max_frames="$4"
  local action_mode="$5"
  local expected_pattern="$6"
  local output_root="${SMOKE_OUTPUT_DIR_RAW:-${SCRIPT_DIR}/output/smoke}"
  local case_output_dir="${output_root}/${label}"
  local metadata_name="${label}.jsonl"
  local metadata_path="${case_output_dir}/screenshots/${metadata_name}"
  local APP_NAME="${app_name}"
  local APP_DEFAULT_TARGET_URL=""
  local TARGET_URL_OVERRIDE="${target_url}"
  local OUTPUT_DIR_RAW="${case_output_dir}"
  local SCREENSHOT_DIR_RAW=""
  local METADATA_OUTPUT="${metadata_name}"
  local SAVE_INTERVAL_SECONDS="0"
  local MAX_FRAMES="${max_frames}"
  local LOG_INTERVAL_SECONDS="0"
  local ACTION_MODE="${action_mode}"
  local LIVE_PREVIEW="0"

  echo "[info] Smoke case ${label}: app=${APP_NAME} target=${TARGET_URL_OVERRIDE} max_frames=${MAX_FRAMES} action_mode=${ACTION_MODE}"
  if ! cmd_container; then
    error_exit "Smoke case ${label} failed while running the container."
  fi

  if [[ ! -s "${metadata_path}" ]]; then
    error_exit "Smoke case ${label} did not produce metadata at ${metadata_path}."
  fi

  if ! grep -q "${expected_pattern}" "${metadata_path}"; then
    error_exit "Smoke case ${label} completed, but ${metadata_path} did not contain the expected marker ${expected_pattern}."
  fi

  echo "[info] Smoke case ${label} passed."
}

cmd_smoke() {
  local SMOKE_OUTPUT_DIR_RAW="${SMOKE_OUTPUT_DIR_RAW:-${SCRIPT_DIR}/output/smoke/$(date +%Y%m%d_%H%M%S)}"

  cmd_doctor
  run_smoke_case "local-frame-report" "frame_report" "game://input-lab" "${SMOKE_MAX_FRAMES}" "auto" '"frame_report"'
  run_smoke_case "external-frame-report" "frame_report" "${SMOKE_EXTERNAL_URL}" "${SMOKE_EXTERNAL_MAX_FRAMES}" "auto" '"frame_report"'
  run_smoke_case "interaction-dry-run" "interaction_showcase" "game://input-lab" "${SMOKE_INTERACTION_MAX_FRAMES}" "dry-run" '"action_results"'
}

cmd_up() {
  local preflight_output
  local preflight_output_file
  local container_exit_code

  ensure_hash_tool
  ensure_browser_launch_prerequisites
  ensure_catalogs
  ensure_docker_access
  ensure_image
  choose_target_selection
  choose_app
  inspect_app
  resolve_effective_target

  echo "[info] Target selection: ${TARGET_SELECTION_LABEL}"
  echo "[info] App selection: ${SELECTED_APP_NAME}"
  echo "[info] App default start target: ${APP_DEFAULT_START_TARGET}"
  echo "[info] App default callback FPS: ${APP_DEFAULT_START_FPS}"
  echo "[info] Resolved app default target: ${RESOLVED_APP_DEFAULT_TARGET}"
  if [[ -n "${SELECTED_TARGET_OVERRIDE}" ]]; then
    echo "[info] Target override selection: ${SELECTED_TARGET_OVERRIDE}"
  else
    echo "[info] Target override selection: <app default>"
  fi
  echo "[info] Effective launch target: ${SELECTED_EFFECTIVE_TARGET}"

  cmd_chrome 0
  wait_for_chrome
  echo "[stage] chrome_ready complete"

  APP_NAME="${SELECTED_APP_NAME}"
  APP_DEFAULT_TARGET_URL="$(normalize_target_url_for_wsl_windows_chrome "${RESOLVED_APP_DEFAULT_TARGET}")"
  TARGET_URL_OVERRIDE="$(normalize_target_url_for_wsl_windows_chrome "${SELECTED_TARGET_OVERRIDE}")"

  if [[ "${APP_DEFAULT_TARGET_URL}" != "${RESOLVED_APP_DEFAULT_TARGET}" ]]; then
    echo "[info] Normalized app default target for Windows Chrome: ${APP_DEFAULT_TARGET_URL}"
  fi
  if [[ -n "${SELECTED_TARGET_OVERRIDE}" ]] && [[ "${TARGET_URL_OVERRIDE}" != "${SELECTED_TARGET_OVERRIDE}" ]]; then
    echo "[info] Normalized target override for Windows Chrome: ${TARGET_URL_OVERRIDE}"
  fi

  echo "[stage] container_preflight starting"
  preflight_output_file="$(mktemp)"
  set +e
  run_container_devtools_probe >"${preflight_output_file}"
  container_exit_code=$?
  set -e
  preflight_output="$(cat "${preflight_output_file}")"
  rm -f "${preflight_output_file}"
  if [[ "${container_exit_code}" -ne 0 ]]; then
    if is_wsl && [[ -n "${WSL_HOST_ROUTE_TRIED}" ]]; then
      error_exit "Docker is reachable, but the container could not connect to the host-side DevTools endpoint ${CHROME_VERSION_URL} using container-side host candidates (${WSL_HOST_ROUTE_TRIED}). Run ./launch.bash doctor for full diagnostics."
    fi
    error_exit "Docker is reachable, but the container cannot reach the Chrome DevTools host at ${CHROME_HOST_IN_CONTAINER}:${CHROME_PORT}. Host-side endpoint: ${CHROME_VERSION_URL}. Run ./launch.bash doctor for full diagnostics."
  fi
  echo "[info] Container preflight probe succeeded:"
  printf '%s\n' "${preflight_output}"

  echo "[stage] container_launch starting"
  set +e
  cmd_container
  container_exit_code=$?
  set -e
  if [[ "${container_exit_code}" -ne 0 ]]; then
    echo "[stage] container_exit code=${container_exit_code}"
    echo "[error] Container launch failed before app runtime completed, or runtime exited with an error."
    echo "[error] Diagnostics:"
    echo "[error]   backend=${WSL_CHROME_LAUNCH_BACKEND:-n/a}"
    echo "[error]   chrome_host_in_container=${CHROME_HOST_IN_CONTAINER}"
    echo "[error]   devtools_endpoint=${CHROME_VERSION_URL}"
    error_exit "Container started and exited unsuccessfully. Run ./launch.bash doctor for full diagnostics."
  fi
  echo "[stage] container_exit code=0"
}

if [[ "${WEBVISIONKIT_SOURCE_ONLY:-0}" != "1" ]]; then
  parse_launch_args "$@"
  set -- "${LAUNCH_POSITIONAL_ARGS[@]}"

  case "${COMMAND}" in
    "" | up)
      cmd_up "$@"
      ;;
    chrome)
      cmd_chrome 1 "$@"
      ;;
    doctor)
      cmd_doctor "$@"
      ;;
    smoke)
      cmd_smoke "$@"
      ;;
    container)
      cmd_container "$@"
      ;;
    help | --help | -h)
      print_usage
      ;;
    *)
      echo "[error] Unknown command: ${COMMAND}" >&2
      print_usage >&2
      exit 1
      ;;
  esac
fi
