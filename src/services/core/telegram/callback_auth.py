"""Inline-tugma callback'lari uchun ruxsat tekshiruvi.

`callback_data` foydalanuvchi kiritmasi: MTProto mijozi (`messages.getBotCallbackAnswer`)
bot yuborgan istalgan xabar ustida ixtiyoriy data yubora oladi. Shuning uchun
"tugma faqat moliya guruhida ko'rinadi" — himoya emas: botga DM yozgan mehmon
(masalan, vodiy/sales-club oqimi) o'z chatidagi xabar orqali `happrove:<id>`
yuborishi mumkin edi.

Ruxsat: bosgan odam OWNER_ID/WHITELIST_IDS da bo'lsa, yoki callback sozlangan
moliya/jamoa guruhidagi xabardan kelgan bo'lsa (guruh a'zoligi — mavjud ishonch
chegarasi).
"""
from __future__ import annotations

from typing import Any

from src.settings import settings


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _trusted_user_ids() -> set[int]:
    ids = {_as_int(item) for item in (getattr(settings, "WHITELIST_IDS", None) or [])}
    ids.add(_as_int(getattr(settings, "OWNER_ID", 0)))
    ids.discard(0)
    return ids


def _trusted_chat_ids() -> set[int]:
    ids = {
        _as_int(getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", None)),
        _as_int(getattr(settings, "TEAM_GROUP_ID", None)),
    }
    ids.discard(0)
    return ids


def is_trusted_finance_callback(callback: Any) -> bool:
    """Aiogram CallbackQuery moliyaviy amalni bajarishga ruxsatlimi."""
    user_id = _as_int(getattr(getattr(callback, "from_user", None), "id", 0))
    if user_id and user_id in _trusted_user_ids():
        return True
    chat = getattr(getattr(callback, "message", None), "chat", None)
    chat_id = _as_int(getattr(chat, "id", 0))
    return bool(chat_id) and chat_id in _trusted_chat_ids()
