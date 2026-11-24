"""amoCRM chat -> Telegram (webhook payload dispatch through the manager's userbot)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from . import accounts
from . import media as media_mod
from .amojo_client import AmoJoClient, STATUS_DELIVERED, STATUS_ERROR
from .store import MessageStore

logger = logging.getLogger("TgAmoBridge.outbound")

_MAX_TEXT = 4096
_MAX_CAPTION = 1024
_MIN_INTERVAL = 1.0  # seconds between sends per account (ban safety)
_locks: Dict[str, asyncio.Lock] = {}
_bg_tasks: set = set()


async def _archive_then_cleanup(path: str, peer_id: int) -> None:
    try:
        await media_mod.archive_outbound(path, peer_id)
    finally:
        media_mod.cleanup(path)


def _log_outbound_shape(data: dict, media: Optional[dict]) -> None:
    """Log non-PII structural keys of amoJo media/empty webhooks for live verification."""
    msg = data.get("message")
    msg_dict = msg if isinstance(msg, dict) else {}
    nested = msg_dict.get("message")
    nested_dict = nested if isinstance(nested, dict) else {}
    inner = nested_dict or msg_dict
    media_field = "media" if inner.get("media") else ("media_url" if inner.get("media_url") else "none")
    raw_url = inner.get("media") or inner.get("media_url") or ""
    host = urlparse(raw_url).netloc if isinstance(raw_url, str) and raw_url.startswith("http") else ""
    logger.info(
        "[TG-AMO] outbound shape outer_keys=%s inner_keys=%s type=%s media_field=%s host=%s parsed=%s",
        sorted(msg_dict.keys()),
        sorted(nested_dict.keys()),
        str(inner.get("type") or ""),
        media_field,
        host,
        bool(media),
    )


def _extract(data: dict) -> Tuple[str, str, str, str]:
    """(amo_msg_id, text, client_id, source_external_id) from a webhook body.

    amoJo's exact shape is not verified against a live account, so both the
    flat form (message.text) and the nested form (message.message.text) are read.
    """
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    inner = message.get("message") if isinstance(message.get("message"), dict) else {}
    text = message.get("text") or inner.get("text") or ""
    amo_msg_id = str(message.get("msg_id") or inner.get("id") or message.get("id") or "")
    receiver = message.get("receiver") if isinstance(message.get("receiver"), dict) else {}
    conversation = message.get("conversation") if isinstance(message.get("conversation"), dict) else {}
    client_id = str(conversation.get("client_id") or receiver.get("id") or "")
    src = message.get("source") or data.get("source") or {}
    source = src.get("external_id") if isinstance(src, dict) else ""
    return amo_msg_id, text, client_id, source or ""


async def _send_to_telegram(
    client: Any, tg_user_id: int, text: str, media: Optional[dict]
) -> Tuple[List[Any], Optional[str]]:
    if media is None:
        return [await client.send_message(tg_user_id, text)], None
    path = await media_mod.fetch_to_temp(media["url"], media["name"])
    caption, rest = (text[:_MAX_CAPTION] or None), text[_MAX_CAPTION:]
    try:
        sent = await client.send_file(
            tg_user_id,
            path,
            caption=caption,
            voice_note=media["type"] == "voice",
            force_document=media["type"] == "file",
        )
        results = [sent]
        if rest:
            results.append(await client.send_message(tg_user_id, rest))
        return results, path
    except Exception:
        media_mod.cleanup(path)
        raise


async def dispatch(
    data: dict, amojo: AmoJoClient, store: MessageStore
) -> Tuple[int, Dict[str, Any]]:
    """Send a manager reply from amoCRM to Telegram. Returns (http_status, body)."""
    amo_msg_id, text, client_id, source = _extract(data)
    media = media_mod.extract_outbound_media(data)
    if media is not None or not text:
        _log_outbound_shape(data, media)
    if not client_id:
        return 200, {"status": "ok", "warning": "no_recipient"}
    if (not text and media is None) or len(text) > _MAX_TEXT:
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
            sent_list, path = await _send_to_telegram(client, tg_user_id, text, media)
            await asyncio.sleep(_MIN_INTERVAL)
        except Exception as exc:
            logger.error("[TG-AMO] send failed: %s", type(exc).__name__)
            if amo_msg_id:
                await amojo.send_status(amo_msg_id, STATUS_ERROR, type(exc).__name__)
            return 502, {"error": "dispatch_failed"}

    if path:
        task = asyncio.create_task(_archive_then_cleanup(path, tg_user_id))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)

    if amo_msg_id:
        for idx, sent in enumerate(sent_list):
            rec_id = amo_msg_id if idx == 0 else f"{amo_msg_id}:part{idx}"
            await store.record(rec_id, getattr(sent, "id", None), account.key, tg_user_id, "amo_out")
        await amojo.send_status(amo_msg_id, STATUS_DELIVERED)
    return 200, {"status": "ok", "msg_id": amo_msg_id}
