"""Tests for accurate single-day 19:30 sales closing report (daily_closing)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from src.services.command_center.autonomous_engine import AutonomousCockpitEngine
from src.services.command_center.live_db_bridge import LiveDataBridge
from src.services.core.crm.amocrm_pipeline_config import (
    HR_PIPELINE_ID,
    SALES_PIPELINE_ID,
    STATUS_LOST,
    STATUS_WON,
)

TZ = ZoneInfo("Asia/Tashkent")


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAmoCRM:
    """Deterministic multi-page amoCRM v4 stub (>200 active deals, today vs yesterday)."""

    base_url = "https://jonbranding.amocrm.ru"
    access_token = "fake-token"

    def __init__(
        self,
        *,
        closed_leads: list[dict[str, Any]],
        active_leads: list[dict[str, Any]],
        new_leads: list[dict[str, Any]],
        events: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
    ) -> None:
        self.closed_leads = closed_leads
        self.active_leads = active_leads
        self.new_leads = new_leads
        self.events = events
        self.tasks = tasks

    async def _request_with_auth(
        self, _method: Any, url: str, params: list[tuple[str, Any]] | None = None, timeout: int = 30
    ) -> _FakeResponse:
        del timeout
        p = dict(params or [])
        page = int(p.get("page", 1))
        limit = int(p.get("limit", 250))

        if url.endswith("/api/v4/leads"):
            if "filter[closed_at][from]" in p:
                source = self.closed_leads
            elif "filter[created_at][from]" in p:
                source = self.new_leads
            else:
                source = self.active_leads
            return self._paginate(source, "leads", page, limit)

        if url.endswith("/api/v4/events"):
            return self._paginate(self.events, "events", page, limit)

        if url.endswith("/api/v4/tasks"):
            return self._paginate(self.tasks, "tasks", page, limit)

        return _FakeResponse(404)

    @staticmethod
    def _paginate(
        items: list[dict[str, Any]], key: str, page: int, limit: int
    ) -> _FakeResponse:
        start = (page - 1) * limit
        chunk = items[start : start + limit]
        if not chunk and page == 1:
            return _FakeResponse(204)
        links = {"next": {"href": f"?page={page + 1}"}} if (start + limit) < len(items) else {}
        return _FakeResponse(200, {"_embedded": {key: chunk}, "_links": links})


@pytest.mark.asyncio
async def test_evening_wrapup_uses_live_amocrm_today_uncapped_and_overdue():
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    morning_10 = int((day_start + timedelta(hours=10)).timestamp())
    morning_10_12 = int((day_start + timedelta(hours=10, minutes=12)).timestamp())
    morning_11 = int((day_start + timedelta(hours=11)).timestamp())
    morning_12_15 = int((day_start + timedelta(hours=12, minutes=15)).timestamp())

    closed_leads = [
        {
            "id": 501,
            "name": "B2B Korporativ Brending",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": STATUS_WON,
            "price": 35_000_000,
            "closed_at": morning_11,
        },
        {
            "id": 502,
            "name": "Direct Sotuv",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": STATUS_WON,
            "price": 15_000_000,
            "closed_at": morning_12_15,
        },
        {
            "id": 503,
            "name": "HR Vakansiya",
            "pipeline_id": HR_PIPELINE_ID,
            "status_id": STATUS_WON,
            "price": 99_000_000,
            "closed_at": morning_11,
        },
        {
            "id": 504,
            "name": "Rad etilgan bitim",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": STATUS_LOST,
            "price": 20_000_000,
            "closed_at": morning_11,
        },
    ]

    # 347 active sales deals (> 200 old SQL cap) + 3 closed deals + 2 HR deals
    active_leads = [
        {"id": 1000 + i, "name": f"Bitim #{i}", "pipeline_id": SALES_PIPELINE_ID, "status_id": 89067962}
        for i in range(347)
    ] + [
        {"id": 501, "name": "Closed Won", "pipeline_id": SALES_PIPELINE_ID, "status_id": STATUS_WON},
        {"id": 9001, "name": "HR Nomzod", "pipeline_id": HR_PIPELINE_ID, "status_id": 111},
    ]

    # 2 new leads today: 701 answered in 12m (<=30m SLA), 702 answered in 75m (>30m SLA)
    new_leads = [
        {"id": 701, "name": "Yangi Lid 1", "pipeline_id": SALES_PIPELINE_ID, "status_id": 87609518, "created_at": morning_10},
        {"id": 702, "name": "Yangi Lid 2", "pipeline_id": SALES_PIPELINE_ID, "status_id": 87609518, "created_at": morning_11},
    ]
    events = [
        {"entity_id": 701, "type": "outgoing_call", "created_by": 991, "created_at": morning_10_12},
        {"entity_id": 702, "type": "outgoing_chat_message", "created_by": 992, "created_at": morning_12_15},
        {"entity_id": 888, "type": "common_note_added", "created_by": 992, "created_at": morning_11},
        # Bot event (created_by=13021974) must NOT count as human seller work
        {"entity_id": 999, "type": "lead_status_changed", "created_by": 13021974, "created_at": morning_10},
    ]
    tasks = [
        {"id": 1, "complete_till": int((now_local - timedelta(hours=3)).timestamp())},
        {"id": 2, "complete_till": int((now_local - timedelta(days=1)).timestamp())},
        {"id": 3, "complete_till": int((now_local + timedelta(days=1)).timestamp())},
    ]

    amo = _FakeAmoCRM(
        closed_leads=closed_leads,
        active_leads=active_leads,
        new_leads=new_leads,
        events=events,
        tasks=tasks,
    )
    bridge = LiveDataBridge(db_connection=None, amocrm=amo, use_local_files=False)
    engine = AutonomousCockpitEngine(bridge=bridge)

    text = await engine.build_evening_closing_card(now=now_local)

    assert "28.11.2026 (00:00–19:30)" in text
    assert "2 ta (50.0 mln soʻm)" in text
    assert "347 ta" in text
    assert "50.0% (1/2 ta ≤30 daq)" in text
    # Worked leads: 701, 702, 888 (human events) + 501, 502, 504 (closed sales today) = 6
    assert "Qayta ishlangan lidlar (bugun):</b> 6 ta" in text
    assert "Muddati oʻtgan ochiq vazifalar:</b> 2 ta" in text
    assert "muddati oʻtgan 2 ta ochiq vazifa bor" in text
    assert "trijaj navbatiga biriktirildi" not in text


@pytest.mark.asyncio
async def test_evening_wrapup_db_fallback_ignores_7day_history_and_200_limit(tmp_path):
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    today_11_utc = datetime(2026, 11, 28, 11, 0, tzinfo=TZ).astimezone(ZoneInfo("UTC"))
    today_11_10_utc = today_11_utc + timedelta(minutes=10)
    three_days_ago_utc = today_11_utc - timedelta(days=3)

    dialer_db = tmp_path / "crm_dialer.db"
    with sqlite3.connect(dialer_db) as conn:
        conn.execute(
            "CREATE TABLE dialer_leads (id INTEGER PRIMARY KEY, name TEXT, status_slug TEXT, "
            "price REAL, responsible_user_id INTEGER, responsible_name TEXT, "
            "last_called_at TEXT, updated_at TEXT, is_active INTEGER)"
        )
        # Insert 265 open active deals -> must report 265, NOT 200!
        conn.executemany(
            "INSERT INTO dialer_leads VALUES (?, ?, 'jarayonda', 10000000, 1, 'Sardor', NULL, ?, 1)",
            [(i, f"Faol Bitim {i}", three_days_ago_utc.strftime("%Y-%m-%d %H:%M:%S")) for i in range(1, 266)],
        )
        # 1 deal won TODAY (12 mln), 1 deal won 3 DAYS AGO (80 mln — must be excluded from today!)
        conn.execute(
            "INSERT INTO dialer_leads VALUES (901, 'Bugungi Sotuv', 'sotuv', 12000000, 1, 'Sardor', NULL, ?, 0)",
            (today_11_utc.strftime("%Y-%m-%d %H:%M:%S"),),
        )
        conn.execute(
            "INSERT INTO dialer_leads VALUES (902, 'Eski Sotuv', 'sotuv', 80000000, 1, 'Sardor', NULL, ?, 0)",
            (three_days_ago_utc.strftime("%Y-%m-%d %H:%M:%S"),),
        )

        conn.execute(
            "CREATE TABLE crm_chat_threads (id INTEGER PRIMARY KEY, lead_id INTEGER, channel TEXT, "
            "contact_name TEXT, unread_count INTEGER, responsible_name TEXT, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE crm_chat_messages (id INTEGER PRIMARY KEY, thread_id INTEGER, "
            "direction TEXT, sender_name TEXT, text TEXT, created_at TEXT)"
        )
        # Thread 1: TODAY with real outgoing reply after 10 min
        t_in = today_11_utc.strftime("%Y-%m-%d %H:%M:%S")
        t_out = today_11_10_utc.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO crm_chat_threads VALUES (1, 55, 'telegram', 'Mijoz Bugun', 0, 'Sardor', ?, ?)",
            (t_in, t_out),
        )
        conn.execute("INSERT INTO crm_chat_messages VALUES (1, 1, 'in', 'Mijoz', 'Salom', ?)", (t_in,))
        conn.execute("INSERT INTO crm_chat_messages VALUES (2, 1, 'out', 'Sardor', 'Javob', ?)", (t_out,))

        # Thread 2: TODAY with unread_count=0 but ZERO outgoing reply -> must NOT count as answered SLA!
        conn.execute(
            "INSERT INTO crm_chat_threads VALUES (2, 56, 'instagram', 'Javobsiz Mijoz', 0, 'Sardor', ?, ?)",
            (t_in, t_in),
        )
        conn.execute("INSERT INTO crm_chat_messages VALUES (3, 2, 'in', 'Mijoz2', 'Narx?', ?)", (t_in,))

        # Thread 3: 3 DAYS AGO -> must NOT leak into today's count!
        old_s = three_days_ago_utc.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO crm_chat_threads VALUES (3, 57, 'telegram', 'Eski Chat', 0, 'Sardor', ?, ?)",
            (old_s, old_s),
        )
        conn.execute("INSERT INTO crm_chat_messages VALUES (4, 3, 'in', 'Eski', 'Salom', ?)", (old_s,))
        conn.execute("INSERT INTO crm_chat_messages VALUES (5, 3, 'out', 'Sardor', 'Ok', ?)", (old_s,))

        conn.execute(
            "CREATE TABLE crm_tasks (id INTEGER PRIMARY KEY, lead_id INTEGER, lead_name TEXT, "
            "contact_name TEXT, title TEXT, responsible_name TEXT, due_at TEXT, is_completed INTEGER)"
        )
        conn.execute(
            "INSERT INTO crm_tasks VALUES (1, 55, 'Bitim', 'Mijoz', 'Qayta aloqa', 'Sardor', ?, 0)",
            (old_s,),
        )

    bridge = LiveDataBridge(
        db_connection=None,
        amocrm=None,
        dialer_db_path=str(dialer_db),
        ad_spend_db_path=str(tmp_path / "no_spend.db"),
        attribution_db_path=str(tmp_path / "no_attr.db"),
        use_local_files=True,
    )
    # Prevent _resolve_conn() from picking up global repo singleton DB during isolated test
    bridge._resolve_conn = lambda: None  # type: ignore[method-assign]

    engine = AutonomousCockpitEngine(bridge=bridge)
    text = await engine.build_evening_closing_card(now=now_local)

    assert "1 ta (12.0 mln soʻm)" in text
    assert "80.0 mln" not in text
    assert "265 ta" in text
    assert "200 ta" not in text
    assert "50.0% (1/2 ta ≤30 daq)" in text
    assert "Qayta ishlangan lidlar (bugun):</b> 2 ta" in text  # lead_901 (won) + lead_55 (replied)
    assert "Muddati oʻtgan ochiq vazifalar:</b> 1 ta" in text
    assert "trijaj navbatiga biriktirildi" not in text


@pytest.mark.asyncio
async def test_evening_wrapup_reports_unknown_when_no_sources_connected(tmp_path):
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    bridge = LiveDataBridge(
        db_connection=None,
        amocrm=None,
        dialer_db_path=str(tmp_path / "missing.db"),
        ad_spend_db_path=str(tmp_path / "missing2.db"),
        attribution_db_path=str(tmp_path / "missing3.db"),
        use_local_files=False,
    )
    text = await AutonomousCockpitEngine(bridge=bridge).build_evening_closing_card(now=now_local)

    assert "nomaʼlum" in text
    assert "0 mln" not in text
    assert "trijaj navbatiga biriktirildi" not in text
