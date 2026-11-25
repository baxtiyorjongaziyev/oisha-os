"""Telegram /toldir buyrugʻi va bittama-bitta Airtable toʻldirish handlerlari."""

from __future__ import annotations

import logging
from typing import Any

from src.services.core.finance.airtable_gap_filler import (
    CB_PREFIX,
    SESSION_KEY_PREFIX,
    SKIP_KEY_PREFIX,
    apply_answer,
    build_prompt_markup,
    is_authorized_filler,
    next_gap_for_user,
)
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


def _to_aiogram_markup(buttons: dict) -> Any:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(**b) for b in row] for row in buttons["inline_keyboard"]
    ])


async def _send_next_prompt(target: Any, db: Any, user_id: int) -> None:
    today_iso = get_local_now().strftime("%Y-%m-%d")
    prompt = await next_gap_for_user(db, user_id, today_iso)
    if prompt is None:
        await db.set_state(f"{SESSION_KEY_PREFIX}{user_id}", None)
        await target.answer("🎉 Barcha tekshirilgan boʻsh maydonlar toʻldirildi!")
        return
    await db.set_state(f"{SESSION_KEY_PREFIX}{user_id}", prompt.__dict__)
    await target.answer(
        prompt.question,
        parse_mode="HTML",
        reply_markup=_to_aiogram_markup(build_prompt_markup(prompt)),
    )


async def handle_toldir_command(message: Any, *, db: Any) -> None:
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    if getattr(chat, "type", None) != "private" or user is None or not is_authorized_filler(user.id):
        return
    await _send_next_prompt(message, db, user.id)


async def handle_gap_callback(callback: Any, *, db: Any) -> None:
    user = getattr(callback, "from_user", None)
    if user is None or not is_authorized_filler(user.id):
        await callback.answer("Ruxsat yoʻq", show_alert=True)
        return
    data = str(getattr(callback, "data", "") or "")
    session = await db.get_state(f"{SESSION_KEY_PREFIX}{user.id}", None)
    if data == f"{CB_PREFIX}stop":
        await db.set_state(f"{SESSION_KEY_PREFIX}{user.id}", None)
        await callback.message.edit_text("⏸️ Toʻldirish toʻxtatildi. Davom ettirish uchun /toldir yozing.")
        await callback.answer()
        return
    if not session:
        await callback.answer("Faol sessiya yoʻq. /toldir yozing.", show_alert=True)
        return
    today_iso = get_local_now().strftime("%Y-%m-%d")
    if data == f"{CB_PREFIX}skip":
        key = f"{SKIP_KEY_PREFIX}{user.id}_{today_iso}"
        skipped = list(await db.get_state(key, []) or [])
        skipped.append(f"{session['record_id']}:{session['field']}")
        await db.set_state(key, skipped)
        await callback.message.edit_text(f"⏭️ <b>{session['title']}</b> ({session['field']}) oʻtkazib yuborildi.", parse_mode="HTML")
        await callback.answer()
        await _send_next_prompt(callback.message, db, user.id)
        return
    if data.startswith(f"{CB_PREFIX}quick:"):
        val = data.split(":", 2)[2]
        actor = f"@{user.username}" if getattr(user, "username", None) else str(user.id)
        ok, msg = await apply_answer(session, val, actor_label=actor, today_iso=today_iso)
        await callback.message.edit_text(msg, parse_mode="HTML")
        await callback.answer()
        if ok:
            await _send_next_prompt(callback.message, db, user.id)


async def handle_gap_text_reply(message: Any, *, db: Any) -> None:
    user = getattr(message, "from_user", None)
    text = str(getattr(message, "text", "") or "").strip()
    if user is None or not text or text.startswith("/"):
        return
    session = await db.get_state(f"{SESSION_KEY_PREFIX}{user.id}", None)
    if not session:
        return
    today_iso = get_local_now().strftime("%Y-%m-%d")
    actor = f"@{user.username}" if getattr(user, "username", None) else str(user.id)
    ok, msg = await apply_answer(session, text, actor_label=actor, today_iso=today_iso)
    await message.answer(msg, parse_mode="HTML")
    if ok:
        await _send_next_prompt(message, db, user.id)


def _finance_group_id() -> int:
    from src.settings import settings

    try:
        return int(getattr(settings, "HISOBCHI_FINANCE_GROUP_ID", 0) or 0)
    except (TypeError, ValueError):
        return 0


def is_group_daily_report(message: Any) -> bool:
    from src.services.core.finance.daily_report_ingest import is_daily_report

    chat = getattr(message, "chat", None)
    gid = _finance_group_id()
    text = str(getattr(message, "text", "") or "")
    return bool(gid) and getattr(chat, "id", None) == gid and is_daily_report(text)


async def handle_group_daily_report(message: Any) -> None:
    """Guruhdagi kunlik hisobot: fakt saldo -> Airtable, solishtiruv natijasi reply."""
    from src.services.core.finance.balance_reconcile import _send_owner
    from src.services.core.finance.daily_report_ingest import ingest_daily_report

    user = getattr(message, "from_user", None)
    if user is None:
        return
    msg_date = getattr(message, "date", None)
    day = msg_date.astimezone(get_local_now().tzinfo).date() if msg_date else get_local_now().date()
    try:
        reply = await ingest_daily_report(
            str(getattr(message, "text", "") or ""),
            sender_id=int(user.id),
            message_date=day,
            notify_owner=_send_owner,
        )
    except Exception:
        logger.error("[DAILY-REPORT] Hisobot qayta ishlanmadi", exc_info=True)
        return
    if reply:
        await message.reply(reply)


def register_airtable_gap_handlers(dispatcher: Any, *, db: Any) -> None:
    if not hasattr(dispatcher, "message") or not hasattr(dispatcher, "callback_query"):
        return
    from aiogram import F

    @dispatcher.message(F.text.regexp(r"(?i)^/toldir$"))
    async def _toldir(message: Any) -> None:
        await handle_toldir_command(message, db=db)

    dispatcher.message.register(handle_group_daily_report, is_group_daily_report)
    if hasattr(dispatcher, "edited_message"):
        dispatcher.edited_message.register(handle_group_daily_report, is_group_daily_report)

    @dispatcher.callback_query(F.data.startswith(CB_PREFIX))
    async def _cb(callback: Any) -> None:
        await handle_gap_callback(callback, db=db)

    async def _has_active_session(message: Any) -> bool:
        chat = getattr(message, "chat", None)
        user = getattr(message, "from_user", None)
        text = str(getattr(message, "text", "") or "").strip()
        if getattr(chat, "type", None) != "private" or user is None or not text or text.startswith("/"):
            return False
        if not is_authorized_filler(user.id):
            return False
        return bool(await db.get_state(f"{SESSION_KEY_PREFIX}{user.id}", None))

    dispatcher.message.register(
        lambda msg: handle_gap_text_reply(msg, db=db),
        _has_active_session,
    )
    logger.info("[AIRTABLE-GAP] /toldir handlerlari ulandi.")
