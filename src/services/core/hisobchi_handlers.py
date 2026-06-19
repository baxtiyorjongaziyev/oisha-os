"""
Hisobchi AI — Telethon userbot handlers.

Flow:
  1. Card bot message arrives (private from @HUMOcardbot / @CardXabarBot)
  2. Parse transaction
  3. Auto-categorize if merchant known, else ask finance group (correct topic)
  4. Finance group member replies → learn + save category

Entry points:
  handle_card_bot_message(event, client, engine)
  handle_finance_group_reply(event, client, engine)
"""
from __future__ import annotations

import logging
from typing import Optional

from src.services.core.hisobchi_card_parser import (
    CARD_BOT_USERNAMES,
    parse_card_notification,
)
from src.services.core.hisobchi_engine import HisobchiEngine

logger = logging.getLogger(__name__)

_MAX_CATEGORY_LEN = 100

# Cache: group_id → (kirim_topic_id, chiqim_topic_id)
_topic_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}


def _get_finance_config() -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Returns (group_id, kirim_topic_id, chiqim_topic_id)."""
    try:
        from src.settings import settings
        return (
            getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None),
            getattr(settings, "HISOBCHI_KIRIM_TOPIC_ID", None),
            getattr(settings, "HISOBCHI_CHIQIM_TOPIC_ID", None),
        )
    except Exception:
        return None, None, None


async def _discover_topics(
    client, group_id: int
) -> tuple[Optional[int], Optional[int]]:
    """Auto-discover Kirim and Chiqim topic IDs via Telethon GetForumTopicsRequest.

    Results are cached per group_id for the lifetime of the process.
    """
    if group_id in _topic_cache:
        return _topic_cache[group_id]

    kirim_id: Optional[int] = None
    chiqim_id: Optional[int] = None
    try:
        from telethon.tl.functions.channels import GetForumTopicsRequest

        result = await client(
            GetForumTopicsRequest(
                channel=group_id,
                q="",
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
        for topic in getattr(result, "topics", []):
            title = (getattr(topic, "title", "") or "").strip().lower()
            tid = getattr(topic, "id", None)
            if title == "kirim":
                kirim_id = tid
            elif title == "chiqim":
                chiqim_id = tid

        logger.info(
            "[HISOBCHI] Auto-discovered topics — Kirim: %s, Chiqim: %s",
            kirim_id,
            chiqim_id,
        )
    except Exception as exc:
        logger.warning("[HISOBCHI] Topic auto-discovery failed: %s", exc)

    _topic_cache[group_id] = (kirim_id, chiqim_id)
    return kirim_id, chiqim_id


async def _resolve_topic_ids(
    client, group_id: int, kirim_cfg: Optional[int], chiqim_cfg: Optional[int]
) -> tuple[Optional[int], Optional[int]]:
    """Return (kirim_id, chiqim_id): use .env values if set, else auto-discover."""
    if kirim_cfg is not None and chiqim_cfg is not None:
        return kirim_cfg, chiqim_cfg
    discovered_kirim, discovered_chiqim = await _discover_topics(client, group_id)
    return (
        kirim_cfg if kirim_cfg is not None else discovered_kirim,
        chiqim_cfg if chiqim_cfg is not None else discovered_chiqim,
    )


def _pick_topic(direction: str, kirim_topic: Optional[int], chiqim_topic: Optional[int]) -> Optional[int]:
    if direction == "in":
        return kirim_topic
    return chiqim_topic


async def handle_card_bot_message(event, client, engine: HisobchiEngine) -> None:
    """Called when @HUMOcardbot or @CardXabarBot sends a message."""
    sender = await event.get_sender()
    username = (getattr(sender, "username", None) or "").lower()
    if username not in CARD_BOT_USERNAMES:
        return

    text = event.message.message or ""
    tx = parse_card_notification(username, text)
    if not tx:
        logger.warning("[HISOBCHI] Could not parse card message from @%s", username)
        return

    finance_group_id, kirim_cfg, chiqim_cfg = _get_finance_config()

    kirim_topic_id: Optional[int] = kirim_cfg
    chiqim_topic_id: Optional[int] = chiqim_cfg
    if finance_group_id and (kirim_cfg is None or chiqim_cfg is None):
        kirim_topic_id, chiqim_topic_id = await _resolve_topic_ids(
            client, finance_group_id, kirim_cfg, chiqim_cfg
        )

    topic_id = _pick_topic(tx.direction, kirim_topic_id, chiqim_topic_id)

    known_cat = await engine.get_known_category(tx.merchant)

    if known_cat:
        tx_id = await engine.save_transaction(
            source_bot=tx.source_bot,
            direction=tx.direction,
            amount=tx.amount,
            merchant=tx.merchant,
            card_suffix=tx.card_suffix,
            tx_time=tx.tx_time,
            balance=tx.balance,
            raw_text=text,
            category=known_cat,
            status="categorized",
        )
        logger.info("[HISOBCHI] Auto-categorized tx #%s → %s", tx_id, known_cat)

        if finance_group_id:
            try:
                await client.send_message(
                    finance_group_id,
                    engine.build_auto_msg(tx, known_cat),
                    parse_mode="html",
                    reply_to=topic_id,
                )
            except Exception as exc:
                logger.error("[HISOBCHI] Failed to notify finance group: %s", exc)
    else:
        tx_id = await engine.save_transaction(
            source_bot=tx.source_bot,
            direction=tx.direction,
            amount=tx.amount,
            merchant=tx.merchant,
            card_suffix=tx.card_suffix,
            tx_time=tx.tx_time,
            balance=tx.balance,
            raw_text=text,
            status="pending",
        )
        logger.info("[HISOBCHI] New tx #%s, asking finance group", tx_id)

        if finance_group_id:
            try:
                sent = await client.send_message(
                    finance_group_id,
                    engine.build_finance_question(tx, tx_id),
                    parse_mode="html",
                    reply_to=topic_id,
                )
                await engine.update_finance_msg(
                    tx_id,
                    finance_msg_id=sent.id,
                    finance_chat_id=finance_group_id,
                )
            except Exception as exc:
                logger.error("[HISOBCHI] Failed to send question to finance group: %s", exc)
        else:
            logger.warning(
                "[HISOBCHI] HISOBCHI_FINANCE_GROUP_ID not set — question not sent"
            )


async def handle_finance_group_reply(event, client, engine: HisobchiEngine) -> bool:
    """
    Called for messages in the finance group.
    Returns True if this was a hisobchi reply (so caller can skip other processing).
    """
    finance_group_id, _, _ = _get_finance_config()
    if not finance_group_id:
        return False

    if event.chat_id != finance_group_id:
        return False

    msg = event.message
    reply_to = getattr(msg, "reply_to", None)
    if not reply_to:
        return False

    replied_msg_id = getattr(reply_to, "reply_to_msg_id", None)
    if not replied_msg_id:
        return False

    # First find the linked transaction so /skip without ID also works
    tx = await engine.get_pending_by_finance_msg(
        finance_chat_id=finance_group_id,
        finance_msg_id=replied_msg_id,
    )
    if not tx:
        return False  # Not a hisobchi question reply

    text = (msg.message or "").strip()

    # /skip — with or without explicit tx ID
    if text.lower().startswith("/skip"):
        await engine.skip(tx["id"])
        await event.reply("⏭ O'tkazib yuborildi.")
        return True

    if not text or text.startswith("/"):
        return False

    # Validate category length
    if len(text) > _MAX_CATEGORY_LEN:
        await event.reply(
            f"⚠️ Kategoriya nomi juda uzun (maksimal {_MAX_CATEGORY_LEN} belgi). "
            "Iltimos, qisqaroq nom yuboring."
        )
        return True

    category = text
    tx_id = tx["id"]
    merchant = tx["merchant"]

    await engine.categorize(tx_id, category)
    await engine.learn_category(merchant, category)

    amount_str = f"{tx['amount']:,}".replace(",", " ")
    direction_icon = "➖" if tx["direction"] == "out" else "➕"
    await event.reply(
        f"✅ Saqlandi!\n"
        f"{direction_icon} {amount_str} UZS — <b>{category}</b>\n"
        f"📍 {merchant}\n"
        f"🧠 Keyingi safar avtomatik qo'yiladi.",
        parse_mode="html",
    )
    logger.info("[HISOBCHI] tx #%s categorized as '%s', merchant learned", tx_id, category)
    return True


def is_card_bot_sender(sender) -> bool:
    username = (getattr(sender, "username", None) or "").lower()
    return username in CARD_BOT_USERNAMES
