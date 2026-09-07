"""Aiogram bot-token head lifecycle.

Restores the wiring dropped when ``bootstrap/runtime.py`` was split into
``orchestration/*`` (commit 5f682b41). Only the @jonairobot bot-token head is
touched here; the Telethon userbot is unaffected.
"""
from __future__ import annotations

import logging
from typing import Any

from src.services.core.admin_aiogram_dispatcher import (
    maybe_build_admin_aiogram_dispatcher,
    register_hisobchi_aiogram_callbacks,
    register_salescoach_aiogram_callbacks,
)
from src.services.core.telegram.aiogram_head import AiogramBotHead
from src.services.core.telegram.aiogram_telethon_compat import (
    AiogramTelethonCompatClient,
)
from src.services.core.telegram.telegram_ai_features import BOT_API_10_ALLOWED_UPDATES

logger = logging.getLogger("OishaBootstrap")


async def init_aiogram_bot_head(
    *,
    bot_runtime: Any,
    bot_ingress_mode: str,
    admin_bot: Any,
    access_manager: Any,
    msg_controller: Any,
    db: Any,
    hisobchi_engine: Any,
    api_module: Any,
    app_ctx: Any,
) -> Any:
    """Compose and start the Aiogram bot-token head. Returns the head or None.

    No-op (returns None) unless backend is aiogram and ingress is polling; the
    caller keeps its existing Telethon ``admin_bot.start()`` path in that case.
    """
    if bot_runtime.backend != "aiogram" or bot_ingress_mode != "polling":
        return None

    crm = getattr(msg_controller, "crm", None)

    async def _get_sales_today_priorities():
        from src.services.core.business_command_center import (
            collect_sales_today_priorities,
        )

        return await collect_sales_today_priorities(
            getattr(crm, "amocrm", None), limit=7
        )

    async def _get_project_delivery_risks():
        from src.services.core.business_command_center import (
            collect_project_delivery_risks,
        )

        return await collect_project_delivery_risks(
            getattr(crm, "airtable", None), limit=7
        )

    async def _get_finance_project_risks():
        from src.services.core.business_command_center import (
            collect_finance_project_risks,
        )

        return await collect_finance_project_risks(
            getattr(crm, "airtable", None), limit=7
        )

    async def _get_team_capacity():
        from src.services.core.business_command_center import (
            collect_team_capacity_snapshot,
        )

        return await collect_team_capacity_snapshot(
            getattr(crm, "airtable", None), limit=7
        )

    async def _get_command_center():
        from src.services.core.business_command_center import (
            collect_business_command_snapshot,
        )

        return await collect_business_command_snapshot(
            amocrm=getattr(crm, "amocrm", None),
            project_source=getattr(crm, "airtable", None),
            finance_source=getattr(crm, "airtable", None),
            limit=3,
        )

    def _get_amocrm_client():
        return getattr(crm, "amocrm", None)

    async def _perform_global_lookup(phone: str):
        fn = getattr(admin_bot, "_perform_global_lookup", None)
        if fn is None:
            return None
        return await fn(phone)

    dispatcher = maybe_build_admin_aiogram_dispatcher(
        enabled=True,
        owner_id=access_manager.owner_id,
        get_role=access_manager.get_role,
        get_role_name=access_manager.get_role_name,
        is_admin=access_manager.is_admin,
        get_today_stats=db.get_today_stats,
        cached_crm_audit=getattr(api_module, "cached_crm_audit", {}) or {},
        get_sales_today_priorities=_get_sales_today_priorities,
        get_project_delivery_risks=_get_project_delivery_risks,
        get_finance_project_risks=_get_finance_project_risks,
        get_team_capacity=_get_team_capacity,
        get_command_center=_get_command_center,
        get_amocrm_client=_get_amocrm_client,
        perform_global_lookup=_perform_global_lookup,
        db=db,
    )
    if dispatcher is None:
        logger.warning(
            "[BOT] Aiogram dispatcher build returned None; head not started."
        )
        return None

    legacy_bot_compat = AiogramTelethonCompatClient(
        bot=bot_runtime.bot, dispatcher=dispatcher
    )
    admin_bot.bot_client = legacy_bot_compat
    await admin_bot.start()

    if hisobchi_engine is not None:
        register_hisobchi_aiogram_callbacks(dispatcher, engine=hisobchi_engine)
    register_salescoach_aiogram_callbacks(dispatcher, context=app_ctx)

    legacy_bot_compat.attach()

    head = AiogramBotHead(
        bot=bot_runtime.bot,
        dispatcher=dispatcher,
        allowed_updates=BOT_API_10_ALLOWED_UPDATES,
        raw_update_handler=api_module.process_telegram_ai_update,
    )
    head.start()
    app_ctx.aiogram_bot_head = head
    app_ctx.admin_aiogram_dispatcher = dispatcher
    api_module.set_telegram_ai_ingress_status(mode="aiogram", active=True)
    logger.info("[BOT] Aiogram bot-token head restored and polling.")
    return head
