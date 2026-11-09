from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.handlers import kirim

SOTUV_GROUP = -1003854308552

PAYMENT_FORM = (
    "💰 TO'LOV TASDIQLASH\n\n"
    "📅 Sana: 09.11.2026\n"
    "💵 Summa (so'm): 6.760.000\n"
    "👤 Mijoz / Loyiha: Hilola opa +998994037888 Patent - Del luna\n"
    "To'lov turi: Naqd\n"
    "Sotuvchi: Baxtiyorjon\n"
    "Chek: Tasdiqlang @jonbranding_finansist"
)


def _event(text, chat_id=SOTUV_GROUP, bot=False, msg_id=88):
    message = SimpleNamespace(
        message=text, reply_to_msg_id=2976, reply_to=None, reply_to_top_id=None
    )
    event = MagicMock(chat_id=chat_id, id=msg_id, message=message)
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=bot, username="seller", first_name="Seller")
    )
    return event


def _wire(monkeypatch):
    from src.context import app_ctx

    db = MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    bot_client_mock = MagicMock()
    bot_client_mock.send_message = AsyncMock()
    monkeypatch.setattr(app_ctx, "bot_client", bot_client_mock)
    monkeypatch.setattr(app_ctx, "advisor_agent", None)
    monkeypatch.setattr(app_ctx, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(
        kirim.settings, "CRM_SALES_REPORT_GROUP_ID", SOTUV_GROUP, raising=False
    )
    return db, bot_client_mock


@pytest.mark.asyncio
async def test_kirim_send_falls_back_to_userbot_reply(monkeypatch):
    from src.context import app_ctx
    bot_client_mock = MagicMock()
    bot_client_mock.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    event = MagicMock(id=77)
    event.reply = AsyncMock()

    monkeypatch.setattr(app_ctx, "bot_client", bot_client_mock)
    monkeypatch.setattr(
        kirim.settings, "CRM_SALES_REPORT_GROUP_ID", SOTUV_GROUP, raising=False
    )

    await kirim._send_kirim_celebration(event, "Tabriklaymiz!")

    bot_client_mock.send_message.assert_awaited_once()
    event.reply.assert_awaited_once_with("Tabriklaymiz!", link_preview=False)


@pytest.mark.asyncio
async def test_income_event_in_sotuv_group_sends_celebration_once(monkeypatch):
    db, bot_client_mock = _wire(monkeypatch)
    event = _event("Logo loyiha uchun avans 1 500 000 so'm tushdi")

    await kirim.kirim_topic_handler(event)

    bot_client_mock.send_message.assert_awaited_once()
    assert db.set_state.await_args_list == [
        call(f"kirim_celebration:{SOTUV_GROUP}:88", "started"),
        call(f"kirim_celebration:{SOTUV_GROUP}:88", "done"),
    ]


@pytest.mark.asyncio
async def test_payment_form_in_any_topic_celebrates_with_summa_not_phone(monkeypatch):
    _, bot_client_mock = _wire(monkeypatch)

    await kirim.kirim_topic_handler(_event(PAYMENT_FORM))

    bot_client_mock.send_message.assert_awaited_once()
    text = bot_client_mock.send_message.await_args.args[1]
    assert "6.760.000" in text
    assert "998994037888" not in text


@pytest.mark.asyncio
async def test_phone_number_only_message_is_not_celebrated(monkeypatch):
    _, bot_client_mock = _wire(monkeypatch)

    await kirim.kirim_topic_handler(_event("+998909220700 telegrami kerak"))

    bot_client_mock.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_group_is_ignored(monkeypatch):
    _, bot_client_mock = _wire(monkeypatch)

    await kirim.kirim_topic_handler(_event(PAYMENT_FORM, chat_id=-100999))

    bot_client_mock.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_sender_is_ignored(monkeypatch):
    _, bot_client_mock = _wire(monkeypatch)

    await kirim.kirim_topic_handler(_event(PAYMENT_FORM, bot=True))

    bot_client_mock.send_message.assert_not_awaited()


@pytest.mark.parametrize("apostrophe", ["'", "‘", "’", "ʻ", "ʼ"])
def test_apostrophe_variants_recognized_and_negations_rejected(apostrophe):
    assert kirim._looks_like_income_announcement(
        f"TO{apostrophe}LOV TASDIQLASH Summa: 6.760.000"
    )
    assert not kirim._looks_like_income_announcement(
        f"avans 1 500 000 bo{apostrophe}lmadi"
    )
    assert not kirim._looks_like_income_announcement(f"kirim 500 000 yo{apostrophe}q")
