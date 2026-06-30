#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${APP_HOME}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${APP_HOME}/.env"
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-${APP_HOME}/.venv/bin/python}"

cd "${APP_HOME}"
mkdir -p logs run

exec "${PYTHON_BIN}" -m app
