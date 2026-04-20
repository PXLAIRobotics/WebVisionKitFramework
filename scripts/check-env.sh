#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[info] Running shell syntax checks"
while IFS= read -r path; do
  [[ -n "${path}" ]] || continue
  bash -n "${ROOT_DIR}/${path}"
done < <(
  cd "${ROOT_DIR}" && find . -type f \( -name '*.sh' -o -name '*.bash' \) \
    -not -path './output/*' \
    -not -path './.git/*' \
    | LC_ALL=C sort \
    | sed 's#^\./##'
)

echo "[info] Running Python import smoke checks"
python3 -c 'import pathlib, sys; root = pathlib.Path("'"${ROOT_DIR}"'"); sys.path.insert(0, str(root / "api")); import webvisionkit; from webvisionkit import BrowserApp, BrowserActions; from webvisionkit.apps import discover_apps; from webvisionkit.runner import resolve_effective_start_target; from webvisionkit.targets import rewrite_ws_host; print("python-imports-ok")'

echo "[info] check-env completed successfully"
