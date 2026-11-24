"""Raqam -> Telegram kontakt kartasi (GET-LID analogi, limitsiz).

Admin botga telefon raqam yuboradi; bot darhol kontakt kartasini qaytaradi,
soʻng userbot orqali akkaunt topilsa "Raqam topildi" va @username tugmasini.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("AdminPhoneContactCard")


def normalize_uz_phone(raw: str) -> str:
    """Har qanday yozuvni +998XXXXXXXXX koʻrinishiga keltiradi."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return "+998" + digits[-9:]


def format_uz_phone(phone: str) -> str:
    """+998901234567 -> +998 90 123 45 67"""
    d = re.sub(r"\D", "", phone)
    if len(d) == 12 and d.startswith("998"):
        return f"+{d[:3]} {d[3:5]} {d[5:8]} {d[8:10]} {d[10:]}"
    return phone


def _profile_button(data: dict) -> Any:
    username = data.get("username")
    user_id = data.get("user_id")
    if username:
        label, url = f"💬 @{username}", f"https://t.me/{username}"
    elif user_id:
        label, url = "💬 Profilni ochish", f"tg://user?id={user_id}"
    else:
        return None
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except Exception:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, url=url)]]
    )


async def _send_result(message: Any, phone: str, data: Optional[dict]) -> None:
    if not data:
        await message.answer(
            f"❌ {format_uz_phone(phone)} Telegramda topilmadi "
            "yoki raqami yashirilgan."
        )
        return
    body = f"✅ Raqam topildi\n📞 {format_uz_phone(phone)}"
    markup = _profile_button(data)
    if markup is not None:
        try:
            await message.answer(body, reply_markup=markup)
            return
        except Exception:
            # tg://user?id tugmasi maxfiylik sabab rad etilishi mumkin.
            logger.debug("[PHONE] profile button rejected", exc_info=True)
    await message.answer(body)


def make_phone_search(
    *,
    is_admin: Callable[[int], bool],
    perform_global_lookup: Callable[[str], Awaitable[Optional[dict]]],
) -> Callable[[Any], Awaitable[None]]:
    from src.services.core.dispatcher.inline_search import PHONE_RE

    async def _phone_search(message: Any) -> None:
        sender = getattr(message, "from_user", None)
        if not is_admin(int(getattr(sender, "id", 0) or 0)):
            return
        match = re.search(PHONE_RE, (getattr(message, "text", "") or "").strip())
        if not match:
            return
        phone = normalize_uz_phone(match.group(0))
        # Karta faqat raqamga bogʻliq — lookupni kutmasdan darhol yuboriladi.
        try:
            await message.answer_contact(phone_number=phone, first_name=phone)
        except Exception:
            logger.warning("[PHONE] contact card send failed", exc_info=True)
        try:
            data = await perform_global_lookup(phone)
        except Exception:
            logger.error("[PHONE] lookup failed", exc_info=True)
            data = None
        await _send_result(message, phone, data)

    return _phone_search
