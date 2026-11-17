"""14:10–17:00 (Toshkent) oraligʼida obeddan qaytmaganlarni ownerʼga bildiradi.

Har xodim kuniga bir marta bildiriladi. Oʼchirish: ``LUNCH_RETURN_ALERT=0``.
"""

from __future__ import annotations

import asyncio
import logging
import os

from src.time_utils import get_local_now

logger = logging.getLogger("LunchReturnScheduler")

CHECK_UNTIL_HOUR = 17  # 17:00 dan keyin chiqish "ketdi" hisoblanadi (auto_presence)


async def lunch_return_loop() -> None:
    from src.database_pool import db_pool
    from src.schedulers.attendance_summary_scheduler import _send
    from src.services.core.attendance import lunch_watch

    if os.getenv("LUNCH_RETURN_ALERT", "1") != "1":
        return
    alerted: dict = {}
    while True:
        try:
            now = get_local_now()
            if now.date() not in alerted:
                alerted = {now.date(): set()}
            seen = alerted[now.date()]
            if lunch_watch.LUNCH_END.hour <= now.hour < CHECK_UNTIL_HOUR:
                items = await lunch_watch.find_late_returners(db_pool, now)
                fresh = [it for it in items if it.employee_id not in seen]
                if fresh and await asyncio.to_thread(_send, lunch_watch.format_alert(fresh)):
                    logger.info("[LUNCH] alert: %s", [it.name for it in fresh])
                    seen.update(it.employee_id for it in fresh)  # faqat yuborilganda
        except Exception as e:
            logger.error("[LUNCH] Error: %s", e)
        await asyncio.sleep(60)
