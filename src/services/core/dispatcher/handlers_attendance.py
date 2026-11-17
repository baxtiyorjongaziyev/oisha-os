"""Botga yuborilgan (jonli) lokatsiya → avtomatik keldi/ketdi. Koordinata saqlanmaydi."""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

from src.services.core.attendance import face_engine, face_verify, repo

logger = logging.getLogger(__name__)

_LABELS = {
    "check_in": "✅ Keldingiz — qayd etildi",
    "check_out": "👋 Ketdingiz — qayd etildi",
    "face_required": "🙂 Avval yuzingizni tasdiqlang: /keldim yozing.",
}
_FACE_MSGS = {
    "not_linked": "Avval /ulanish Ism Familiya bilan davomatga ulaning.",
    "already_enrolled": "Yuzingiz allaqachon roʻyxatdan oʻtgan. Oʻzgartirish uchun rahbarga murojaat qiling.",
    "not_enrolled": "Avval /yuz yozib, yuzingizni roʻyxatdan oʻtkazing.",
    "enroll_start": "📸 Yorugʻ joyda, kameraga toʻgʻri qarab, bitta selfi yuboring.",
    "verify_start": ("📸 Yuzni tasdiqlash: avval kameraga toʻgʻri qarab selfi yuboring. "
                     "2 daqiqa ichida bajaring."),
    "enrolled": "✅ Yuzingiz roʻyxatdan oʻtdi. Endi /keldim bilan davomat qilishingiz mumkin.",
    "need_turn": "✅ Mos keldi. Endi boshingizni yon tomonga (taxminan 30°) burib, yana bitta selfi yuboring.",
    "verified": "✅ Yuz tasdiqlandi. 10 daqiqa ichida pastdagi 📍 tugmani bosing.",
    "no_face": "Rasmda yuz topilmadi. Yorugʻroq joyda qayta yuboring.",
    "many_faces": "Rasmda bitta yuz boʻlishi kerak. Qayta yuboring.",
    "not_frontal": "Kameraga toʻgʻri qarab selfi yuboring.",
    "no_match": "Yuz roʻyxatdagi yuzga mos kelmadi. Qayta urinib koʻring.",
    "not_turned": "Boshingizni yon tomonga ancha burib selfi yuboring.",
    "too_many": "Urinishlar koʻp boʻldi. /keldim yozib, boshidan boshlang.",
    "forwarded": "Forward qilingan rasm qabul qilinmaydi. Selfini oʻzingiz oling.",
    "stale": "Rasm eskirgan. Yangi selfi oling.",
    "engine_down": "Yuz tekshiruvi hozir ishlamayapti. Rahbarga xabar bering.",
    "error": "Xatolik yuz berdi. Keyinroq qayta urinib koʻring.",
}
_HOWTO = (
    "📍 Avtomatik davomat uchun <b>jonli lokatsiya</b> yuboring:\n"
    "📎 → Lokatsiya → «Jonli lokatsiyani ulashish» → «To'xtatmaguncha».\n"
    "Ofisga kirsangiz «keldi», 17:00 dan keyin chiqib ketsangiz «ketdi» o'zi belgilanadi."
)


_KELDIM_HINT = "📍 Davomat uchun /keldim yozing va pastdagi tugmani bosing."
_KELDIM_PROMPT = "Tugmani bosing — joriy joylashuvingiz yuboriladi."
_KELDIM_BUTTON = "📍 Keldim"

MAX_LOCATION_AGE_S = 120  # eski yoki forward qilingan lokatsiya bilan "keldi" qoʻyilmaydi


