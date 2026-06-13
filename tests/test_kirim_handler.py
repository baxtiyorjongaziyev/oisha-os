from types import SimpleNamespace
import json
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src import main


@pytest.mark.asyncio
async def test_kirim_send_falls_back_to_userbot_reply(monkeypatch):
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock(side_effect=RuntimeError("chat not found"))
    event = MagicMock(id=77)
    event.reply = AsyncMock()

    monkeypatch.setattr(main, "bot_client", bot_client)
    monkeypatch.setattr(main.settings, "TEAM_GROUP_ID", -100123, raising=False)

    await main._send_kirim_celebration(event, "Tabriklaymiz!")

    bot_client.send_message.assert_awaited_once()
    event.reply.assert_awaited_once_with("Tabriklaymiz!", link_preview=False)


@pytest.mark.asyncio
async def test_kirim_topic_income_event_waits_for_finance_confirmation(monkeypatch):
    db = MagicMock()
    db.get_state = AsyncMock(return_value=None)
    db.set_state = AsyncMock()
    db.get_user_by_role = AsyncMock(
        return_value={"user_id": 500, "name": "Finance", "username": "finance"}
    )
    bot_client = MagicMock()
    bot_client.send_message = AsyncMock()
    finance_workflow = MagicMock()
    finance_workflow.announce_income = AsyncMock(
        return_value={"workflow_id": "finance-1"}
    )
    message = SimpleNamespace(
        message="Logo loyiha uchun avans 1 500 000 so'm tushdi",
        reply_to_msg_id=168,
        reply_to=None,
        reply_to_top_id=None,
    )
    event = MagicMock(chat_id=-100123, id=88, message=message)
    event.reply = AsyncMock(return_value=SimpleNamespace(id=99))
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(
            id=700,
            bot=False,
            username="seller",
            first_name="Seller",
        )
    )

    async def project(_text):
        return {
            "record_id": "recProject1",
            "project_name": "Logo loyiha",
            "client_ids": ["recClient1"],
            "seller_ids": ["recSeller1"],
            "project_fields": {"AmoCRM_ID": 2001},
        }

    monkeypatch.setattr(main, "bot_client", bot_client)
    monkeypatch.setattr(main, "advisor_agent", None)
    monkeypatch.setattr(main, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(main, "finance_workflow", finance_workflow)
    monkeypatch.setattr(main, "_find_project_for_income", project)
    monkeypatch.setattr(main.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(main.settings, "TOPIC_KIRIM_ID", 168, raising=False)
    monkeypatch.setattr(main.settings, "AMOCRM_SUBDOMAIN", "jonbranding", raising=False)

    await main.kirim_topic_handler(event)

    bot_client.send_message.assert_not_awaited()
    finance_workflow.announce_income.assert_awaited_once()
    assert finance_workflow.announce_income.await_args.kwargs["lead_id"] == 2001
    assert call(
        "kirim_celebration:-100123:88",
        "waiting_finance_confirmation",
    ) in db.set_state.await_args_list


@pytest.mark.asyncio
async def test_kirim_finance_approval_queues_airtable_action(monkeypatch):
    saved = {
        "workflow_id": "finance-1",
        "original_message_id": 88,
        "status": "waiting_finance_confirmation",
    }
    db = MagicMock()

    async def get_state(key, default=None):
        if key == "income_workflow:99":
            return json.dumps(saved)
        return default

    db.get_state = AsyncMock(side_effect=get_state)
    db.set_state = AsyncMock()
    db.get_user_by_role = AsyncMock(
        return_value={"user_id": 500, "name": "Finance", "username": "finance"}
    )
    finance_workflow = MagicMock()
    finance_workflow.confirm_income = AsyncMock()
    message = SimpleNamespace(
        message="tasdiq",
        reply_to_msg_id=99,
        reply_to_top_id=168,
        reply_to=None,
    )
    event = MagicMock(chat_id=-100123, id=100, message=message)
    event.reply = AsyncMock()
    event.get_sender = AsyncMock(
        return_value=SimpleNamespace(
            id=500,
            bot=False,
            username="finance",
            first_name="Finance",
        )
    )

    monkeypatch.setattr(main, "msg_controller", SimpleNamespace(db=db))
    monkeypatch.setattr(main, "finance_workflow", finance_workflow)
    monkeypatch.setattr(main.settings, "TEAM_GROUP_ID", -100123, raising=False)
    monkeypatch.setattr(main.settings, "TOPIC_KIRIM_ID", 168, raising=False)

    await main.kirim_topic_handler(event)

    finance_workflow.confirm_income.assert_awaited_once_with(
        "finance-1",
        confirmed_by="500",
        confirmer_role="finance",
    )
