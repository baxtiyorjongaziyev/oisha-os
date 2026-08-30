"""
Callback event handlers for CRM note approval actions.
"""
from __future__ import annotations

from typing import Any

import structlog
from src.services.core.crm.note_approval.state import (
    _pending,
    _pending_edit,
    post_notes_to_amocrm,
)

logger = structlog.get_logger()


async def handle_callback(callback_data: str, bot_or_event: Any, new_text: str = "") -> bool:
    if callback_data.startswith("crm_approve:"):
        pending = _pending.get(callback_data)
        if not pending:
            try:
                answer_fn = getattr(bot_or_event, "answer", None)
                if answer_fn:
                    await answer_fn("⚠️ So'rov topilmadi (bot qayta ishga tushgandirmi?).")
            except Exception:
                logger.debug(
                    "Failed to answer callback: pending approval not found",
                    exc_info=True,
                )
            return False
        ok = await post_notes_to_amocrm(
            pending["amocrm"], pending["lead_id"], pending["note_texts"]
        )
        if ok:
            _pending.pop(callback_data, None)
        try:
            reply_fn = getattr(bot_or_event, "answer", None) or getattr(bot_or_event, "respond", None)
            if reply_fn:
                msg = "✅ CRM ga izoh qo'shildi!" if ok else "❌ CRM ga yozishda xatolik"
                await reply_fn(msg)
        except Exception:
            logger.debug(
                "Failed to reply with CRM post result",
                exc_info=True,
            )
        return ok

    if callback_data.startswith("crm_edit:"):
        approve_key = callback_data.replace("crm_edit:", "crm_approve:", 1)
        pending = _pending.get(approve_key)
        if not pending:
            try:
                answer_fn = getattr(bot_or_event, "answer", None)
                if answer_fn:
                    await answer_fn("⚠️ So'rov topilmadi (bot qayta ishga tushgandirmi?).")
            except Exception:
                logger.debug(
                    "Failed to answer callback: edit pending approval not found",
                    exc_info=True,
                )
            return False
        if new_text:
            pending["note_texts"] = [new_text] + (
                pending["note_texts"][1:] if len(pending["note_texts"]) > 1 else []
            )
            ok = await post_notes_to_amocrm(
                pending["amocrm"], pending["lead_id"], pending["note_texts"]
            )
            if ok:
                _pending.pop(approve_key, None)
            try:
                reply_fn = getattr(bot_or_event, "answer", None) or getattr(bot_or_event, "respond", None)
                if reply_fn:
                    msg = "✅ Tahrirlangan izoh CRM ga qo'shildi!" if ok else "❌ Xatolik"
                    await reply_fn(msg)
            except Exception:
                logger.debug(
                    "Failed to reply with edited note result",
                    exc_info=True,
                )
            return ok
        else:
            try:
                user_id = getattr(bot_or_event, "sender_id", None)
                if user_id:
                    _pending_edit[user_id] = approve_key
                answer_fn = getattr(bot_or_event, "answer", None)
                if answer_fn:
                    try:
                        await answer_fn("✏️ Tahrirlashni boshlang")
                    except Exception:
                        logger.debug(
                            "Failed to answer callback: start edit acknowledgement",
                            exc_info=True,
                        )
                respond_fn = getattr(bot_or_event, "respond", None)
                if respond_fn:
                    first_note = (pending["note_texts"] or [""])[0]
                    await respond_fn(
                        "✏️ Yangi izoh matnini yuboring.\n"
                        f"(Joriy tahlil matni):\n`{first_note[:300]}`"
                    )
            except Exception:
                logger.warning(
                    "Failed to send edit prompt message to user",
                    exc_info=True,
                )
            return True

    return False
