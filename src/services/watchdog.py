import os
import sys
import time
import logging
import requests
import subprocess

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("watchdog.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("Watchdog")

HEALTH_URL = os.environ.get(
    "OISHA_HEALTH_URL",
    f"http://127.0.0.1:{os.environ.get('PORT', '8080')}/healthz/",
)
SERVICE_NAME = os.environ.get("OISHA_SYSTEMD_SERVICE", "oisha-os")
CHECK_INTERVAL = 30  # seconds
FAILURE_THRESHOLD = int(os.environ.get("OISHA_FAILURE_THRESHOLD", "3"))  # consecutive failures before restart
HEALTH_TIMEOUT = float(os.environ.get("OISHA_HEALTH_TIMEOUT", "10"))
STARTUP_GRACE_SECONDS = int(os.environ.get("OISHA_STARTUP_GRACE_SECONDS", "180"))
RESTART_COUNT_FILE = os.environ.get(
    "OISHA_WATCHDOG_RESTART_COUNT_FILE", "/run/oisha-watchdog-restarts"
)

EXTRA_SERVICES = [
    s.strip()
    for s in os.environ.get(
        "OISHA_WATCHED_SERVICES", "openclaw-gateway,hermes-gateway"
    ).split(",")
    if s.strip()
]
ALERT_COOLDOWN_SECONDS = int(os.environ.get("OISHA_ALERT_COOLDOWN", "600"))
_last_alert: dict = {}


def send_alert(key: str, text: str) -> None:
    """Telegramʼga ownerʼga xabar yuboradi (BOT_TOKEN/OWNER_ID boʼlmasa no-op)."""
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("OWNER_ID")
    if not token or not chat_id:
        return
    now = time.time()
    if now - _last_alert.get(key, 0) < ALERT_COOLDOWN_SECONDS:
        return
    _last_alert[key] = now
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Alert send failed: {e}")


def check_extra_services() -> None:
    """Qoʼshimcha servislar (OpenClaw, Hermes) yiqilgan boʼlsa qayta koʼtaradi."""
    if os.name == "nt":
        return
    for name in EXTRA_SERVICES:
        try:
            res = subprocess.run(
                ["systemctl", "is-active", name],
                capture_output=True, text=True, timeout=10,
            )
            if res.stdout.strip() == "active":
                continue
            logger.warning(f"{name} is {res.stdout.strip() or 'unknown'}; restarting")
            subprocess.run(["systemctl", "restart", name], check=True, timeout=60)
            send_alert(name, f"Watchdog: {name} toʼxtagan edi, qayta ishga tushirildi.")
        except Exception as e:
            logger.error(f"Extra service check failed for {name}: {e}")
            send_alert(name + ":fail", f"Watchdog: {name} ni tiklab boʼlmadi: {e}")


def service_uptime_seconds():
    """Return the systemd service process age so boot-time failures are tolerated."""
    if os.name == "nt":
        return None
    try:
        raw_pid = subprocess.check_output(
            ["systemctl", "show", SERVICE_NAME, "--property=MainPID", "--value"],
            text=True,
            timeout=5,
        ).strip()
        pid = int(raw_pid or "0")
        if pid <= 0:
            return None
        return max(0.0, time.time() - os.stat(f"/proc/{pid}").st_ctime)
    except Exception as e:
        logger.debug(f"Could not determine {SERVICE_NAME} uptime: {e}")
        return None

def restart_service():
    logger.warning(f"Triggering systemctl restart {SERVICE_NAME}...")
    try:
        if os.name == 'nt':
            logger.info("Windows detected. No-op for systemctl.")
        else:
            # We are running as root in systemd, so we can directly run systemctl
            subprocess.run(["systemctl", "restart", SERVICE_NAME], check=True)
            logger.info(f"systemctl restart {SERVICE_NAME} executed successfully.")
            send_alert(
                SERVICE_NAME,
                f"Watchdog: {SERVICE_NAME} healthz javob bermadi, qayta ishga tushirildi.",
            )
            # Record restart count
            try:
                count = 0
                if os.path.exists(RESTART_COUNT_FILE):
                    with open(RESTART_COUNT_FILE, "r") as f:
                        count = int(f.read().strip() or "0")
                with open(RESTART_COUNT_FILE, "w") as f:
                    f.write(str(count + 1))
            except Exception as e:
                logger.error(f"Failed to update restart count file: {e}")
    except Exception as e:
        logger.error(f"Failed to restart service: {e}")

def check_health() -> bool:
    try:
        response = requests.get(HEALTH_URL, timeout=HEALTH_TIMEOUT)
        if response.status_code == 200:
            logger.info(f"Health check OK: {response.status_code}")
            return True
        else:
            logger.warning(f"Health check returned non-200: {response.status_code}")
            return False
    except Exception as e:
        logger.warning(f"Health check request failed: {e}")
        return False

def main():
    logger.info(f"Oisha-OS Self-Healing Watchdog active. Target: {HEALTH_URL}")
    consecutive_failures = 0
    
    while True:
        try:
            check_extra_services()
            if check_health():
                consecutive_failures = 0
            else:
                uptime = service_uptime_seconds()
                if uptime is not None and uptime < STARTUP_GRACE_SECONDS:
                    logger.info(
                        "Health check failed during startup grace: "
                        f"{uptime:.0f}s/{STARTUP_GRACE_SECONDS}s"
                    )
                    consecutive_failures = 0
                    time.sleep(CHECK_INTERVAL)
                    continue
                consecutive_failures += 1
                logger.warning(f"Consecutive health failures: {consecutive_failures}/{FAILURE_THRESHOLD}")
                if consecutive_failures >= FAILURE_THRESHOLD:
                    restart_service()
                    consecutive_failures = 0
                    # Sleep a bit longer after restart to let the service boot
                    time.sleep(60)
                    continue
            
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Watchdog shutting down.")
            break
        except Exception as e:
            logger.error(f"Watchdog main loop exception: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
