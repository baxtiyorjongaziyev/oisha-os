"""
Event handler setup and message pipeline registration.
"""
from __future__ import annotations

import logging
from typing import Any

from telethon import events

import src.config as src_config
from src.context import app_ctx
from src.services.core.finance.handlers import (
    handle_card_bot_message,
    handle_finance_group_reply,
    handle_hisobchi_command,
    handle_qarz_command,
    handle_byudjet_command,
    handle_kirim_chiqim_text,
    handle_receipt_photo,
    handle_valyuta_command,
    handle_kassa_command,
    handle_otkazma_command,
    handle_xodim_command,
    is_card_bot_sender,
    should_process_private_receipt_photo,
)
from src.settings import settings
from src.handlers.kirim import kirim_topic_handler
from src.handlers.case_publisher import case_publisher_handler
from src.handlers.negotiation import negotiation_agent_handler
from src.handlers.shadow_advisor import shadow_advisor_handler
from src.handlers.monitoring import activity_monitor_handler
from src.handlers.meeting import meeting_scheduler_handler
from src.entrypoint.message_event import handle_new_message, self_command_handler

logger = logging.getLogger("OishaBootstrap")


def register_event_handlers(
    client: Any,
    bot_client: Any,
    bot_runtime: Any,
    hisobchi_engine: Any,
    hisobchi_analyst: Any,
    m: Any,
    me: Any,
) -> None:
    async def _hisobchi_event_handler(event):
        try:
            if me and event.is_private and event.chat_id == me.id:
                return

            sender = await event.get_sender()
            if event.is_private and not event.out and is_card_bot_sender(sender):
                await handle_card_bot_message(event, client, hisobchi_engine, bot_client=bot_runtime)
                raise events.StopPropagation
            if not event.is_private and not event.out:
                if await handle_finance_group_reply(
                    event, client, hisobchi_engine, bot_client=bot_runtime
                ):
                    raise events.StopPropagation
                return
            if event.is_private and not event.out:
                text = (event.message.message or "").strip()
                is_owner = sender and sender.id == src_config.OWNER_ID
                if is_owner and text.startswith("/"):
                    lowered = text.lower()
                    handled = True
                    if lowered.startswith("/hisobchi"):
                        handled = await handle_hisobchi_command(event, client, hisobchi_engine, hisobchi_analyst)
                    elif lowered.startswith("/qarz"):
                        handled = await handle_qarz_command(event, hisobchi_engine)
                    elif lowered.startswith("/byudjet"):
                        handled = await handle_byudjet_command(event, hisobchi_engine)
                    elif lowered.startswith("/valyuta"):
                        handled = await handle_valyuta_command(event, hisobchi_engine)
                    elif lowered.startswith("/kassa"):
                        handled = await handle_kassa_command(event, hisobchi_engine)
                    elif lowered.startswith("/otkazma"):
                        handled = await handle_otkazma_command(event, hisobchi_engine)
                    elif lowered.startswith("/xodim"):
                        handled = await handle_xodim_command(event, hisobchi_engine)
                    elif lowered.startswith("/kirim") or lowered.startswith("/chiqim"):
                        handled = await handle_kirim_chiqim_text(event, hisobchi_engine)
                    if handled:
                        raise events.StopPropagation
                if should_process_private_receipt_photo(
                    is_owner=bool(is_owner),
                    has_photo=bool(event.message.photo),
                    text=text,
                ):
                    if await handle_receipt_photo(event, hisobchi_engine):
                        raise events.StopPropagation
        except events.StopPropagation:
            raise
        except Exception as exc:
            logger.error("[HISOBCHI] Dedicated handler failed: %s", exc, exc_info=True)

    if client:
        client.add_event_handler(
            _hisobchi_event_handler,
            events.NewMessage(incoming=True),
        )

        if settings.TEAM_GROUP_ID and settings.TOPIC_KIRIM_ID:
            client.add_event_handler(
                kirim_topic_handler,
                events.NewMessage(chats=settings.TEAM_GROUP_ID),
            )
            logger.info(f"[KIRIM] Listener active team={settings.TEAM_GROUP_ID} topic={settings.TOPIC_KIRIM_ID}")

        client.add_event_handler(case_publisher_handler, events.NewMessage(incoming=True))
        client.add_event_handler(negotiation_agent_handler, events.NewMessage(incoming=True))
        client.add_event_handler(shadow_advisor_handler, events.NewMessage(incoming=True))
        client.add_event_handler(activity_monitor_handler, events.NewMessage(outgoing=True))
        client.add_event_handler(meeting_scheduler_handler, events.NewMessage(incoming=True))
        client.add_event_handler(meeting_scheduler_handler, events.NewMessage(outgoing=True))
        client.add_event_handler(self_command_handler, events.NewMessage(chats="me"))
        client.add_event_handler(handle_new_message, events.NewMessage(incoming=True))

    async def _hisobchi_callback_handler(event):
        try:
            from src.services.core.hisobchi_approval import handle_callback
            data = event.data.decode("utf-8") if isinstance(event.data, bytes) else event.data
            if data and data.startswith(("scapprove:", "screject:")):
                from src.services.core.telegram_salescoach_runtime import handle_salescoach_callback
                await handle_salescoach_callback(str(data), event, app_ctx)
                raise events.StopPropagation
            if data and (data.startswith("happrove:") or data.startswith("hedit:") or
                         data.startswith("hskip:") or data.startswith("hcat:") or
                         data.startswith("howner:") or data.startswith("hback:")):
                logger.info("[HISOBCHI] Callback received: %s", data)
                try:
                    await handle_callback(data, event, hisobchi_engine)
                except Exception as exc:
                    logger.error("[HISOBCHI] handle_callback failed for %s: %s", data, exc, exc_info=True)
                    try:
                        await event.answer("⚠️ Xatolik yuz berdi, qayta urinib ko'ring.")
                    except Exception as answer_exc:
                        logger.debug("[HISOBCHI] Callback error answer failed: %s", answer_exc)
                raise events.StopPropagation
        except events.StopPropagation:
            raise
        except Exception as exc:
            logger.error("[HISOBCHI] Callback handler failed: %s", exc, exc_info=True)

    if bot_runtime.backend == "telethon":
        if client:
            client.add_event_handler(_hisobchi_callback_handler, events.CallbackQuery())
        if bot_client is not None:
            bot_client.add_event_handler(_hisobchi_callback_handler, events.CallbackQuery())
    logger.info("[EVENTS] Safe userbot handlers registered.")
