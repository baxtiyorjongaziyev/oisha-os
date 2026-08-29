"""
Runtime installation, message interception hookup, and background worker setup.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.services.core.salescoach_runtime.adapters import (
    AmoCRMConversationMatcher,
    AmoCRMTaskAdapter,
    TelethonConversationLoader,
    _env_bool,
    _env_int,
    _parse_id_list,
)
from src.services.core.salescoach_runtime.notifier import (
    TelegramSalesCoachNotifier,
    handle_salescoach_callback,
)

logger = logging.getLogger("TelegramSalesCoachRuntime")


async def _personal_sender_checker(sender: Any) -> bool:
    try:
        from src.main import _is_personal_folder_sender

        return bool(await _is_personal_folder_sender(sender))
    except Exception as exc:
        logger.warning("Personal folder adapter failed: %s", type(exc).__name__)
        return True


def _internal_user_ids(settings: Any) -> set[int]:
    values = _parse_id_list(os.getenv("SALESCOACH_INTERNAL_TELEGRAM_IDS", ""))
    owner_id = int(getattr(settings, "OWNER_ID", 0) or 0)
    if owner_id:
        values.add(owner_id)
    for item in getattr(settings, "SALES_MANAGER_IDS", []) or []:
        try:
            values.add(int(item))
        except (TypeError, ValueError):
            continue
    return values


async def install_telegram_salescoach(context: Any) -> Optional[TelegramSalesCoach]:
    """Install once on the Oracle userbot runtime; default is disabled."""
    from src.settings import settings

    if not _env_bool(
        "TELEGRAM_SALESCOACH_ENABLED",
        bool(getattr(settings, "TELEGRAM_SALESCOACH_ENABLED", False)),
    ):
        return None
    if getattr(context, "telegram_salescoach", None) is not None:
        return context.telegram_salescoach

    client = getattr(context, "client", None)
    msg_controller = getattr(context, "msg_controller", None)
    if client is None or msg_controller is None:
        return None

    salescoach_sync = get_salescoach_sync()
    if not salescoach_sync.enabled:
        logger.warning("Telegram SalesCoach disabled: salescoach_api_unconfigured")
        return None

    store = TelegramSalesCoachStore(msg_controller.db)
    await store.initialize()
    mode = os.getenv(
        "TELEGRAM_SALESCOACH_MODE",
        str(getattr(settings, "TELEGRAM_SALESCOACH_MODE", "shadow")),
    ).strip().lower()
    bot_runtime = getattr(context, "bot_runtime", None)
    if mode in {"approval", "auto"} and bot_runtime is None:
        logger.warning("Telegram SalesCoach disabled: bot_runtime_unavailable")
        return None
    notifier = TelegramSalesCoachNotifier(
        bot_runtime=bot_runtime,
        owner_id=int(getattr(settings, "OWNER_ID", 0) or 0),
    )
    amocrm_adapter = AmoCRMTaskAdapter(msg_controller.crm.amocrm)
    task_writer = SalesCoachTaskWriter(
        amocrm=amocrm_adapter,
        store=store,
        admin_notifier=notifier,
    )
    coach = TelegramSalesCoach(
        store=store,
        salescoach_sync=salescoach_sync,
        crm_matcher=AmoCRMConversationMatcher(
            db=msg_controller.db,
            amocrm=msg_controller.crm.amocrm,
        ),
        task_writer=task_writer,
        message_loader=TelethonConversationLoader(client, limit=50),
        personal_sender_checker=_personal_sender_checker,
        internal_user_ids=_internal_user_ids(settings),
        approval_notifier=notifier,
        enabled=True,
        mode=mode,
        idle_seconds=_env_int(
            "TELEGRAM_SALESCOACH_IDLE_SECONDS",
            int(getattr(settings, "TELEGRAM_SALESCOACH_IDLE_SECONDS", 600)),
        ),
    )

    async def _event_handler(event: Any) -> None:
        try:
            sender = await event.get_sender()
            await coach.handle_private_event(
                event,
                sender=sender,
                client=client,
            )
        except Exception as exc:
            logger.warning("SalesCoach event hook failed: %s", type(exc).__name__)

    client.add_event_handler(_event_handler, events.NewMessage(incoming=True))
    client.add_event_handler(_event_handler, events.NewMessage(outgoing=True))
    context.telegram_salescoach = coach
    context.telegram_salescoach_store = store
    context.salescoach_task_writer = task_writer
    logger.info(
        "Telegram SalesCoach installed: mode=%s idle_seconds=%s",
        coach.mode,
        coach.idle_seconds,
    )
    return coach
