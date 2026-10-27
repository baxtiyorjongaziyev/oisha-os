"""Sotuvchi Oisha'ning soatlik check-in xabariga reply qilsa, Oisha do'st-murabbiy sifatida javob beradi.

Faqat check-in guruhida, odam yozgan va aynan botning check-in xabariga qilingan reply
ushlanadi. Qolgan xabarlar boshqa handlerlarga (Hamroh, legacy) o'tadi.
CRM'ga yozilmaydi: vazifalarni qo'ng'iroq tahlili (STT) o'zi qo'yadi.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CHECKIN_MARKERS = ("lid", "qo'ng'iroq", "raqam")


def _text_of(message: Any) -> str:
    return getattr(message, "text", None) or getattr(message, "caption", None) or ""


def is_checkin_text(text: str) -> bool:
    lowered = (text or "").lower()
    return lowered.startswith("assalomu alaykum") and any(m in lowered for m in CHECKIN_MARKERS)


def _default_group_id() -> Optional[int]:
    from src.schedulers.remote_staff_checkin_scheduler import get_target_destination

    return get_target_destination()[0]


def register_seller_reply_handlers(
    dispatcher: Any,
    *,
    group_id_getter: Callable[[], Optional[int]] = _default_group_id,
) -> None:
    """Hamroh'dan OLDIN ulanadi, aks holda check-in reply'ini Hamroh oddiy savol deb oladi."""

    async def _is_checkin_reply(message: Any) -> bool:
        try:
            user = getattr(message, "from_user", None)
            reply = getattr(message, "reply_to_message", None)
            if user is None or getattr(user, "is_bot", False) or reply is None:
                return False
            if getattr(message.chat, "id", None) != group_id_getter():
                return False
            me = await message.bot.me()
            reply_user = getattr(reply, "from_user", None)
            if getattr(reply_user, "id", None) != me.id:
                return False
            reply_text = _text_of(reply)
            # AI yozgan check-in qolipsiz bo'ladi: bot xabari javob berayotgan odamni @username bilan chaqirgan bo'lsa ham check-in.
            username = getattr(user, "username", None)
            mentions_replier = bool(username) and f"@{username}".lower() in reply_text.lower()
            return mentions_replier or is_checkin_text(reply_text)
        except Exception:
            logger.error("[SELLER-REPLY] Filtrda xato.", exc_info=True)
            return False

    async def _handle(message: Any) -> None:
        from src.services.core.checkin_composer import save_context
        from src.services.core.sales_coach_reply import coach_reply
        from src.time_utils import get_local_now

        try:
            now = get_local_now()
            name = getattr(message.from_user, "first_name", None) or "do'stim"
            reply_text = _text_of(message)
            save_context({"date": now.strftime("%Y-%m-%d"), "last_reply": reply_text})
            answer = await coach_reply(name, reply_text, _text_of(message.reply_to_message))
            await message.reply(answer, parse_mode=None)
        except Exception:
            logger.error("[SELLER-REPLY] Javob berishda xato.", exc_info=True)

    dispatcher.message.register(_handle, _is_checkin_reply)
    logger.info("[SELLER-REPLY] Faol.")
