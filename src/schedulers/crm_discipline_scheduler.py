"""CRM discipline and capacity archiver background schedulers."""

from __future__ import annotations

import asyncio
import logging

from src.config import FARMER_PIPELINE_ID, SALES_PIPELINE_ID
from src.context import app_ctx
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
    """Check active AmoCRM deals count against 500 limit and auto-archive stagnant leads."""
    await asyncio.sleep(60)
    while True:
        try:
            logger.info("[ARCHIVER_LOOP] Active AmoCRM capacity check starting...")
            from src.services.core.crm.crm_archiver import CRMArchiver

            if app_ctx.msg_controller and app_ctx.msg_controller.crm:
                archiver = CRMArchiver(
                    amocrm=app_ctx.msg_controller.crm.amocrm,
                    db=app_ctx.msg_controller.db,
                )
                await archiver.init_tables()
                active_leads = await archiver.fetch_all_active_leads()
                active_count = len(active_leads)
                logger.info("[ARCHIVER_LOOP] Active sdelkas: %s / 500 limit", active_count)

                if active_count >= 480:
                    logger.warning(
                        "[ARCHIVER_LOOP] Active sdelkas count %s exceeds threshold of 480! Autocleaning...",
                        active_count,
                    )
                    stagnant = await archiver.get_stagnant_leads(max_stagnant_days=21)
                    if stagnant:
                        targets = stagnant[:30]
                        processed = 0
                        for lead in targets:
                            try:
                                res = await archiver.archive_lead(lead, dry_run=False)
                                if res.get("success"):
                                    processed += 1
                            except Exception as ex:
                                logger.error(
                                    "[ARCHIVER_LOOP] Error archiving lead %s: %s",
                                    lead.get("id"),
                                    ex,
                                )
                        logger.info("[ARCHIVER_LOOP] Autocleanup complete. Archived %s leads.", processed)
                    else:
                        logger.info("[ARCHIVER_LOOP] No stagnant leads found.")
        except Exception as e:
            logger.error("[ARCHIVER_LOOP] Error in capacity archiver loop: %s", e)
        await asyncio.sleep(21600)
