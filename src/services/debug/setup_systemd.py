import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=15)
except Exception as e:
    print("Ulanish xatosi:", e)
    sys.exit(1)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

HOME = "/home/baxtiyorjongaziyev"
BOT_DIR = f"{HOME}/telegram_bot"
CF = f"{BOT_DIR}/cloudflared"
CF_TOKEN = "eyJhIjoiZTI5ZmRhMmU2NmUwODkyN2E2NDIzYzJkOGQ3MzIwY2UiLCJ0IjoiZmExY2NiNzMtODhmMC00ZWZmLWE4MTMtMzg0NjNmZGM4NGIxIiwicyI6IlpqaGpOelkzTVdZdFl6VmhOeTAwT1RWbExUaGxZMlF0TlRjeE5qSmxNRFJsTW1GayJ9"
SYSTEMD_DIR = f"{HOME}/.config/systemd/user"

print("1. Systemd user papkasi yaratilmoqda...")
print(run(f"mkdir -p {SYSTEMD_DIR}"))

# ── cloudflared service ──────────────────────────────────────────────────────
CF_SERVICE = f"""[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
ExecStart={CF} tunnel run --token {CF_TOKEN}
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""

print("2. cloudflared.service fayli yozilmoqda...")
run(f"cat > {SYSTEMD_DIR}/cloudflared.service << 'EOF'\n{CF_SERVICE}\nEOF")

# ── meta_webhook service ────────────────────────────────────────────────────
META_SERVICE = f"""[Unit]
Description=JonBranding META Webhook
After=network.target

[Service]
Type=simple
WorkingDirectory={BOT_DIR}
ExecStart={BOT_DIR}/venv/bin/python {BOT_DIR}/meta_webhook.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""

print("3. meta_webhook.service fayli yozilmoqda...")
run(f"cat > {SYSTEMD_DIR}/meta_webhook.service << 'EOF'\n{META_SERVICE}\nEOF")

# ── userbot service ────────────────────────────────────────────────────────
USERBOT_SERVICE = f"""[Unit]
Description=JonBranding Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory={BOT_DIR}
ExecStart={BOT_DIR}/venv/bin/python {BOT_DIR}/userbot.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
"""

print("4. userbot.service fayli yozilmoqda...")
run(f"cat > {SYSTEMD_DIR}/userbot.service << 'EOF'\n{USERBOT_SERVICE}\nEOF")

print("5. loginctl linger yoqilmoqda (server qayta ishlasa user servicelari avtomatik boshlansin)...")
print(run("loginctl enable-linger baxtiyorjongaziyev"))

print("6. Systemd daemon yangilanmoqda va serviceler yoqilmoqda...")
print(run("systemctl --user daemon-reload"))
print(run("systemctl --user enable cloudflared meta_webhook userbot"))

print("7. Eski nohup jarayonlari to'xtatilmoqda...")
run("pkill -f cloudflared; pkill -f meta_webhook.py; pkill -f userbot.py")
time.sleep(3)

print("8. Serviceler ishga tushirilmoqda...")
print(run("systemctl --user start cloudflared"))
time.sleep(2)
print(run("systemctl --user start meta_webhook"))
time.sleep(2)
print(run("systemctl --user start userbot"))
time.sleep(3)

print("9. Holat tekshirilmoqda...")
print(run("systemctl --user status cloudflared --no-pager | head -8"))
print(run("systemctl --user status meta_webhook --no-pager | head -8"))
print(run("systemctl --user status userbot --no-pager | head -8"))

print("10. Health check:")
print(run("curl -s http://localhost:5050/health"))

ssh.close()
print("✅ Barcha serviceler systemd orqali sozlandi!")
