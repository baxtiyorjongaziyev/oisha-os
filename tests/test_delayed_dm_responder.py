from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.services.core.delayed_dm_responder import (
    DelayedDmResponder,
    calculate_target_reply_time,
    get_delay_minutes,
    is_delayed_dm_enabled,
)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_messages = AsyncMock(return_value=[])
    client.send_message = AsyncMock()
    client.action = MagicMock()
    # Mock async context manager for client.action
    action_cm = MagicMock()
    action_cm.__aenter__ = AsyncMock(return_value=None)
    action_cm.__aexit__ = AsyncMock(return_value=None)
    client.action.return_value = action_cm
    return client


@pytest.fixture
def responder():
    return DelayedDmResponder()


def test_is_delayed_dm_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_DELAYED_DM_AUTO_REPLY", "1")
    assert is_delayed_dm_enabled() is True

    monkeypatch.setenv("ENABLE_DELAYED_DM_AUTO_REPLY", "0")
    assert is_delayed_dm_enabled() is False


def test_get_delay_minutes(monkeypatch):
    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "15")
    assert get_delay_minutes() == 15

    monkeypatch.setenv("DM_UNANSWERED_DELAY_MINUTES", "invalid")
    assert get_delay_minutes() == 15


def test_calculate_target_reply_time_daytime():
    # 14:00 daytime in Tashkent -> should add 15 minutes -> 14:15
    tz = ZoneInfo("Asia/Tashkent")
    day_now = datetime(2026, 10, 26, 14, 0, 0, tzinfo=tz)
    target = calculate_target_reply_time(now=day_now, delay_minutes=15)

    assert target.hour == 14
    assert target.minute == 15
    assert target.day == 26


def test_calculate_target_reply_time_night_quiet_hours():
    # 22:30 night in Tashkent -> falls in quiet hours -> should push to tomorrow 09:00
    tz = ZoneInfo("Asia/Tashkent")
    night_now = datetime(2026, 10, 26, 22, 30, 0, tzinfo=tz)
    target = calculate_target_reply_time(now=night_now, delay_minutes=15)

    assert target.hour == 9
    assert target.minute == 0
    assert target.day == 27  # next day


def test_calculate_target_reply_time_early_morning_quiet_hours():
    # 04:00 early morning in Tashkent -> should push to today 09:00
    tz = ZoneInfo("Asia/Tashkent")
    morning_now = datetime(2026, 10, 26, 4, 0, 0, tzinfo=tz)
    target = calculate_target_reply_time(now=morning_now, delay_minutes=15)

    assert target.hour == 9
    assert target.minute == 0
    assert target.day == 26  # today


@pytest.mark.asyncio
async def test_register_incoming_dm_skips_when_disabled(monkeypatch, responder, mock_client):
    monkeypatch.setenv("ENABLE_DELAYED_DM_AUTO_REPLY", "0")
    event = SimpleNamespace(
        chat_id=12345,
        is_private=True,
        out=False,
        raw_text="Salom",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=12345, bot=False)),
    )
    await responder.register_incoming_dm(event, client=mock_client)
    assert 12345 not in responder._pending_tasks


@pytest.mark.asyncio
async def test_register_incoming_dm_skips_outgoing_or_group(responder, mock_client):
    # Group event
    event_group = SimpleNamespace(
        chat_id=-10012345,
        is_private=False,
        out=False,
        raw_text="Salom",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=12345, bot=False)),
    )
    await responder.register_incoming_dm(event_group, client=mock_client)
    assert -10012345 not in responder._pending_tasks

    # Outgoing event
    event_out = SimpleNamespace(
        chat_id=12345,
        is_private=True,
        out=True,
        raw_text="Salom",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=12345, bot=False)),
    )
    await responder.register_incoming_dm(event_out, client=mock_client)
    assert 12345 not in responder._pending_tasks


@pytest.mark.asyncio
async def test_register_incoming_dm_skips_escalation_trigger(responder, mock_client):
    event = SimpleNamespace(
        chat_id=12345,
        is_private=True,
        out=False,
        raw_text="Pulimni qaytarib bering, shikoyat qilaman!",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=12345, bot=False)),
    )
    await responder.register_incoming_dm(event, client=mock_client)
    assert 12345 not in responder._pending_tasks


@pytest.mark.asyncio
async def test_register_incoming_dm_skips_personal_folder(monkeypatch, responder, mock_client):
    event = SimpleNamespace(
        chat_id=12345,
        is_private=True,
        out=False,
        raw_text="Salom jigar",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=12345, bot=False)),
    )
    with patch(
        "src.entrypoint.filters._is_personal_folder_sender",
        AsyncMock(return_value=True),
    ):
        await responder.register_incoming_dm(event, client=mock_client)
        assert 12345 not in responder._pending_tasks


@pytest.mark.asyncio
async def test_on_owner_reply_cancels_pending_task(responder, mock_client):
    event = SimpleNamespace(
        chat_id=99999,
        is_private=True,
        out=False,
        raw_text="Logo narxi qancha?",
        get_sender=AsyncMock(return_value=SimpleNamespace(id=99999, bot=False, first_name="Ali")),
    )
    with patch(
        "src.entrypoint.filters._is_personal_folder_sender",
        AsyncMock(return_value=False),
    ):
        await responder.register_incoming_dm(event, client=mock_client)
        assert 99999 in responder._pending_tasks

        # Owner replies!
        responder.on_owner_reply(99999)
        assert 99999 not in responder._pending_tasks


@pytest.mark.asyncio
async def test_check_if_still_unanswered_aborts_if_owner_replied(responder, mock_client):
    # Simulated messages where owner sent an outgoing message
    arrival_time = 1700000000.0
    mock_msg_out = SimpleNamespace(
        out=True,
        date=SimpleNamespace(timestamp=lambda: arrival_time + 100.0),
        text="Assalomu alaykum! Eshitaman",
    )
    mock_client.get_messages = AsyncMock(return_value=[mock_msg_out])

    is_unanswered, _ = await responder._check_if_still_unanswered(
        mock_client, 12345, arrival_time
    )
    assert is_unanswered is False


@pytest.mark.asyncio
async def test_check_if_still_unanswered_succeeds_when_only_client_messages(responder, mock_client):
    arrival_time = 1700000000.0
    mock_msg_in = SimpleNamespace(
        out=False,
        date=SimpleNamespace(timestamp=lambda: arrival_time + 10.0),
        text="Branding bo'yicha maslahat olmoqchi edim",
    )
    mock_client.get_messages = AsyncMock(return_value=[mock_msg_in])

    is_unanswered, text = await responder._check_if_still_unanswered(
        mock_client, 12345, arrival_time
    )
    assert is_unanswered is True
    assert "Branding bo'yicha" in text


@pytest.mark.asyncio
async def test_generate_personal_reply_fallback(responder):
    with patch.dict("os.environ", {}, clear=True):
        reply = await responder.generate_personal_reply("Ali", "Salom")
        assert "Assalomu alaykum" in reply
        assert "Baxtiyor" not in reply or "uchrashuvdaman" in reply
