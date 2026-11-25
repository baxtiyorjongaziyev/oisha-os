"""Har kuni 10:00 (Toshkent) da mijoz maʼlumotlarini 5 tizimda sinxronlaydi.

Telegram, Google Contacts, AmoCRM, Airtable va Obsidian. Standart: dry-run
(COMMUNITY_SYNC_DRY_RUN=1) - faqat reja ownerʼga yuboriladi, tasdiqdan keyin yoziladi.
COMMUNITY_SYNC_ENABLED=1 boʻlmasa runner hech narsa qilmaydi.
"""

from __future__ import annotations

import asyncio
import logging

from src.time_utils import get_local_now

logger = logging.getLogger("CommunitySyncScheduler")

RUN_AT = (10, 0)


def register(app_ctx) -> None:
    bot = getattr(app_ctx, "bot_client", None)
    if bot is None or not hasattr(bot, "on"):
        logger.warning("[COMMUNITY_SYNC] bot klienti yöq: tasdiq tugmalari ulanmadi")
        return
    from src.services.core.community_sync.wiring import register_callbacks

    register_callbacks(bot, app_ctx)


async def community_sync_loop(app_ctx) -> None:
    from src.services.core.community_sync.wiring import scheduled_job

    last_day = None
    while True:
        now = get_local_now()
        if (now.hour, now.minute) >= RUN_AT and now.date() != last_day:
            last_day = now.date()
            res = await scheduled_job(app_ctx)
            logger.info("[COMMUNITY_SYNC] kunlik natija: %s", res)
        await asyncio.sleep(60)
