"""Unit tests for aiogram_proactive_digest scheduler loops."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest


class _FakeBotRuntime:
    """Minimal bot runtime stub for testing."""

    backend = "aiogram"

    def __init__(self):
        self.sent: list[tuple] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))


@pytest.fixture()
def bot():
    return _FakeBotRuntime()


async def _snapshot_ok():
    return {
        "status": "ready",
        "items": [
            {
                "lead_id": 1,
                "name": "Test lead",
                "priority": "high",
                "priority_score": 90,
                "reasons": ["no_open_task"],
                "action": "Call now.",
            }
        ],
        "scanned_count": 1,
        "skipped_closed_count": 0,
    }


async def _project_snapshot_ok():
    return {
        "status": "ready",
        "items": [
            {
                "project_id": "rec1",
                "name": "Brandbook",
                "risk": "critical",
                "risk_score": 80,
                "reasons": ["overdue"],
                "action": "Fix deadline.",
                "evidence": {"deadline": "2026-07-18", "manager": "Ali"},
            }
        ],
        "scanned_count": 1,
        "skipped_closed_count": 0,
    }


async def _finance_snapshot_ok():
    return {
        "status": "ready",
        "items": [
            {
                "project_id": "fin1",
                "name": "Brandbook",
                "risk": "critical",
                "risk_score": 85,
                "reasons": ["advance_below_50"],
                "action": "Collect advance.",
                "evidence": {
                    "budget": 20_000_000,
                    "paid_amount": 2_000_000,
                    "remaining_amount": 18_000_000,
                },
            }
        ],
        "scanned_count": 1,
        "skipped_closed_count": 0,
    }


async def _team_snapshot_ok():
    return {
        "status": "ready",
        "items": [
            {
                "owner_name": "Ali",
                "load": "busy",
                "load_score": 45,
                "reasons": ["due_3_days"],
                "action": "Confirm priorities.",
                "evidence": {
                    "active_projects": 3,
                    "overdue_projects": 0,
                    "due_3_days": 2,
                },
            }
        ],
        "scanned_count": 3,
        "unassigned_project_count": 0,
    }


@pytest.mark.asyncio
async def test_safe_send_skips_missing_runtime():
    """_safe_send should return False if bot_client is None."""
    from src.schedulers.aiogram_proactive_digest import _safe_send

    assert await _safe_send(None, -100123, "hi") is False


@pytest.mark.asyncio
async def test_safe_send_skips_missing_chat():
    from src.schedulers.aiogram_proactive_digest import _safe_send

    bot = _FakeBotRuntime()
    assert await _safe_send(bot, None, "hi") is False
    assert bot.sent == []


@pytest.mark.asyncio
async def test_safe_send_delivers_message():
    from src.schedulers.aiogram_proactive_digest import _safe_send

    bot = _FakeBotRuntime()
    result = await _safe_send(bot, -100123, "Hello!")
    assert result is True
    assert bot.sent[0][1] == "Hello!"


def test_build_vps_text_contains_expected_fields():
    from src.schedulers.aiogram_proactive_digest import _build_vps_text

    text = _build_vps_text()
    assert "CPU:" in text
    assert "RAM:" in text
    assert "Disk:" in text
    assert "VPS SERVER HOLATI" in text


def test_once_daily_guard_prevents_double_run():
    from src.schedulers.aiogram_proactive_digest import _once_daily_guard

    state: dict = {}
    assert _once_daily_guard(state, "daily", "2026-07-27") is True
    assert _once_daily_guard(state, "daily", "2026-07-27") is False
    assert _once_daily_guard(state, "daily", "2026-07-28") is True


@pytest.mark.asyncio
async def test_start_proactive_digest_loops_creates_tasks():
    """start_proactive_digest_loops should return a list of asyncio Tasks."""
    from src.schedulers.aiogram_proactive_digest import start_proactive_digest_loops

    tasks = start_proactive_digest_loops(
        bot_client=_FakeBotRuntime(),
        target_chat_id=-100123,
        get_sales_today_priorities=_snapshot_ok,
        get_project_delivery_risks=_project_snapshot_ok,
        get_finance_project_risks=_finance_snapshot_ok,
        get_team_capacity=_team_snapshot_ok,
    )
    assert len(tasks) == 5
    for t in tasks:
        assert isinstance(t, asyncio.Task)
    # Cleanup — cancel tasks so they don't linger in the event loop
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
