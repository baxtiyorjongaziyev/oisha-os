"""Sotuvchi Oisha'ning soatlik check-in xabariga reply qilsa, javobni amoCRM vazifalariga aylantiradi.

Faqat check-in guruhida, odam yozgan va aynan botning check-in xabariga qilingan reply
ushlanadi. Qolgan xabarlar boshqa handlerlarga (Hamroh, legacy) o'tadi.
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
    amocrm_getter: Callable[[], Any],
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
        from src.services.core.seller_reply_tasks import (
            apply_actions,
            extract_actions,
            format_summary,
        )
        from src.services.core.checkin_composer import save_context
        from src.time_utils import get_local_now

        try:
            now = get_local_now()
            name = getattr(message.from_user, "first_name", None) or "do'stim"
            actions = await extract_actions(_text_of(message), _text_of(message.reply_to_message), now)
            save_context({"date": now.strftime("%Y-%m-%d"), "last_reply": _text_of(message)})
            amocrm = amocrm_getter()
            if amocrm is None:
                logger.warning("[SELLER-REPLY] amoCRM client yo'q, vazifalar yaratilmadi.")
                await message.reply(f"Rahmat, {name}! Yozganlaringizni oldim 🙌", parse_mode=None)
                return
            result = await apply_actions(amocrm, actions, now)
            await message.reply(format_summary(name, result), parse_mode=None)
            logger.info(
                "[SELLER-REPLY] created=%d unresolved=%d skipped=%d",
                len(result.created), len(result.unresolved), len(result.skipped),
            )
        except Exception:
            logger.error("[SELLER-REPLY] Javobni qayta ishlashda xato.", exc_info=True)

    dispatcher.message.register(_handle, _is_checkin_reply)
    logger.info("[SELLER-REPLY] Faol.")
