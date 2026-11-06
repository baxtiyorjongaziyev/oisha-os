"""Telegram -> amoCRM chat. Handles client messages and the manager's own replies."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Optional

from .accounts import Account
from .amojo_client import AmoJoClient, STATUS_DELIVERED
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.inbound")

# Wait for outbound.dispatch to record the tg message id of a message that
# amoCRM itself asked us to send, so it is not echoed back as a manager reply.
_ECHO_GRACE_SECONDS = 1.5


def _describe(message: Any) -> str:
    """Text for amoCRM. Media is a placeholder until the media stage."""
    text = (getattr(message, "raw_text", None) or "").strip()
    if text:
        return text
    if getattr(message, "voice", None):
        return "[ovozli xabar]"
    if getattr(message, "photo", None):
        return "[rasm]"
    if getattr(message, "document", None) or getattr(message, "media", None):
        return "[fayl]"
    return ""


async def handle_message(
    event: Any,
    account: Account,
    amojo: AmoJoClient,
    store: MessageStore,
    *,
    is_non_client: Optional[Any] = None,
) -> bool:
    """Forward one Telethon NewMessage event. Returns True if sent to amoCRM."""
    if not getattr(event, "is_private", False):
        return False
    message = event.message
    peer_id = getattr(event, "chat_id", None)
    if not peer_id or peer_id <= 0:
        return False

    text = _describe(message)
    if not text:
        return False

    is_manager = bool(getattr(event, "out", False))
    if is_manager:
        await asyncio.sleep(_ECHO_GRACE_SECONDS)
        if await store.has_tg_msg(account.key, message.id):
            return False  # sent by us on amoCRM's request

    sender = await event.get_sender() if hasattr(event, "get_sender") else None
    if getattr(sender, "bot", False):
        return False
    client_name = (
        " ".join(filter(None, [getattr(sender, "first_name", None), getattr(sender, "last_name", None)]))
        or getattr(sender, "username", None)
        or str(peer_id)
    )
    if not is_manager and is_non_client is not None:
        skip, reason = await is_non_client(
            phone=getattr(sender, "phone", None), user_id=peer_id, name=client_name
        )
        if skip:
            logger.info("[TG-AMO] skip non-client chat (%s)", reason)
            return False

    # The chat peer is always the client; build_message_event moves it to the
    # receiver side for manager messages.
    amo_msg_id = str(uuid.uuid4())
    event_body = amojo.build_message_event(
        conversation_id=str(peer_id),
        sender_id=str(peer_id),
        sender_name=client_name,
        text=text,
        msg_id=amo_msg_id,
        phone=getattr(sender, "phone", None),
        source_external_id=account.source_external_id,
        silent=is_manager,
        is_manager=is_manager,
    )
    result = await amojo.send_event(event_body)
    if result is None:
        logger.warning("[TG-AMO] amoCRM rejected/failed message from tg msg %s", message.id)
        return False
    await store.record(
        amo_msg_id, message.id, account.key, peer_id, "tg_out" if is_manager else "tg_in"
    )
    if is_manager:
        await amojo.send_status(amo_msg_id, STATUS_DELIVERED)
    return True


def register(client: Any, account: Account, amojo: AmoJoClient, store: MessageStore, is_non_client=None) -> None:
    """Attach incoming+outgoing private handlers to a Telethon client."""
    from telethon import events

    async def _on_msg(event):
        try:
            await handle_message(event, account, amojo, store, is_non_client=is_non_client)
        except Exception as exc:  # never break the userbot loop
            logger.error("[TG-AMO] inbound error: %s", type(exc).__name__)

    client.add_event_handler(_on_msg, events.NewMessage(incoming=True))
    client.add_event_handler(_on_msg, events.NewMessage(outgoing=True))
