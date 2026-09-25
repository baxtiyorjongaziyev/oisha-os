"""Autonomous 24/7 status reporter and heartbeat monitor for Meta Lead Ads automation."""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
from typing import Any, Dict, List, Optional

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


_AD_NAME_OVERRIDES: Dict[str, str] = {
    "120249419742870032": "v2 (Video 2)",
    "120249477279140032": "V6 (Video 6)",
}
_AD_NAME_CACHE: Dict[str, str] = {}
_AD_URL_CACHE: Dict[str, Optional[str]] = {}


def _meta_client() -> Any:
    from src.services.core.marketing.meta_ads_client import MetaAdsClient

    return MetaAdsClient()


def _resolve_ad_name(ad_id: str) -> str:
    ad_id = str(ad_id or "").strip()
    if not ad_id:
        return "Noma'lum reklama"
    if ad_id in _AD_NAME_OVERRIDES:
        return _AD_NAME_OVERRIDES[ad_id]
    if ad_id not in _AD_NAME_CACHE:
        name = None
        try:
            name = _meta_client().get_ad_name(ad_id)
        except Exception as exc:
            logger.warning("[LEADGEN REPORTER] Ad name lookup failed: %s", exc)
        _AD_NAME_CACHE[ad_id] = name or f"Ad {ad_id}"
    return _AD_NAME_CACHE[ad_id]


def _resolve_ad_url(ad_id: str) -> Optional[str]:
    from src.services.core.marketing.meta_ads_client import get_creative_url

    ad_id = str(ad_id or "").strip()
    if not ad_id:
        return None
    known = get_creative_url(ad_id)
    if known:
        return known
    if ad_id not in _AD_URL_CACHE:
        url = None
        try:
            url = _meta_client().get_ad_creative_url(ad_id)
        except Exception as exc:
            logger.warning("[LEADGEN REPORTER] Creative URL lookup failed: %s", exc)
        _AD_URL_CACHE[ad_id] = url
    return _AD_URL_CACHE[ad_id]


def get_creative_summary(hours: int = 24) -> list[tuple[str, int, float, str]]:
    """Lead counts per ad for the last `hours` — (name, count, pct, ad_id), sorted desc."""
    try:
        from src.services.core.marketing.attribution_store import _connection
        with _connection() as conn:
            rows = conn.execute(
                "SELECT ad_id, count(1) FROM lead_attribution "
                "WHERE created_at >= datetime('now', ?) GROUP BY ad_id",
                (f"-{int(hours)} hours",),
            ).fetchall()
    except Exception as exc:
        logger.warning("[LEADGEN REPORTER] Creative summary failed: %s", exc)
        return []

    total = sum(r[1] for r in rows)
    res = []
    for ad_id, count in rows:
        pct = round((count / total) * 100, 1) if total else 0
        res.append((_resolve_ad_name(ad_id), count, pct, str(ad_id or "")))
    return sorted(res, key=lambda x: x[1], reverse=True)


def build_creative_buttons(
    summary: list[tuple[str, int, float, str]], limit: int = 3
) -> list[list[Dict[str, str]]]:
    buttons = []
    for name, count, pct, ad_id in summary[:limit]:
        url = _resolve_ad_url(ad_id)
        if url:
            buttons.append([{"text": f"🎬 {name} — {count} ta lid ({pct}%)", "url": url}])
    return buttons


def build_status_report_text(summary: Optional[list[tuple[str, int, float, str]]] = None) -> str:
    """Compile executive 24/7 status report across Meta, AmoCRM, Sheets, and Telegram."""
    if summary is None:
        summary = get_creative_summary()
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

    creative_lines = []
    for c_name, c_count, c_pct, ad_id in summary:
        url = _resolve_ad_url(ad_id)
        if url:
            creative_lines.append(f'• <a href="{url}"><b>{c_name}</b></a>: {c_count} ta lid ({c_pct}%)')
        else:
            creative_lines.append(f"• <b>{c_name}:</b> {c_count} ta lid ({c_pct}%)")
    if not creative_lines:
        creative_lines.append("• Oxirgi 24 soatda kreativ bo'yicha lid yo'q")

    footer_note = (
        "✅ <i>Barcha lidlar avtomatik tarzda 3 ta tizimga (AmoCRM, Sheets, Telegram) 100% to'liq yetkazildi.</i>"
        if pending == 0
        else f"⚠️ <i>{pending} ta lid integratsiyasi navbatda / qayta urinish jarayonida.</i>"
    )

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
        "🎬 <b>Kreativlar samaradorligi (24 soat):</b>",
        *creative_lines,
        "",
        "⚙️ <b>Baza va Integratsiyalar:</b>",
        f"• Meta Lead Ads barcha formalardagi lidlar: <b>{meta_total} ta</b>",
        f"• Google Sheets jadvallari: <code>UTC Outsource & Inhouse</code>",
        "• AmoCRM voronkalari: <code>Sotuv Bo'limi (#11162698) & UTC (#11322658)</code>",
        f"• Kutilayotgan/xatoli lidlar: <b>{pending} ta</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        footer_note,
    ]
    return "\n".join(lines)


async def send_daily_status_report() -> bool:
    """Send daily integration health report to Target Leads & Marketing groups."""
    summary = get_creative_summary()
    text = build_status_report_text(summary)
    buttons = build_creative_buttons(summary)
    reply_markup = {"inline_keyboard": buttons} if buttons else None

    # 1. Sales group (Target Leads topic)
    sales_chat_id = getattr(settings, "TARGET_LEADS_GROUP_ID", None) or -1003854308552
    sales_topic_id = getattr(settings, "TARGET_LEADS_TOPIC_ID", None) or 1020
    ok_sales = await asyncio.to_thread(_send_tg_message, text, sales_chat_id, sales_topic_id, reply_markup=reply_markup)

    # 2. Marketing group (Jon Branding | Marketing -> AI Hisobot topic #42)
    mktg_chat_id = getattr(settings, "MARKETING_REPORT_CHAT_ID", None) or -1003608624065
    mktg_topic_id = getattr(settings, "MARKETING_REPORT_TOPIC_ID", None) or 42
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
