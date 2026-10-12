"""Forged inline callbacks must not mutate finance state.

callback_data is client-controlled: any user who has a message from the bot in
their own DM can send `happrove:<id>` via MTProto getBotCallbackAnswer.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.core.telegram import callback_auth

OWNER = 111
WHITELISTED = 222
STRANGER = 999
FINANCE_GROUP = -100500
TEAM_GROUP = -100600


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    s = callback_auth.settings
    monkeypatch.setattr(s, "OWNER_ID", OWNER, raising=False)
    monkeypatch.setattr(s, "WHITELIST_IDS", [WHITELISTED], raising=False)
    monkeypatch.setattr(s, "HISOBCHI_FINANCE_GROUP_ID", FINANCE_GROUP, raising=False)
    monkeypatch.setattr(s, "TEAM_GROUP_ID", TEAM_GROUP, raising=False)


class _Callback:
    def __init__(self, user_id, chat_id, data="happrove:7:personal"):
        self.from_user = SimpleNamespace(id=user_id)
        self.message = SimpleNamespace(chat=SimpleNamespace(id=chat_id))
        self.data = data
        self.answers = []

    async def answer(self, text="", **kwargs):
        self.answers.append((text, kwargs))


@pytest.mark.parametrize(
    ("user_id", "chat_id", "expected"),
    [
        (OWNER, STRANGER, True),
        (WHITELISTED, STRANGER, True),
        (STRANGER, FINANCE_GROUP, True),
        (STRANGER, TEAM_GROUP, True),
        (STRANGER, STRANGER, False),  # forged from the stranger's own DM
        (0, 0, False),
    ],
)
def test_is_trusted_finance_callback(user_id, chat_id, expected):
    assert callback_auth.is_trusted_finance_callback(_Callback(user_id, chat_id)) is expected


def test_no_trusted_chats_when_unconfigured(monkeypatch):
    monkeypatch.setattr(callback_auth.settings, "HISOBCHI_FINANCE_GROUP_ID", None, raising=False)
    monkeypatch.setattr(callback_auth.settings, "TEAM_GROUP_ID", None, raising=False)
    assert not callback_auth.is_trusted_finance_callback(_Callback(STRANGER, 0))


class _CapturingDispatcher:
    def __init__(self):
        self.handlers = []

    def callback_query(self, *_filters):
        def decorator(fn):
            self.handlers.append(fn)
            return fn

        return decorator


@pytest.mark.asyncio
async def test_hisobchi_callback_rejects_forged_dm_callback():
    from src.services.core import hisobchi_callbacks

    dp = _CapturingDispatcher()
    hisobchi_callbacks.register_callbacks(dp, engine=object())
    handler = dp.handlers[0]

    with patch.object(hisobchi_callbacks, "handle_callback", AsyncMock()) as approve:
        forged = _Callback(STRANGER, STRANGER)
        await handler(forged)
        approve.assert_not_called()
        assert forged.answers and forged.answers[0][1].get("show_alert") is True

        legit = _Callback(STRANGER, FINANCE_GROUP)
        await handler(legit)
        approve.assert_awaited_once()


@pytest.mark.asyncio
async def test_airtable_approval_rejects_forged_callback():
    from src.services.core import airtable_approval_callbacks as mod

    dp = _CapturingDispatcher()
    mod.register_airtable_approval_callbacks(dp)
    handler = dp.handlers[0]

    with patch.object(mod, "update_airtable_transaction_status", AsyncMock(return_value=True)) as upd:
        await handler(_Callback(STRANGER, STRANGER, data="at_app:recABC"))
        upd.assert_not_called()


@pytest.mark.asyncio
async def test_kreativlar_requires_admin(monkeypatch):
    from src.services.core.dispatcher.handlers_admin import handle_aiogram_kreativlar

    message = SimpleNamespace(from_user=SimpleNamespace(id=STRANGER), answer=AsyncMock())
    await handle_aiogram_kreativlar(message, is_admin=lambda _uid: False)
    message.answer.assert_not_called()
