#!/usr/bin/env bash
# Oisha-OS × OpenClaw o'rnatish skripti
# Ishlatish: bash deploy/openclaw/setup.sh

set -euo pipefail

WORKSPACE="$HOME/.openclaw/workspace/oisha"
OPENCLAW_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Oisha-OS × OpenClaw sozlash ==="
echo ""

# ── 1. Node.js tekshiruvi ─────────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "[XATO] Node.js topilmadi. Node 24 (yoki 22.16+) o'rnating:"
    echo "  https://nodejs.org/"
    exit 1
fi
NODE_VER=$(node --version | sed 's/v//')
echo "[OK] Node.js: v$NODE_VER"

# ── 2. OpenClaw o'rnatish ─────────────────────────────────────────────────────
if ! command -v openclaw &>/dev/null; then
    echo "[...] OpenClaw o'rnatilmoqda..."
    npm install -g openclaw@latest
    echo "[OK] OpenClaw o'rnatildi"
else
    echo "[OK] OpenClaw allaqachon o'rnatilgan: $(openclaw --version 2>/dev/null || echo 'noma`lum')"
fi

# ── 3. Workspace yaratish ─────────────────────────────────────────────────────
echo "[...] Workspace sozlanmoqda: $WORKSPACE"
mkdir -p "$WORKSPACE/skills/oisha-crm"
mkdir -p "$WORKSPACE/skills/oisha-web"

# Fayllarni nusxalash
cp "$OPENCLAW_DIR/workspace/SOUL.md"   "$WORKSPACE/SOUL.md"
cp "$OPENCLAW_DIR/workspace/AGENTS.md" "$WORKSPACE/AGENTS.md"
cp "$OPENCLAW_DIR/workspace/skills/oisha-crm/SKILL.md" \
   "$WORKSPACE/skills/oisha-crm/SKILL.md"
cp "$OPENCLAW_DIR/workspace/skills/oisha-web/SKILL.md" \
   "$WORKSPACE/skills/oisha-web/SKILL.md"
echo "[OK] Workspace fayllari ko'chirildi"

# ── 4. openclaw.json sozlash ──────────────────────────────────────────────────
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
mkdir -p "$HOME/.openclaw"

if [ ! -f "$OPENCLAW_CONFIG" ]; then
    # Muhit o'zgaruvchilari o'rniga real qiymatlar bilan config yaratish
    OISHA_URL="${OISHA_API_URL:-http://localhost:8080}"
    OC_SECRET="${OPENCLAW_SECRET:-$(openssl rand -hex 32)}"

    cat > "$OPENCLAW_CONFIG" <<EOF
{
  "agent": {
    "model": "google/gemini-2.0-flash",
    "workspaceRoot": "$WORKSPACE"
  },
  "gateway": {
    "port": 18789,
    "webhook": {
      "url": "$OISHA_URL/webhook/openclaw",
      "secret": "$OC_SECRET",
      "signatureHeader": "x-openclaw-signature"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "${TELEGRAM_BOT_TOKEN:-YOUR_BOT_TOKEN_HERE}",
      "dmPolicy": "open"
    },
    "whatsapp": {
      "enabled": false,
      "dmPolicy": "open"
    },
    "slack": {
      "enabled": false,
      "dmPolicy": "open"
    },
    "discord": {
      "enabled": false,
      "dmPolicy": "open"
    }
  },
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main"
      }
    }
  },
  "skills": ["oisha-crm", "oisha-web"]
}
EOF
    echo "[OK] openclaw.json yaratildi: $OPENCLAW_CONFIG"
    echo ""
    echo "[MUHIM] Quyidagi tokenlarni $OPENCLAW_CONFIG fayliga qo'shing:"
    echo "  - TELEGRAM_BOT_TOKEN"
    echo "  - OISHA_API_URL (masalan: https://your-service.run.app)"
    echo "  - OPENCLAW_SECRET (yaratilgan: $OC_SECRET)"
    echo ""
    echo "  OPENCLAW_SECRET ni .env ga ham qo'shing:"
    echo "  OPENCLAW_SECRET=$OC_SECRET"
else
    echo "[OK] openclaw.json allaqachon mavjud: $OPENCLAW_CONFIG"
fi

# ── 5. Daemon o'rnatish (ixtiyoriy) ──────────────────────────────────────────
echo ""
read -r -p "OpenClaw daemon o'rnatilsinmi? (y/N): " INSTALL_DAEMON
if [[ "$INSTALL_DAEMON" =~ ^[Yy]$ ]]; then
    openclaw onboard --install-daemon
    echo "[OK] Daemon o'rnatildi"
fi

# ── 6. Tekshiruv ─────────────────────────────────────────────────────────────
echo ""
echo "=== O'rnatish tugadi ==="
echo ""
echo "Ishga tushirish:"
echo "  openclaw gateway --port 18789 --verbose"
echo ""
echo "Oisha-OS webhook holati:"
echo "  curl ${OISHA_API_URL:-http://localhost:8080}/webhook/openclaw/health"
echo ""
echo "Kanal ulash (Telegram misol):"
echo "  openclaw channel add telegram --token YOUR_BOT_TOKEN"
echo ""
echo "WhatsApp ulash:"
echo "  openclaw channel add whatsapp"
echo ""
echo "Slack ulash:"
echo "  openclaw channel add slack"