def location_rejection(message: Any, loc: Any, *, edited: bool, now: datetime | None = None) -> str | None:
    """Lokatsiya haqiqiy GPS emasligi ehtimoli bor boʻlsa sabab kodi, aks holda None.

    Xaritadan qoʻlda tanlangan nuqta (horizontal_accuracy yoʻq), forward qilingan yoki eskirgan
    xabar davomat belgisi boʻla olmaydi. Soxta GPS ilovasini Telegram orqali aniqlab boʻlmaydi:
    buni ofis Wi-Fi/IP tasdigʻi yoki yuz tekshiruvi qisman yopadi.
    """
    if getattr(message, "forward_origin", None) or getattr(message, "forward_date", None):
        return "forwarded"
    # Jonli yoki "📍 Keldim" tugmasi bilan yuborilgan joriy GPS. Xaritadan qoʻlda tanlangan nuqtada
    # horizontal_accuracy boʻlmaydi, shu orqali ajratiladi.
    accuracy = getattr(loc, "horizontal_accuracy", None)
    if not isinstance(accuracy, (int, float)) or accuracy <= 0:
        return "no_accuracy"
    stamp = (getattr(message, "edit_date", None) if edited else None) or getattr(message, "date", None)
    if not isinstance(stamp, datetime):
        return "no_timestamp"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if abs(((now or datetime.now(timezone.utc)) - stamp).total_seconds()) > MAX_LOCATION_AGE_S:
        return "stale"
    return None


async def handle_location(message: Any, *, edited: bool) -> None:
    from src.database_pool import db_pool
    from src.services.core.attendance import auto_presence

    chat = getattr(message, "chat", None)
    loc = getattr(message, "location", None)
    if loc is None or getattr(chat, "type", "") != "private" or message.from_user is None:
        return
    reason = location_rejection(message, loc, edited=edited)
    if reason:
        logger.warning("[AUTO-ATT] lokatsiya rad etildi: %s", reason)
        if not edited:
            await message.answer(_KELDIM_HINT)
        return
    try:
        allow_check_in = True
        if face_verify.required():
            emp = await repo.employee_by_telegram(db_pool, str(message.from_user.id))
            if emp is not None:
                allow_check_in = await face_verify.recently_verified(db_pool, int(emp["id"]))
        result = await auto_presence.on_location(
            db_pool, int(message.from_user.id), float(loc.latitude), float(loc.longitude),
            getattr(loc, "horizontal_accuracy", None), allow_check_in=allow_check_in,
        )
    except Exception as exc:
        logger.warning("[AUTO-ATT] lokatsiya ishlanmadi: %s", type(exc).__name__)
        return
    if result == "face_required":
        if not edited:
            await message.answer(_LABELS[result])
    elif result:
        await message.answer(_LABELS[result])
    elif not edited and not getattr(loc, "live_period", None):
        await message.answer(_HOWTO, parse_mode="HTML")


def _location_keyboard() -> Any:
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_KELDIM_BUTTON, request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True)


async def handle_keldim(message: Any) -> None:
    """/keldim — joylashuv tugmasi; yuz tasdigʻi yoqilgan boʻlsa avval yuz tekshiriladi."""
    from src.database_pool import db_pool

    if getattr(message.chat, "type", "") != "private" or message.from_user is None:
        return
    if face_verify.required():
        emp = await repo.employee_by_telegram(db_pool, str(message.from_user.id))
        if emp is not None:
            employee_id = int(emp["id"])
            if not await face_verify.is_enrolled(db_pool, employee_id):
                await message.answer(_FACE_MSGS["not_enrolled"])
                return
            if not await face_verify.recently_verified(db_pool, employee_id):
                await face_verify.start_verify(db_pool, employee_id)
                await message.answer(_FACE_MSGS["verify_start"])
                return
    await message.answer(_KELDIM_PROMPT, reply_markup=_location_keyboard())


async def handle_face_enroll(message: Any) -> None:
    """/yuz — yuzni bir marta roʻyxatdan oʻtkazish."""
    from src.database_pool import db_pool

    if getattr(message.chat, "type", "") != "private" or message.from_user is None:
        return
    emp = await repo.employee_by_telegram(db_pool, str(message.from_user.id))
    if emp is None:
        await message.answer(_FACE_MSGS["not_linked"])
        return
    if not await face_verify.start_enroll(db_pool, int(emp["id"])):
        await message.answer(_FACE_MSGS["already_enrolled"])
        return
    await message.answer(_FACE_MSGS["enroll_start"])


