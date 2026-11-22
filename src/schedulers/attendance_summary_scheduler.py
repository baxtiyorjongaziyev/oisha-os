"""Har kuni 19:30 (Toshkent) da davomat xulosasini owner'ga (yoki ATTENDANCE_NOTIFY_CHAT_ID) yuboradi."""

from __future__ import annotations

import asyncio
import logging
import os

import requests

from src.time_utils import get_local_now

logger = logging.getLogger("AttendanceSummaryScheduler")

SEND_AT = (19, 30)


def _send(text: str) -> bool:
    from src.services.core.telegram.telegram_ai_features import get_owner_topic_id
    from src.settings import settings

    token = settings.BOT_TOKEN.get_secret_value()
    owner_str = str(settings.OWNER_ID or "")
    chat = os.getenv("ATTENDANCE_NOTIFY_CHAT_ID", "").strip() or owner_str
    if not token or not chat or chat == "0":
        return False
    payload: dict[str, object] = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
    if chat == owner_str:
        hr_topic = get_owner_topic_id("hr")
        if hr_topic:
            payload["message_thread_id"] = hr_topic
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json=payload, timeout=20)
        return r.status_code == 200
    except requests.RequestException:
        return False


async def attendance_summary_loop() -> None:
    from src.database_pool import db_pool
    from src.services.core.attendance import bot_flow

    if os.getenv("ATTENDANCE_DAILY_SUMMARY", "1") != "1":
        return
    sent_on = None
    while True:
        try:
            now = get_local_now()
            # Faqat 19:30–19:59 oynasida: kechqurun restart bo'lsa qayta yuborilmaydi.
            if now.hour == SEND_AT[0] and now.minute >= SEND_AT[1] and sent_on != now.date():
                if await asyncio.to_thread(_send, await bot_flow.today_text(db_pool, now.date())):
                    logger.info("[ATT-SUMMARY] yuborildi %s", now.date())
                sent_on = now.date()  # xato bo'lsa ham kuniga bir marta urinadi
        except Exception as e:
            logger.error("[ATT-SUMMARY] Error: %s", e)
        await asyncio.sleep(60)
