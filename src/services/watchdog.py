
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
OWNER_ID = os.getenv("OWNER_ID", "5824905101")
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
        if os.name == 'nt': # Windows
            output = subprocess.check_output(["tasklist", "/FI", f"IMAGENAME eq python.exe", "/FO", "CSV"])
            # Checking if python is running and script name is in command line is harder on Windows without psutil,
            # but we can check if it exists in the output as a simple check.
            return BOT_SCRIPT in output.decode() or "python" in output.decode().lower()
        else: # Linux/Mac
            output = subprocess.check_output(["ps", "aux"])
            return BOT_SCRIPT in output.decode()
    except:
        return False

def get_python_executable():
    """Find the best python executable path."""
    paths = [
        ".venv_oi/Scripts/python.exe", # Windows specific
        "venv/Scripts/python.exe",     # Windows alternative
        ".venv/Scripts/python.exe",    # The broken one (fallback)
        ".venv_oi/bin/python3",        # Linux specific
        "venv/bin/python3",            # Linux alternative
        "python",                      # System fallback
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return "python"

def restart_bot():
    logger.info("Restarting bot...")
    python_exe = get_python_executable()
    try:
        # Kill existing if any
        if os.name == 'nt':
            # On Windows, pkill doesn't exist. We use taskkill.
            # However, taskkill /F /IM python.exe might kill EVERYTHING.
            # It's better to just try starting it or use a more specific method.
            pass 
        else:
            os.system(f"pkill -f {BOT_SCRIPT}")
            
        # Start new
        subprocess.Popen([python_exe, BOT_SCRIPT], stdout=open(LOG_FILE, "a"), stderr=subprocess.STDOUT)
        logger.info(f"Bot restarted successfully using {python_exe}.")
        send_to_owner(f"✅ Botda xatolik aniqlandi va u avtomatik qayta ishga tushirildi (Using {python_exe}).")
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
