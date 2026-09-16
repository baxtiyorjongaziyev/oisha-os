"""
Sales Club uchrashuv ro'yxatga olish so'rovnomasi.

Deep-link (/start register) orqali chaqiriladi, bosqichma-bosqich inline
tugma va matn savollari bilan ma'lumot yig'adi, natijani OWNER_ID'ga DM
qilib yuboradi.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("SalesClubSurvey")

DEEP_LINK_PAYLOAD = "register"


class SalesClubSurveyForm:
    """aiogram FSM state group (lazy import so aiogram stays optional at module load)."""

    def __new__(cls):  # pragma: no cover - not meant to be instantiated
        raise RuntimeError("Use SalesClubSurveyForm.states, not an instance")


def _build_states() -> Any:
    from aiogram.fsm.state import State, StatesGroup

    class _SalesClubSurveyForm(StatesGroup):
        name_role = State()
        topic_interest = State()
        first_time = State()

    return _SalesClubSurveyForm


def register_sales_club_survey_handlers(dispatcher: Any, *, owner_id: int) -> None:
    """Wire the Sales Club registration survey into an existing aiogram Dispatcher."""
    from aiogram import F
    from aiogram.filters import CommandObject, CommandStart

    Form = _build_states()

    @dispatcher.message(CommandStart(deep_link=True))
    async def _start_with_payload(message: Any, command: CommandObject, state: Any) -> None:
        if (command.args or "").strip() != DEEP_LINK_PAYLOAD:
            return
        await state.set_state(Form.name_role)
        await message.answer("Ismingiz, lavozimingiz?")

    @dispatcher.message(F.text == "/register")
    async def _start_with_command(message: Any, state: Any) -> None:
        await state.set_state(Form.name_role)
        await message.answer("Ismingiz, lavozimingiz?")

    @dispatcher.message(Form.name_role)
    async def _got_name_role(message: Any, state: Any) -> None:
        await state.update_data(name_role=(message.text or "").strip())
        await state.set_state(Form.topic_interest)
        await message.answer(
            "Psixologiya bo'yicha speechda aynan qanday mavzu yoki savolga "
            "javob sizga qiziq bo'ladi?"
        )

    @dispatcher.message(Form.topic_interest)
    async def _got_topic(message: Any, state: Any) -> None:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        await state.update_data(topic_interest=(message.text or "").strip())
        await state.set_state(Form.first_time)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Ha", callback_data="scsurvey:first:yes"),
                    InlineKeyboardButton(text="Yo'q", callback_data="scsurvey:first:no"),
                ]
            ]
        )
        await message.answer(
            "Uchrashuvga birinchi qatnashishingizmi?",
            reply_markup=keyboard,
        )

    @dispatcher.callback_query(F.data.startswith("scsurvey:first:"))
    async def _got_first_time(callback: Any, state: Any) -> None:
        current_state = await state.get_state()
        if current_state != Form.first_time.state:
            await callback.answer()
            return

        is_first_time = callback.data.rsplit(":", 1)[-1] == "yes"
        data = await state.get_data()
        await state.clear()

        respondent = callback.from_user
        respondent_label = (
            f"@{respondent.username}" if respondent and respondent.username
            else str(getattr(respondent, "id", "noma'lum"))
        )

        first_time_label = "Ha" if is_first_time else "Yo'q"
        summary = (
            "\U0001F4CB Sales Club | 16.09 — yangi ro'yxatdan o'tish\n\n"
            f"Yuboruvchi: {respondent_label}\n"
            f"Ism, lavozim: {data.get('name_role', '-')}\n"
            f"Qiziq mavzu: {data.get('topic_interest', '-')}\n"
            f"Birinchi marta: {first_time_label}"
        )

        try:
            await callback.bot.send_message(chat_id=owner_id, text=summary)
        except Exception:
            logger.error("Sales Club survey: owner DM yuborishda xatolik", exc_info=True)

        await callback.message.edit_text("Rahmat! Ro'yxatdan o'tdingiz ✅")
        await callback.answer()

    logger.info("[SALES_CLUB] Survey handlers registered (deep-link payload=%s).", DEEP_LINK_PAYLOAD)
