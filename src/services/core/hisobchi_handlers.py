"""
Hisobchi AI — Telethon userbot handlers.

Flow:
  1. Card bot message arrives (private from @HUMOcardbot / @CardXabarBot)
  2. Parse transaction
  3. Auto-categorize if merchant known, else ask finance group
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


def _get_finance_group_id() -> Optional[int]:
    try:
        from src.settings import settings
        return getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None)
    except Exception:
        return None


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

    finance_group_id = _get_finance_group_id()

    # Check merchant memory for auto-categorization
    known_cat = await engine.get_known_category(tx.merchant)

    if known_cat:
        # Auto-categorize: save immediately, notify finance group
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
                )
            except Exception as exc:
                logger.error("[HISOBCHI] Failed to notify finance group: %s", exc)
    else:
        # Unknown merchant: save as pending, ask finance group
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
                )
                # Store message ID so we can match the reply
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
    finance_group_id = _get_finance_group_id()
    if not finance_group_id:
        return False

    chat_id = event.chat_id
    if chat_id != finance_group_id:
        return False

    msg = event.message
    reply_to = getattr(msg, "reply_to", None)
    if not reply_to:
        return False

    replied_msg_id = getattr(reply_to, "reply_to_msg_id", None)
    if not replied_msg_id:
        return False

    text = (msg.message or "").strip()
    if not text or text.startswith("/"):
        # /skip command
        if text.lower().startswith("/skip"):
            parts = text.split()
            tx_id_str = parts[1] if len(parts) > 1 else None
            if tx_id_str and tx_id_str.isdigit():
                await engine.skip(int(tx_id_str))
                await event.reply("⏭ O'tkazib yuborildi.")
                return True
        return False

    # Find the pending transaction linked to this message
    tx = await engine.get_pending_by_finance_msg(
        finance_chat_id=finance_group_id,
        finance_msg_id=replied_msg_id,
    )
    if not tx:
        return False  # Not a hisobchi question reply

    category = text.strip()
    tx_id = tx["id"]
    merchant = tx["merchant"]

    # Save category + learn
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
    """Quick check: is this sender one of the tracked card bots?"""
    username = (getattr(sender, "username", None) or "").lower()
    return username in CARD_BOT_USERNAMES
