
import os
import time
import subprocess
import logging
import requests
from datetime import datetime

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    filename="watchdog.log",
    filemode="a"
)
logger = logging.getLogger("Watchdog")

# Config
BOT_SCRIPT = "userbot.py"
LOG_FILE = "userbot.log"
CHECK_INTERVAL = 30 # seconds
OWNER_ID = "5824905101"
BOT_TOKEN = os.getenv("BOT_TOKEN")

def send_to_owner(message):
    if not BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": OWNER_ID,
            "text": f"🛡️ **WATCHDOG ALERT**\n\n{message}",
            "parse_mode": "Markdown"
        })
    except Exception as e:
        logger.error(f"Failed to notify owner: {e}")

def is_bot_running():
    try:
        output = subprocess.check_output(["ps", "aux"])
        return BOT_SCRIPT in output.decode()
    except:
        return False

def restart_bot():
    logger.info("Restarting bot...")
    try:
        # Kill existing if any
        os.system(f"pkill -f {BOT_SCRIPT}")
        # Start new
        subprocess.Popen(["./venv/bin/python3", BOT_SCRIPT], stdout=open(LOG_FILE, "a"), stderr=subprocess.STDOUT)
        logger.info("Bot restarted successfully.")
        send_to_owner("✅ Botda xatolik aniqlandi va u avtomatik qayta ishga tushirildi (Self-Healing).")
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        send_to_owner(f"❌ Botni restart qilishda xatolik: {e}")

def monitor_logs():
    last_size = os.path.getsize(LOG_FILE) if os.path.exists(LOG_FILE) else 0
    
    while True:
        try:
            # 1. Process tekshiruvi
            if not is_bot_running():
                logger.warning("Bot is not running! Triggering restart...")
                restart_bot()
            
            # 2. Log tahlili (Xatoliklarni qidirish)
            if os.path.exists(LOG_FILE):
                current_size = os.path.getsize(LOG_FILE)
                if current_size > last_size:
                    with open(LOG_FILE, "r") as f:
                        f.seek(last_size)
                        new_content = f.read()
                        if "Traceback" in new_content or "ERROR" in new_content:
                            # Faqat bitta xatolik qismini olish
                            error_lines = [line for line in new_content.split("\n") if "Traceback" in line or "ERROR" in line]
                            if error_lines:
                                logger.error(f"Error detected in logs: {error_lines[0]}")
                                send_to_owner(f"⚠️ **Xatolik aniqlandi:**\n`{error_lines[0][:200]}`\n\nAntigravity (AI) buni ko'rib chiqmoqda...")
                    last_size = current_size
            
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Watchdog loop error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    logger.info("Self-Healing Watchdog started.")
    monitor_logs()