async def handle_photo(message: Any) -> Any:
    """Yuz roʻyxati/tasdiq rasmi. Faol soʻrov boʻlmasa — boshqa handlerlarga oʻtkazadi."""
    from aiogram.dispatcher.event.bases import UNHANDLED

    from src.database_pool import db_pool

    if getattr(message.chat, "type", "") != "private" or message.from_user is None:
        return UNHANDLED
    emp = await repo.employee_by_telegram(db_pool, str(message.from_user.id))
    if emp is None or await face_verify.get_challenge(db_pool, int(emp["id"])) is None:
        return UNHANDLED
    stamp = getattr(message, "date", None)
    if getattr(message, "forward_origin", None) or getattr(message, "forward_date", None):
        await message.answer(_FACE_MSGS["forwarded"])
        return None
    if isinstance(stamp, datetime):
        stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
        if abs((datetime.now(timezone.utc) - stamp).total_seconds()) > MAX_LOCATION_AGE_S:
            await message.answer(_FACE_MSGS["stale"])
            return None
    buf = io.BytesIO()
    await message.bot.download(message.photo[-1], destination=buf)
    try:
        code = await face_verify.submit_photo(db_pool, face_engine.get_engine(), int(emp["id"]), buf.getvalue())
    except face_engine.FaceEngineUnavailable:
        logger.error("[AUTO-ATT] yuz dvigateli oʻrnatilmagan (requirements-face.txt)")
        await message.answer(_FACE_MSGS["engine_down"])
        return None
    except Exception as exc:
        logger.warning("[AUTO-ATT] yuz rasmi ishlanmadi: %s", type(exc).__name__)
        await message.answer(_FACE_MSGS["error"])
        return None
    if code == "verified":
        await message.answer(_FACE_MSGS[code], reply_markup=_location_keyboard())
    else:
        await message.answer(_FACE_MSGS.get(code, _FACE_MSGS["error"]))
    return None


async def handle_face_reset(message: Any) -> None:
    """/yuz_reset Ism Familiya — faqat rahbar: yuzni qayta roʻyxatdan oʻtkazish uchun tozalaydi."""
    from src.database_pool import db_pool

    if message.from_user is None or int(message.from_user.id) != _owner_id():
        return
    parts = (message.text or "").split(maxsplit=1)
    name = parts[1].strip() if len(parts) > 1 else ""
    rows = await db_pool.execute("SELECT id, name FROM employees WHERE lower(name) = lower(?) AND is_active = 1",
                                 [name]) if name else []
    if len(rows) != 1:
        await message.answer("Ism-familiyani aniq yozing: /yuz_reset Ism Familiya")
        return
    await face_verify.reset(db_pool, int(rows[0]["id"]))
    await message.answer("Yuz maʼlumoti tozalandi. Xodim /yuz bilan qayta roʻyxatdan oʻtadi.")


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

    @dp.message(F.text.regexp(r"(?i)^/keldim"))
    async def _keldim(message: Any) -> None:
        await handle_keldim(message)

    @dp.message(F.text.regexp(r"(?i)^/yuz_reset"))
    async def _face_reset(message: Any) -> None:
        await handle_face_reset(message)

    @dp.message(F.text.regexp(r"(?i)^/yuz(?!\w)"))
    async def _face_enroll(message: Any) -> None:
        await handle_face_enroll(message)

    @dp.message(F.photo)
    async def _face_photo(message: Any) -> Any:
        return await handle_photo(message)

    @dp.message(F.text.regexp(r"(?i)^/ulanish"))
    async def _link(message: Any) -> None:
        await handle_link(message)

    @dp.message(F.text.regexp(r"(?i)^/davomat"))
    async def _report(message: Any) -> None:
        await handle_report(message)

    @dp.callback_query(F.data.startswith("att_link:"))
    async def _decision(callback: Any) -> None:
        await handle_link_decision(callback)
