#!/usr/bin/env bash
set -euo pipefail

OISHA_DIR="${OISHA_DIR:-/home/ubuntu/oisha-os}"
ENV_FILE="$OISHA_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Oisha .env topilmadi" >&2
  exit 1
fi

"$OISHA_DIR/venv/bin/python" - "$ENV_FILE" <<'PY'
import sys
from dotenv import dotenv_values

values = dotenv_values(sys.argv[1])
dedicated = (values.get("TELEGRAM_MCP_SESSION_STRING") or "").strip()
production = (values.get("USERBOT_SESSION_STRING") or "").strip()
if not dedicated:
    raise SystemExit("TELEGRAM_MCP_SESSION_STRING kiritilmagan")
if production and dedicated == production:
    raise SystemExit("MCP session production userbot sessionidan alohida bo'lishi shart")
PY

sudo install -m 0644 \
  "$OISHA_DIR/deploy/systemd/telegram-mcp-upstream.service" \
  /etc/systemd/system/telegram-mcp-upstream.service
sudo install -m 0644 \
  "$OISHA_DIR/deploy/systemd/oisha-telegram-mcp-gateway.service" \
  /etc/systemd/system/oisha-telegram-mcp-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable telegram-mcp-upstream.service oisha-telegram-mcp-gateway.service
sudo systemctl restart telegram-mcp-upstream.service oisha-telegram-mcp-gateway.service
sudo systemctl --no-pager --full status \
  telegram-mcp-upstream.service oisha-telegram-mcp-gateway.service
