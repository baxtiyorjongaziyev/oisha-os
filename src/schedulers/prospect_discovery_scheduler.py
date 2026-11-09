"""Opt-in hourly prospect queue refresh; no outreach or CRM writes."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def prospect_discovery_loop():
    from src.context import app_ctx
    from src.services.core.leads.prospect_discovery import scan_prospects
    from src.services.core.leads.prospect_store import get_prospect_store
    from src.time_utils import get_local_now

    await asyncio.sleep(120)
    while True:
        try:
            now = get_local_now()
            # Keep quiet hours and do not connect/start any Telegram session.
            if 7 <= now.hour < 23:
                store = get_prospect_store()
                await store.initialize()
                if await store.auto_enabled():
                    result = await scan_prospects(app_ctx.client, store)
                    logger.info("Prospect discovery: status=%s new=%s", result["status"], result["new"])
        except Exception as exc:
            logger.warning("Prospect discovery unavailable: %s", type(exc).__name__)
        await asyncio.sleep(3600)
