"""AI Chat Manager: jim qolgan dialoglardan zayavka ajratish (5 daqiqada bir)."""

from __future__ import annotations

import asyncio
import logging

from src.context import app_ctx

logger = logging.getLogger("ChatManagerScheduler")

_INTERVAL_SECONDS = 300


async def chat_manager_extract_loop() -> None:
    await asyncio.sleep(30)
    from src.services.core.chat_manager import extractor
    from src.services.utils.free_ai_router import get_free_ai_router

    router = get_free_ai_router()
    while True:
        amocrm = getattr(getattr(app_ctx.msg_controller, "crm", None), "amocrm", None)
        try:
            created = await extractor.run_cycle(router, amocrm)
            if created:
                logger.info("[CHAT-MANAGER] %s ta yangi zayavka", created)
        except Exception:  # noqa: BLE001 - loop must survive one bad cycle
            logger.exception("[CHAT-MANAGER] extraction cycle failed")
        await asyncio.sleep(_INTERVAL_SECONDS)
