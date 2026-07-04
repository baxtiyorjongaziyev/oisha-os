#!/bin/bash
# Oisha Admin Dashboard — oisha.jonbranding.uz uchun to'liq server sozlash
# Oracle jon-free-micro (Ubuntu 24.04, 1GB RAM + 2GB swap) uchun mo'ljallangan.
#
# Ishlatish (serverda, ubuntu user sifatida):
#   export ADMIN_USER=oisha ADMIN_PASS='kuchli-parol' CERTBOT_EMAIL=you@example.com
#   bash deploy/oracle-web-setup.sh
#
# Ixtiyoriy: OISHA_BRANCH (default: refactor/architecture-cleanup)

set -euo pipefail

DOMAIN="oisha.jonbranding.uz"
OISHA_DIR="/home/ubuntu/oisha-os"
BRANCH="${OISHA_BRANCH:-refactor/architecture-cleanup}"
ADMIN_USER="${ADMIN_USER:-oisha}"
ADMIN_PASS="${ADMIN_PASS:-}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

if [ -z "$ADMIN_PASS" ]; then
    echo "XATO: ADMIN_PASS o'rnatilmagan. Basic auth paroli majburiy."
    echo "  export ADMIN_USER=oisha ADMIN_PASS='kuchli-parol'"
    exit 1
fi

echo "=== [1/8] Sistem paketlari ==="
sudo apt-get update -qq
sudo apt-get install -y -qq nginx certbot python3-certbot-nginx apache2-utils git curl

echo "=== [2/8] Node.js 22 + pnpm ==="
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -c2-3)" -lt 20 ]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
fi
sudo corepack enable 2>/dev/null || sudo npm install -g pnpm
command -v pnpm >/dev/null || { echo "XATO: pnpm o'rnatilmadi"; exit 1; }
sudo ln -sf "$(command -v pnpm)" /usr/local/bin/pnpm

echo "=== [3/8] Repo: $BRANCH ==="
if [ ! -d "$OISHA_DIR" ]; then
    git clone https://github.com/baxtiyorjongaziyev/oisha-os.git "$OISHA_DIR"
fi
cd "$OISHA_DIR"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "=== [4/8] Python bot (oisha-os.service) ==="
if ! systemctl list-unit-files | grep -q '^oisha-os.service'; then
    bash deploy/oracle-setup.sh
else
    ./venv/bin/pip install -q -r requirements.txt 2>/dev/null || {
        python3.12 -m venv venv && ./venv/bin/pip install -q -r requirements.txt
    }
fi

if [ ! -f "$OISHA_DIR/.env" ]; then
    cat > "$OISHA_DIR/.env" <<'ENVFILE'
# TO'LDIRING: eski serverdan .env'ni ko'chiring yoki GitHub secrets'dan oling
BOT_TOKEN=
API_ID=
API_HASH=
GEMINI_API_KEY=
AMOCRM_SUBDOMAIN=jonbrandingagency
AMOCRM_CLIENT_ID=
AMOCRM_CLIENT_SECRET=
AMOCRM_REDIRECT_URL=https://localhost
TURSO_DATABASE_URL=
TURSO_AUTH_TOKEN=
AIRTABLE_API_KEY=
AIRTABLE_BASE_ID=app8xoyx1XCumYFXV
OWNER_ID=150074828
OISHA_RUNTIME=vm_service
SESSION_MODE=file
ENABLE_AUTO_REPLY=false
ALLOWED_ORIGINS=https://oisha.jonbranding.uz
ENVFILE
    echo "!!! $OISHA_DIR/.env yaratildi — secretlarni TO'LDIRING, keyin:"
    echo "    sudo systemctl restart oisha-os"
fi

echo "=== [5/8] Web app build (NEXT_PUBLIC_API_URL=https://$DOMAIN/api/v1) ==="
cd "$OISHA_DIR/salescoach-ai"
# 1GB RAM: heap cheklovi + swap bilan build (sekin, lekin ishlaydi)
export NODE_OPTIONS=--max-old-space-size=1536
export NEXT_TELEMETRY_DISABLED=1
pnpm install --frozen-lockfile --filter @salescoach/web... 2>/dev/null || pnpm install --filter @salescoach/web...
NEXT_PUBLIC_API_URL="https://$DOMAIN/api/v1" pnpm --filter @salescoach/web run build

echo "=== [6/8] systemd: oisha-web.service ==="
sudo cp "$OISHA_DIR/deploy/oisha-web.service" /etc/systemd/system/oisha-web.service
sudo systemctl daemon-reload
sudo systemctl enable oisha-web
sudo systemctl restart oisha-web

echo "=== [7/8] nginx + basic auth ==="
sudo htpasswd -bc /etc/nginx/.htpasswd-oisha "$ADMIN_USER" "$ADMIN_PASS"
sudo cp "$OISHA_DIR/deploy/nginx-oisha.conf" /etc/nginx/sites-available/oisha
sudo ln -sf /etc/nginx/sites-available/oisha /etc/nginx/sites-enabled/oisha
sudo nginx -t
sudo systemctl reload nginx

echo "=== [8/8] HTTPS (Let's Encrypt) ==="
if [ -n "$CERTBOT_EMAIL" ]; then
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$CERTBOT_EMAIL" --redirect
else
    echo "CERTBOT_EMAIL berilmagan — HTTPS'ni keyin qo'lda yoqing:"
    echo "  sudo certbot --nginx -d $DOMAIN --redirect"
fi

echo ""
echo "=== TAYYOR ==="
echo "Web:     https://$DOMAIN  (basic auth: $ADMIN_USER)"
echo "API:     https://$DOMAIN/api/v1/admin/dashboard/stats"
echo "Health:  https://$DOMAIN/healthz (auth'siz)"
echo ""
echo "Tekshirish:"
echo "  sudo systemctl status oisha-web oisha-os nginx --no-pager"
echo "  sudo journalctl -u oisha-web -n 30 --no-pager"
echo "  curl -s -u $ADMIN_USER:*** https://$DOMAIN/api/v1/admin/dashboard/stats"
