from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.handlers import kirim


@pytest.mark.asyncio
async def test_kirim_send_falls_back_to_userbot_reply(monkeypatch):
    from src.context import app_ctx
    bot_client_mock = MagicMock()
    bot_client_mock.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    event = MagicMock(id=77)
    event.reply = AsyncMock()

    monkeypatch.setattr(app_ctx, "bot_client", bot_client_mock)
    monkeypatch.setattr(kirim.settings, "TEAM_GROUP_ID", -100123, raising=False)

    await kirim._send_kirim_celebration(event, "Tabriklaymiz!")

    bot_client_mock.send_message.assert_awaited_once()
    event.reply.assert_awaited_once_with("Tabriklaymiz!", link_preview=False)


@pytest.mark.asyncio
async def test_kirim_topic_income_event_sends_celebration_once(monkeypatch):
    from src.context import app_ctx
    db = MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    bot_client_mock = MagicMock()
    bot_client_mock.send_message = AsyncMock()
    message = SimpleNamespace(
        message="Logo loyiha uchun avans 1 500 000 so'm tushdi",
        reply_to_msg_id=168,
        reply_to=None,
        reply_to_top_id=None,
    )
    event = MagicMock(chat_id=-100123, id=88, message=message)
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=False, username="seller", first_name="Seller")
    )

    monkeypatch.setattr(app_ctx, "bot_client", bot_client_mock)
    monkeypatch.setattr(app_ctx, "advisor_agent", None)
    monkeypatch.setattr(app_ctx, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(kirim.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(kirim.settings, "TOPIC_KIRIM_ID", 168, raising=False)

    await kirim.kirim_topic_handler(event)

    bot_client_mock.send_message.assert_awaited_once()
    assert db.set_state.await_args_list == [
        call("kirim_celebration:-100123:88", "started"),
        call("kirim_celebration:-100123:88", "done"),
    ]


def _kirim_env(monkeypatch, *, db=None):
    from src.context import app_ctx
    db = db or MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    bot = MagicMock()
    bot.send_message = AsyncMock()
    monkeypatch.setattr(app_ctx, "bot_client", bot)
    monkeypatch.setattr(app_ctx, "advisor_agent", None)
    monkeypatch.setattr(app_ctx, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(kirim.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(kirim.settings, "TOPIC_KIRIM_ID", 168, raising=False)
    schedule = MagicMock()
    monkeypatch.setattr(kirim, "_schedule_won_check", schedule)
    return db, bot, schedule


def _kirim_event(text="", *, photo=None, reply_to_msg_id=168, reply_to_top_id=None, msg_id=90):
    message = SimpleNamespace(
        message=text, photo=photo, document=None,
        reply_to_msg_id=reply_to_msg_id, reply_to=None, reply_to_top_id=reply_to_top_id,
    )
    event = MagicMock(chat_id=-100123, id=msg_id, message=message)
    event.reply = AsyncMock()
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(id=555, bot=False, username="seller", first_name="Seller")
    )
    return event


@pytest.mark.asyncio
async def test_kirim_receipt_photo_without_text_is_celebrated(monkeypatch):
    _, bot, schedule = _kirim_env(monkeypatch)

    await kirim.kirim_topic_handler(_kirim_event("", photo=object()))

    bot.send_message.assert_awaited_once()
    assert "yangi kirim" not in bot.send_message.await_args.args[1]
    schedule.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["Sotuv bo'ldi", "Sotuv boʻldi, toʻlov tushdi", "Mijoz to'lov qildi"])
async def test_kirim_confirmation_text_without_amount_is_celebrated(monkeypatch, text):
    _, bot, _ = _kirim_env(monkeypatch)

    await kirim.kirim_topic_handler(_kirim_event(text))

    bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["To'lov tushmadi", "to'lov qachon tushadi?", "salom hammaga"])
async def test_kirim_non_confirmation_text_is_ignored(monkeypatch, text):
    _, bot, schedule = _kirim_env(monkeypatch)

    await kirim.kirim_topic_handler(_kirim_event(text))

    bot.send_message.assert_not_awaited()
    schedule.assert_not_called()


@pytest.mark.asyncio
async def test_kirim_thread_reply_without_amount_is_ignored(monkeypatch):
    """Buxgalterning 'tushdi' javobi sotuvchi tabrigini qayta chaqirmasin."""
    _, bot, _ = _kirim_env(monkeypatch)

    await kirim.kirim_topic_handler(_kirim_event("tushdi", reply_to_msg_id=90, reply_to_top_id=168, msg_id=91))

    bot.send_message.assert_not_awaited()


def _won_env(monkeypatch, *, won_leads, roster):
    db, bot, _ = _kirim_env(monkeypatch)
    from src.context import app_ctx
    db.rop = MagicMock()
    monkeypatch.setattr(app_ctx, "msg_controller", SimpleNamespace(db=db, crm=SimpleNamespace(amocrm=MagicMock())))
    fetcher = MagicMock()
    fetcher.fetch_won_leads_since = AsyncMock(return_value=won_leads)
    monkeypatch.setattr(kirim, "RopFetcher", MagicMock(return_value=fetcher))
    monkeypatch.setattr(kirim, "load_roster", AsyncMock(return_value=roster))
    return db, bot


_SELLER = SimpleNamespace(responsible_user_id=7, telegram_user_id=555, seller_name="Seller")


@pytest.mark.asyncio
async def test_won_check_reminds_seller_when_lead_not_won(monkeypatch):
    db, bot = _won_env(monkeypatch, won_leads=[{"id": 1, "responsible_user_id": 99}], roster=[_SELLER])

    await kirim._check_won_after_payment(_kirim_event("x"), 555, "@seller", db, delay=0)

    bot.send_message.assert_awaited_once()
    assert "amoCRM" in bot.send_message.await_args.args[1]
    db.set_state.assert_awaited_with("kirim_won_check:-100123:90", "reminded")


@pytest.mark.asyncio
async def test_won_check_is_silent_when_lead_is_won(monkeypatch):
    db, bot = _won_env(monkeypatch, won_leads=[{"id": 1, "responsible_user_id": 7}], roster=[_SELLER])

    await kirim._check_won_after_payment(_kirim_event("x"), 555, "@seller", db, delay=0)

    bot.send_message.assert_not_awaited()
    db.set_state.assert_awaited_with("kirim_won_check:-100123:90", "won:1")


@pytest.mark.asyncio
async def test_won_check_skips_unknown_seller(monkeypatch):
    db, bot = _won_env(monkeypatch, won_leads=[], roster=[])

    await kirim._check_won_after_payment(_kirim_event("x"), 555, "@seller", db, delay=0)

    bot.send_message.assert_not_awaited()
    db.set_state.assert_awaited_with("kirim_won_check:-100123:90", "unknown_seller")
