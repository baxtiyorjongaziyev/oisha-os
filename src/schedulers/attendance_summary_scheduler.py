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


async def maybe_send_daily_summary(db, day, sender=_send) -> bool:
    from src.services.core.attendance import bot_flow

    if not await bot_flow.has_scheduled_or_present(db, day):
        logger.info("[ATT-SUMMARY] %s dam olish kuni — yuborilmadi", day)
        return False
    text = await bot_flow.today_text(db, day)
    return bool(await asyncio.to_thread(sender, text))


async def attendance_summary_loop() -> None:
    from src.database_pool import db_pool

    if os.getenv("ATTENDANCE_DAILY_SUMMARY", "1") != "1":
        return
    sent_on = None
    while True:
        try:
            now = get_local_now()
            # Faqat 19:30–19:59 oynasida: kechqurun restart boʻlsa qayta yuborilmaydi.
            if now.hour == SEND_AT[0] and now.minute >= SEND_AT[1] and sent_on != now.date():
                if await maybe_send_daily_summary(db_pool, now.date()):
                    logger.info("[ATT-SUMMARY] yuborildi %s", now.date())
                sent_on = now.date()  # xato boʻlsa ham kuniga bir marta urinadi
        except Exception as e:
            logger.error("[ATT-SUMMARY] Error: %s", e)
        await asyncio.sleep(60)
