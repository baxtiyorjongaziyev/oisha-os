"""Hamroh: @jonairobot jamoa guruhida jim kuzatadi va faqat murojaat qilinganda javob beradi.

- Kuzatuv: aiogram ``message`` outer-middleware — jamoa guruhidagi a'zolar matnini
  ``jamoa_xabarlar`` ga yozadi va boshqa handlerlarga xalaqit bermaydi (hech qachon xato tashlamaydi).
- Javob: xabarda ``@bot`` bo'lsa yoki bot xabariga reply qilinsa. Buyruqlar (``/...``),
  boshqa botlar, quiet-hours (23:00–07:00) va tezlik chegarasi (``ReplyLimiter``) javobsiz qoladi.

Eslatma: botga guruhdagi oddiy xabarlar kelishi uchun u guruh admini bo'lishi yoki
BotFather'da Group Privacy o'chirilgan bo'lishi kerak.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

from src.services.core.jamoa_ritm.brain import HamrohBrain
from src.services.core.jamoa_ritm.config import JamoaConfig, load_config
from src.services.core.jamoa_ritm.guard import ReplyLimiter, extract_question, is_addressed
from src.services.core.jamoa_ritm.store import ROLE_HAMROH, ROLE_MEMBER, JamoaStore

logger = logging.getLogger(__name__)

CONTEXT_SECONDS = 24 * 3600
CONTEXT_LIMIT = 60
EMPTY_MENTION_REPLY = "Eshitaman. Savolingizni shu xabarga reply qilib yozing."


def _display_name(user: Any) -> str:
    return (
        getattr(user, "full_name", None)
        or getattr(user, "first_name", None)
        or getattr(user, "username", None)
        or "A'zo"
    )


def _text_of(message: Any) -> str:
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    if text:
        return text
    contact = getattr(message, "contact", None)
    if contact is not None:
        parts = [getattr(contact, "first_name", "") or "", getattr(contact, "last_name", "") or ""]
        full_name = " ".join(p.strip() for p in parts if p and p.strip())
        phone = getattr(contact, "phone_number", "") or ""
        if full_name or phone:
            return f"[Kontakt: {full_name} {phone}]".strip()
    return ""


def _default_quiet_check() -> bool:
    from src.time_utils import is_quiet_hours

    return is_quiet_hours()


class HamrohService:
    def __init__(
        self,
        cfg: JamoaConfig,
        store: JamoaStore,
        brain: HamrohBrain,
        limiter: Optional[ReplyLimiter] = None,
        quiet_check: Callable[[], bool] = _default_quiet_check,
    ):
        self.cfg = cfg
        self.store = store
        self.brain = brain
        self.limiter = limiter or ReplyLimiter()
        self.quiet_check = quiet_check

    def _from_member(self, message: Any) -> bool:
        chat = getattr(message, "chat", None)
        user = getattr(message, "from_user", None)
        return (
            chat is not None
            and getattr(chat, "id", None) == self.cfg.group_id
            and user is not None
            and not getattr(user, "is_bot", False)
        )

    async def observe(self, message: Any) -> None:
        if not self._from_member(message):
            return
        try:
            await self.store.save_message(
                chat_id=message.chat.id,
                message_id=getattr(message, "message_id", None),
                user_id=message.from_user.id,
                user_name=_display_name(message.from_user),
                text=_text_of(message),
                role=ROLE_MEMBER,
            )
        except Exception:
            logger.error("[HAMROH] Xabar xotiraga yozilmadi.", exc_info=True)

    async def is_for_me(self, message: Any) -> bool:
        if not self._from_member(message):
            return False
        me = await message.bot.me()
        reply = getattr(message, "reply_to_message", None)
        reply_user = getattr(reply, "from_user", None) if reply is not None else None
        return is_addressed(
            _text_of(message),
            bot_username=getattr(me, "username", None),
            bot_id=getattr(me, "id", None),
            reply_to_user_id=getattr(reply_user, "id", None),
        )

    async def respond(self, message: Any) -> Optional[str]:
        if self.quiet_check():
            logger.info("[HAMROH] Quiet-hours: javob berilmadi.")
            return None
        if not self.limiter.allow(message.from_user.id):
            logger.info("[HAMROH] Tezlik chegarasi: javob berilmadi.")
            return None
        me = await message.bot.me()
        question = extract_question(_text_of(message), getattr(me, "username", None))
        if question:
            since = int(time.time()) - CONTEXT_SECONDS
            context = await self.store.recent_messages(message.chat.id, since, limit=CONTEXT_LIMIT)
            answer = await self.brain.answer(question, context, asker=_display_name(message.from_user))
        else:
            answer = EMPTY_MENTION_REPLY
        await message.reply(answer, parse_mode=None)
        await self.store.save_message(
            chat_id=message.chat.id, text=answer, user_name="Hamroh", role=ROLE_HAMROH
        )
        return answer


def register_jamoa_hamroh_handlers(
    dispatcher: Any,
    *,
    config_loader: Callable[[], JamoaConfig] = load_config,
    store: Optional[JamoaStore] = None,
    brain: Optional[HamrohBrain] = None,
) -> Optional[HamrohService]:
    """Legacy catch-all (``AiogramTelethonCompatClient.attach``) dan OLDIN chaqirilishi kerak."""
    cfg = config_loader()
    if not cfg.hamroh_active or getattr(dispatcher, "message", None) is None:
        logger.info("[HAMROH] O'chiq (JAMOA_GROUP_ID yo'q yoki JAMOA_HAMROH_ENABLED=0).")
        return None
    service = HamrohService(cfg, store or JamoaStore(), brain or HamrohBrain())

    async def _observer(handler: Any, event: Any, data: dict) -> Any:
        await service.observe(event)
        return await handler(event, data)

    async def _addressed(message: Any) -> bool:
        try:
            return await service.is_for_me(message)
        except Exception:
            logger.error("[HAMROH] Murojaatni aniqlashda xato.", exc_info=True)
            return False

    async def _reply(message: Any) -> None:
        try:
            await service.respond(message)
        except Exception:
            logger.error("[HAMROH] Javob berishda xato.", exc_info=True)

    dispatcher.message.outer_middleware.register(_observer)
    dispatcher.message.register(_reply, _addressed)
    logger.info("[HAMROH] Faol: guruh=%s", cfg.group_id)
    return service
