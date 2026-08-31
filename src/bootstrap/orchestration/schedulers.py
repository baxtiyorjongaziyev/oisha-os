"""
Background discipline and reporting schedulers.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from src.settings import settings

logger = logging.getLogger("OishaBootstrap")


def start_background_schedulers(bot_runtime: Any) -> None:
    if settings.RUN_USERBOT_ONLY:
        return

    from src.schedulers.crm_discipline_scheduler import (
        crm_capacity_archiver_loop,
        crm_discipline_loop,
    )
    asyncio.create_task(crm_discipline_loop(), name="crm_discipline_loop")
    asyncio.create_task(crm_capacity_archiver_loop(), name="crm_capacity_archiver_loop")
    if os.getenv("ENABLE_AI_AUTOPILOT", "").strip().lower() in {"1", "true", "yes", "on"}:
        from src.schedulers.ai_autopilot_scheduler import ai_autopilot_loop
        asyncio.create_task(ai_autopilot_loop(), name="ai_autopilot_loop")
    else:
        logger.info("[AUTOPILOT] Disabled by default; analysis remains manual.")

    from src.schedulers.frog_scheduler import daily_frog_loop
    asyncio.create_task(daily_frog_loop(bot_runtime, settings.TEAM_GROUP_ID), name="daily_frog_loop")
    from src.schedulers.channel_scout_scheduler import channel_scout_loop
    asyncio.create_task(channel_scout_loop(), name="channel_scout_loop")
    from src.schedulers.instagram_weekly_reporter import instagram_weekly_report_loop
    asyncio.create_task(
        instagram_weekly_report_loop(bot_runtime, settings.TEAM_GROUP_ID),
        name="instagram_weekly_report_loop",
    )

    try:
        from src.schedulers.call_analysis_scheduler import call_analysis_loop
        asyncio.create_task(call_analysis_loop(), name="call_analysis_loop")
    except ImportError as exc:
        logger.warning("[CALL-SCHEDULER] Call analysis loop unavailable: %s", exc)

    try:
        from src.schedulers.cloud_brain_synthesizer import brain_synthesizer_loop
        asyncio.create_task(
            brain_synthesizer_loop(bot_runtime, settings.OWNER_ID),
            name="cloud_brain_synthesizer_loop",
        )
    except ImportError as exc:
        logger.warning("[BRAIN] Cloud synthesizer unavailable: %s", exc)
