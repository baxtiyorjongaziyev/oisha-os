"""Tests for src.services.core.delayed_dm_reminder — assistant DM reminder."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.services.core.delayed_dm_reminder import (
    SHAHNOZA_USERNAME,
    get_delay_minutes,
    is_assistant_reminder_enabled,
    schedule_assistant_reminder,
)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_messages = AsyncMock(return_value=[])
    client.send_message = AsyncMock()
    return client


def _outgoing_msg(user_id: int, ts: float) -> SimpleNamespace:
    return SimpleNamespace(
        out=True,
        from_id=SimpleNamespace(user_id=user_id),
        date=SimpleNamespace(timestamp=lambda: ts),
    )


def test_is_assistant_reminder_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_ASSISTANT_DM_REMINDER", "1")
    assert is_assistant_reminder_enabled() is True

    monkeypatch.setenv("ENABLE_ASSISTANT_DM_REMINDER", "0")
    assert is_assistant_reminder_enabled() is False


def test_get_delay_minutes(monkeypatch):
    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "15")
    assert get_delay_minutes() == 15

    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "invalid")
    assert get_delay_minutes() == 15


@pytest.mark.asyncio
async def test_schedule_skips_group_outgoing_bot_and_assistant(mock_client):
    from src.services.core.delayed_dm_reminder import _IS_SCHEDULED
    _IS_SCHEDULED.clear()

    group_event = SimpleNamespace(
        chat_id=-100123, is_private=False, out=False, raw_text="x",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=1, bot=False)),
    )
    await schedule_assistant_reminder(group_event, client=mock_client)
    assert mock_client.send_message.await_count == 0

    out_event = SimpleNamespace(
        chat_id=-100123,
        is_private=False,
        out=False,
        raw_text="x",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=1, bot=False)),
    )


@pytest.mark.asyncio
async def test_wait_and_remind_sends_to_team_group(monkeypatch, mock_client):
    from src.services.core.delayed_dm_reminder import (
        OWNER_USER_ID,
        SHAHNOZA_USER_ID,
        _IS_SCHEDULED,
        _wait_and_remind,
    )
    _IS_SCHEDULED.clear()

    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "1")
    monkeypatch.setattr(
        __import__("src.settings", fromlist=["settings"]).settings,
        "TEAM_GROUP_ID",
        -100123,
        raising=False,
    )

    # No outgoing messages at all -> reminder must be sent
    mock_client.get_messages = AsyncMock(return_value=[])
    with patch("asyncio.sleep", new=AsyncMock()):
        await _wait_and_remind(mock_client, 12345, "Ali", 1)

    assert mock_client.send_message.await_count == 1
    call_args = mock_client.send_message.await_args
    assert call_args.args[0] == -100123
    text = call_args.args[1]
    assert SHAHNOZA_USERNAME in text
    assert "Ali" in text
    assert "eslatmasi" in text


@pytest.mark.asyncio
async def test_wait_and_remind_skips_if_owner_replied(monkeypatch, mock_client):
    from src.services.core.delayed_dm_reminder import (
        OWNER_USER_ID,
        _IS_SCHEDULED,
        _wait_and_remind,
    )
    _IS_SCHEDULED.clear()

    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "1")
    monkeypatch.setattr(
        __import__("src.settings", fromlist=["settings"]).settings,
        "TEAM_GROUP_ID",
        -100123,
        raising=False,
    )

    now = datetime.now(ZoneInfo("Asia/Tashkent")).timestamp()
    mock_client.get_messages = AsyncMock(return_value=[_outgoing_msg(OWNER_USER_ID, now)])
    with patch("asyncio.sleep", new=AsyncMock()):
        await _wait_and_remind(mock_client, 12345, "Ali", 1)

    assert mock_client.send_message.await_count == 0


@pytest.mark.asyncio
async def test_wait_and_remind_skips_if_assistant_replied(monkeypatch, mock_client):
    from src.services.core.delayed_dm_reminder import (
        SHAHNOZA_USER_ID,
        _IS_SCHEDULED,
        _wait_and_remind,
    )
    _IS_SCHEDULED.clear()

    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "1")
    monkeypatch.setattr(
        __import__("src.settings", fromlist=["settings"]).settings,
        "TEAM_GROUP_ID",
        -100123,
        raising=False,
    )

    now = datetime.now(ZoneInfo("Asia/Tashkent")).timestamp()
    mock_client.get_messages = AsyncMock(return_value=[_outgoing_msg(SHAHNOZA_USER_ID, now)])
    with patch("asyncio.sleep", new=AsyncMock()):
        await _wait_and_remind(mock_client, 12345, "Ali", 1)

    assert mock_client.send_message.await_count == 0


@pytest.mark.asyncio
async def test_wait_and_remind_skips_when_team_group_missing(monkeypatch, mock_client):
    from src.services.core.delayed_dm_reminder import (
        _IS_SCHEDULED,
        schedule_assistant_reminder,
    )
    _IS_SCHEDULED.clear()

    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "1")
    monkeypatch.setattr(
        __import__("src.settings", fromlist=["settings"]).settings,
        "TEAM_GROUP_ID",
        None,
        raising=False,
    )

    event = SimpleNamespace(
        chat_id=12345, is_private=True, out=False, raw_text="x",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=99999, bot=False, first_name="Ali")),
    )
    mock_client.get_messages = AsyncMock(return_value=[])
    with patch("asyncio.sleep", new=AsyncMock()):
        await schedule_assistant_reminder(event, client=mock_client)

    assert mock_client.send_message.await_count == 0

