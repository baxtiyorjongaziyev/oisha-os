"""Blocking HTTP/subprocess calls moved off the event loop (audit 2026-11-07).

Codacy review on PR #1031: the `await asyncio.to_thread(...).decode()`
rewrite awaited the wrong expression, and nothing proved the converted paths
no longer block. pilot_sync_v1 also built LeadScraper without its db.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_shell_tool_awaits_thread_before_decoding(monkeypatch):
    from src.agents.agent_tools.google_actions import GoogleActionsMixin

    monkeypatch.setattr("subprocess.check_output", lambda *a, **k: b"up 3 days\n")
    tool = GoogleActionsMixin.__new__(GoogleActionsMixin)

    result = await tool._execute_shell_safe("uptime")

    assert result == {"success": True, "output": "up 3 days\n"}


@pytest.mark.asyncio
async def test_crm_guard_http_fetch_does_not_block_event_loop(monkeypatch):
    import requests

    from src.services.core.crm.crm_guard import CRMGuard

    def slow_get(*args, **kwargs):
        time.sleep(0.3)  # a slow amoCRM response
        return SimpleNamespace(status_code=200, json=lambda: {"_embedded": {"leads": [{"id": 1}]}})

    monkeypatch.setattr(requests, "get", slow_get)
    guard = CRMGuard.__new__(CRMGuard)
    guard.amo = MagicMock(base_url="https://x.amocrm.ru", _get_headers=MagicMock(return_value={}))

    ticks = 0

    async def ticker():
        nonlocal ticks
        for _ in range(10):
            await asyncio.sleep(0.02)
            ticks += 1

    started = time.perf_counter()
    leads_a, leads_b, _ = await asyncio.gather(
        guard._get_active_leads(1), guard._get_active_leads(2), ticker()
    )
    elapsed = time.perf_counter() - started

    assert leads_a == leads_b == [{"id": 1}]
    assert ticks == 10  # the loop kept running while both requests were in flight
    assert elapsed < 0.55  # the two 0.3 s requests overlapped instead of running back to back


@pytest.mark.asyncio
async def test_pilot_sync_builds_lead_scraper_with_database(monkeypatch):
    from src.services.utils import pilot_sync_v1

    client = MagicMock(connect=AsyncMock(), is_user_authorized=AsyncMock(return_value=False))
    db = object()
    scraper_cls = MagicMock()
    monkeypatch.setattr(pilot_sync_v1, "TelegramClient", MagicMock(return_value=client))
    monkeypatch.setattr(pilot_sync_v1, "GoogleService", MagicMock(return_value="google"))
    monkeypatch.setattr(pilot_sync_v1, "Database", MagicMock(return_value=db))
    monkeypatch.setattr(pilot_sync_v1, "LeadScraper", scraper_cls)

    await pilot_sync_v1.main()

    scraper_cls.assert_called_once_with("google", db, client=client)
