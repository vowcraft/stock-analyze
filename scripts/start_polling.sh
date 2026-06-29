#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${APP_HOME}"
mkdir -p logs run

exec java -jar target/stock-analyze-1.0.0-SNAPSHOT.jar
