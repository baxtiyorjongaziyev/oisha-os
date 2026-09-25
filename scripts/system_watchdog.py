#!/usr/bin/env python3
"""External 24/7 Watchdog Monitor & Self-Healing Agent.

Runs every 2 minutes via cron or systemd timer to verify:
1. oisha-leads.service (Dedicated Lead Ads worker)
2. oisha-os.service (Userbot & AI Engine)
3. HTTP /healthz/ endpoint
4. Leadgen heartbeat freshness

Automatically auto-restarts failed services and dispatches instant Telegram SOS alerts.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import requests

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG-MONITOR] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("WatchdogMonitor")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROUP_ID = os.getenv("TARGET_LEADS_GROUP_ID", "-1003854308552").strip()
TOPIC_ID = os.getenv("TARGET_LEADS_TOPIC_ID", "1020").strip()
HEARTBEAT_FILE = _ROOT / "data" / "leadgen_heartbeat.json"


def send_sos_telegram(alert_title: str, details: str) -> None:
    """Send immediate high-priority SOS alert to management/leads topic."""
    if not BOT_TOKEN or not GROUP_ID:
        logger.warning("Telegram alert skipped: missing BOT_TOKEN or GROUP_ID")
        return

    text = (
        f"🚨 <b>[OISHA TIZIM SOS OGOHLANTIRISH]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Holat:</b> {alert_title}\n"
        f"📝 <b>Tafsilot:</b>\n<code>{details}</code>\n"
        f"⏰ <b>Vaqt:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 <i>Avtomatik tuzatish mexanizmi ishga tushirildi.</i>"
    )
    payload = {
        "chat_id": GROUP_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if TOPIC_ID:
        try:
            payload["message_thread_id"] = int(TOPIC_ID)
        except ValueError:
            pass

    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10)
    except Exception as exc:
        logger.error("Failed to send SOS alert: %s", exc)


def is_service_active(service_name: str) -> bool:
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return res.stdout.strip() == "active"
    except Exception as exc:
        logger.error("Error checking service %s: %s", service_name, exc)
        return False


def restart_service(service_name: str) -> bool:
    logger.warning("Attempting auto-restart for %s...", service_name)
    try:
        res = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return res.returncode == 0
    except Exception as exc:
        logger.error("Error restarting %s: %s", service_name, exc)
        return False


def check_health_endpoint() -> bool:
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/healthz/")
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            return resp.status == 200
    except Exception as exc:
        logger.warning("HTTP healthcheck error: %s", exc)
        return False


def check_leadgen_heartbeat() -> tuple[bool, str]:
    if not HEARTBEAT_FILE.exists():
        return False, "Heartbeat file not found"
    try:
        data = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
        ts_str = data.get("timestamp")
        if not ts_str:
            return False, "Timestamp missing"
        last_dt = datetime.datetime.fromisoformat(ts_str)
        diff = (datetime.datetime.now() - last_dt).total_seconds()
        if diff > 180:  # More than 3 minutes stale
            return False, f"Heartbeat stale ({int(diff)}s old)"
        return True, "Heartbeat healthy"
    except Exception as exc:
        return False, f"Heartbeat parse error: {exc}"


def get_service_uptime_sec(service_name: str) -> int:
    """Return process uptime in seconds to respect warmup phases."""
    try:
        pid_res = subprocess.run(
            ["systemctl", "show", "-p", "MainPID", "--value", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pid = pid_res.stdout.strip()
        if not pid or pid == "0":
            return 0
        ps_res = subprocess.run(
            ["ps", "-p", pid, "-o", "etimes="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(ps_res.stdout.strip() or "0")
    except Exception:
        return 999


def main() -> None:
    logger.info("Executing periodic watchdog check...")

    # 1. Check Leads Dedicated Service
    if not is_service_active("oisha-leads.service"):
        logger.error("oisha-leads.service is INACTIVE!")
        send_sos_telegram(
            "oisha-leads.service to'xtab qolgan!",
            "Lidlar konveyeri to'xtab qolgan. Avtomatik qayta ishga tushirilmoqda...",
        )
        restart_service("oisha-leads.service")
    else:
        # Check heartbeat
        hb_ok, hb_msg = check_leadgen_heartbeat()
        if not hb_ok:
            logger.warning("Leadgen heartbeat check failed: %s", hb_msg)
            send_sos_telegram(
                "Lidlar konveyeri qotib qolgan (Stale Heartbeat)!",
                f"{hb_msg}. Xizmat qayta yuklanmoqda...",
            )
            restart_service("oisha-leads.service")

    # 2. Check Oisha-OS Main Service
    if not is_service_active("oisha-os.service"):
        logger.error("oisha-os.service is INACTIVE!")
        send_sos_telegram(
            "oisha-os.service to'xtab qolgan!",
            "Asosiy userbot xizmati faol emas. Avtomatik qayta ishga tushirilmoqda...",
        )
        restart_service("oisha-os.service")
    else:
        # Check uptime to respect initial warmup (Telethon & Turso init)
        uptime = get_service_uptime_sec("oisha-os.service")
        if uptime < 180:
            logger.info("oisha-os.service is warming up (%d seconds old), skipping healthcheck", uptime)
        else:
            # Check HTTP health with 3 spaced retries (15s timeout each)
            if not check_health_endpoint():
                logger.warning("HTTP healthcheck 8080 probe 1 failed, waiting 15s...")
                import time
                time.sleep(15)
                if not check_health_endpoint():
                    logger.warning("HTTP healthcheck 8080 probe 2 failed, waiting 15s...")
                    time.sleep(15)
                    if not check_health_endpoint():
                        logger.error("HTTP healthcheck 8080 failed 3 consecutive times!")
                        send_sos_telegram(
                            "oisha-os.service /healthz javob bermayapti!",
                            "FastAPI porti 8080 ketma-ket 3 marta (45 soniya) javob bermadi. Servis qayta yuklanmoqda...",
                        )
                        if restart_service("oisha-os.service"):
                            time.sleep(30)
                            if check_health_endpoint():
                                send_sos_telegram(
                                    "✅ oisha-os.service muvaffaqiyatli tiklandi",
                                    "Tizim to'liq tiklandi va /healthz 200 OK qaytarmoqda.",
                                )

    logger.info("Watchdog monitor check completed successfully.")


if __name__ == "__main__":
    main()
