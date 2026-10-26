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
    from src.settings import settings

    token = settings.BOT_TOKEN.get_secret_value()
    chat = os.getenv("ATTENDANCE_NOTIFY_CHAT_ID", "").strip() or str(settings.OWNER_ID or "")
    if not token or not chat or chat == "0":
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=20)
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
