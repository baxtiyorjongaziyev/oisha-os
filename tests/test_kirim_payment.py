from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.handlers import kirim, kirim_payment

CARD = (
    "💰 TO'LOV TASDIQLASH\n\n"
    "📅 Sana: 02.11.2026\n"
    "💵 Summa (so'm): 700.000\n"
    "👤 Mijoz / Loyiha: OOMAR\n"
    "🧾 To'lov turi: Expert tekshiruvi\n"
    "🙋 Sotuvchi: Rayxona\n"
    "📎 Chek: Tasdiqlang @jonbranding_finansist"
)


def _event(text: str = CARD, *, message_id: int = 88, reply_to=None):
    message = SimpleNamespace(
        message=text,
        reply_to_msg_id=reply_to,
        reply_to=None,
        reply_to_top_id=168,
    )
    event = MagicMock(chat_id=-100123, id=message_id, out=False, message=message)
    event.reply = AsyncMock(return_value=SimpleNamespace(id=501))
    event.respond = AsyncMock(return_value=SimpleNamespace(id=502))
    return event


def _patch_env(monkeypatch, db, bot_client):
    from src.context import app_ctx

    monkeypatch.setattr(app_ctx, "bot_client", bot_client)
    monkeypatch.setattr(app_ctx, "client", None)
    monkeypatch.setattr(app_ctx, "advisor_agent", None)
    monkeypatch.setattr(app_ctx, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(kirim_payment.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(kirim_payment.settings, "TOPIC_KIRIM_ID", 168, raising=False)
    monkeypatch.setattr(kirim_payment.settings, "OWNER_ID", 9999, raising=False)
    monkeypatch.delenv(kirim_payment.FINANCE_MENTION_ENV, raising=False)


@pytest.mark.asyncio
async def test_payment_card_sends_group_dm_and_finance_ask(monkeypatch):
    db = MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(return_value=SimpleNamespace(id=500))
    _patch_env(monkeypatch, db, bot_client)

    event = _event()
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(
            bot=False, id=1001, username="rayxona", first_name="Rayxona"
        )
    )

    await kirim_payment.kirim_payment_handler(event)

    sent_texts = [c.args[1] for c in bot_client.send_message.await_args_list]
    assert len(sent_texts) == 3
    assert any("Rayxona" in text and "700.000 so'm" in text for text in sent_texts)
    assert any("@jonbranding_finansist" in text and "tasdiqlaysizmi" in text for text in sent_texts)

    dm_calls = [c for c in bot_client.send_message.await_args_list if c.args[0] == 1001]
    assert dm_calls, "sotuvchiga shaxsiy tabrik yuborilmadi"

    stages = [
        c.args[1].get("stage")
        for c in db.set_state.await_args_list
        if isinstance(c.args[1], dict) and "stage" in c.args[1]
    ]
    assert stages == ["processing", "awaiting_approval"]


@pytest.mark.asyncio
async def test_payment_card_skips_duplicates(monkeypatch):
    db = MagicMock()
    db.get_state = AsyncMock(return_value={"stage": "awaiting_approval"})
    db.set_state = AsyncMock()
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(return_value=SimpleNamespace(id=500))
    _patch_env(monkeypatch, db, bot_client)

    event = _event()
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=False, id=1001, username="rayxona")
    )

    await kirim_payment.kirim_payment_handler(event)

    bot_client.send_message.assert_not_awaited()
    db.set_state.assert_not_awaited()


def test_card_is_not_treated_as_income_announcement():
    assert kirim._looks_like_income_announcement(CARD) is False
    assert kirim._looks_like_income_announcement("Logo loyiha uchun avans 1 500 000 so'm tushdi") is True


@pytest.mark.asyncio
async def test_finance_approval_sends_second_congratulation(monkeypatch):
    state = {
        "stage": "awaiting_approval",
        "card_message_id": 88,
        "seller_id": 1001,
        "seller_name": "Rayxona",
        "seller_handle": None,
        "amount_label": "700.000 so'm",
        "project": "OOMAR",
    }
    db = MagicMock()
    db.get_state = AsyncMock(side_effect=lambda key: state if ":88" in key and "ask" not in key else None)
    db.set_state = AsyncMock()
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(return_value=SimpleNamespace(id=500))
    _patch_env(monkeypatch, db, bot_client)

    event = _event(text="tasdiqlandi", message_id=90, reply_to=88)
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=False, id=2002, username="jonbranding_finansist")
    )

    await kirim_payment.kirim_payment_reply_handler(event)

    assert db.set_state.await_args.args[1]["stage"] == "approved"
    sent_texts = [c.args[1] for c in bot_client.send_message.await_args_list]
    assert any("yana bir bor tabriklaymiz" in text for text in sent_texts)
    dm_calls = [c for c in bot_client.send_message.await_args_list if c.args[0] == 1001]
    assert dm_calls, "tasdiqdan keyingi shaxsiy tabrik yuborilmadi"


@pytest.mark.asyncio
async def test_seller_cannot_confirm_own_payment(monkeypatch):
    state = {
        "stage": "awaiting_approval",
        "seller_id": 1001,
        "seller_name": "Rayxona",
    }
    db = MagicMock()
    db.get_state = AsyncMock(side_effect=lambda key: state if ":88" in key and "ask" not in key else None)
    db.set_state = AsyncMock()
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(return_value=SimpleNamespace(id=500))
    _patch_env(monkeypatch, db, bot_client)

    event = _event(text="tasdiqlandi", message_id=91, reply_to=88)
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=False, id=1001, username="rayxona")
    )

    await kirim_payment.kirim_payment_reply_handler(event)

    bot_client.send_message.assert_not_awaited()
    db.set_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_random_member_cannot_confirm_payment(monkeypatch):
    state = {
        "stage": "awaiting_approval",
        "seller_id": 1001,
        "seller_name": "Rayxona",
    }
    db = MagicMock()
    db.get_state = AsyncMock(side_effect=lambda key: state if ":88" in key and "ask" not in key else None)
    db.set_state = AsyncMock()
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(return_value=SimpleNamespace(id=500))
    _patch_env(monkeypatch, db, bot_client)

    event = _event(text="tasdiqlandi", message_id=92, reply_to=88)
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(bot=False, id=3003, username="random_member")
    )

    await kirim_payment.kirim_payment_reply_handler(event)

    bot_client.send_message.assert_not_awaited()
    db.set_state.assert_not_awaited()
