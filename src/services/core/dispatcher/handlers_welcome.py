"""Bot API 10.5: taklif havolasi orqali kelgan foydalanuvchini kutib olish.

Egasi botga 10 tagacha odamni maxsus havola bilan taklif qiladi. Har bir
taklif qilingan foydalanuvchi uchun bot ``write_access_allowed`` xizmat
xabarini oladi — shu payt qisqa salom va keyingi qadam yuboriladi, egasiga
esa xabar beriladi.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 Assalomu alaykum{name}! Men Oisha — Jon Branding ichki yordamchisiman.\n\n"
    "Boshlash uchun <code>/ulanish Ism Familiya</code> yuboring, "
    "shunda sizni xodimlar roʻyxatiga bogʻlayman."
)


def build_welcome_text(first_name: str | None) -> str:
    name = f", {first_name.strip()}" if first_name and first_name.strip() else ""
    return WELCOME_TEXT.format(name=name)


def build_owner_notice(user: Any) -> str:
    uid = getattr(user, "id", "?")
    first = getattr(user, "first_name", "") or ""
    username = getattr(user, "username", None)
    tag = f" @{username}" if username else ""
    return f"🆕 Botga yangi foydalanuvchi qoʻshildi: {first}{tag} (id {uid})"


async def handle_write_access_allowed(message: Any, *, owner_id: int) -> None:
    user = getattr(message, "from_user", None)
    try:
        await message.answer(build_welcome_text(getattr(user, "first_name", None)), parse_mode="HTML")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Welcome send failed: %s", exc)
        return
    if owner_id and user is not None and getattr(user, "id", None) != owner_id:
        try:
            await message.bot.send_message(owner_id, build_owner_notice(user))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Owner notice failed: %s", exc)


def register_welcome_handlers(dp: Any, *, owner_id: int) -> None:
    from aiogram import F

    @dp.message(F.write_access_allowed)
    async def _welcome(message: Any) -> None:
        await handle_write_access_allowed(message, owner_id=owner_id)
