import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.services.response_quality.delivery_ledger import DeliveryLedger, send_once


def test_restart_does_not_repeat(tmp_path):
    path = str(tmp_path / 'ledger.db')
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=123)))
    asyncio.run(send_once(bot, chat_id=1, text='Synthetic test message', key='synthetic:1', ledger=DeliveryLedger(path)))
    asyncio.run(send_once(bot, chat_id=1, text='Changed synthetic text', key='synthetic:1', ledger=DeliveryLedger(path)))
    assert bot.send_message.await_count == 1


def test_uncertain_timeout_is_not_retried(tmp_path):
    path = str(tmp_path / 'ledger.db')
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=TimeoutError))
    try:
        asyncio.run(send_once(bot, chat_id=1, text='Synthetic', key='synthetic:2', ledger=DeliveryLedger(path)))
    except TimeoutError:
        pass
    assert not DeliveryLedger(path).claim('synthetic:2', 'Synthetic')
