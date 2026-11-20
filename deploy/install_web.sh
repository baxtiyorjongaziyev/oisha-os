#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_PATH="${1:-${HOME}/oisha-web-bundle.tar.gz}"
WEB_DIR="${HOME}/oisha-web"

# 1. Ensure node is installed
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -c2-3 | tr -d '.')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi

# 2. Extract standalone bundle
sudo systemctl stop oisha-web 2>/dev/null || true
rm -rf "$WEB_DIR"
mkdir -p "$WEB_DIR"
tar -xzf "$BUNDLE_PATH" -C "$WEB_DIR"
rm -f "$BUNDLE_PATH"

# 3. Setup systemd unit
sudo cp "${SCRIPT_DIR}/oisha-web.service" /etc/systemd/system/oisha-web.service
sudo systemctl daemon-reload
sudo systemctl enable oisha-web
sudo systemctl restart oisha-web

# 4. Setup Caddyfile only if Caddy is active on this host
if systemctl is-active --quiet caddy; then
  sudo cp "${SCRIPT_DIR}/Caddyfile" /etc/caddy/Caddyfile
  sudo caddy validate --config /etc/caddy/Caddyfile
  sudo systemctl reload caddy
else
  echo "[WEB] Caddy faol emas — Caddyfile bosqichi o'tkazib yuborildi."
fi

# 5. Verify local port 3000 and domain
sleep 6
sudo systemctl status oisha-web --no-pager | head -10 || true
if ! sudo systemctl is-active --quiet oisha-web; then
  echo "XATO: oisha-web servisi ishga tushmadi"
  sudo journalctl -u oisha-web --no-pager -n 40 || true
  exit 1
fi
curl -s -m 8 -o /dev/null -w 'localhost:3000 -> %{http_code}\n' http://127.0.0.1:3000/ || true
curl -s -m 8 -o /dev/null -w 'https://oisha.jonbranding.uz -> %{http_code}\n' https://oisha.jonbranding.uz/ || true
