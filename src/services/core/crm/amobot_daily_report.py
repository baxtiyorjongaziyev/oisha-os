"""
AmoCRM daily report translator and dispatcher.

Translates the daily Russian summary report sent by @amocrm_amobot into Uzbek,
preserving all numbers, currency units, and deep filter links.
Relays the formatted report to the CRM Sales Group topic and to the owner.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.settings import settings

logger = logging.getLogger("AmoBotDailyReport")

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
SEEN_AMOBOT_REPORTS_KEY = "amobot_report:seen_dates"
MAX_SEEN_DATES = 60

AMOBOT_TRANSLATION_PATTERNS = [
    (
        r"(?i)^Отчет за сегодня\s*\((.*?)\)",
        r"📊 **Kunlik AmoCRM hisoboti (\1)**\n",
    ),
    (
        r"(?i)^Отчет за\s*\((.*?)\)",
        r"📊 **AmoCRM hisoboti (\1)**\n",
    ),
    (
        r"(?i)^Активных сделок на конец периода на сумму:\s*(.*)",
        r"🔹 **Faol bitimlar umumiy summasi:** \1",
    ),
    (
        r"(?i)^Активных сделок на конец периода:\s*(.*)",
        r"🔹 **Davr oxiridagi faol bitimlar:** \1",
    ),
    (
        r"(?i)^Успешно завершено сделок на сумму:\s*(.*)",
        r"💰 **Muvaffaqiyatli yakunlangan summa:** \1",
    ),
    (
        r"(?i)^Успешно завершено сделок:\s*(.*)",
        r"✅ **Muvaffaqiyatli yakunlangan bitimlar:** \1",
    ),
    (
        r"(?i)^Нереализовано сделок на сумму:\s*(.*)",
        r"🔻 **Amalga oshmagan bitimlar summasi:** \1",
    ),
    (
        r"(?i)^Нереализовано сделок\s*:\s*(.*)",
        r"❌ **Amalga oshmagan (yopilgan) bitimlar:** \1",
    ),
    (
        r"(?i)^Новых сделок за период создано:\s*(.*)",
        r"🆕 **Davr ichida yangi bitimlar:** \1",
    ),
    (
        r"(?i)^Новых компаний за период создано:\s*(.*)",
        r"🏢 **Yangi yaratilgan kompaniyalar:** \1",
    ),
    (
        r"(?i)^Новых контактов за период создано:\s*(.*)",
        r"👤 **Yangi yaratilgan kontaktlar:** \1",
    ),
]


def is_amobot_daily_report(text: str) -> bool:
    """Check if the given text matches an AmoCRM bot daily report."""
    if not text:
        return False
    lower = text.lower()
    has_header = "отчет за сегодня" in lower or "отчет за" in lower
    has_metrics = "активных сделок" in lower or "успешно завершено" in lower
    return bool(has_header and has_metrics)


def extract_report_date(text: str) -> str:
    """Extract report date string (e.g. 02.11.2026) or fallback to today."""
    match = re.search(r"\((\d{2}\.\d{2}\.\d{4})\)", text)
    if match:
        return match.group(1)
    now = datetime.now(TASHKENT_TZ)
    return now.strftime("%d.%m.%Y")


def translate_amobot_daily_report(text: str) -> str:
    """Translate Russian amoBot daily report to Uzbek, keeping links & numbers."""
    if not text:
        return ""

    translated_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            translated_lines.append("")
            continue

        matched = False
        for pat, repl in AMOBOT_TRANSLATION_PATTERNS:
            if re.search(pat, stripped):
                translated_lines.append(re.sub(pat, repl, stripped))
                matched = True
                break

        if not matched:
            translated_lines.append(stripped)

    translated_lines.append("\n---\n🤖 *Oisha OS avtomatlashtirilgan CRM monitoringi*")
    return "\n".join(translated_lines)


async def send_daily_report_to_destinations(
    report_text: str,
    bot_runtime: Any,
    user_client: Any = None,
) -> int:
    """Deliver report to configured sales group topic and owner."""
    sent_count = 0
    group_id = settings.CRM_SALES_REPORT_GROUP_ID or settings.AMOCRM_ALERT_FORWARD_GROUP_ID
    topic_id = settings.CRM_SALES_REPORT_TOPIC_ID or settings.AMOCRM_ALERT_FORWARD_TOPIC_ID

    # 1. Send to Sales Group Topic
    if group_id and bot_runtime:
        try:
            kw = {"message_thread_id": topic_id} if topic_id else {}
            await bot_runtime.send_message(group_id, report_text, parse_mode="md", **kw)
            sent_count += 1
            logger.info("[AMOBOT_REPORT] Sent to sales group %s (topic %s)", group_id, topic_id)
        except Exception as exc:
            logger.error("[AMOBOT_REPORT] Failed sending to sales group %s: %s", group_id, exc)

    # 2. Send to Owner DM (via bot_runtime if OWNER_ID configured, or via user_client 'me')
    owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
    if owner_id and bot_runtime:
        try:
            from src.services.core.telegram.telegram_ai_features import get_owner_topic_id

            owner_topic = get_owner_topic_id("sales")
            kw = {"message_thread_id": owner_topic} if owner_topic else {}
            await bot_runtime.send_message(owner_id, report_text, parse_mode="md", **kw)
            sent_count += 1
            logger.info("[AMOBOT_REPORT] Sent to owner %s via bot_runtime", owner_id)
        except Exception as exc:
            logger.warning("[AMOBOT_REPORT] bot_runtime DM to owner %s failed: %s", owner_id, exc)

    if sent_count == 0 and user_client:
        try:
            await user_client.send_message("me", report_text, parse_mode="md")
            sent_count += 1
            logger.info("[AMOBOT_REPORT] Fallback sent to user_client 'me'")
        except Exception as exc:
            logger.error("[AMOBOT_REPORT] Fallback to 'me' failed: %s", exc)

    return sent_count


async def process_amobot_message(
    raw_text: str,
    bot_runtime: Any,
    user_client: Any = None,
    db: Any = None,
) -> bool:
    """Process incoming amoBot message, translating and relaying if it is a daily report."""
    if not is_amobot_daily_report(raw_text):
        return False

    report_date = extract_report_date(raw_text)
    seen_dates: list[str] = []
    if db and hasattr(db, "get_state"):
        try:
            seen_dates = await db.get_state(SEEN_AMOBOT_REPORTS_KEY, []) or []
        except Exception as exc:
            logger.debug("[AMOBOT_REPORT] db get_state error: %s", exc)

    if report_date in seen_dates:
        logger.info("[AMOBOT_REPORT] Report for date %s already sent, skipping.", report_date)
        return False

    uzbek_text = translate_amobot_daily_report(raw_text)
    sent = await send_daily_report_to_destinations(uzbek_text, bot_runtime, user_client)
    if sent > 0:
        seen_dates.append(report_date)
        if db and hasattr(db, "set_state"):
            try:
                trimmed = seen_dates[-MAX_SEEN_DATES:]
                await db.set_state(SEEN_AMOBOT_REPORTS_KEY, trimmed)
            except Exception as exc:
                logger.debug("[AMOBOT_REPORT] db set_state error: %s", exc)
        return True
    return False


async def check_and_relay_amobot_report(
    user_client: Any,
    bot_runtime: Any,
    db: Any = None,
) -> bool:
    """Poll amoBot chat for today's report if event was missed."""
    if not user_client:
        return False

    try:
        messages = await user_client.get_messages("amocrm_amobot", limit=5)
    except Exception as exc:
        logger.warning("[AMOBOT_REPORT] get_messages from amocrm_amobot failed: %s", exc)
        return False

    for msg in messages:
        text = getattr(msg, "text", "") or getattr(msg, "message", "") or ""
        if is_amobot_daily_report(text):
            handled = await process_amobot_message(text, bot_runtime, user_client, db)
            if handled:
                logger.info("[AMOBOT_REPORT] Polled and successfully relayed daily report.")
                return True
    return False
