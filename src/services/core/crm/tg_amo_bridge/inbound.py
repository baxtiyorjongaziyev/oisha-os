"""Telegram -> amoCRM chat. Handles client messages and the manager's own replies."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Optional

from . import media as media_mod
from .accounts import Account
from .amojo_client import AmoJoClient, STATUS_DELIVERED
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.inbound")

# Wait for outbound.dispatch to record the tg message id of a message that
# amoCRM itself asked us to send, so it is not echoed back as a manager reply.
_ECHO_GRACE_SECONDS = 1.5


def _sources_enabled() -> bool:
    return os.getenv("TG_AMO_SOURCES_ENABLED", "0").strip().lower() in {"1", "true", "yes"}


def _describe(message: Any) -> str:
    """Caption/text, or a placeholder so media messages are not dropped."""
    text = (getattr(message, "raw_text", None) or "").strip()
    if text:
        return text
    other = media_mod.describe_non_file(message)
    if other:
        return other
    if getattr(message, "sticker", None):
        return "[stiker]"
    if getattr(message, "voice", None):
        return "[ovozli xabar]"
    if getattr(message, "photo", None):
        return "[rasm]"
    if getattr(message, "document", None) or getattr(message, "media", None):
        return "[fayl]"
    return ""


def _has_file(message: Any) -> bool:
    return media_mod.classify(message) is not None or bool(getattr(message, "sticker", None))


async def _resolve_peer_entity(event: Any, is_manager: bool) -> Any:
    """Return the client Telethon entity (get_chat for outgoing manager replies)."""
    if is_manager and hasattr(event, "get_chat"):
        chat = await event.get_chat()
        if chat is not None:
            return chat
    if hasattr(event, "get_sender"):
        return await event.get_sender()
    return None


def _format_client_name(peer_entity: Any, peer_id: int) -> str:
    return (
        " ".join(
            filter(
                None,
                [getattr(peer_entity, "first_name", None), getattr(peer_entity, "last_name", None)],
            )
        )
        or getattr(peer_entity, "username", None)
        or str(peer_id)
    )


async def _maybe_link_before_send(
    merger: Optional[Any],
    *,
    peer_id: int,
    client_name: str,
    client_phone: Optional[str],
    client_username: Optional[str],
    text: str,
    is_manager: bool,
    source_ext: Optional[str],
) -> Optional[str]:
    resolved_phone = client_phone
    if merger is None:
        return resolved_phone
    try:
        outcome = await merger.ensure_chat_linked_before_send(
            peer_id=peer_id,
            client_name=client_name,
            sender_phone=client_phone,
            message_text="" if is_manager else text,
            username=client_username,
            source_external_id=source_ext,
        )
        if getattr(outcome, "phone", ""):
            return f"+{outcome.phone}"
    except Exception as exc:
        logger.warning("[TG-AMO] auto-merge check failed: %s", type(exc).__name__)
    return resolved_phone


async def _send_and_record(
    *,
    amojo: AmoJoClient,
    store: MessageStore,
    account: Account,
    peer_id: int,
    tg_msg_id: int,
    client_name: str,
    text: str,
    phone: Optional[str],
    source_ext: Optional[str],
    is_manager: bool,
    media: Optional[media_mod.MediaRef] = None,
) -> bool:
    amo_msg_id = str(uuid.uuid4())
    event_body = amojo.build_message_event(
        conversation_id=str(peer_id),
        sender_id=str(peer_id),
        sender_name=client_name,
        text=text,
        msg_id=amo_msg_id,
        phone=phone,
        source_external_id=source_ext,
        silent=is_manager,
        is_manager=is_manager,
        manager_id=f"oisha-tg-{account.key}",
        manager_ref_id=os.getenv("AMOCRM_BRIDGE_MANAGER_REF_ID") or None,
        manager_name=account.display_name,
        media_type=media.media_type if media else None,
        media_url=media.url if media else None,
        file_name=media.file_name if media else None,
        file_size=media.file_size if media else None,
    )
    if await amojo.send_event(event_body) is None:
        logger.warning("[TG-AMO] amoCRM rejected/failed message from tg msg %s", tg_msg_id)
        return False
    await store.record(amo_msg_id, tg_msg_id, account.key, peer_id, "tg_out" if is_manager else "tg_in")
    if is_manager:
        await amojo.send_status(amo_msg_id, STATUS_DELIVERED)
    return True


async def handle_message(
    event: Any,
    account: Account,
    amojo: AmoJoClient,
    store: MessageStore,
    *,
    is_non_client: Optional[Any] = None,
    merger: Optional[Any] = None,
) -> bool:
    """Forward one Telethon NewMessage event. Returns True if sent to amoCRM."""
    if not getattr(event, "is_private", False):
        return False
    message = event.message
    peer_id = getattr(event, "chat_id", None)
    text = _describe(message)
    if not peer_id or peer_id <= 0 or not text:
        return False

    is_manager = bool(getattr(event, "out", False))
    if is_manager:
        await asyncio.sleep(_ECHO_GRACE_SECONDS)
        if await store.has_tg_msg(account.key, message.id):
            return False  # sent by us on amoCRM's request

    peer_entity = await _resolve_peer_entity(event, is_manager)
    if getattr(peer_entity, "bot", False):
        return False
    client_name = _format_client_name(peer_entity, peer_id)
    client_phone = getattr(peer_entity, "phone", None)
    skip_automerge = False
    if is_non_client is not None and (not is_manager or merger is not None):
        skip, reason = await is_non_client(phone=client_phone, user_id=peer_id, name=client_name)
        if skip:
            if not is_manager:
                logger.info("[TG-AMO] skip non-client chat (%s)", reason)
                return False
            skip_automerge = True

    source_ext = account.source_external_id if _sources_enabled() else None
    resolved_phone = await _maybe_link_before_send(
        None if skip_automerge else merger,
        peer_id=peer_id,
        client_name=client_name,
        client_phone=client_phone,
        client_username=getattr(peer_entity, "username", None),
        text=text,
        is_manager=is_manager,
        source_ext=source_ext,
    )
    media_ref = None
    if _has_file(message):
        caption = (getattr(message, "raw_text", None) or "").strip()
        media_ref, fallback = await media_mod.prepare_inbound(message, peer_id)
        if media_ref is not None:
            text = caption
        elif fallback:
            text = f"{fallback}\n{caption}".strip() if caption else fallback
    return await _send_and_record(
        amojo=amojo, store=store, account=account, peer_id=peer_id, tg_msg_id=message.id,
        client_name=client_name, text=text, phone=resolved_phone, source_ext=source_ext, is_manager=is_manager,
        media=media_ref,
    )


def register(
    client: Any,
    account: Account,
    amojo: AmoJoClient,
    store: MessageStore,
    is_non_client=None,
    merger=None,
) -> None:
    """Attach incoming+outgoing private handlers to a Telethon client."""
    from telethon import events

    async def _on_msg(event):
        try:
            await handle_message(
                event, account, amojo, store, is_non_client=is_non_client, merger=merger
            )
        except Exception as exc:  # never break the userbot loop
            logger.error("[TG-AMO] inbound error: %s", type(exc).__name__)

    client.add_event_handler(_on_msg, events.NewMessage(incoming=True))
    client.add_event_handler(_on_msg, events.NewMessage(outgoing=True))
