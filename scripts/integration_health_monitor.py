#!/usr/bin/env python
"""
Integratsiya sog'lomligini monitoring qiluvchi skript.
AmoCRM, Google Sheets, Telegram Bot va Meta/Instagram Lead Ads holatini tekshiradi.
Muvaffaqiyatsizlik yoki xatolik yuz berganda Telegram va Discord orqali ogohlantiradi.

Ishga tushirish:
    python -m scripts.integration_health_monitor [--alert-always]
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("HealthMonitor")

DEFAULT_GSHEET_ID = "1aWmfomtd2x4QoHQIWLPD88lHbepIRvuPhzuugM7-vEc"
DEFAULT_TIMEOUT = 15


def _get_telegram_config() -> Tuple[str, str, str]:
    """Telegram bot token, chat_id va topic_id ni qaytaradi."""
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    chat_id = os.getenv("TARGET_LEADS_GROUP_ID") or os.getenv("TELEGRAM_ALERT_CHAT_ID") or "-1003854308552"
    topic_id = os.getenv("TARGET_LEADS_TOPIC_ID") or "1020"
    return token.strip(), chat_id.strip(), topic_id.strip()


def send_telegram_alert(message: str) -> bool:
    """Telegram orqali ogohlantirish yuborish."""
    token, chat_id, topic_id = _get_telegram_config()
    if not token or not chat_id:
        logger.warning("[TG] Bot token yoki chat ID topilmadi, xabar yuborilmadi.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if topic_id:
        try:
            payload["message_thread_id"] = int(topic_id)
        except ValueError:
            pass

    try:
        resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        logger.info("[TG] Ogohlantirish muvaffaqiyatli yuborildi.")
        return True
    except Exception as exc:
        logger.error(f"[TG] Xabar yuborishda xatolik: {exc}")
        return False


def send_discord_alert(message: str) -> bool:
    """Discord webhook orqali ogohlantirish yuborish."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        logger.debug("[Discord] Webhook URL mavjud emas, o'tkazib yuborildi.")
        return False

    clean_text = message.replace("<b>", "**").replace("</b>", "**")
    clean_text = clean_text.replace("<code>", "`").replace("</code>", "`")
    payload = {"content": clean_text}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        logger.info("[Discord] Ogohlantirish muvaffaqiyatli yuborildi.")
        return True
    except Exception as exc:
        logger.error(f"[Discord] Webhook xatosi: {exc}")
        return False


def check_amocrm() -> Tuple[bool, str]:
    """AmoCRM ulanishini tekshiradi."""
    subdomain = os.getenv("AMOCRM_SUBDOMAIN", "jonbranding").strip()
    url = f"https://{subdomain}.amocrm.ru"
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
        if resp.status_code in (200, 301, 302, 401):
            return True, f"AmoCRM: OK (subdomain: {subdomain}, status {resp.status_code})"
        return False, f"AmoCRM: Xatolik (status {resp.status_code})"
    except Exception as exc:
        return False, f"AmoCRM: Aloqa uzildi ({type(exc).__name__}: {exc})"


def check_google_sheets() -> Tuple[bool, str]:
    """Google Sheets service account va spreadsheet ruxsatini tekshiradi."""
    try:
        from google.oauth2.service_account import Credentials
        import gspread

        creds_path = os.getenv("GSHEET_CREDS_FILE") or "data/service_account.json"
        if not Path(creds_path).exists():
            return False, f"Google Sheets: Kalit fayli topilmadi ({creds_path})"

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or DEFAULT_GSHEET_ID
        sh = client.open_by_key(spreadsheet_id)
        return True, f"Google Sheets: OK ('{sh.title}')"
    except Exception as exc:
        return False, f"Google Sheets: Xatolik ({type(exc).__name__}: {exc})"


