"""Unit tests for Cockpit Autopilot Background Scheduler."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.schedulers.cockpit_autopilot_scheduler import (
    CockpitAutopilotScheduler,
    parse_seller_map,
    start_cockpit_autopilot_scheduler,
)
from src.services.command_center.autonomous_engine import AutonomousAlert


@pytest.fixture
def mock_bot_runtime():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=True)
    bot.backend = "aiogram"
    return bot


def test_parse_seller_map():
    raw = "mgr_1:1001, mgr_2: 1002 , mgr_3:invalid"
    res = parse_seller_map(raw)
    assert res["mgr_1"] == "1001"
    assert res["mgr_2"] == "1002"
    assert "mgr_3" in res


@pytest.mark.asyncio
async def test_send_alert(mock_bot_runtime):
    scheduler = CockpitAutopilotScheduler(mock_bot_runtime)
    alert = AutonomousAlert(
        alert_type="sla_nudge",
        recipient_chat_id="12345",
        message_text="Test alert message",
    )
    ok = await scheduler.send_alert(alert)
    assert ok is True
    mock_bot_runtime.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_speed_to_lead_cycle(mock_bot_runtime):
    engine = MagicMock()
    engine.scan_speed_to_lead_alerts = AsyncMock(
        return_value=[
            AutonomousAlert("sla_nudge", "1001", "Alert 1"),
            AutonomousAlert("sla_escalation", "-1002", "Alert 2"),
        ]
    )
    scheduler = CockpitAutopilotScheduler(mock_bot_runtime, engine=engine)

    sent = await scheduler.execute_speed_to_lead_cycle(force=True)
    assert sent == 2
    assert mock_bot_runtime.send_message.await_count == 2


@pytest.mark.asyncio
async def test_execute_ad_anomaly_cycle(mock_bot_runtime):
    engine = MagicMock()
    engine.scan_ad_spend_anomalies = AsyncMock(
        return_value=[
            AutonomousAlert("ad_anomaly", "150074828", "CPL alert"),
        ]
    )
    scheduler = CockpitAutopilotScheduler(mock_bot_runtime, engine=engine)

    sent = await scheduler.execute_ad_anomaly_cycle(force=True)
    assert sent == 1
    mock_bot_runtime.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_morning_pulse_if_due(mock_bot_runtime, monkeypatch):
    from src.settings import settings
    monkeypatch.setattr(settings, "OWNER_ID", "150074828")
    monkeypatch.setattr(settings, "TEAM_GROUP_ID", "-100999888")

    engine = MagicMock()
    engine.build_morning_executive_card = AsyncMock(
        return_value=("Morning Pulse Text", None)
    )
    scheduler = CockpitAutopilotScheduler(mock_bot_runtime, engine=engine)

    # 1. Before 08:45 -> should NOT trigger
    dt_early = datetime(2026, 11, 7, 8, 30, tzinfo=UTC)
    res_early = await scheduler.execute_morning_pulse_if_due(now=dt_early)
    assert res_early is False

    # 2. At 08:50 (Saturday, weekday 5) -> SHOULD trigger
    dt_due = datetime(2026, 11, 7, 8, 50, tzinfo=UTC)
    res_due = await scheduler.execute_morning_pulse_if_due(now=dt_due)
    assert res_due is True
    assert mock_bot_runtime.send_message.await_count >= 1

    # 3. Repeated check on the same day -> should NOT re-trigger
    res_again = await scheduler.execute_morning_pulse_if_due(now=dt_due)
    assert res_again is False


@pytest.mark.asyncio
async def test_execute_evening_wrapup_if_due(mock_bot_runtime, monkeypatch):
    from src.settings import settings
    monkeypatch.setattr(settings, "TEAM_GROUP_ID", "-100999888")

    engine = MagicMock()
    engine.build_evening_closing_card = AsyncMock(
        return_value="Evening Wrapup Text"
    )
    scheduler = CockpitAutopilotScheduler(mock_bot_runtime, engine=engine)

    # At 19:35 -> SHOULD trigger
    dt_evening = datetime(2026, 11, 7, 19, 35, tzinfo=UTC)
    res = await scheduler.execute_evening_wrapup_if_due(now=dt_evening)
    assert res is True
    mock_bot_runtime.send_message.assert_awaited()


def test_start_cockpit_autopilot_scheduler(monkeypatch):
    monkeypatch.setenv("ENABLE_COCKPIT_AUTOPILOT", "0")
    task = start_cockpit_autopilot_scheduler(None)
    assert task is None
