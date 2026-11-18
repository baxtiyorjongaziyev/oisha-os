"""Oisha Connect bot buyruqlari (faqat shaxsiy chatda).

/connect          — holat va ulanish sahifasiga tugma
/connect off      — uzish (tasdiq tugmasi bilan)

QR va chat tanlash faqat veb sahifada: bot kod, parol yoki sessiya soʻramaydi.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://oisha.jonbranding.uz/api/connect/app"
CB_REVOKE, CB_CANCEL = "tgc:revoke", "tgc:cancel"

GUARANTEES = (
    "🔒 <b>Kafolatlar</b>\n"
    "• Kod, SMS yoki parol yozmaysiz — faqat QR skanerlaysiz.\n"
    "• Oisha faqat siz tanlagan chatlarni koʻradi.\n"
    "• Oisha nomingizdan oʻzi xabar yubormaydi.\n"
    "• Sessiya shifrlangan holda faqat kompaniya serverida.\n"
    "• Istalgan payt <code>/connect off</code> bilan uzasiz."
)
NOT_EMPLOYEE = "Telegram hisobingiz xodimlar roʻyxatiga bogʻlanmagan. Avval /ulanish Ism Familiya yuboring."
REVOKE_ASK = ("Oisha Connect uziladi va sessiya Telegramda ham yopiladi "
              "(Devices roʻyxatidan “Oisha Connect” yoʻqoladi). Davom etasizmi?")


def connect_url() -> str:
    return (os.getenv("CONNECT_PUBLIC_URL") or DEFAULT_URL).strip()


def _fmt(ts: Optional[int]) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def status_text(acc: Optional[dict], allowed_chats: int) -> str:
    if acc and acc.get("status") == "connected":
        return (f"✅ <b>Oisha Connect ulangan</b>\n"
                f"Ulangan vaqt: {_fmt(acc.get('connected_at'))}\n"
                f"Oisha koʻradigan chatlar: <b>{allowed_chats}</b>\n\n"
                "Chatlarni oʻzgartirish va jurnalni koʻrish uchun sahifani oching.\n"
                "Uzish: <code>/connect off</code>")
    return ("🔗 <b>Telegram chatlaringizni Oishaga ulang</b>\n"
            "Oisha mijozlar bilan yozishmalarni tahlil qiladi va javobsiz qolganlarni eslatadi.\n\n"
            f"{GUARANTEES}\n\nUlanish uchun pastdagi tugmani bosing.")


def open_button(connected: bool) -> dict:
    label = "⚙️ Sozlamalarni ochish" if connected else "🔗 Ulanish sahifasi"
    return {"inline_keyboard": [[{"text": label, "url": connect_url()}]]}


def revoke_buttons() -> dict:
    return {"inline_keyboard": [[{"text": "🔴 Ha, uzish", "callback_data": CB_REVOKE},
                                 {"text": "Bekor qilish", "callback_data": CB_CANCEL}]]}


def _markup(buttons: dict) -> Any:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(**b) for b in row] for row in buttons["inline_keyboard"]])


async def _allowed(db, tg: int) -> bool:
    from src.settings import settings

    if int(settings.OWNER_ID or 0) == tg:
        return True
    try:
        rows = await db.execute("SELECT id FROM employees WHERE telegram_id = ? AND is_active = 1", [tg])
    except Exception:  # noqa: BLE001 - employees jadvali hali yoʻq
        return False
    return bool(rows)


async def _ready(db) -> None:
    from src.services.core.tg_connect import store

    await store.init_tables(db)


async def handle_connect(message: Any, db=None) -> None:
    from src.services.core.tg_connect import store

    if getattr(message.chat, "type", "") != "private" or message.from_user is None:
        return
    if db is None:
        from src.database_pool import db_pool as db
    tg = int(message.from_user.id)
    if not await _allowed(db, tg):
        await message.answer(NOT_EMPLOYEE)
        return
    await _ready(db)
    acc = await store.account(db, tg)
    connected = bool(acc and acc.get("status") == "connected")
    arg = (message.text or "").split(maxsplit=1)[1:] or [""]
    if arg[0].strip().lower() in ("off", "uzish", "stop"):
        if not connected:
            await message.answer("Oisha Connect ulanmagan.")
            return
        await message.answer(REVOKE_ASK, reply_markup=_markup(revoke_buttons()))
        return
    allowed = sum(1 for c in await store.chats(db, tg) if c["allowed"]) if connected else 0
    await message.answer(status_text(acc, allowed), parse_mode="HTML",
                         reply_markup=_markup(open_button(connected)), disable_web_page_preview=True)


async def handle_revoke_callback(callback: Any, db=None) -> None:
    from src.services.core.tg_connect import session_ops

    if db is None:
        from src.database_pool import db_pool as db
    tg = int(callback.from_user.id)
    if callback.data == CB_CANCEL:
        await callback.message.edit_text("Bekor qilindi. Oisha Connect ulangan holda qoldi.")
        await callback.answer()
        return
    ok = await session_ops.revoke(db, tg, f"bot:{tg}")
    text = ("✅ Oisha Connect uzildi. Sessiya Oisha serveridan oʻchirildi."
            if ok else "Oisha Connect allaqachon uzilgan.")
    await callback.message.edit_text(text)
    await callback.answer()


def register_connect_handlers(dp: Any) -> None:
    from aiogram import F

    @dp.message(F.text.regexp(r"(?i)^/connect(@\w+)?(\s|$)"))
    async def _connect(message: Any) -> None:
        await handle_connect(message)

    @dp.callback_query(F.data.in_({CB_REVOKE, CB_CANCEL}))
    async def _revoke(callback: Any) -> None:
        await handle_revoke_callback(callback)
