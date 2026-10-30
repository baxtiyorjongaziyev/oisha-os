"""Group name-call handler for the @jonairobot (aiogram) head.

Oisha answers in team groups when:
  * her name is written in free text ("oisha", "oyisha", "оиша", "ойша", "oishaxon"),
  * @jonairobot is tagged, or
  * a message replies to one of the bot's own messages.

Plain group chatter without any of the above is ignored.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger("OishaGroupMention")

# Word-boundary-ish match: the name must not be glued to other letters on the left
# ("poisha" must not match) but suffixes are fine ("oishaga", "oishaxon", "оишам").
_NAME_RE = re.compile(
    r"(?<![0-9a-zа-яёўқғҳ])(oisha|oyisha|oysha|оиша|ойша|оиши|ойши)",
    re.IGNORECASE,
)

_TEAM_GROUP_KEYS = ("jonbranding",)

DIRECT_CALL_FALLBACK = "Ha, shu yerdaman 👋 Nima kerak?"


def is_name_called(text: str, bot_username: Optional[str] = None) -> bool:
    """True if the text addresses Oisha by name or by the bot @username."""
    if not text:
        return False
    if bot_username:
        uname = bot_username.lstrip("@").lower()
        if f"@{uname}" in text.lower():
            return True
    return bool(_NAME_RE.search(text))


def strip_call(text: str, bot_username: Optional[str] = None) -> str:
    """Remove @username (and the leading name) so agents see the actual question."""
    cleaned = text
    if bot_username:
        cleaned = re.sub(
            re.escape("@" + bot_username.lstrip("@")), "", cleaned, flags=re.IGNORECASE
        )
    # Only strip the name when it opens the message ("Oisha, narxni ayt").
    cleaned = re.sub(
        r"^\s*(oisha|oyisha|oysha|оиша|ойша)[\s,:!\-–—]*", "", cleaned, flags=re.IGNORECASE
    )
    return cleaned.strip()


def is_team_chat(chat_id: int, chat_title: Optional[str], team_chat_ids: set[int]) -> bool:
    if chat_id in team_chat_ids:
        return True
    norm = re.sub(r"[^a-z0-9]", "", (chat_title or "").lower())
    return any(key in norm for key in _TEAM_GROUP_KEYS)


def _team_chat_ids() -> set[int]:
    try:
        from src.settings import settings as _s

        ids = {
            _s.TEAM_GROUP_ID,
            _s.CRM_GROUP_ID,
            _s.PROJECTS_GROUP_ID,
            _s.TASKS_GROUP_ID,
            getattr(_s, "CRM_SALES_REPORT_GROUP_ID", None),
            getattr(_s, "TARGET_LEADS_GROUP_ID", None),
            -1003854308552,
        }
        return {i for i in ids if i}
    except Exception:
        logger.debug("team_chat_ids_unavailable", exc_info=True)
        return set()


def register_group_mention_handler(dispatcher: Any, *, msg_controller: Any) -> None:
    """Register LAST so slash-command handlers keep priority."""
    from aiogram import F

    state: dict[str, Any] = {"username": None, "id": None}

    async def _bot_identity(message: Any) -> tuple[Optional[str], Optional[int]]:
        if state["username"] is None:
            me = await message.bot.me()
            state["username"], state["id"] = me.username, me.id
        return state["username"], state["id"]

    @dispatcher.message(F.chat.type.in_({"group", "supergroup"}))
    async def _group_name_call(message: Any) -> None:
        user = message.from_user
        if user is None or user.is_bot:
            return
        text = message.text or message.caption or ""
        if not text.strip():
            return

        bot_username, bot_id = await _bot_identity(message)
        reply_msg = getattr(message, "reply_to_message", None)
        reply_from = getattr(reply_msg, "from_user", None)
        reply_to_text = getattr(reply_msg, "text", "") or getattr(reply_msg, "caption", "") or ""
        replied_to_bot = bool(reply_from and bot_id and reply_from.id == bot_id)
        called = is_name_called(text, bot_username) or replied_to_bot
        if not called:
            return

        chat = message.chat
        if not is_team_chat(chat.id, getattr(chat, "title", None), _team_chat_ids()):
            return

        # Intercept sales staff check-in reply or client closing assistance
        try:
            from src.services.core.sales_staff_copilot import (
                is_checkin_interaction,
                bind_and_welcome_staff,
                handle_sales_staff_interaction,
            )
            if is_checkin_interaction(text, reply_to_text=reply_to_text, username=user.username):
                logger.info("[COPILOT] Handling sales staff interaction for user=%s (@%s)", user.id, user.username)

                # 1. Automatik ID olib tanishib olish (agar birinchi marta bo'lsa)
                is_new_intro, intro_msg = bind_and_welcome_staff(
                    user_id=user.id,
                    username=user.username or "RayxonJonbranding",
                    first_name=user.first_name or "Rayxon",
                )
                if is_new_intro and intro_msg:
                    await message.reply(intro_msg, parse_mode="HTML")

                # 2. Sotuv bo'yicha maslahat va yordam berish
                copilot_reply = await handle_sales_staff_interaction(
                    rep_name=user.first_name or "Rayxon",
                    rep_username=f"@{user.username}" if user.username else "@RayxonJonbranding",
                    message_text=text,
                )
                if copilot_reply:
                    await message.reply(copilot_reply, parse_mode="HTML")
                    return
        except Exception as exc:
            logger.error("[COPILOT] Sales copilot processing error: %s", exc, exc_info=True)

        question = strip_call(text, bot_username) or text
        logger.info(
            "[GROUP-CALL] chat=%s user=%s replied_to_bot=%s", chat.id, user.id, replied_to_bot
        )
        try:
            answer = await msg_controller.get_response(
                user_id=user.id,
                user_name=user.first_name or "Jamoa a'zosi",
                message=question,
                context={
                    "username": user.username or "yoq",
                    "chat_title": chat.title,
                    "chat_id": chat.id,
                    "is_bot": False,
                    "is_team_group": True,
                    "directly_addressed": True,
                },
            )
        except Exception:
            logger.error("group_call_failed", exc_info=True)
            answer = ""

        await message.reply((answer or "").strip() or DIRECT_CALL_FALLBACK)
