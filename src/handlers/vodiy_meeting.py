"""Private bot flow for the Qo'shtepa business meeting."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MEETING_TITLE = "Vodiy biznes uchrashuvlari | Qo'shtepa"
MEETING_PLACE = "Farg'ona viloyati, Qo'shtepa tumani"
PHONE_PATTERN = re.compile(r"^\+?\d{9,15}$")
CHANNEL_PATTERN = re.compile(r"^-100\d+$")


def _rich_card(bot_username: str) -> dict[str, Any]:
    bot_link = f"https://t.me/{bot_username}"

    def button(text: str, **action: str) -> dict[str, Any]:
        return {"text": text, **action}

    return {
        "blocks": [
            {"type": "heading", "text": MEETING_TITLE, "size": 3},
            {"type": "paragraph", "text": "Bepul biznes uchrashuv. Sayohat emas."},
            {"type": "paragraph", "text": MEETING_PLACE},
            {"type": "paragraph", "text": "Sana va vaqt tez orada e'lon qilinadi."},
            {
                "type": "buttons",
                "buttons": [
                    button("Ishtirok etaman", url=f"{bot_link}?start=qoshtepa_register"),
                    button("Manzil", callback_data="vodiy:place"),
                ],
            },
            {
                "type": "buttons",
                "buttons": [
                    button("Savol berish", url=f"{bot_link}?start=qoshtepa_question"),
                    button("Bepulmi?", callback_data="vodiy:free"),
                ],
            },
        ]
    }


async def _send_rich_card(bot: Any, chat_id: int | str) -> None:
    from aiogram.methods.base import TelegramMethod
    from aiogram.types import Message

    class SendRichMessage(TelegramMethod[Message]):
        __returning__ = Message
        __api_method__ = "sendRichMessage"

        chat_id: int | str
        rich_message: dict[str, Any]

    me = await bot.get_me()
    if not me.username:
        raise ValueError("Bot username is required for meeting links")
    await bot(SendRichMessage(chat_id=chat_id, rich_message=_rich_card(me.username)))


def _states() -> Any:
    from aiogram.fsm.state import State, StatesGroup

    class MeetingForm(StatesGroup):
        name = State()
        phone = State()
        question = State()

    return MeetingForm


def _menu() -> Any:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ishtirok etaman", callback_data="vodiy:register")],
            [
                InlineKeyboardButton(text="Manzil", callback_data="vodiy:place"),
                InlineKeyboardButton(text="Savol berish", callback_data="vodiy:question"),
            ],
        ]
    )


def register_vodiy_meeting_handlers(dispatcher: Any, *, owner_id: int) -> None:
    """Register the meeting menu before the generic /start deep-link handler."""
    from aiogram import F

    Form = _states()

    @dispatcher.message(F.text.in_({"/start qoshtepa", "/qoshtepa"}))
    async def show_meeting(message: Any, state: Any) -> None:
        if message.chat.type != "private":
            await message.answer("Ro'yxatdan o'tish uchun botga shaxsiy xabar yozing: /qoshtepa")
            return
        await state.clear()
        try:
            await _send_rich_card(message.bot, message.chat.id)
        except Exception:
            logger.exception("Rich meeting preview failed")
            await message.answer(
                f"{MEETING_TITLE}\n\nQatnashish bepul.\n{MEETING_PLACE}\n"
                "Sana va vaqt tez orada e'lon qilinadi.",
                reply_markup=_menu(),
            )

    @dispatcher.message(F.text == "/start qoshtepa_question")
    async def question_from_link(message: Any, state: Any) -> None:
        if message.chat.type != "private":
            return
        await state.set_state(Form.question)
        await message.answer("Savolingizni yozing. U tashkilotchiga yuboriladi.")

    @dispatcher.message(F.text == "/start qoshtepa_register")
    async def register_from_link(message: Any, state: Any) -> None:
        if message.chat.type != "private":
            return
        await state.set_state(Form.name)
        await message.answer(
            "Ro'yxatdan o'tish uchun ism-familiyangizni yozing. "
            "Ma'lumotlaringiz tashkilotchiga yuboriladi."
        )

    @dispatcher.message(F.text.startswith("/qoshtepa_post"))
    async def publish_meeting(message: Any) -> None:
        if message.chat.type != "private" or message.from_user.id != owner_id:
            return
        parts = (message.text or "").split()
        if len(parts) != 2 or not CHANNEL_PATTERN.fullmatch(parts[1]):
            await message.answer("Kanal ID sini yuboring: /qoshtepa_post -100...")
            return
        try:
            await _send_rich_card(message.bot, int(parts[1]))
        except Exception:
            logger.exception("Rich meeting post failed")
            await message.answer("Post yuborilmadi. Botning kanalga post yozish huquqini tekshiring.")
            return
        await message.answer("Qo'shtepa uchrashuvi posti kanalga yuborildi.")

    @dispatcher.callback_query(F.data == "vodiy:place")
    async def show_place(callback: Any) -> None:
        await callback.answer(
            f"Uchrashuv joyi: {MEETING_PLACE}. Sana va vaqt e'lon qilinadi.",
            show_alert=True,
        )

    @dispatcher.callback_query(F.data == "vodiy:free")
    async def show_free(callback: Any) -> None:
        await callback.answer("Ha, qatnashish bepul. Bu sayohat emas, biznes uchrashuv.", show_alert=True)

    @dispatcher.callback_query(F.data == "vodiy:register")
    async def start_registration(callback: Any, state: Any) -> None:
        await callback.answer()
        await state.set_state(Form.name)
        await callback.message.answer(
            "Ro'yxatdan o'tish uchun ism-familiyangizni yozing. "
            "Ma'lumotlaringiz tashkilotchiga yuboriladi."
        )

    @dispatcher.message(Form.name)
    async def receive_name(message: Any, state: Any) -> None:
        name = (message.text or "").strip()
        if not 2 <= len(name) <= 100:
            await message.answer("Iltimos, ism-familiyangizni matn bilan yozing.")
            return
        await state.update_data(name=name)
        await state.set_state(Form.phone)
        await message.answer("Telefon raqamingizni yozing (+998... formatida).")

    @dispatcher.message(Form.phone)
    async def receive_phone(message: Any, state: Any) -> None:
        phone = re.sub(r"[\s()-]", "", (message.text or ""))
        if not PHONE_PATTERN.fullmatch(phone):
            await message.answer("Raqamni +998... formatida qayta yozing.")
            return
        data = await state.get_data()
        try:
            await message.bot.send_message(
                owner_id,
                f"{MEETING_TITLE}\nYangi ishtirokchi: {data['name']}\n"
                f"Telefon: {phone}\nTelegram ID: {message.from_user.id}",
            )
        except Exception:
            logger.exception("Meeting registration could not reach owner")
            await message.answer("Hozir ro'yxatga olishda xatolik bor. Keyinroq qayta urinib ko'ring.")
            return
        await state.clear()
        await message.answer("Ro'yxatdan o'tdingiz. Qatnashish bepul; sana e'lon qilinadi.")

    @dispatcher.callback_query(F.data == "vodiy:question")
    async def start_question(callback: Any, state: Any) -> None:
        await callback.answer()
        await state.set_state(Form.question)
        await callback.message.answer("Savolingizni yozing. U tashkilotchiga yuboriladi.")

    @dispatcher.message(Form.question)
    async def receive_question(message: Any, state: Any) -> None:
        question = (message.text or "").strip()
        if not 2 <= len(question) <= 1000:
            await message.answer("Savolni 1000 belgidan oshirmay matn bilan yozing.")
            return
        try:
            await message.bot.send_message(
                owner_id,
                f"{MEETING_TITLE}\nSavol: {question}\nTelegram ID: {message.from_user.id}",
            )
        except Exception:
            logger.exception("Meeting question could not reach owner")
            await message.answer("Savol yuborilmadi. Keyinroq qayta urinib ko'ring.")
            return
        await state.clear()
        await message.answer("Savolingiz yetkazildi. Rahmat!")
