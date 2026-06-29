#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/stock-analyze}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_MAVEN_BUILD="${SKIP_MAVEN_BUILD:-auto}"

echo "[deploy] app home: ${APP_HOME}"
echo "[deploy] python bin: ${PYTHON_BIN}"
echo "[deploy] skip maven build: ${SKIP_MAVEN_BUILD}"

if ! command -v java >/dev/null 2>&1; then
  echo "[deploy] java not found. install Java 11+ first. Ubuntu 24.04 recommendation: openjdk-11-jdk" >&2
  exit 1
fi

echo "[deploy] checking java version"
JAVA_VERSION_RAW="$(java -version 2>&1 | awk -F '\"' '/version/ {print $2; exit}')"
JAVA_MAJOR="${JAVA_VERSION_RAW%%.*}"
if [[ "${JAVA_VERSION_RAW}" == 1.* ]]; then
  JAVA_MAJOR="$(echo "${JAVA_VERSION_RAW}" | cut -d'.' -f2)"
fi
if [ -z "${JAVA_MAJOR}" ] || [ "${JAVA_MAJOR}" -lt 11 ]; then
  echo "[deploy] java ${JAVA_VERSION_RAW:-unknown} detected, but this project requires Java 11+" >&2
  echo "[deploy] Ubuntu 24.04 recommendation: sudo apt install -y openjdk-11-jdk" >&2
  exit 1
fi

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

if [ "${SKIP_MAVEN_BUILD}" = "true" ]; then
  echo "[deploy] skip maven build forced"
elif [ "${SKIP_MAVEN_BUILD}" = "auto" ] && [ -f target/stock-analyze-1.0.0-SNAPSHOT.jar ]; then
  echo "[deploy] found prebuilt application jar, skipping maven build"
else
  if ! command -v mvn >/dev/null 2>&1; then
    echo "[deploy] maven not found, and no usable prebuilt jar was found under target/" >&2
    echo "[deploy] either install Maven, or upload a package built by scripts/package_release.sh" >&2
    exit 1
  fi

  echo "[deploy] building spring boot jar"
  mvn -DskipTests package
fi

echo "[deploy] ensuring runtime directories"
mkdir -p logs run

echo "[deploy] done"
