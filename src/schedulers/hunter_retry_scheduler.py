"""Hunter: amoCRM'ga yozilmay qolgan (`pending`) nomzodlarni qayta yuborish."""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger("HunterRetryScheduler")

_INTERVAL_SECONDS = 900


def _amocrm():
    from src.api.routes.state import api_state

    if api_state.amocrm_instance:
        return api_state.amocrm_instance
    from src.services.core.crm.amocrm.sync import AmoCRMSync

    return AmoCRMSync()


async def hunter_retry_loop() -> None:
    """Har 15 daqiqada `pending` nomzodlarni qayta yuboradi (quiet-hours'da emas)."""
    from src.database_pool import db_pool
    from src.services.core.leads.hunter import HunterWriter

    if os.getenv("HUNTER_RETRY_ENABLED", "1") != "1":
        logger.info("[HUNTER-RETRY] Disabled by HUNTER_RETRY_ENABLED")
        return
    await asyncio.sleep(180)
    while True:
        try:
            stats = await HunterWriter(_amocrm(), db_pool).retry_pending()
            if stats["retried"] or stats["failed"]:
                logger.info("[HUNTER-RETRY] %s", stats)
        except Exception as e:
            logger.error("[HUNTER-RETRY] Error: %s", e)
        await asyncio.sleep(_INTERVAL_SECONDS)
