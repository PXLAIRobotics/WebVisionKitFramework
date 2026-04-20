#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/infrastructure/docker"
DOCKER_BUILD_SCRIPT="${DOCKER_DIR}/build.bash"
DOCKERFILE_RELATIVE="infrastructure/docker/Dockerfile"

COMMAND="${1:-up}"
if [[ "${#}" -gt 0 ]]; then
  shift
fi

IMAGE_NAME="${IMAGE_NAME:-chromium-opencv-stream}"
CHROME_APP="${CHROME_APP:-}"
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

print_usage() {
  cat <<'EOF'
Usage:
  ./launch.bash [up]
  ./launch.bash chrome
  ./launch.bash doctor
  ./launch.bash smoke
  ./launch.bash container
  ./launch.bash help

Commands:
  up         Run the full launcher flow: build/reuse the image, choose a target and app, ensure Chrome, then run the container.
  chrome     Start or reuse Google Chrome with DevTools remote debugging enabled.
  doctor     Run prerequisite and connectivity checks for Docker, Chrome, and the DevTools endpoint.
  smoke      Run bounded non-interactive smoke checks against one local target, one external target, and one dry-run action flow.
  container  Run the Docker container directly using the current environment variables.
  help       Show this help text.

Examples:
  ./launch.bash
  ./launch.bash doctor
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

resolve_default_chrome_profile_dir() {
  if is_wsl; then
    if ! command_exists "powershell.exe"; then
      error_exit "powershell.exe is required in WSL to resolve a Windows-native Chrome profile path."
    fi

    local windows_local_app_data
    windows_local_app_data="$(
      powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("LocalApplicationData")' 2>/dev/null
    )"
    windows_local_app_data="$(trim_carriage_return "${windows_local_app_data}")"
    if [[ -z "${windows_local_app_data}" ]]; then
      error_exit "Could not determine a Windows LocalApplicationData path from WSL."
    fi
    printf '%s\n' "${windows_local_app_data}\\WebVisionKit\\chrome-cdp-profile"
    return 0
  fi

  printf '%s\n' "/tmp/webvisionkit-chrome-cdp-profile"
}

ensure_chrome_profile_dir_resolved() {
  if [[ -n "${CHROME_PROFILE_DIR}" ]]; then
    return 0
  fi

  if [[ -n "${CHROME_PROFILE_DIR_RAW}" ]]; then
    CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR_RAW}"
    return 0
  fi

  CHROME_PROFILE_DIR="$(resolve_default_chrome_profile_dir)"
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

  require_command "powershell.exe" "Install WSL Windows interop or launch Chrome manually from Windows."
  require_command "wslpath" "Install the standard WSL utilities so WebVisionKit can convert host paths."
}

ensure_browser_launch_prerequisites() {
  ensure_curl_access
  ensure_wsl_prerequisites
  ensure_chrome_profile_dir_resolved

  case "$(resolve_platform)" in
    wsl)
      resolve_wsl_chrome_app >/dev/null
      ;;
    macos)
      resolve_macos_chrome_app >/dev/null
      ;;
    linux)
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
  if [[ "${path}" == [A-Za-z]:\\* ]] || [[ "${path}" == \\\\* ]]; then
    if ! is_wsl; then
      return 0
    fi
    if ! command_exists "powershell.exe"; then
      error_exit "powershell.exe is required in WSL to create Windows-native Chrome profile directories."
    fi
    WEBVISIONKIT_CHROME_PROFILE_DIR="${path}" \
      powershell.exe -NoProfile -Command 'New-Item -ItemType Directory -Force -Path $env:WEBVISIONKIT_CHROME_PROFILE_DIR | Out-Null' \
      >/dev/null
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

