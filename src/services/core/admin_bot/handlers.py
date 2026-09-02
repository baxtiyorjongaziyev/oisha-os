import os
import structlog
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()

from src.services.core.admin_bot.handlers_commands import register_command_handlers
from src.services.core.admin_bot.handlers_callbacks import register_callback_handlers
from src.services.core.admin_bot.handlers_search import register_search_handlers
from src.services.core.admin_bot.handlers_settings import register_settings_handlers

class AdminHandlersMixin:
    async def register_admin_handlers(self):
        """Botni eventlarini ro'yxatdan o'tkazish va schedulerni parallel yuritish."""
        logger.info("[ADMIN_BOT] Oisha Enterprise v2.1 ishga tushmoqda...")

        async def heartbeat():
            while True:
                logger.debug(
                    "👸 [ADMIN_BOT] HEARTBEAT: Oisha is alive and listening... 🛡️"
                )
                await asyncio.sleep(300)

        from src.settings import settings

        db_mode = await self.db.get_state("lead_distribution_mode")
        if db_mode:
            settings.LEAD_DISTRIBUTION_MODE = db_mode

        db_managers = await self.db.get_state("sales_managers")
        if db_managers:
            manager_ids = [int(i.strip()) for i in db_managers.split(",") if i.strip()]
            settings.SALES_MANAGER_IDS = manager_ids
            logger.info(f"👸 [ADMIN_BOT] Sales Managers loaded: {manager_ids}")

        asyncio.create_task(heartbeat())
        if os.getenv("ENABLE_ADMIN_SCHEDULER", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            asyncio.create_task(self.run_scheduler())
        else:
            logger.info("[SAFETY] AdminBot autonomous scheduler disabled by default.")

        register_command_handlers(self)
        register_callback_handlers(self)
        register_search_handlers(self)
        register_settings_handlers(self)
