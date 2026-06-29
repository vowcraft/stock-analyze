#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="$(cd "${SCRIPT_DIR}/.." && pwd)"
RELEASE_DIR="${APP_HOME}/release"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
ARCHIVE_NAME="stock-analyze-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${RELEASE_DIR}/${ARCHIVE_NAME}"

mkdir -p "${RELEASE_DIR}"

if ! command -v mvn >/dev/null 2>&1; then
  echo "[package] maven not found. install Maven locally before packaging." >&2
  exit 1
fi

cd "${APP_HOME}"

echo "[package] building java artifacts"
mvn -DskipTests package

tar \
  --exclude='./.git' \
  --exclude='./.idea' \
  --exclude='./.venv' \
  --exclude='./logs' \
  --exclude='./run' \
  --exclude='./release' \
  -czf "${ARCHIVE_PATH}" \
  -C "${APP_HOME}" \
  .

echo "[package] created: ${ARCHIVE_PATH}"
