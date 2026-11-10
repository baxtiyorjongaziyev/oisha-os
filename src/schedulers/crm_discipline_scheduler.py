"""CRM discipline and capacity archiver background schedulers."""

from __future__ import annotations

import asyncio
import logging

from src.context import app_ctx
from src.services.core.crm.amocrm_pipeline_config import (
    FARMER_PIPELINE_ID,
    SALES_PIPELINE_ID,
)
from src.services.core.crm.crm_guard import CRMGuard

logger = logging.getLogger("CRMDisciplineScheduler")


async def crm_discipline_loop() -> None:
    """Periodically check CRM pipeline discipline across sales and farmer pipelines."""
    while True:
        try:
            if app_ctx.msg_controller and app_ctx.msg_controller.crm:
                crm_guard = CRMGuard(
                    amo=app_ctx.msg_controller.crm.amocrm,
                    db=app_ctx.msg_controller.db,
                    bot=None,
                )
                await crm_guard.check_discipline(pipeline_id=SALES_PIPELINE_ID)
                await crm_guard.check_discipline(pipeline_id=FARMER_PIPELINE_ID)
        except Exception as e:
            logger.error("[CRM_GUARD_LOOP] Error: %s", e)
        await asyncio.sleep(7200)


async def crm_capacity_archiver_loop() -> None:
    """Check active AmoCRM deals count against 500 limit, enforce tasks, and auto-archive stagnant leads."""
    await asyncio.sleep(60)
    while True:
        try:
            logger.info("[ARCHIVER_LOOP] Active AmoCRM capacity & hygiene check starting...")
            from src.services.core.crm.amocrm_hygiene import AmoCRMHygieneService

            amo_instance = (
                app_ctx.msg_controller.crm.amocrm
                if app_ctx.msg_controller and app_ctx.msg_controller.crm
                else None
            )
            bot_rt = getattr(app_ctx, "bot_runtime", None)
            service = AmoCRMHygieneService(amocrm=amo_instance, bot_runtime=bot_rt)
            report = await service.run_hygiene_cycle(
                dry_run=False,
                auto_archive=False,
                capacity_threshold=480,
                max_stagnant_days=30,
            )
            logger.info(
                "[ARCHIVER_LOOP] Done: active=%s/500, tasks=+%s, archived=%s",
                report.get("total_active_after"),
                report.get("tasks_created"),
                report.get("archived_leads"),
            )
        except Exception as e:
            logger.error("[ARCHIVER_LOOP] Error in capacity archiver loop: %s", e)
        await asyncio.sleep(14400)
