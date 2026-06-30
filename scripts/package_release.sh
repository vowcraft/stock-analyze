#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="$(cd "${SCRIPT_DIR}/.." && pwd)"
RELEASE_DIR="${APP_HOME}/release"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
ARCHIVE_NAME="stock-analyze-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${RELEASE_DIR}/${ARCHIVE_NAME}"
STAGE_DIR="${RELEASE_DIR}/stock-analyze"

mkdir -p "${RELEASE_DIR}"

cd "${APP_HOME}"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"

cp -R app "${STAGE_DIR}/"
cp -R deploy "${STAGE_DIR}/"
cp -R scripts "${STAGE_DIR}/"
cp README.md requirements.txt .env.example .gitignore "${STAGE_DIR}/"

tar \
  -czf "${ARCHIVE_PATH}" \
  -C "${RELEASE_DIR}" \
  stock-analyze

rm -rf "${STAGE_DIR}"

echo "[package] created: ${ARCHIVE_PATH}"
