"""Lid kuzatuvi: biriktirilmaganlarni berish, "Yangi"da qolganlarni eslatish/o'tkazish."""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger("LeadFollowUpScheduler")

_INTERVAL_SECONDS = 300


async def lead_follow_up_loop() -> None:
    from src.database_pool import db_pool
    from src.schedulers.hunter_retry_scheduler import _amocrm
    from src.services.core.leads.assignment import LeadAssigner

    if os.getenv("LEAD_ASSIGNMENT_ENABLED", "0") != "1":
        logger.info("[LEAD-FOLLOWUP] Disabled by LEAD_ASSIGNMENT_ENABLED")
        return
    await asyncio.sleep(240)
    while True:
        try:
            stats = await LeadAssigner(_amocrm(), db_pool).follow_up_once()
            if any(stats.values()):
                logger.info("[LEAD-FOLLOWUP] %s", stats)
        except Exception as e:
            logger.error("[LEAD-FOLLOWUP] Error: %s", e)
        await asyncio.sleep(_INTERVAL_SECONDS)
