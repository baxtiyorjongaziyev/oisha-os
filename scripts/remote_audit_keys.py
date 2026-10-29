import os
import requests
from dotenv import dotenv_values

env_path = "/root/oisha-os/.env"
if not os.path.exists(env_path):
    env_path = "/home/ubuntu/oisha-os/.env"

env = dotenv_values(env_path) if os.path.exists(env_path) else {}
print(f"Env file: {env_path} (exists: {os.path.exists(env_path)})")

# 1. Check BOT_TOKEN
bot_token = env.get("BOT_TOKEN", "").strip()
if bot_token:
    try:
        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=5)
        res = r.json()
        print(f"BOT_TOKEN: HTTP {r.status_code}, ok: {res.get('ok')}, username: @{res.get('result', {}).get('username')}, error: {res.get('description')}")
    except Exception as e:
        print(f"BOT_TOKEN check error: {e}")
else:
    print("BOT_TOKEN: MISSING in .env")

# 2. Check GEMINI_API_KEY
gemini_key = env.get("GEMINI_API_KEY", "").strip()
if gemini_key:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
        r = requests.get(url, timeout=5)
        print(f"GEMINI_API_KEY: HTTP {r.status_code}, valid: {r.status_code == 200}")
        if r.status_code != 200:
            print(f"Gemini error: {r.text[:150]}")
    except Exception as e:
        print(f"GEMINI check error: {e}")
else:
    print("GEMINI_API_KEY: MISSING in .env")

# 3. Check MOIZVONKI
mv_email = env.get("MOIZVONKI_EMAIL", "").strip()
mv_key = env.get("MOIZVONKI_API_KEY", "").strip()
mv_sec = env.get("MOIZVONKI_WEBHOOK_SECRET", "").strip()
print(f"MOIZVONKI_EMAIL: exists={bool(mv_email)}")
print(f"MOIZVONKI_API_KEY: exists={bool(mv_key)}")
print(f"MOIZVONKI_WEBHOOK_SECRET: exists={bool(mv_sec)}")

# 4. Check systemd services
for s in ["oisha.service", "oisha-calls-report.service", "oisha-leads.service"]:
    ret = os.system(f"systemctl is-active --quiet {s}")
    print(f"Service {s}: {'ACTIVE' if ret == 0 else 'INACTIVE/FAILED'}")
