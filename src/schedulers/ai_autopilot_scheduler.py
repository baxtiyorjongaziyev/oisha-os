"""AI Autopilot background scheduler for automated lead tasks, call scans and outreach."""

from __future__ import annotations

import asyncio
import logging

from src.context import app_ctx
from src.settings import settings

logger = logging.getLogger("AIAutopilotScheduler")


async def ai_autopilot_loop() -> None:
    """Periodically scan recent leads, dialogs and call recordings for AI automation."""
    await asyncio.sleep(15)
    from src.services.core.call_analyzer import CallAnalyzer
    from src.services.core.telegram.telegram_task_creator import TelegramTaskCreator
    from src.services.utils.voice_processor import VoiceProcessor

    gemini_key = None
    if app_ctx.msg_controller:
        gemini_key = getattr(app_ctx.msg_controller, "api_keys", {}).get("gemini")
    if not gemini_key:
        logger.warning("[AUTOPILOT] Gemini key missing — AI Autopilot loop disabled.")
        return

    voice_proc = VoiceProcessor(api_key=gemini_key)
    task_creator = TelegramTaskCreator(
        amocrm=app_ctx.msg_controller.crm.amocrm,
        db=app_ctx.msg_controller.db,
        user_client=app_ctx.client,
        voice_processor=voice_proc,
        gemini_api_key=gemini_key,
    )
    call_analyzer = CallAnalyzer(
        amocrm=app_ctx.msg_controller.crm.amocrm,
        db=app_ctx.msg_controller.db,
    )

    logger.info("[AUTOPILOT] AI Autopilot loop started.")
    while True:
        try:
            logger.info("[AUTOPILOT] Running periodic AI Autopilot cycle...")
            try:
                leads = await app_ctx.msg_controller.crm.amocrm.get_leads_detailed(limit=30)
                if leads and isinstance(leads, list):
                    for lead in leads:
                        if task_creator.blocks_dialogue_analysis():
                            break
                        lead_id = lead.get("id")
                        if not lead_id:
                            continue
                        phone = None
                        contacts = (
                            lead.get("_embedded", {}).get("contacts", [])
                            or lead.get("contacts", [])
                        )
                        for contact in contacts:
                            fields = contact.get("custom_fields_values") or []
                            for field in fields:
                                if str(field.get("field_code", "")).upper() == "PHONE":
                                    vals = field.get("values") or []
                                    if vals:
                                        phone = str(vals[0].get("value", ""))
                                        break
                            if phone:
                                break
                        phone_getter = getattr(
                            app_ctx.msg_controller.crm.amocrm, "get_primary_contact_phone", None
                        )
                        if not phone and callable(phone_getter):
                            phone = await phone_getter(lead)
                        if phone:
                            await task_creator.create_amocrm_tasks_from_chat(
                                phone_or_username=phone, lead_id=int(lead_id), limit=15
                            )
            except Exception as tg_err:
                logger.error("[AUTOPILOT] Telegram Task Creator error: %s", tg_err)

            try:
                await call_analyzer.analyze_recent_calls(
                    limit=30,
                    min_call_duration_seconds=settings.AMOCRM_CALL_ANALYSIS_MIN_DURATION_SECONDS,
                )
            except Exception as call_err:
                logger.error("[AUTOPILOT] Call Analyzer error: %s", call_err)

            logger.info("[AUTOPILOT] AI Autopilot cycle completed.")
        except Exception as exc:
            logger.error("[AUTOPILOT] Critical error in autopilot loop: %s", exc)

        interval = getattr(settings, "AUTOPILOT_INTERVAL_SECONDS", 180)
        await asyncio.sleep(interval)