def check_telegram_bot() -> Tuple[bool, str]:
    """Telegram Bot API getMe tekshiruvi."""
    token, _, _ = _get_telegram_config()
    if not token:
        return False, "Telegram Bot: BOT_TOKEN aniqlanmagan"
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
        data = resp.json()
        if data.get("ok"):
            bot_user = data.get("result", {}).get("username", "bot")
            return True, f"Telegram Bot: OK (@{bot_user})"
        return False, f"Telegram Bot: API xatosi ({data.get('description')})"
    except Exception as exc:
        return False, f"Telegram Bot: Ulanishda xato ({type(exc).__name__}: {exc})"


def check_meta_leadgen() -> Tuple[bool, str]:
    """Meta Graph API (Instagram Leads) tekshiruvi."""
    token = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("META_PAGE_ID", "103894334533931").strip()
    if not token:
        return False, "Meta/Instagram: META_PAGE_ACCESS_TOKEN aniqlanmagan"

    url = f"https://graph.facebook.com/v19.0/{page_id}?fields=id,name&access_token={token}"
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
        data = resp.json()
        if "error" in data:
            err_msg = data["error"].get("message", "Noma'lum xatolik")
            return False, f"Meta/Instagram: API xatosi ({err_msg})"
        name = data.get("name", page_id)
        return True, f"Meta/Instagram: OK ({name})"
    except Exception as exc:
        return False, f"Meta/Instagram: Ulanishda xato ({type(exc).__name__}: {exc})"


def run_health_checks() -> Tuple[List[str], List[str]]:
    """Barcha tizimlarni tekshirib, muvaffaqiyatli va muammolilar ro'yxatini qaytaradi."""
    successes: List[str] = []
    failures: List[str] = []

    checks = [
        ("AmoCRM", check_amocrm),
        ("GoogleSheets", check_google_sheets),
        ("TelegramBot", check_telegram_bot),
        ("MetaLeadgen", check_meta_leadgen),
    ]

    for name, func in checks:
        ok, detail = func()
        if ok:
            logger.info(f"[PASS] {detail}")
            successes.append(detail)
        else:
            logger.error(f"[FAIL] {detail}")
            failures.append(detail)

    return successes, failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Oisha-OS Integratsiya Monitoringi")
    parser.add_argument("--alert-always", action="store_true", help="Barcha tizimlar sog'lom bo'lsa ham xabar yuborish")
    args = parser.parse_args()

    logger.info("Integratsiya sog'lomligini tekshirish boshlandi...")
    successes, failures = run_health_checks()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if failures:
        msg_lines = [
            "🚨 <b>[OISHA: INTEGRATSIYA SOG'LOMLIGI OGOHLANTIRISHI]</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🕒 <b>Tekshiruv vaqti:</b> <code>{now_str}</code>",
            "",
            "❌ <b>Aniqlangan muammolar:</b>",
        ]
        for f in failures:
            msg_lines.append(f"• <code>{f}</code>")

        if successes:
            msg_lines.extend(["", "✅ <b>Ishlayotgan tizimlar:</b>"])
            for s in successes:
                msg_lines.append(f"• {s}")

        msg_lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "⚠️ <i>Zudlik bilan integratsiya kalitlari va xizmatlarni tekshiring!</i>",
        ])
        alert_text = "\n".join(msg_lines)
        send_telegram_alert(alert_text)
        send_discord_alert(alert_text)
    elif args.alert_always:
        msg_lines = [
            "✅ <b>[OISHA: INTEGRATSIYA STATUSI: HAMMASI SOG'LOM]</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"🕒 <b>Vaqt:</b> <code>{now_str}</code>",
            "",
            "Barcha asosiy integratsiyalar (AmoCRM, Sheets, Telegram, Meta) bekamu-ko'st ishlamoqda.",
        ]
        for s in successes:
            msg_lines.append(f"• {s}")
        alert_text = "\n".join(msg_lines)
        send_telegram_alert(alert_text)
        send_discord_alert(alert_text)
    else:
        logger.info("Barcha integratsiyalar sog'lom. Ogohlantirish talab etilmaydi.")


if __name__ == "__main__":
    main()
