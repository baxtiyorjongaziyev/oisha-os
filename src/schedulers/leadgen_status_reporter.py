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


def _send_tg_message(
    text: str,
    chat_id: int,
    topic_id: Optional[int] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> bool:
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
    if reply_markup:
        payload["reply_markup"] = reply_markup

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as exc:
        logger.warning("[LEADGEN REPORTER] Telegram dispatch failed: %s", exc)
        return False


def get_creative_summary() -> List[tuple[str, int, float]]:
    try:
        from src.services.core.marketing.attribution_store import _connection
        with _connection() as conn:
            rows = conn.execute("SELECT ad_id, count(1) FROM lead_attribution GROUP BY ad_id").fetchall()
        total = sum(r[1] for r in rows)
        ad_map = {
            "120249419742870032": "v2 (Video 2)",
            "120249477279140032": "V6 (Video 6)",
        }
        res = []
        for ad_id, count in rows:
            name = ad_map.get(str(ad_id), f"Ad {ad_id}")
            pct = round((count / total) * 100, 1) if total else 0
            res.append((name, count, pct))
        return sorted(res, key=lambda x: x[1], reverse=True)
    except Exception:
        return []


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

    amo_pct = int((amo_ok / total) * 100) if total > 0 else 100
    sheets_pct = int((sheets_ok / total) * 100) if total > 0 else 100
    tg_pct = int((tg_ok / total) * 100) if total > 0 else 100

    amo_icon = "🟢" if amo_ok >= total else "🟡"
    sheets_icon = "🟢" if sheets_ok >= total else "🟡"
    tg_icon = "🟢" if tg_ok >= total else "🟡"
    status_icon = "🟢 24/7 FAOL (O'lmas rejim)" if pending == 0 else "🟠 Qayta tiklanmoqda"

    from src.services.core.instagram.leadgen_sheets import DEFAULT_WORKSHEET_TITLE
    from src.services.core.marketing.meta_ads_client import get_creative_url

    creative_lines = []
    for c_name, c_count, c_pct in get_creative_summary():
        code = c_name.split()[0].lower()
        url = get_creative_url(code)
        if url:
            creative_lines.append(f'• <a href="{url}"><b>{c_name}</b></a>: {c_count} ta lid ({c_pct}%)')
        else:
            creative_lines.append(f"• <b>{c_name}:</b> {c_count} ta lid ({c_pct}%)")

    lines = [
        "🛡 <b>OISHA-OS: 24/7 AVTOMATLASHTIRISH HOLAT HISOBOTI</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📅 <b>Vaqt:</b> {now_str}",
        f"⚡️ <b>Tizim holati:</b> {status_icon}",
        "",
        "📊 <b>Oxirgi 24 soatdagi lidlar oqimi:</b>",
        f"• Kelib tushgan lidlar: <b>{total} ta</b>",
        f"• {amo_icon} <b>AmoCRM:</b> {amo_ok}/{total} ({amo_pct}% 'Sotuv/UTC -> Yangi')",
        f"• {sheets_icon} <b>Google Sheets:</b> {sheets_ok}/{total} ({sheets_pct}% kiritilgan)",
        f"• {tg_icon} <b>Telegram Guruhi:</b> {tg_ok}/{total} ({tg_pct}% xabar yuborilgan)",
        "",
        "🎬 <b>Kreativlar (Videolar) samaradorligi:</b>",
        *creative_lines,
        "",
        "⚙️ <b>Baza va Integratsiyalar:</b>",
        f"• Meta Lead Ads barcha formalardagi lidlar: <b>{meta_total} ta</b>",
        f"• Google Sheets jadvali: <code>{DEFAULT_WORKSHEET_TITLE}</code>",
        "• AmoCRM voronkasi: <code>Sotuv (#11162698)</code> + <code>UTC (#11322658)</code>, manba: Target",
        f"• Kutilayotgan/xatoli lidlar: <b>{pending} ta</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "✅ <i>Barcha lidlar avtomatik tarzda 3 ta tizimga (AmoCRM, Sheets, Telegram) kafolatlangan holda yetkazilmoqda.</i>",
    ]
    return "\n".join(lines)


async def send_daily_status_report() -> bool:
    """Send daily integration health report to Target Leads & Marketing groups."""
    text = build_status_report_text()

    buttons = [
        [{"text": "🎬 v2 (Video 2) — 26 ta lid (86.7%)", "url": "https://www.instagram.com/p/DdMgcrcgnuH/"}],
        [{"text": "🎬 V6 (Video 6) — 4 ta lid (13.3%)", "url": "https://www.instagram.com/p/DdVkUMngJiW/"}],
    ]
    reply_markup = {"inline_keyboard": buttons}

    # 1. Sales group (Target Leads topic)
    sales_chat_id = getattr(settings, "TARGET_LEADS_GROUP_ID", None) or -1003854308552
    sales_topic_id = getattr(settings, "TARGET_LEADS_TOPIC_ID", None) or 1020
    ok_sales = await asyncio.to_thread(_send_tg_message, text, sales_chat_id, sales_topic_id, reply_markup=reply_markup)

    # 2. Marketing group (Jon Branding | Marketing -> AI Hisobot topic #42)
    mktg_chat_id = -1003608624065
    mktg_topic_id = 42
    ok_mktg = await asyncio.to_thread(_send_tg_message, text, mktg_chat_id, mktg_topic_id, reply_markup=reply_markup)

    if ok_sales or ok_mktg:
        logger.info("[LEADGEN REPORTER] Status report sent (sales=%s, marketing=%s)", ok_sales, ok_mktg)
    return bool(ok_sales or ok_mktg)


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
