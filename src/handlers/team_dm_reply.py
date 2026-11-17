"""Jamoa aʼzosi @jonairobot ga shaxsan yozsa — Oisha AI javob beradi.

Faqat shaxsiy chat, faqat jamoa roʻyxatidagi aʼzo (admin emas: adminlar oʻz
buyruq/qidiruv handlerlariga ega). Boshqa hamma xabar keyingi handlerlarga oʻtadi.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _text_of(message: Any) -> str:
    return getattr(message, "text", None) or getattr(message, "caption", None) or ""


def build_team_dm_filter(is_admin: Callable[[int], bool]) -> Callable[[Any], Any]:
    async def _is_team_dm(message: Any) -> bool:
        try:
            chat = getattr(message, "chat", None)
            user = getattr(message, "from_user", None)
            if getattr(chat, "type", None) != "private" or user is None or getattr(user, "is_bot", False):
                return False
            text = _text_of(message).strip()
            if not text or text.startswith("/"):
                return False
            if is_admin(user.id):
                return False
            from src.services.core.daily_priority.team import find_member

            return find_member(user.id) is not None
        except Exception:
            logger.error("[TEAM-DM] Filtrda xato.", exc_info=True)
            return False

    return _is_team_dm


def register_team_dm_handlers(
    dispatcher: Any, *, msg_controller: Any, is_admin: Callable[[int], bool]
) -> None:
    async def _handle_team_dm(message: Any) -> None:
        user = message.from_user
        text = _text_of(message).strip()
        try:
            answer = await msg_controller.get_response(
                user_id=user.id,
                user_name=user.first_name or "Jamoa",
                message=text,
                context={
                    "username": user.username or "yoq",
                    "is_business": False,
                    "chat_id": message.chat.id,
                    "is_team_dm": True,
                    "is_bot": False,
                },
            )
            if answer:
                await message.answer(answer, parse_mode=None)
        except Exception:
            logger.error("[TEAM-DM] Javob berishda xato.", exc_info=True)

    dispatcher.message.register(_handle_team_dm, build_team_dm_filter(is_admin))
    logger.info("[TEAM-DM] Faol.")
