"""
Callback queries and text reply handlers for financial approval inline flows.
"""
from __future__ import annotations

import html
import logging
from typing import Any

from src.services.core.finance.approval.keyboards import (
    build_approval_keyboard,
    build_approval_message,
    build_category_keyboard,
)
from src.services.core.finance.approval.state import (
    _get_or_load_pending,
    _pending,
    _pending_edit,
)

logger = logging.getLogger("HisobchiApproval")


def _fmt_money(val: Any) -> str:
    try:
        return f"{float(val):,.0f}".replace(",", " ")
    except (ValueError, TypeError):
        return str(val)


async def _handle_ownership_toggle(callback_data: str, event: Any, engine: Any) -> bool:
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


async def _handle_approve_callback(callback_data: str, event: Any, engine: Any) -> bool:
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
    try:
        await engine.categorize(tx_id, category, ownership)
        if tx:
            await engine.learn_rule(
                merchant=getattr(tx, "merchant", ""), card_suffix=getattr(tx, "card_suffix", ""),
                direction=getattr(tx, "direction", "out"), amount=getattr(tx, "amount", 0),
                category=category, ownership=ownership,
            )
            await engine.learn_category(getattr(tx, "merchant", ""), category)
    except Exception as exc:
        logger.error("[HISOBCHI] Approve xatolik: %s", exc)

    try:
        dir_icon = "➖" if getattr(tx, "direction", "out") == "out" else "➕"
        owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
        amt_str = _fmt_money(getattr(tx, "amount", None))
        await event.edit(f"✅ <b>Tasdiqlandi</b>\n\n{dir_icon} {amt_str} UZS\n🗂 {html.escape(category)}\n📊 {owner_label}", parse_mode="html")
    except Exception as exc:
        logger.debug("[HISOBCHI] Edit approved text: %s", exc)

    for key in list(_pending.keys()):
        if _pending[key].get("tx_id") == tx_id:
            _pending.pop(key, None)
    await event.answer("✅ Tasdiqlandi!")
    return True


async def _handle_edit_and_category(callback_data: str, event: Any, engine: Any) -> bool:
    if callback_data.startswith("hedit:"):
        tx_id = int(callback_data.split(":")[1])
        await _get_or_load_pending(tx_id, engine)
        kb = build_category_keyboard(tx_id)
        if kb:
            await event.edit("📂 <b>Kategoriyani tanlang:</b>", parse_mode="html", buttons=kb)
        await event.answer("✏️ Kategoriyani tanlang")
        return True

    # hcat:tx_id:category
    parts = callback_data.split(":")
    tx_id, category = int(parts[1]), parts[2].replace(";", ":")
    pending = await _get_or_load_pending(tx_id, engine)
    if pending:
        pending["category"] = category
        ownership = pending.get("ownership", "business")
        tx = pending.get("tx")
        if tx:
            msg = f"🗂 <b>Kategoriya:</b> {html.escape(category)}\n\n" + build_approval_message(tx, tx_id, ownership)
            kb = build_approval_keyboard(tx_id, ownership)
            if kb:
                await event.edit(msg, parse_mode="html", buttons=kb)
    await event.answer(f"🗂 {category} tanlandi")
    return True


async def _handle_skip_and_back(callback_data: str, event: Any, engine: Any) -> bool:
    tx_id = int(callback_data.split(":")[1])
    if callback_data.startswith("hskip:"):
        try:
            await engine.skip(tx_id)
            await event.edit("⏭ <b>O'tkazib yuborildi</b>", parse_mode="html")
        except Exception as exc:
            logger.error("[HISOBCHI] Skip error: %s", exc)
        for key in list(_pending.keys()):
            if _pending[key].get("tx_id") == tx_id:
                _pending.pop(key, None)
        await event.answer("⏭ O'tkazib yuborildi")
        return True

    # hback:
    pending = await _get_or_load_pending(tx_id, engine)
    if pending and pending.get("tx"):
        msg = build_approval_message(pending["tx"], tx_id, pending.get("ownership", "business"))
        if pending.get("category"):
            msg = f"🗂 <b>Kategoriya:</b> {html.escape(pending['category'])}\n\n" + msg
        kb = build_approval_keyboard(tx_id, pending.get("ownership", "business"))
        if kb:
            await event.edit(msg, parse_mode="html", buttons=kb)
    await event.answer("🔙 Ortga")
    return True


async def handle_callback(callback_data: str, event: Any, engine: Any) -> bool:
    """Callback query dispatcher."""
    if callback_data.startswith("howner:"):
        return await _handle_ownership_toggle(callback_data, event, engine)
    if callback_data.startswith("happrove:"):
        return await _handle_approve_callback(callback_data, event, engine)
    if callback_data.startswith(("hedit:", "hcat:")):
        return await _handle_edit_and_category(callback_data, event, engine)
    if callback_data.startswith(("hskip:", "hback:")):
        return await _handle_skip_and_back(callback_data, event, engine)
    return False


async def handle_text_reply(event: Any, engine: Any) -> bool:
    """Text reply handler for editing merchant or category directly."""
    if not event.message.reply_to_msg_id or not event.message.text:
        return False
    reply_to_id = event.message.reply_to_msg_id
    edit_info = _pending_edit.get(reply_to_id)
    if not edit_info:
        return False

    tx_id = edit_info["tx_id"]
    new_text = event.message.text.strip()
    try:
        await engine.categorize(tx_id, new_text, "business")
        await event.respond(f"✅ Yangilandi: `{new_text}`")
        _pending_edit.pop(reply_to_id, None)
        return True
    except Exception as exc:
        logger.error("[HISOBCHI] Text reply edit failed: %s", exc)
    return False
