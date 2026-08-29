import os
import io
import time
import json
import logging
import structlog
import asyncio
import psutil
import platform
from datetime import datetime
from telethon import events, Button, functions, types
from src.database import Database
from src.controllers.message_controller import MessageController
from src.time_utils import get_local_now, is_quiet_hours
from src.services.core.mission_control import MissionControl, MissionControlFetchError
from src.services.core.crm.crm_night_shift import CRMNightShift
from src.services.core.admin_command_router import (
    build_chatid_response,
    build_command_center_response,
    build_finance_risks_response,
    build_oisha_stats_response,
    build_project_risks_response,
    build_sales_priorities_response,
    build_start_response,
    build_team_capacity_response,
    resolve_start_role,
)
from src.services.core.business_command_center import (
    collect_business_command_snapshot,
    collect_finance_project_risks,
    collect_project_delivery_risks,
    collect_sales_today_priorities,
    collect_team_capacity_snapshot,
)
from src.services.core.telegram.bot_runtime import BotRuntimePort, TelethonBotRuntime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.services.utils.access_manager import AccessManager

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
