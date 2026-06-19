from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import main


@pytest.mark.asyncio
async def test_dispatcher_routes_bank_messages_to_accountant(monkeypatch):
    accountant = SimpleNamespace(
        handle_bank_message=AsyncMock(return_value={"status": "awaiting_reason"}),
        handle_finance_reply=AsyncMock(),
    )
    event = SimpleNamespace()
    monkeypatch.setattr(main, "card_transaction_accountant", accountant, raising=False)

    await main.card_transaction_handler(event)

    accountant.handle_bank_message.assert_awaited_once_with(event)
    accountant.handle_finance_reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_routes_non_bank_messages_to_finance_reply(monkeypatch):
    accountant = SimpleNamespace(
        handle_bank_message=AsyncMock(return_value={"status": "ignored_sender"}),
        handle_finance_reply=AsyncMock(return_value=True),
    )
    event = SimpleNamespace()
    monkeypatch.setattr(main, "card_transaction_accountant", accountant, raising=False)

    await main.card_transaction_handler(event)

    accountant.handle_finance_reply.assert_awaited_once_with(event)