resolve_linux_chrome_app() {
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
    error_exit "Chrome executable not found at ${CHROME_APP}. Set CHROME_APP to a valid Chrome or Chromium executable."
  fi

  for candidate in google-chrome google-chrome-stable chromium chromium-browser; do
    if resolved="$(command -v "${candidate}" 2>/dev/null)"; then
      printf '%s\n' "${resolved}"
      return 0
    fi
  done

  error_exit "Chrome or Chromium was not found on Linux. Install one of them or set CHROME_APP."
}

resolve_wsl_chrome_app() {
  local candidate

  if [[ -n "${CHROME_APP}" ]]; then
    printf '%s\n' "${CHROME_APP}"
    return 0
  fi

  for candidate in \
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
  do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  error_exit "Windows Chrome was not found from WSL. Install Chrome on Windows or set CHROME_APP to chrome.exe."
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

launch_macos() {
  local app_path
  app_path="$(resolve_macos_chrome_app)"

  ensure_chrome_profile_dir_resolved
  ensure_profile_dir "${CHROME_PROFILE_DIR}"
  echo "[info] Launching Chrome with remote debugging on port ${CHROME_PORT} on macOS"
  open -na "${app_path}" --args \
    --user-data-dir="${CHROME_PROFILE_DIR}" \
    --remote-debugging-port="${CHROME_PORT}" \
    --remote-allow-origins="${CHROME_REMOTE_ALLOW_ORIGINS}"
}

launch_linux() {
  local chrome_bin
  chrome_bin="$(resolve_linux_chrome_app)"

  ensure_chrome_profile_dir_resolved
  ensure_profile_dir "${CHROME_PROFILE_DIR}"
  echo "[info] Launching Chrome with remote debugging on port ${CHROME_PORT} on Linux"
  nohup "${chrome_bin}" \
    --user-data-dir="${CHROME_PROFILE_DIR}" \
    --remote-debugging-port="${CHROME_PORT}" \
    --remote-allow-origins="${CHROME_REMOTE_ALLOW_ORIGINS}" \
    >/dev/null 2>&1 &
}

launch_wsl() {
  local chrome_app_path
  local chrome_app_windows
  local profile_windows

  if ! command -v powershell.exe >/dev/null 2>&1; then
    error_exit "powershell.exe is unavailable in WSL. Install Windows integration or launch Chrome manually."
  fi

  chrome_app_path="$(resolve_wsl_chrome_app)"
  ensure_chrome_profile_dir_resolved
  chrome_app_windows="$(to_windows_path "${chrome_app_path}")"
  ensure_profile_dir "${CHROME_PROFILE_DIR}"
  profile_windows="$(to_windows_path "${CHROME_PROFILE_DIR}")"

  echo "[info] Launching Windows Chrome from WSL with remote debugging on port ${CHROME_PORT}"
  if ! \
    WEBVISIONKIT_CHROME_APP="${chrome_app_windows}" \
    WEBVISIONKIT_CHROME_PROFILE_DIR="${profile_windows}" \
    WEBVISIONKIT_CHROME_PORT="${CHROME_PORT}" \
    WEBVISIONKIT_CHROME_REMOTE_ALLOW_ORIGINS="${CHROME_REMOTE_ALLOW_ORIGINS}" \
    powershell.exe -NoProfile -Command 'Start-Process -FilePath $env:WEBVISIONKIT_CHROME_APP -ArgumentList @("--user-data-dir=$env:WEBVISIONKIT_CHROME_PROFILE_DIR", "--remote-debugging-port=$env:WEBVISIONKIT_CHROME_PORT", "--remote-allow-origins=$env:WEBVISIONKIT_CHROME_REMOTE_ALLOW_ORIGINS") | Out-Null'
  then
    error_exit "Failed to launch Windows Chrome from WSL. Check CHROME_APP and PowerShell access."
  fi
}

cmd_chrome() {
  local print_endpoint="${1:-1}"

  ensure_browser_launch_prerequisites

  if curl -fsSL "${CHROME_VERSION_URL}" >/dev/null 2>&1; then
    echo "[info] Reusing existing DevTools endpoint at ${CHROME_VERSION_URL}"
    if [[ "${print_endpoint}" == "1" ]]; then
      printf '%s\n' "${CHROME_VERSION_URL}"
    fi
    return 0
  fi

  echo "[info] Chrome DevTools endpoint is not up. Starting Chrome."

  case "$(resolve_platform)" in
    wsl)
      launch_wsl
      ;;
    macos)
      launch_macos
      ;;
    linux)
      launch_linux
      ;;
  esac

  if [[ "${print_endpoint}" == "1" ]]; then
    printf '%s\n' "${CHROME_VERSION_URL}"
  fi
}

