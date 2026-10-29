#!/bin/bash
set -euo pipefail

DOMAIN="crm.jonbranding.uz"
CONF_FILE="/etc/nginx/sites-available/crm.jonbranding.uz.conf"
LINK_FILE="/etc/nginx/sites-enabled/crm.jonbranding.uz.conf"

echo "=========================================="
echo "  crm.jonbranding.uz — Nginx & SSL Setup  "
echo "=========================================="

# 1. Nginx o'rnatilganligini tekshirish
if ! command -v nginx >/dev/null 2>&1; then
    echo "Nginx topilmadi. O'rnatilmoqda..."
    sudo apt update && sudo apt install -y nginx
fi

# 2. Vhost konfiguratsiyasini yozish
echo "1. Nginx vhost konfiguratsiyasi yaratilmoqda: $CONF_FILE"
sudo tee "$CONF_FILE" > /dev/null << 'EOF'
upstream oisha_web_crm {
    server 127.0.0.1:3000;
    keepalive 32;
}

upstream oisha_api_crm {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name crm.jonbranding.uz;

    client_max_body_size 50m;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 512;
    gzip_types text/plain text/css text/xml application/javascript application/json application/xml image/svg+xml;

    # Asosiy URL ochilganda to'g'ridan-to'g'ri CRM voronkasiga yo'naltirish
    location = / {
        return 302 /crm;
    }

    # API so'rovlari
    location /api/ {
        proxy_pass http://oisha_api_crm;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # Health check
    location ~ ^/(healthz|readyz)/?$ {
        proxy_pass http://oisha_api_crm;
        proxy_set_header Host $host;
    }

    # Next.js static assetlar
    location /_next/static/ {
        proxy_pass http://oisha_web_crm;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        expires 365d;
        add_header Cache-Control "public, immutable";
    }

    # CRM Web interfeysi
    location / {
        proxy_pass http://oisha_web_crm;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
EOF

# 3. Faollashtirish (symlink)
echo "2. Konfiguratsiya faollashtirilmoqda..."
sudo ln -sf "$CONF_FILE" "$LINK_FILE"

# 4. Sintaksisni tekshirish
echo "3. Nginx sintaksisi tekshirilmoqda..."
sudo nginx -t

# 5. Nginx qayta yuklash
echo "4. Nginx qayta yuklanmoqda..."
sudo systemctl reload nginx

# 6. SSL olish (Certbot)
echo "5. Let's Encrypt SSL sertifikati olinmoqda..."
if ! command -v certbot >/dev/null 2>&1; then
    echo "Certbot o'rnatilmoqda..."
    sudo apt update && sudo apt install -y certbot python3-certbot-nginx
fi

echo "Certbot bilan SSL sozlanmoqda..."
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m baxtiyorjongaziyev@gmail.com || {
    echo ""
    echo "[DIQQAT] Certbot hali SSL ololmadi, chunki DNS A yozuvi (crm -> 109.199.100.137) hali to'liq tarqalmagan bo'lishi mumkin."
    echo "Cloudflare'da A yozuvni qo'shgach, quyidagi buyruqni qayta ishga tushiring:"
    echo "  sudo certbot --nginx -d $DOMAIN --agree-tos -m baxtiyorjongaziyev@gmail.com"
}

echo ""
echo "=========================================="
echo "  Muvaffaqiyatli yakunlandi!              "
echo "  Sayt: http://$DOMAIN (yoki https://$DOMAIN) "
echo "=========================================="
