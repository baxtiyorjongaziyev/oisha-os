"""
Callback queries and text reply handlers for financial approval inline flows.
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.services.core.finance.approval.keyboards import (
    QUICK_CATEGORIES,
    _approval_key,
    _category_key,
    _change_owner_key,
    _edit_key,
    _skip_key,
    build_approval_keyboard,
    build_approval_message,
    build_category_keyboard,
)
from src.services.core.finance.approval.state import (
    _get_or_load_pending,
    _pending,
    _pending_edit,
    register_pending,
)

logger = logging.getLogger("HisobchiApproval")

async def handle_callback(
    callback_data: str,
    event: Any,
    engine: Any,
) -> bool:
    """
    Callback handler — Telethon callback event yoki Aiogram CallbackQuery'dan chaqiriladi.

    Returns True if handled.
    """
    # ── OWNERSHIP TOGGLE ──────────────────────────────────────────────
    if callback_data.startswith("howner:"):
        parts = callback_data.split(":")
        if len(parts) != 3:
            return False
        try:
            tx_id = int(parts[1])
            new_owner = parts[2]
        except (ValueError, IndexError):
            return False

        pending = await _get_or_load_pending(tx_id, engine)
        if pending:
            pending["ownership"] = new_owner
            kb = build_approval_keyboard(tx_id, new_owner)
            if kb:
                try:
                    await event.edit(buttons=kb)
                except Exception as exc:
                    logger.debug("[HISOBCHI] Edit ownership button: %s", exc)
            await event.answer(f"📊 {'🏢 Biznes' if new_owner == 'business' else '🏠 Shaxsiy'} tanlandi")
            return True

        await event.answer("⚠️ Topilmadi")
        return False

    # ── APPROVE ───────────────────────────────────────────────────────
    if callback_data.startswith("happrove:"):
        parts = callback_data.split(":")
        if len(parts) != 3:
            return False
        try:
            tx_id = int(parts[1])
            ownership = parts[2]
        except (ValueError, IndexError):
            return False

        pending = await _get_or_load_pending(tx_id, engine)
        if not pending:
            await event.answer("⚠️ Topilmadi yoki allaqachon tasdiqlangan")
            return False

        category = pending.get("category") or "❓ Noma'lum"
        tx = pending.get("tx")

        # Categorize and learn
        try:
            await engine.categorize(tx_id, category, ownership)
            if tx:
                await engine.learn_rule(
                    merchant=getattr(tx, "merchant", ""),
                    card_suffix=getattr(tx, "card_suffix", ""),
                    direction=getattr(tx, "direction", "out"),
                    amount=getattr(tx, "amount", 0),
                    category=category,
                    ownership=ownership,
                )
                await engine.learn_category(getattr(tx, "merchant", ""), category)
        except Exception as exc:
            logger.error("[HISOBCHI] Approve xatolik: %s", exc)

        # Edit message to show approved status
        try:
            dir_icon = "➖" if getattr(tx, "direction", "out") == "out" else "➕"
            owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
            amt_val = getattr(tx, "amount", None)
            amt_str = _fmt_money(amt_val) if amt_val is not None else "?"
            approved_text = (
                f"✅ <b>Tasdiqlandi</b>\n\n"
                f"{dir_icon} {amt_str} UZS\n"
                f"🗂 {html.escape(category)}\n"
                f"📊 {owner_label}"
            )
            await event.edit(approved_text, parse_mode="html")
        except Exception as exc:
            logger.debug("[HISOBCHI] Edit approved text: %s", exc)

        # Cleanup
        for key in list(_pending.keys()):
            if _pending[key].get("tx_id") == tx_id:
                _pending.pop(key, None)

        await event.answer("✅ Tasdiqlandi!")
        return True

    # ── EDIT (show category selection) ────────────────────────────────
    if callback_data.startswith("hedit:"):
        parts = callback_data.split(":")
        if len(parts) != 2:
            return False
        try:
            tx_id = int(parts[1])
        except (ValueError, IndexError):
            return False

        await _get_or_load_pending(tx_id, engine)
        kb = build_category_keyboard(tx_id)
        if kb:
            try:
                await event.edit(
                    "📂 <b>Kategoriyani tanlang:</b>",
                    parse_mode="html",
                    buttons=kb,
                )
            except Exception as exc:
                logger.debug("[HISOBCHI] Edit category keyboard: %s", exc)

        await event.answer("✏️ Kategoriyani tanlang")
        return True

    # ── CATEGORY SELECTION ────────────────────────────────────────────
    if callback_data.startswith("hcat:"):
        parts = callback_data.split(":")
        if len(parts) != 3:
            return False
        try:
            tx_id = int(parts[1])
            category = parts[2].replace(";", ":")
        except (ValueError, IndexError):
            return False

        pending = await _get_or_load_pending(tx_id, engine)
        if pending:
            pending["category"] = category
            ownership = pending.get("ownership", "business")

            # Show back to approval with selected category
            try:
                tx = pending.get("tx")
                if tx:
                    msg = build_approval_message(tx, tx_id, ownership)
                    msg = f"🗂 <b>Kategoriya:</b> {html.escape(category)}\n\n" + msg
                    kb = build_approval_keyboard(tx_id, ownership)
                    if kb:
                        await event.edit(msg, parse_mode="html", buttons=kb)
            except Exception as exc:
                logger.debug("[HISOBCHI] Edit category selection: %s", exc)

        await event.answer(f"🗂 {category} tanlandi")
        return True

    # ── SKIP ──────────────────────────────────────────────────────────
    if callback_data.startswith("hskip:"):
        parts = callback_data.split(":")
        if len(parts) != 2:
            return False
        try:
            tx_id = int(parts[1])
        except (ValueError, IndexError):
            return False

        try:
            await engine.skip(tx_id)
        except Exception as exc:
            logger.error("[HISOBCHI] Skip xatolik: %s", exc)

        # Edit message
        try:
            await event.edit("⏭ <b>O'tkazib yuborildi</b>", parse_mode="html")
        except Exception as exc:
            logger.debug("[HISOBCHI] Edit skip text: %s", exc)

        # Cleanup
        for key in list(_pending.keys()):
            if _pending[key].get("tx_id") == tx_id:
                _pending.pop(key, None)

        await event.answer("⏭ O'tkazib yuborildi")
        return True

    # ── BACK TO APPROVAL ──────────────────────────────────────────────
    if callback_data.startswith("hback:"):
        parts = callback_data.split(":")
        if len(parts) != 2:
            return False
        try:
            tx_id = int(parts[1])
        except (ValueError, IndexError):
            return False

        pending = await _get_or_load_pending(tx_id, engine)
        if pending:
            tx = pending.get("tx")
            ownership = pending.get("ownership", "business")
            category = pending.get("category")
            if tx:
                msg = build_approval_message(tx, tx_id, ownership)
                if category:
                    msg = f"🗂 <b>Kategoriya:</b> {html.escape(category)}\n\n" + msg
                kb = build_approval_keyboard(tx_id, ownership)
                if kb:
                    try:
                        await event.edit(msg, parse_mode="html", buttons=kb)
                    except Exception as exc:
                        logger.debug("[HISOBCHI] Edit back to approval: %s", exc)

        await event.answer("🔙 Ortga")
        return True

    return False


async def handle_text_reply(
    event: Any,
    engine: Any,
) -> bool:
    """
    Admin reply text handler — category yoki ownership o'zgartirish uchun.
    Returns True if handled.
    """
    user_id = getattr(event.sender_id, "user_id", None) or getattr(event, "sender_id", None)
    if not user_id:
        return False

    # Check if user is in edit mode
    approve_key = _pending_edit.get(user_id)
    if not approve_key:
        return False

    text = (event.message.message or "").strip()
    if not text:
        return False

    pending = _pending.get(approve_key)
    if not pending:
        _pending_edit.pop(user_id, None)
        return False

    tx_id = pending.get("tx_id")
    ownership = pending.get("ownership", "business")

    # Use replied text as category
    await engine.categorize(tx_id, text, ownership)
    tx = pending.get("tx")
    if tx:
        try:
            await engine.learn_rule(
                merchant=tx.merchant,
                card_suffix=tx.card_suffix,
                direction=tx.direction,
                amount=tx.amount,
                category=text,
                ownership=ownership,
            )
            await engine.learn_category(tx.merchant, text)
        except Exception as exc:
            logger.debug("[HISOBCHI] Learn category from text reply: %s", exc)

    # Edit message
    try:
        dir_icon = "➖" if tx.direction == "out" else "➕" if tx else "💳"
        owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
        approved_text = (
            f"✅ <b>Tasdiqlandi</b>\n\n"
            f"{dir_icon} {_fmt_money(tx.amount) if tx else '?'} UZS\n"
            f"🗂 {html.escape(text)}\n"
            f"📊 {owner_label}"
        )
        await event.edit(approved_text, parse_mode="html")
    except Exception as exc:
        logger.debug("[HISOBCHI] Edit text reply approved: %s", exc)

    # Cleanup
    _pending_edit.pop(user_id, None)
    for key in list(_pending.keys()):
        if _pending[key].get("tx_id") == tx_id:
            _pending.pop(key, None)

    return True

