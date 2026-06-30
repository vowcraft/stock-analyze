#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/app/stock-analyze}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[deploy] app home: ${APP_HOME}"
echo "[deploy] python bin: ${PYTHON_BIN}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[deploy] python not found: ${PYTHON_BIN}" >&2
  exit 1
fi

cd "${APP_HOME}"

echo "[deploy] checking python version"
PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
PYTHON_MAJOR="${PYTHON_VERSION%%.*}"
PYTHON_MINOR="${PYTHON_VERSION#*.}"
if [ "${PYTHON_MAJOR}" -lt 3 ] || { [ "${PYTHON_MAJOR}" -eq 3 ] && [ "${PYTHON_MINOR}" -lt 9 ]; }; then
  echo "[deploy] python ${PYTHON_VERSION} detected, but akshare==1.18.64 requires Python >= 3.9" >&2
  echo "[deploy] please install Python 3.9+ and rerun with PYTHON_BIN=/path/to/python3.9+" >&2
  exit 1
fi

echo "[deploy] creating virtualenv"
"${PYTHON_BIN}" -m venv .venv

echo "[deploy] installing python dependencies"
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[deploy] ensuring runtime directories"
mkdir -p logs run

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[deploy] created .env from template, review it before first start"
fi

echo "[deploy] done"
