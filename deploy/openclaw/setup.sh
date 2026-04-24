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
    echo "[OK] OpenClaw: $(openclaw --version 2>/dev/null || echo 'noma`lum')"
fi

# ── 3. Workspace yaratish ─────────────────────────────────────────────────────
echo "[...] Workspace sozlanmoqda: $WORKSPACE"
mkdir -p "$WORKSPACE/skills/oisha-crm"
mkdir -p "$WORKSPACE/skills/oisha-web"

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
    OC_SECRET="${OPENCLAW_SECRET:-$(openssl rand -hex 32)}"

    sed \
      -e "s|~/.openclaw/workspace/oisha|$WORKSPACE|g" \
      "$OPENCLAW_DIR/openclaw.json" > "$OPENCLAW_CONFIG"

    echo "[OK] openclaw.json yaratildi: $OPENCLAW_CONFIG"
    echo ""
    echo "[MUHIM] Quyidagi muhit o'zgaruvchilarini .env ga qo'shing:"
    echo "  GEMINI_API_KEY=<Google AI Studio dan oling>"
    echo "  OPENCLAW_SECRET=$OC_SECRET"
    echo "  OISHA_API_URL=https://your-service.run.app"
    echo "  TELEGRAM_BOT_TOKEN=<ixtiyoriy>"
else
    echo "[OK] openclaw.json allaqachon mavjud: $OPENCLAW_CONFIG"
fi

# ── 5. Auth profiles ──────────────────────────────────────────────────────────
AUTH_FILE="$HOME/.openclaw/agents/main/agent/auth-profiles.json"
mkdir -p "$(dirname "$AUTH_FILE")"

if [ ! -f "$AUTH_FILE" ] && [ -n "${GEMINI_API_KEY:-}" ]; then
    cat > "$AUTH_FILE" <<EOF
{
  "profiles": {
    "default": {
      "providers": {
        "google": {
          "apiKey": "${GEMINI_API_KEY}"
        }
      }
    }
  },
  "default": "default"
}
EOF
    echo "[OK] auth-profiles.json yaratildi (Gemini)"
fi

# ── 6. Config tekshiruvi ──────────────────────────────────────────────────────
echo ""
echo "[...] Config tekshirilmoqda..."
openclaw config validate 2>&1 && echo "[OK] Config valid" || echo "[OGOHLANTIRISH] Config muammosi bor"

# ── 7. Oisha-OS API server ────────────────────────────────────────────────────
echo ""
OISHA_URL="${OISHA_API_URL:-http://localhost:8080}"
if curl -sf "$OISHA_URL/webhook/openclaw/health" &>/dev/null; then
    echo "[OK] Oisha-OS API ishlayapti: $OISHA_URL"
else
    echo "[OGOHLANTIRISH] Oisha-OS API ishlamayapti ($OISHA_URL)"
    echo "  Avval Oisha-OS ni ishga tushiring:"
    echo "  python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080"
fi

# ── 8. Kanal qo'shish (ixtiyoriy) ────────────────────────────────────────────
echo ""
echo "=== O'rnatish tugadi ==="
echo ""
echo "Gateway ishga tushirish:"
echo "  openclaw gateway --port 18789"
echo ""
echo "Telegram kanali ulash:"
echo "  openclaw channels add telegram --token \$TELEGRAM_BOT_TOKEN"
echo ""
echo "WhatsApp ulash:"
echo "  openclaw channels add whatsapp"
echo ""
echo "Slack ulash:"
echo "  openclaw channels add slack"
echo ""
echo "Agent test:"
echo "  openclaw agent --message 'salom' --session-id oisha-main"
echo ""
echo "Oisha-OS webhook test:"
echo "  curl -X POST $OISHA_URL/webhook/openclaw \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"text\":\"salom\",\"sender\":\"test\",\"sender_id\":\"1\",\"channel\":\"slack\"}'"
