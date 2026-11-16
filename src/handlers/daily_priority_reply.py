"""Jamoa aʼzosi Oishaʼga shaxsan yozsa — kunlik "eng muhim ish" suhbatini davom ettiradi.

Faqat shaxsiy chat, faqat roʻyxatdagi aʼzo va faqat bugun unga savol ketgan boʻlsa
ushlanadi; qolgan holatlarda xabar boshqa handlerlarga oʻtadi.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _text_of(message: Any) -> str:
    return getattr(message, "text", None) or getattr(message, "caption", None) or ""


async def _is_daily_reply(message: Any) -> bool:
    try:
        chat = getattr(message, "chat", None)
        user = getattr(message, "from_user", None)
        if getattr(chat, "type", None) != "private" or user is None or getattr(user, "is_bot", False):
            return False
        if not _text_of(message).strip():
            return False
        from src.services.core.daily_priority import state as st
        from src.services.core.daily_priority.team import find_member
        from src.time_utils import get_local_now

        member = find_member(getattr(user, "id", None))
        if not member:
            return False
        day = get_local_now().strftime("%Y-%m-%d")
        return st.get_entry(st.load(), day, member["key"]) is not None
    except Exception:
        logger.error("[DAILY-REPLY] Filtrda xato.", exc_info=True)
        return False


async def _handle_daily_reply(message: Any) -> None:
    from src.services.core.daily_priority.engine import handle_reply
    from src.time_utils import get_local_now

    try:
        answer = await handle_reply(message.from_user.id, _text_of(message), get_local_now())
        if answer:
            await message.answer(answer)
    except Exception:
        logger.error("[DAILY-REPLY] Javob berishda xato.", exc_info=True)


def register_daily_priority_handlers(dispatcher: Any) -> None:
    dispatcher.message.register(_handle_daily_reply, _is_daily_reply)
    logger.info("[DAILY-REPLY] Faol.")
