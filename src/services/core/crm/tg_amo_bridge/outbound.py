"""amoCRM chat -> Telegram (webhook payload dispatch through the manager's userbot)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Tuple

from . import accounts
from .amojo_client import AmoJoClient, STATUS_DELIVERED, STATUS_ERROR
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.outbound")

_MAX_TEXT = 4096
_MIN_INTERVAL = 1.0  # seconds between sends per account (ban safety)
_locks: Dict[str, asyncio.Lock] = {}


def _extract(data: dict) -> Tuple[str, str, str, str]:
    """(amo_msg_id, text, client_id, source_external_id) from a webhook body.

    amoJo's exact shape is not verified against a live account, so both the
    flat form (message.text) and the nested form (message.message.text) are read.
    """
    message = data.get("message") or {}
    inner = message.get("message") if isinstance(message.get("message"), dict) else {}
    text = message.get("text") or inner.get("text") or ""
    amo_msg_id = str(message.get("msg_id") or inner.get("id") or message.get("id") or "")
    receiver = message.get("receiver") or {}
    conversation = message.get("conversation") or {}
    client_id = str(conversation.get("client_id") or receiver.get("id") or "")
    source = (message.get("source") or data.get("source") or {}).get("external_id") or ""
    return amo_msg_id, text, client_id, source


async def dispatch(
    data: dict, amojo: AmoJoClient, store: MessageStore
) -> Tuple[int, Dict[str, Any]]:
    """Send a manager reply from amoCRM to Telegram. Returns (http_status, body)."""
    amo_msg_id, text, client_id, source = _extract(data)
    if not client_id:
        return 200, {"status": "ok", "warning": "no_recipient"}
    if not text or len(text) > _MAX_TEXT:
        return 400, {"error": "invalid_text"}
    try:
        tg_user_id = int(client_id)
        if tg_user_id <= 0:
            raise ValueError
    except ValueError:
        return 400, {"error": "invalid_recipient"}
    if amo_msg_id and await store.has_amo_msg(amo_msg_id):
        return 200, {"status": "ok", "duplicate": True}

    account = accounts.by_source(source)
    client = account.get_client()
    if client is None:
        return 503, {"error": "account_unavailable"}

    lock = _locks.setdefault(account.key, asyncio.Lock())
    async with lock:
        try:
            sent = await client.send_message(tg_user_id, text)
            await asyncio.sleep(_MIN_INTERVAL)
        except Exception as exc:
            logger.error("[TG-AMO] send failed: %s", type(exc).__name__)
            if amo_msg_id:
                await amojo.send_status(amo_msg_id, STATUS_ERROR, type(exc).__name__)
            return 502, {"error": "dispatch_failed"}

    if amo_msg_id:
        await store.record(amo_msg_id, getattr(sent, "id", None), account.key, tg_user_id, "amo_out")
        await amojo.send_status(amo_msg_id, STATUS_DELIVERED)
    return 200, {"status": "ok", "msg_id": amo_msg_id}
