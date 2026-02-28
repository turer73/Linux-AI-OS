#!/bin/bash
# coolify-webhook.sh - Coolify deployment webhook handler
#
# This script is called by Coolify after a deployment event.
# Configure in Coolify: Settings -> Webhooks -> Post-deploy
#
# Usage:
#   coolify-webhook.sh <app_name> <status> [commit_sha]
#
# Environment:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  - Telegram notifications
#   DISCORD_WEBHOOK_URL                    - Discord notifications

set -euo pipefail

TAG="[coolify-webhook]"
APP_NAME="${1:-unknown}"
STATUS="${2:-unknown}"
COMMIT="${3:-}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_FILE="/var/AI-stump/deploy.log"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# --- Logging ---
log_deploy() {
    echo "[${TIMESTAMP}] app=${APP_NAME} status=${STATUS} commit=${COMMIT}" >> "$LOG_FILE" 2>/dev/null || true
}

# --- Notifications ---
send_telegram() {
    local msg="$1"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\":\"${TELEGRAM_CHAT_ID}\",\"text\":\"${msg}\",\"parse_mode\":\"HTML\"}" > /dev/null 2>&1 || true
    fi
}

send_discord() {
    local msg="$1"
    if [ -n "${DISCORD_WEBHOOK_URL:-}" ]; then
        curl -s -X POST "${DISCORD_WEBHOOK_URL}" \
            -H "Content-Type: application/json" \
            -d "{\"content\":\"${msg}\"}" > /dev/null 2>&1 || true
    fi
}

# --- Main ---
echo -e "${TAG} Deploy event: app=${GREEN}${APP_NAME}${NC} status=${STATUS}"

# Log the event
log_deploy

# Build notification message
if [ "$STATUS" = "success" ] || [ "$STATUS" = "running" ]; then
    ICON="✅"
    MSG="${ICON} <b>Deploy Basarili</b>\nApp: ${APP_NAME}\nDurum: ${STATUS}\nCommit: ${COMMIT}\nZaman: ${TIMESTAMP}"
    MSG_PLAIN="${ICON} Deploy Basarili | App: ${APP_NAME} | ${STATUS} | ${TIMESTAMP}"
else
    ICON="❌"
    MSG="${ICON} <b>Deploy Basarisiz</b>\nApp: ${APP_NAME}\nDurum: ${STATUS}\nCommit: ${COMMIT}\nZaman: ${TIMESTAMP}"
    MSG_PLAIN="${ICON} Deploy Basarisiz | App: ${APP_NAME} | ${STATUS} | ${TIMESTAMP}"
fi

# Send notifications
send_telegram "$MSG"
send_discord "$MSG_PLAIN"

# Run post-deploy health check
if [ "$STATUS" = "success" ] || [ "$STATUS" = "running" ]; then
    echo "${TAG} Running post-deploy health check..."
    if command -v ai-monitor &> /dev/null; then
        ai-monitor check 2>/dev/null || echo "${TAG} Health check completed with warnings"
    fi
fi

echo "${TAG} Webhook handler complete."
