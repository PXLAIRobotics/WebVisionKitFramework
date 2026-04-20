#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

"${SCRIPT_DIR}/check-env.sh"

echo "[info] Running unit tests"
cd "${ROOT_DIR}"
python3 -m unittest discover -s tests -p 'test_*.py' -v
