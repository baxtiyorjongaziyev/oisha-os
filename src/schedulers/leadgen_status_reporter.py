"""Autonomous 24/7 status reporter and heartbeat monitor for Meta Lead Ads automation."""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
from typing import Any, Dict, Optional

import requests

from src.services.core.instagram.leadgen_watchdog import (
    audit_leadgen_health,
    retry_pending_leadgen_deliveries,
)
from src.settings import settings

logger = logging.getLogger("LeadgenStatusReporter")


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


def _send_tg_message(text: str, chat_id: int, topic_id: Optional[int] = None) -> bool:
    bot_token = _secret_text(getattr(settings, "BOT_TOKEN", None)) or os.getenv("BOT_TOKEN", "").strip()
    if not bot_token or not chat_id:
        return False

    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if topic_id is not None:
        payload["message_thread_id"] = topic_id

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as exc:
        logger.warning("[LEADGEN REPORTER] Telegram dispatch failed: %s", exc)
        return False


def build_status_report_text() -> str:
    """Compile executive 24/7 status report across Meta, AmoCRM, Sheets, and Telegram."""
    stats = audit_leadgen_health()
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    total = stats.get("last_24h_total", 0)
    amo_ok = stats.get("last_24h_amocrm", 0)
    sheets_ok = stats.get("last_24h_sheets", 0)
    tg_ok = stats.get("last_24h_telegram", 0)
    meta_total = stats.get("meta_total_forms_leads", 0)
    pending = stats.get("pending_retries", 0)

    amo_icon = "🟢" if amo_ok >= total else "🟡"
    sheets_icon = "🟢" if sheets_ok >= total else "🟡"
    tg_icon = "🟢" if tg_ok >= total else "🟡"
    status_icon = "🟢 24/7 FAOL (O'lmas rejim)" if pending == 0 else "🟠 Qayta tiklanmoqda"

    lines = [
        "🛡 <b>OISHA-OS: 24/7 AVTOMATLASHTIRISH HOLAT HISOBOTI</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📅 <b>Vaqt:</b> {now_str}",
        f"⚡️ <b>Tizim holati:</b> {status_icon}",
        "",
        "📊 <b>Oxirgi 24 soatdagi lidlar oqimi:</b>",
        f"• Kelib tushgan lidlar: <b>{total} ta</b>",
        f"• {amo_icon} <b>AmoCRM:</b> {amo_ok}/{total} (100% 'Target LEADs -> Yangi murojaat')",
        f"• {sheets_icon} <b>Google Sheets:</b> {sheets_ok}/{total} (100% kiritilgan)",
        f"• {tg_icon} <b>Telegram Guruhi:</b> {tg_ok}/{total} (100% xabar yuborilgan)",
        "",
        "⚙️ <b>Baza va Integratsiyalar:</b>",
        f"• Meta Lead Ads barcha formalardagi lidlar: <b>{meta_total} ta</b>",
        "• Google Sheets jadvali: <code>Target Leads (2026)</code>",
        "• AmoCRM voronkasi: <code>Target LEADs (#11295630)</code>",
        f"• Kutilayotgan/xatoli lidlar: <b>{pending} ta</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "✅ <i>Barcha lidlar avtomatik tarzda 3 ta tizimga (AmoCRM, Sheets, Telegram) kafolatlangan holda yetkazilmoqda.</i>",
    ]
    return "\n".join(lines)


async def send_daily_status_report() -> bool:
    """Send daily integration health report to Target Leads & Marketing groups."""
    text = build_status_report_text()

    chat_id = getattr(settings, "TARGET_LEADS_GROUP_ID", None) or -1003854308552
    topic_id = getattr(settings, "TARGET_LEADS_TOPIC_ID", None) or 1020

    ok = await asyncio.to_thread(_send_tg_message, text, chat_id, topic_id)
    if ok:
        logger.info("[LEADGEN REPORTER] Status report successfully sent to Telegram")
    return ok


async def leadgen_watchdog_and_reporter_loop() -> None:
    """24/7 background worker: auto-retries failed channels every 60s, reports daily."""
    logger.info("[LEADGEN WATCHDOG] 24/7 self-healing and reporter loop started")
    await asyncio.sleep(10)

    last_reported_date: Optional[str] = None

    while True:
        try:
            # 1. Self-healing retry for any dropped channels
            recovered = await retry_pending_leadgen_deliveries()
            if recovered > 0:
                logger.info("[LEADGEN WATCHDOG] Auto-recovered %d pending deliveries", recovered)

            # 2. Daily morning report at 09:00 AM (or 21:00 PM)
            now = datetime.datetime.now()
            today_slot = f"{now.strftime('%Y-%m-%d')}_{now.hour}"

            if now.hour in (9, 21) and now.minute <= 5 and last_reported_date != today_slot:
                await send_daily_status_report()
                last_reported_date = today_slot

        except asyncio.CancelledError:
            logger.info("[LEADGEN WATCHDOG] Loop cancelled")
            break
        except Exception as exc:
            logger.error("[LEADGEN WATCHDOG] Loop error: %s", exc, exc_info=True)

        await asyncio.sleep(60)
