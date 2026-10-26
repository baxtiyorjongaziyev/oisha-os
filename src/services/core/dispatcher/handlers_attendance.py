"""Botga yuborilgan (jonli) lokatsiya → avtomatik keldi/ketdi. Koordinata saqlanmaydi."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_LABELS = {"check_in": "✅ Keldingiz — qayd etildi", "check_out": "👋 Ketdingiz — qayd etildi"}
_HOWTO = (
    "📍 Avtomatik davomat uchun <b>jonli lokatsiya</b> yuboring:\n"
    "📎 → Lokatsiya → «Jonli lokatsiyani ulashish» → «To'xtatmaguncha».\n"
    "Ofisga kirsangiz «keldi», 17:00 dan keyin chiqib ketsangiz «ketdi» o'zi belgilanadi."
)


async def handle_location(message: Any, *, edited: bool) -> None:
    from src.database_pool import db_pool
    from src.services.core.attendance import auto_presence

    chat = getattr(message, "chat", None)
    loc = getattr(message, "location", None)
    if loc is None or getattr(chat, "type", "") != "private" or message.from_user is None:
        return
    try:
        result = await auto_presence.on_location(
            db_pool, int(message.from_user.id), float(loc.latitude), float(loc.longitude),
            getattr(loc, "horizontal_accuracy", None),
        )
    except Exception as exc:
        logger.warning("[AUTO-ATT] lokatsiya ishlanmadi: %s", type(exc).__name__)
        return
    if result:
        await message.answer(_LABELS[result])
    elif not edited and not getattr(loc, "live_period", None):
        await message.answer(_HOWTO, parse_mode="HTML")


def register_attendance_handlers(dp: Any) -> None:
    from aiogram import F

    @dp.message(F.location)
    async def _location(message: Any) -> None:
        await handle_location(message, edited=False)

    @dp.edited_message(F.location)
    async def _live_update(message: Any) -> None:
        await handle_location(message, edited=True)