wait_for_chrome() {
  local attempt
  for (( attempt=1; attempt<=CHROME_STARTUP_RETRIES; attempt++ )); do
    if curl -fsSL "${CHROME_VERSION_URL}" >/dev/null 2>&1; then
      echo "[info] Chrome DevTools endpoint is ready on attempt ${attempt}"
      return 0
    fi

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

rewrite_ws_url_for_container() {
  local ws_url="$1"
  ws_url="${ws_url//127.0.0.1/${CHROME_HOST_IN_CONTAINER}}"
  ws_url="${ws_url//localhost/${CHROME_HOST_IN_CONTAINER}}"
  ws_url="${ws_url//\\//}"
  printf '%s\n' "${ws_url}"
}

resolve_browser_ws_url() {
  if [[ -n "${BROWSER_BROWSER_WS_URL:-}" ]]; then
    printf '%s\n' "${BROWSER_BROWSER_WS_URL}"
    return 0
  fi

  echo "[info] Fetching browser websocket from: ${CHROME_VERSION_URL}" >&2

  local version_json
  if ! version_json="$(curl -fsSL "${CHROME_VERSION_URL}")"; then
    echo "[error] Could not reach ${CHROME_VERSION_URL}" >&2
    echo "[hint] Start Chrome with remote debugging first, or use ./launch.bash." >&2
    return 1
  fi

  local browser_ws_url
  browser_ws_url="$(json_extract_string_field "${version_json}" "webSocketDebuggerUrl")"

  if [[ -z "${browser_ws_url}" ]]; then
    echo "[error] Could not extract browser webSocketDebuggerUrl from ${CHROME_VERSION_URL}" >&2
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

  build_docker_host_args
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
  build_docker_host_args

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

  docker run "${docker_args[@]}" "${IMAGE_NAME}"
}

cmd_doctor() {
  local host_version_json
  local probe_output

  echo "[info] Running WebVisionKit doctor"
  ensure_hash_tool
  ensure_curl_access
  ensure_docker_access
  ensure_browser_launch_prerequisites

  echo "[info] Hash tool: $(detect_hash_tool)"
  echo "[info] Docker: available"
  echo "[info] Chrome platform: $(resolve_platform)"
  echo "[info] Chrome profile dir: ${CHROME_PROFILE_DIR}"

  cmd_chrome 0
  wait_for_chrome

  if ! host_version_json="$(curl -fsSL "${CHROME_VERSION_URL}")"; then
    error_exit "Chrome DevTools responded during startup but ${CHROME_VERSION_URL} could not be fetched afterward."
  fi
  echo "[info] Host DevTools version endpoint is reachable."
  echo "[info] Host browser websocket: $(json_extract_string_field "${host_version_json}" "webSocketDebuggerUrl")"

  ensure_image

  if ! probe_output="$(run_container_devtools_probe)"; then
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

  APP_NAME="${SELECTED_APP_NAME}"
  APP_DEFAULT_TARGET_URL="${RESOLVED_APP_DEFAULT_TARGET}"
  TARGET_URL_OVERRIDE="${SELECTED_TARGET_OVERRIDE}"

  echo "[info] Handing off to launch.bash container"
  cmd_container
}

if [[ "${WEBVISIONKIT_SOURCE_ONLY:-0}" != "1" ]]; then
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
