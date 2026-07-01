#!/usr/bin/env bash
# scripts/deploy_restart.sh
# 停止 stock-analyze 服务 → (可选解压新包) → 重启 → 健康检查
#
# 使用:
#   bash scripts/deploy_restart.sh
#   # 带新包:
#   ARCHIVE_PATH=/app/stock-analyze-20260701120000.tar.gz bash scripts/deploy_restart.sh
#   # 自定义服务名 / 端口 / 安装目录:
#   SERVICE_NAME=my-svc APP_PORT=8080 APP_HOME=/opt/sa bash scripts/deploy_restart.sh
#
# 默认假设: systemd + sudo 可用,APP_HOME=/app/stock-analyze
# 不会触碰: .env / logs/ / .venv/

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-stock-analyze-polling}"
APP_HOME="${APP_HOME:-/app/stock-analyze}"
ARCHIVE_PATH="${ARCHIVE_PATH:-}"
APP_PORT="${APP_PORT:-80}"

echo "[deploy] service:  ${SERVICE_NAME}"
echo "[deploy] app home: ${APP_HOME}"
echo "[deploy] archive:  ${ARCHIVE_PATH:-(none, only restart)}"

cd "${APP_HOME}"

# 1. 停服务
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "[deploy] stopping ${SERVICE_NAME}..."
    sudo systemctl stop "${SERVICE_NAME}"
    for _ in 1 2 3 4 5; do
        systemctl is-active --quiet "${SERVICE_NAME}" || break
        sleep 1
    done
    echo "[deploy] stopped"
else
    echo "[deploy] ${SERVICE_NAME} not active, skipping stop"
fi

# 2. (可选) 解压并覆盖代码 (不碰 .env / logs/ / .venv/)
if [ -n "${ARCHIVE_PATH}" ] && [ -f "${ARCHIVE_PATH}" ]; then
    echo "[deploy] extracting ${ARCHIVE_PATH}..."
    ARCHIVE_DIR="$(dirname "${ARCHIVE_PATH}")"
    EXTRACT_DIR="${ARCHIVE_DIR}/stock-analyze"
    rm -rf "${EXTRACT_DIR}"
    mkdir -p "${EXTRACT_DIR}"
    tar -xzf "${ARCHIVE_PATH}" -C "${ARCHIVE_DIR}"

    for item in app deploy scripts README.md requirements.txt .env.example; do
        if [ -e "${EXTRACT_DIR}/${item}" ]; then
            rm -rf "${APP_HOME:?}/${item}"
            cp -R "${EXTRACT_DIR}/${item}" "${APP_HOME}/"
        fi
    done
    rm -rf "${EXTRACT_DIR}"

    # systemd unit 变更检测
    SRC_UNIT="${APP_HOME}/deploy/systemd/${SERVICE_NAME}.service"
    DST_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
    if [ -f "${SRC_UNIT}" ] && { [ ! -f "${DST_UNIT}" ] || ! cmp -s "${SRC_UNIT}" "${DST_UNIT}"; }; then
        sudo cp "${SRC_UNIT}" "${DST_UNIT}"
        sudo systemctl daemon-reload
        echo "[deploy] reloaded systemd unit"
    fi
fi

# 3. 启动
echo "[deploy] starting ${SERVICE_NAME}..."
if ! sudo systemctl start "${SERVICE_NAME}"; then
    echo "[deploy] FATAL: start failed"
    echo "--- last 30 log lines ---"
    tail -30 "${APP_HOME}/logs/polling.log" 2>/dev/null || echo "(no log file)"
    exit 1
fi

# 4. 健康检查 (最多 10s)
HEALTH_OK=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf --max-time 2 "http://127.0.0.1:${APP_PORT}/healthz" >/dev/null 2>&1; then
        HEALTH_OK=1
        break
    fi
    sleep 1
done

# 5. 报告
echo
if [ "${HEALTH_OK}" = "1" ]; then
    echo "[deploy] OK: service up and healthy"
else
    echo "[deploy] WARN: service started but health check failed after 10s"
    echo "--- last 30 log lines ---"
    tail -30 "${APP_HOME}/logs/polling.log" 2>/dev/null || echo "(no log file)"
    echo "--- journald tail ---"
    sudo journalctl -u "${SERVICE_NAME}" -n 30 --no-pager 2>/dev/null || true
fi

sudo systemctl status "${SERVICE_NAME}" --no-pager
