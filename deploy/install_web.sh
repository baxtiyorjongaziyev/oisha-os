#!/usr/bin/env bash
set -euo pipefail

# 1. Ensure node is installed
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -c2-3 | tr -d '.')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi

# 2. Extract standalone bundle
sudo systemctl stop oisha-web 2>/dev/null || true
rm -rf /home/ubuntu/oisha-web
mkdir -p /home/ubuntu/oisha-web
tar -xzf /home/ubuntu/oisha-web-bundle.tar.gz -C /home/ubuntu/oisha-web
rm -f /home/ubuntu/oisha-web-bundle.tar.gz

# 3. Setup systemd unit
sudo cp /home/ubuntu/oisha-web.service /etc/systemd/system/oisha-web.service
sudo systemctl daemon-reload
sudo systemctl enable oisha-web
sudo systemctl restart oisha-web

# 4. Setup Caddyfile
sudo cp /home/ubuntu/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 5. Verify local port 3000 and domain
sleep 6
sudo systemctl status oisha-web --no-pager | head -10 || true
curl -s -m 8 -o /dev/null -w 'localhost:3000 -> %{http_code}\n' http://127.0.0.1:3000/ || true
curl -s -m 8 -o /dev/null -w 'https://oisha.jonbranding.uz -> %{http_code}\n' https://oisha.jonbranding.uz/ || true
