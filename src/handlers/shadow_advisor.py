"""Shadow advisor handler — real-time monitoring for incoming messages."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _env_enabled(name: str) -> bool:
    import os
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _should_block_private_userbot_reply(event) -> bool:
    return bool(getattr(event, "is_private", False)) and not bool(
        getattr(event, "out", False)
    )


async def run_autonomous_advice(
    chat_id: int,
    sender_name: str,
    text: str,
    *,
    advisor_agent: Any = None,
    client: Any = None,
    action_parser: Any = None,
    evolution_scheduler: Any = None,
) -> None:
    """Background worker to provide strategic advice without blocking regular message handling."""
    if not _env_enabled("ENABLE_SHADOW_ADVISOR"):
        return
    if not advisor_agent or not client:
        return

    try:
        messages = []
        async for msg in client.iter_messages(chat_id, limit=7):
            s_name = "Mijoz" if msg.incoming else "Siz (Baxtiyor)"
            messages.append(f"[{s_name}]: {msg.text or ''}")

        history_context = "\n".join(reversed(messages))

        advice = await advisor_agent.analyze_and_advise(
            chat_id=chat_id,
            message_text=text,
            history_context=history_context,
            sender_name=sender_name,
        )

        if advice and await advisor_agent.should_notify(chat_id, 0, advice):
            header = f"👸 **Oisha-OS Strategik Maslahati** (Suhbat: {sender_name})\n\n"
            await client.send_message("me", header + advice)

            if "[" in advice and "]" in advice and action_parser:
                await action_parser.parse_and_execute(
                    reply_text=advice,
                    sender_id=chat_id,
                    sender_name=sender_name,
                    username="yoq",
                    saved_phone=None,
                    context={"chat_id": "me"},
                    is_business=False,
                )

        if evolution_scheduler and history_context:
            await evolution_scheduler.on_conversation_end(
                conversation=history_context,
                client_type="lead",
                outcome="advice_given" if advice else "no_action",
                manager_name=sender_name,
                chat_id=chat_id,
            )
    except Exception as exc:
        logger.error("[ADVISOR] Background advice error: %s", exc)


async def shadow_advisor_handler(event):
    """Event-driven shadow advisor for real-time monitoring."""
    if not _env_enabled("ENABLE_SHADOW_ADVISOR"):
        return
    if _should_block_private_userbot_reply(event):
        logger.info("[ADVISOR] Personal DM ignored by policy chat=%s", event.chat_id)
        return
    if event.out or not event.is_private or not event.message.text:
        return

    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        logger.info(
            "[ADVISOR] Bot chat ignored: %s",
            getattr(sender, "id", event.chat_id),
        )
        return

    sender_name = getattr(sender, "first_name", "User")
    await run_autonomous_advice(event.chat_id, sender_name, event.message.text)
