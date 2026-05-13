#!/bin/bash
# Oracle Cloud Free Tier — Watchdog + Auto-Heal
# Cron: */5 * * * * /home/ubuntu/oisha-os/deploy/oracle-watchdog.sh
# Checks if oisha-os is healthy; restarts if frozen or dead.

set -euo pipefail

SERVICE="oisha-os"
HEALTH_URL="http://localhost:8080/api/system/health"
LOG_TAG="[WATCHDOG]"
MAX_RESTART_COUNT=5
RESTART_COUNT_FILE="/tmp/oisha-watchdog-restarts"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $LOG_TAG $1"; }

# Reset restart counter daily
if [ -f "$RESTART_COUNT_FILE" ]; then
    FILE_DATE=$(date -r "$RESTART_COUNT_FILE" '+%Y-%m-%d')
    TODAY=$(date '+%Y-%m-%d')
    if [ "$FILE_DATE" != "$TODAY" ]; then
        echo "0" > "$RESTART_COUNT_FILE"
    fi
fi

RESTART_COUNT=$(cat "$RESTART_COUNT_FILE" 2>/dev/null || echo "0")

# Check 1: Is the service running?
if ! systemctl is-active --quiet "$SERVICE"; then
    log "Service is DEAD. Restarting..."
    if [ "$RESTART_COUNT" -lt "$MAX_RESTART_COUNT" ]; then
        sudo systemctl restart "$SERVICE"
        echo "$((RESTART_COUNT + 1))" > "$RESTART_COUNT_FILE"
        log "Restart #$((RESTART_COUNT + 1)) triggered."
    else
        log "CRITICAL: Too many restarts today ($RESTART_COUNT). Manual intervention needed."
    fi
    exit 1
fi

# Check 2: Is the health endpoint responding?
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    log "Health check FAILED (HTTP $HTTP_CODE). Restarting..."
    if [ "$RESTART_COUNT" -lt "$MAX_RESTART_COUNT" ]; then
        sudo systemctl restart "$SERVICE"
        echo "$((RESTART_COUNT + 1))" > "$RESTART_COUNT_FILE"
        log "Restart #$((RESTART_COUNT + 1)) triggered (health failure)."
    else
        log "CRITICAL: Too many restarts today. HTTP=$HTTP_CODE"
    fi
    exit 1
fi

# Check 3: Memory usage — restart if >80% of system RAM
MEM_PERCENT=$(ps -o %mem= -p $(pgrep -f "python.*main.py" | head -1) 2>/dev/null || echo "0")
MEM_INT=${MEM_PERCENT%.*}
if [ "${MEM_INT:-0}" -gt 80 ]; then
    log "Memory usage too high (${MEM_PERCENT}%). Restarting..."
    sudo systemctl restart "$SERVICE"
    echo "$((RESTART_COUNT + 1))" > "$RESTART_COUNT_FILE"
    exit 1
fi

log "OK — service healthy, HTTP=$HTTP_CODE, MEM=${MEM_PERCENT}%"
