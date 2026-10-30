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


def _owner_id() -> int:
    from src.settings import settings

    return int(settings.OWNER_ID or 0)


def _markup(buttons: dict) -> Any:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(**b) for b in row] for row in buttons["inline_keyboard"]])


async def handle_link(message: Any) -> None:
    """/ulanish Ism Familiya — xodim davomatga ulanish so'rovini yuboradi."""
    from src.database_pool import db_pool
    from src.services.core.attendance import bot_flow
    from src.services.core.attendance.service import AttendanceError

    if getattr(message.chat, "type", "") != "private" or message.from_user is None:
        return
    parts = (message.text or "").split(maxsplit=1)
    name = parts[1].strip() if len(parts) > 1 else ""
    if len(name) < 2:
        await message.answer("Ism-familiyangizni yozing, masalan:\n/ulanish Rayxona Rahimova")
        return
    try:
        req = await bot_flow.request_link(db_pool, int(message.from_user.id), name)
    except AttendanceError as e:
        await message.answer(bot_flow.error_text(e), parse_mode="HTML")
        return
    owner = _owner_id()
    if owner:
        await message.bot.send_message(
            owner, bot_flow.owner_request_text(req["name"], message.from_user.username),
            parse_mode="HTML", reply_markup=_markup(bot_flow.owner_buttons(req["id"])))
    await message.answer("✅ So'rov yuborildi. Rahbar tasdiqlagach, sizga xabar keladi.")


async def handle_link_decision(callback: Any) -> None:
    from src.database_pool import db_pool
    from src.services.core.attendance import bot_flow
    from src.services.core.attendance.service import AttendanceError

    if callback.from_user is None or int(callback.from_user.id) != _owner_id():
        await callback.answer("Faqat rahbar tasdiqlaydi", show_alert=True)
        return
    try:
        text, employee_tg = await bot_flow.decide(db_pool, actor=str(callback.from_user.id), data=callback.data)
    except AttendanceError as e:
        await callback.answer(bot_flow.error_text(e), show_alert=True)
        return
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()
    if employee_tg:
        approved = callback.data.startswith(bot_flow.CB_APPROVE)
        msg = "✅ Davomatga ulandingiz.\n" + bot_flow.LIVE_HOWTO if approved else "❌ So'rovingiz rad etildi."
        try:
            await callback.bot.send_message(employee_tg, msg, parse_mode="HTML")
        except Exception as exc:
            logger.warning("[ATT-LINK] xodimga xabar ketmadi: %s", type(exc).__name__)


async def handle_report(message: Any) -> None:
    """/davomat — bugun; /davomat oy — oylik xulosa. Faqat rahbar."""
    from src.database_pool import db_pool
    from src.services.core.attendance import bot_flow

    if message.from_user is None or int(message.from_user.id) != _owner_id():
        return
    monthly = "oy" in (message.text or "").lower().split()[1:]
    text = await (bot_flow.month_text(db_pool) if monthly else bot_flow.today_text(db_pool))
    await message.answer(text, parse_mode="HTML")


def register_attendance_handlers(dp: Any) -> None:
    from aiogram import F

    @dp.message(F.location)
    async def _location(message: Any) -> None:
        await handle_location(message, edited=False)

    @dp.edited_message(F.location)
    async def _live_update(message: Any) -> None:
        await handle_location(message, edited=True)

    @dp.message(F.text.regexp(r"(?i)^/ulanish"))
    async def _link(message: Any) -> None:
        await handle_link(message)

    @dp.message(F.text.regexp(r"(?i)^/davomat"))
    async def _report(message: Any) -> None:
        await handle_report(message)

    @dp.callback_query(F.data.startswith("att_link:"))
    async def _decision(callback: Any) -> None:
        await handle_link_decision(callback)
