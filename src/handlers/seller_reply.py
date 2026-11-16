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


def _matches_rep_greeting(reply_text: str, rep_name: str) -> bool:
    name = (rep_name or "").strip().lower()
    if not name:
        return False
    lowered = (reply_text or "").lstrip().lower()
    return (
        lowered.startswith(f"{name},")
        or lowered.startswith(f"{name} (")
        or lowered.startswith(f"assalomu alaykum, {name}")
    )


def _resolve_rep(message: Any, reply_text: str) -> Optional[dict]:
    from src.schedulers.remote_staff_checkin_scheduler import get_reps

    reps = get_reps()
    reply = getattr(message, "reply_to_message", None)
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id is None and reply is not None:
        thread_id = getattr(reply, "message_thread_id", None)
    if thread_id is not None:
        for rep in reps:
            if rep.get("topic") == thread_id:
                return rep

    user = getattr(message, "from_user", None)
    username = (getattr(user, "username", None) or "").lstrip("@").lower()
    if username:
        for rep in reps:
            rep_tg = str(rep.get("tg") or "").lstrip("@").lower()
            if rep_tg and rep_tg == username:
                return rep

    for rep in reps:
        if _matches_rep_greeting(reply_text, str(rep.get("name") or "")):
            return rep
    return None


async def _matches_checkin_reply(
    message: Any, group_id_getter: Callable[[], Optional[int]]
) -> bool:
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
        username = getattr(user, "username", None)
        mentions_replier = bool(username) and f"@{username}".lower() in reply_text.lower()
        if mentions_replier or is_checkin_text(reply_text):
            return True
        thread_id = getattr(message, "message_thread_id", None) or getattr(
            reply, "message_thread_id", None
        )
        if thread_id is None:
            return False
        rep = _resolve_rep(message, reply_text)
        if not rep or rep.get("topic") != thread_id:
            return False
        rep_tg = str(rep.get("tg") or "").lstrip("@").lower()
        if rep_tg and username and rep_tg != username.lstrip("@").lower():
            return False
        return _matches_rep_greeting(reply_text, str(rep.get("name") or ""))
    except Exception:
        logger.error("[SELLER-REPLY] Filtrda xato.", exc_info=True)
        return False


async def _handle_checkin_reply(message: Any) -> None:
    from src.schedulers.remote_staff_checkin_scheduler import rep_storage
    from src.services.core.adaptive_learning import is_owner_user, record_owner_feedback_rule
    from src.services.core.checkin_composer import save_context
    from src.services.core.sales_coach_reply import coach_reply
    from src.time_utils import get_local_now

    try:
        now = get_local_now()
        user = getattr(message, "from_user", None)
        name = getattr(user, "first_name", None) or "doʻstim"
        reply_text = _text_of(message)
        reply_to_text = _text_of(message.reply_to_message)
        is_owner = is_owner_user(user)
        if is_owner:
            await record_owner_feedback_rule(
                reply_text,
                user_id=getattr(user, "id", None),
                speaker=name,
                chat_id=getattr(getattr(message, "chat", None), "id", None),
            )
        else:
            rep = _resolve_rep(message, reply_to_text)
            rep_key = str(rep.get("key") or "rayxon") if rep else "rayxon"
            _, _, context_file = rep_storage(rep_key)
            save_context({"date": now.strftime("%Y-%m-%d"), "last_reply": reply_text}, path=context_file)
        answer = await coach_reply(name, reply_text, reply_to_text, is_owner=is_owner)
        await message.reply(answer, parse_mode=None)
    except Exception:
        logger.error("[SELLER-REPLY] Javob berishda xato.", exc_info=True)


def register_seller_reply_handlers(
    dispatcher: Any,
    *,
    group_id_getter: Callable[[], Optional[int]] = _default_group_id,
) -> None:
    """Hamroh'dan OLDIN ulanadi, aks holda check-in reply'ini Hamroh oddiy savol deb oladi."""

    async def _is_checkin_reply(message: Any) -> bool:
        return await _matches_checkin_reply(message, group_id_getter)

    dispatcher.message.register(_handle_checkin_reply, _is_checkin_reply)
    logger.info("[SELLER-REPLY] Faol.")
