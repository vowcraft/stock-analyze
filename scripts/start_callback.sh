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

AKSHARE_PYTHON="${AKSHARE_PYTHON:-${APP_HOME}/.venv/bin/python}"
export AKSHARE_PYTHON
export APP_POLLING_ENABLED=false

cd "${APP_HOME}"
mkdir -p logs run

exec java -jar target/stock-analyze-1.0.0-SNAPSHOT.jar
