"""
Background discipline and reporting schedulers.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

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
    from src.schedulers.phone_plus_fixer_scheduler import phone_plus_fixer_loop
    asyncio.create_task(phone_plus_fixer_loop(), name="phone_plus_fixer_loop")
    if os.getenv("ENABLE_AI_AUTOPILOT", "").strip().lower() in {"1", "true", "yes", "on"}:
        from src.schedulers.ai_autopilot_scheduler import ai_autopilot_loop
        asyncio.create_task(ai_autopilot_loop(), name="ai_autopilot_loop")
    else:
        logger.info("[AUTOPILOT] Disabled by default; analysis remains manual.")

    from src.schedulers.frog_scheduler import daily_frog_loop
    asyncio.create_task(daily_frog_loop(bot_runtime, settings.TEAM_GROUP_ID), name="daily_frog_loop")
    from src.schedulers.channel_scout_scheduler import channel_scout_loop
    asyncio.create_task(channel_scout_loop(), name="channel_scout_loop")
    from src.schedulers.hunter_retry_scheduler import hunter_retry_loop
    asyncio.create_task(hunter_retry_loop(), name="hunter_retry_loop")
    from src.schedulers.lead_follow_up_scheduler import lead_follow_up_loop
    asyncio.create_task(lead_follow_up_loop(), name="lead_follow_up_loop")
    from src.schedulers.chat_manager_scheduler import chat_manager_extract_loop
    asyncio.create_task(chat_manager_extract_loop(), name="chat_manager_extract_loop")
    from src.schedulers.attendance_summary_scheduler import attendance_summary_loop
    asyncio.create_task(attendance_summary_loop(), name="attendance_summary_loop")
    from src.schedulers.lunch_return_scheduler import lunch_return_loop
    asyncio.create_task(lunch_return_loop(), name="lunch_return_loop")
    from src.schedulers.card_payment_watch_scheduler import card_payment_watch_loop
    asyncio.create_task(card_payment_watch_loop(bot_runtime), name="card_payment_watch_loop")
    from src.schedulers.sales_copilot_scheduler import sales_copilot_loop
    asyncio.create_task(sales_copilot_loop(bot_runtime), name="sales_copilot_loop")
    from src.schedulers.instagram_weekly_reporter import instagram_weekly_report_loop
    asyncio.create_task(
        instagram_weekly_report_loop(bot_runtime, settings.TEAM_GROUP_ID),
        name="instagram_weekly_report_loop",
    )
    from src.schedulers.airtable_missing_fields_scheduler import airtable_missing_fields_loop
    asyncio.create_task(
        airtable_missing_fields_loop(bot_runtime, settings.TEAM_GROUP_ID),
        name="airtable_missing_fields_loop",
    )
    from src.schedulers.meta_health_scheduler import meta_health_check_loop
    asyncio.create_task(meta_health_check_loop(bot_runtime), name="meta_health_check_loop")
    try:
        from src.schedulers.instagram_comment_backfill_scheduler import (
            instagram_comment_backfill_loop,
        )
        _ig_db = getattr(bot_runtime, "db", None) or getattr(bot_runtime, "db_instance", None)
        asyncio.create_task(
            instagram_comment_backfill_loop(_ig_db),
            name="instagram_comment_backfill_loop",
        )
    except ImportError as exc:
        logger.warning("[IG-BACKFILL] Comment backfill loop unavailable: %s", exc)

    try:
        from src.schedulers.youtube_comment_backfill_scheduler import (
            youtube_comment_backfill_loop,
        )
        asyncio.create_task(
            youtube_comment_backfill_loop(),
            name="youtube_comment_backfill_loop",
        )
    except ImportError as exc:
        logger.warning("[YT-BACKFILL] YouTube comment loop unavailable: %s", exc)

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

    try:
        from src.schedulers.training_advice_scheduler import training_advice_loop
        asyncio.create_task(training_advice_loop(), name="training_advice_loop")
    except ImportError as exc:
        logger.warning("[TRAINING-ADVICE] Daily advice loop unavailable: %s", exc)

    try:
        from src.schedulers.rop_scheduler import start_rop_schedulers
        start_rop_schedulers(bot_runtime)
    except ImportError as exc:
        logger.warning("[ROP] scheduler unavailable: %s", exc)

    try:
        from src.schedulers.daily_insights_scheduler import (
            daily_insights_loop,
            sales_intel_loop,
        )
        asyncio.create_task(daily_insights_loop(bot_runtime), name="daily_insights_loop")
        asyncio.create_task(sales_intel_loop(bot_runtime), name="sales_intel_loop")
    except ImportError as exc:
        logger.warning("[INSIGHTS] scheduler unavailable: %s", exc)

    standalone_leadgen = (
        os.getenv("STANDALONE_LEADGEN_WORKER", "").strip().lower() in {"1", "true", "yes"}
        or getattr(settings, "STANDALONE_LEADGEN_WORKER", False)
        or os.path.exists("/etc/systemd/system/oisha-leads.service")
    )
    if standalone_leadgen:
        logger.info("[META LEADGEN] Ingestion & watchdog delegated to dedicated standalone worker.")
    else:
        try:
            from src.schedulers.meta_leadgen_scheduler import meta_leadgen_loop
            asyncio.create_task(meta_leadgen_loop(), name="meta_leadgen_loop")
        except ImportError as exc:
            logger.warning("[META LEADGEN] scheduler unavailable: %s", exc)

        try:
            from src.schedulers.leadgen_status_reporter import (
                leadgen_watchdog_and_reporter_loop,
            )
            asyncio.create_task(leadgen_watchdog_and_reporter_loop(), name="leadgen_watchdog_loop")
        except ImportError as exc:
            logger.warning("[LEADGEN WATCHDOG] reporter unavailable: %s", exc)

    try:
        from src.schedulers.unowned_lead_alert import unowned_lead_alert_loop
        asyncio.create_task(unowned_lead_alert_loop(), name="unowned_lead_alert_loop")
    except ImportError as exc:
        logger.warning("[UNOWNED LEAD] scheduler unavailable: %s", exc)

    try:
        from src.schedulers.speed_to_lead import speed_to_lead_loop
        asyncio.create_task(speed_to_lead_loop(), name="speed_to_lead_loop")
    except ImportError as exc:
        logger.warning("[SPEED-TO-LEAD] scheduler unavailable: %s", exc)

    try:
        from src.schedulers.marketing_attribution_scheduler import (
            marketing_attribution_loop,
        )
        asyncio.create_task(marketing_attribution_loop(), name="marketing_attribution_loop")
    except ImportError as exc:
        logger.warning("[ADS ATTRIBUTION] scheduler unavailable: %s", exc)

    try:
        from src.services.core.finance.income_supervisor import income_supervisor_loop
        asyncio.create_task(income_supervisor_loop(), name="income_supervisor_loop")
    except ImportError as exc:
        logger.warning("[INCOME SUPERVISOR] scheduler unavailable: %s", exc)

    try:
        from src.schedulers.jamoa_ritm_scheduler import jamoa_ritm_loop
        asyncio.create_task(jamoa_ritm_loop(bot_runtime), name="jamoa_ritm_loop")
    except ImportError as exc:
        logger.warning("[JAMOA-RITM] scheduler unavailable: %s", exc)

    # Soatlik guruh check-in oʻchirilgan; oʻrniga kunlik "eng muhim ish" kun tartibi.
    try:
        from src.schedulers.daily_priority_checkin import daily_priority_checkin_loop
        asyncio.create_task(daily_priority_checkin_loop(bot_runtime), name="daily_priority_checkin_loop")
    except ImportError as exc:
        logger.warning("[DAILY] scheduler unavailable: %s", exc)
    try:
        from src.context import app_ctx
        from src.schedulers.community_sync_scheduler import community_sync_loop, register

        register(app_ctx)
        asyncio.create_task(community_sync_loop(app_ctx), name="community_sync_loop")
    except ImportError as exc:
        logger.warning("[COMMUNITY_SYNC] scheduler unavailable: %s", exc)
    try:
        from src.schedulers.juma_greeting_scheduler import juma_greeting_loop
        asyncio.create_task(juma_greeting_loop(bot_runtime), name="juma_greeting_loop")
    except ImportError as exc:
        logger.warning("[JUMA] scheduler unavailable: %s", exc)
    try:
        from src.schedulers.cockpit_autopilot_scheduler import (
            start_cockpit_autopilot_scheduler,
        )
        start_cockpit_autopilot_scheduler(bot_runtime)
    except ImportError as exc:
        logger.warning("COCKPIT AUTOPILOT scheduler unavailable: %s", exc)

    try:
        from src.handlers.metasell_menu import configure_telegram_menu_button
        asyncio.create_task(configure_telegram_menu_button(), name="configure_telegram_menu_button")
    except (ImportError, RuntimeError, OSError) as exc:
        logger.debug("[TELEGRAM MENU] configuration skipped: %s", exc)
