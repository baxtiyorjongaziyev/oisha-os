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
    """Deterministic multi-page amoCRM v4 stub enforcing query filters and bounds."""

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
        extra_leads_by_id: dict[int, dict[str, Any]] | None = None,
        fail_events: bool = False,
        force_next_on_active: bool = False,
    ) -> None:
        self.closed_leads = closed_leads
        self.active_leads = active_leads
        self.new_leads = new_leads
        self.events = events
        self.tasks = tasks
        self.extra_leads_by_id = extra_leads_by_id or {}
        self.fail_events = fail_events
        self.force_next_on_active = force_next_on_active

    async def _request_with_auth(
        self, _method: Any, url: str, params: list[tuple[str, Any]] | None = None, timeout: int = 30
    ) -> _FakeResponse:
        del timeout
        raw_params = params or []
        p = dict(raw_params)
        page = int(p.get("page", 1))
        limit = int(p.get("limit", 250))

        if url.endswith("/api/v4/leads"):
            id_filters = [int(v) for k, v in raw_params if k == "filter[id][]"]
            if id_filters:
                found = [self.extra_leads_by_id[i] for i in id_filters if i in self.extra_leads_by_id]
                return self._paginate(found, "leads", page, limit)
            if "filter[closed_at][from]" in p:
                lo, hi = int(p["filter[closed_at][from]"]), int(p["filter[closed_at][to]"])
                filtered = [ld for ld in self.closed_leads if lo <= int(ld.get("closed_at") or 0) <= hi]
                return self._paginate(filtered, "leads", page, limit)
            if "filter[created_at][from]" in p:
                lo, hi = int(p["filter[created_at][from]"]), int(p["filter[created_at][to]"])
                filtered = [ld for ld in self.new_leads if lo <= int(ld.get("created_at") or 0) <= hi]
                return self._paginate(filtered, "leads", page, limit)
            return self._paginate(
                self.active_leads, "leads", page, limit, force_next=self.force_next_on_active
            )

        if url.endswith("/api/v4/events"):
            if self.fail_events:
                return _FakeResponse(503)
            lo, hi = int(p["filter[created_at][from]"]), int(p["filter[created_at][to]"])
            filtered = [ev for ev in self.events if lo <= int(ev.get("created_at") or 0) <= hi]
            return self._paginate(filtered, "events", page, limit)

        if url.endswith("/api/v4/tasks"):
            want_completed = int(p.get("filter[is_completed]", 0))
            filtered = [
                t for t in self.tasks if int(bool(t.get("is_completed", False))) == want_completed
            ]
            return self._paginate(filtered, "tasks", page, limit)

        return _FakeResponse(404)

    @staticmethod
    def _paginate(
        items: list[dict[str, Any]],
        key: str,
        page: int,
        limit: int,
        *,
        force_next: bool = False,
    ) -> _FakeResponse:
        start = (page - 1) * limit
        chunk = items[start : start + limit]
        if not chunk and page == 1 and not force_next:
            return _FakeResponse(204)
        has_more = force_next or ((start + limit) < len(items))
        links = {"next": {"href": f"?page={page + 1}"}} if has_more else {}
        return _FakeResponse(200, {"_embedded": {key: chunk}, "_links": links})


@pytest.mark.asyncio
async def test_evening_wrapup_uses_live_amocrm_today_uncapped_and_overdue():
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_close = int((day_start - timedelta(hours=5)).timestamp())
    # Lead 701 arrives at 07:30 (before 09:00 work start) and is answered at 09:20:
    # raw elapsed = 110 min (>30m), business_minutes = 20 min (<=30m)!
    pre_work_07_30 = int((day_start + timedelta(hours=7, minutes=30)).timestamp())
    work_09_20 = int((day_start + timedelta(hours=9, minutes=20)).timestamp())
    morning_11 = int((day_start + timedelta(hours=11)).timestamp())
    morning_12_15 = int((day_start + timedelta(hours=12, minutes=15)).timestamp())

    closed_leads = [
        {
            "id": 500,
            "name": "Kechagi Sotuv",
            "pipeline_id": SALES_PIPELINE_ID,
            "status_id": STATUS_WON,
            "price": 90_000_000,
            "closed_at": yesterday_close,
        },
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

    # 347 active sales deals (> 200 old SQL cap) + closed + HR deals
    active_leads = [
        {"id": 1000 + i, "name": f"Bitim #{i}", "pipeline_id": SALES_PIPELINE_ID, "status_id": 89067962}
        for i in range(347)
    ] + [
        {"id": 501, "name": "Closed Won", "pipeline_id": SALES_PIPELINE_ID, "status_id": STATUS_WON},
        {"id": 9001, "name": "HR Nomzod", "pipeline_id": HR_PIPELINE_ID, "status_id": 111},
    ]

    new_leads = [
        {"id": 701, "name": "Erta Tong Lid", "pipeline_id": SALES_PIPELINE_ID, "status_id": 87609518, "created_at": pre_work_07_30},
        {"id": 702, "name": "Kechikkan Lid", "pipeline_id": SALES_PIPELINE_ID, "status_id": 87609518, "created_at": morning_11},
        # Closed quickly without any human first-touch event -> must NOT count as SLA met!
        {"id": 703, "name": "Avto Yopilgan Lid", "pipeline_id": SALES_PIPELINE_ID, "status_id": STATUS_WON, "created_at": morning_11, "closed_at": morning_11 + 60},
    ]
    events = [
        {"entity_id": 701, "type": "outgoing_call", "created_by": 991, "created_at": work_09_20},
        {"entity_id": 702, "type": "outgoing_chat_message", "created_by": 992, "created_at": morning_12_15},
        {"entity_id": 1005, "type": "common_note_added", "created_by": 992, "created_at": morning_11},
        # Note on HR lead 9001 -> must NOT inflate sales worked leads!
        {"entity_id": 9001, "type": "common_note_added", "created_by": 992, "created_at": morning_11},
        # Bot event (created_by=13021974) -> must NOT count as human seller work
        {"entity_id": 1006, "type": "lead_status_changed", "created_by": 13021974, "created_at": morning_11},
    ]
    tasks = [
        {"id": 1, "is_completed": False, "complete_till": int((now_local - timedelta(hours=3)).timestamp())},
        {"id": 2, "is_completed": False, "complete_till": int((now_local - timedelta(days=1)).timestamp())},
        # Completed overdue task -> must NOT be counted!
        {"id": 3, "is_completed": True, "complete_till": int((now_local - timedelta(days=2)).timestamp())},
        {"id": 4, "is_completed": False, "complete_till": int((now_local + timedelta(days=1)).timestamp())},
    ]

    amo = _FakeAmoCRM(
        closed_leads=closed_leads,
        active_leads=active_leads,
        new_leads=new_leads,
        events=events,
        tasks=tasks,
    )
    bridge = LiveDataBridge(db_connection=None, amocrm=amo, use_local_files=False)
    text = await AutonomousCockpitEngine(bridge=bridge).build_evening_closing_card(now=now_local)

    assert "28.11.2026 (00:00–19:30)" in text
    assert "2 ta (50.0 mln soʻm)" in text
    assert "90.0 mln" not in text
    assert "347 ta" in text
    assert "33.3% (1/3 ta ≤30 daq)" in text
    # Worked sales leads: 701, 702, 1005 (sales human events) + 501, 502, 504 (closed sales today) = 6
    assert "Qayta ishlangan lidlar (bugun):</b> 6 ta" in text
    assert "Muddati oʻtgan ochiq vazifalar:</b> 2 ta" in text
    assert "muddati oʻtgan 2 ta ochiq vazifa bor" in text
    assert "trijaj navbatiga biriktirildi" not in text


@pytest.mark.asyncio
async def test_evening_wrapup_partial_failure_and_pagination_cap_mark_only_affected_metrics():
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    morning_10 = int((day_start + timedelta(hours=10)).timestamp())

    amo = _FakeAmoCRM(
        closed_leads=[
            {"id": 1, "name": "Sotuv", "pipeline_id": SALES_PIPELINE_ID, "status_id": STATUS_WON, "price": 10_000_000, "closed_at": morning_10}
        ],
        active_leads=[{"id": 2, "name": "Faol", "pipeline_id": SALES_PIPELINE_ID, "status_id": 89067962}],
        new_leads=[{"id": 3, "name": "Yangi", "pipeline_id": SALES_PIPELINE_ID, "status_id": 89067962, "created_at": morning_10}],
        events=[],
        tasks=[],
        fail_events=True,
        force_next_on_active=True,
    )
    bridge = LiveDataBridge(db_connection=None, amocrm=amo, use_local_files=False)
    text = await AutonomousCockpitEngine(bridge=bridge).build_evening_closing_card(now=now_local)

    assert "1 ta (10.0 mln soʻm)" in text
    assert "Qayta ishlangan lidlar (bugun):</b> nomaʼlum" in text
    assert "bugun yangi lid tushmadi" not in text
    assert "javob hodisalari oʻqilmadi" in text
    assert "Faol bitimlar soni:</b> nomaʼlum" in text
    assert "Muddati oʻtgan ochiq vazifalar:</b> 0 ta" in text


@pytest.mark.asyncio
async def test_evening_wrapup_db_fallback_verified_close_callbacks_and_mixed_timestamps(tmp_path):
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    # 08:00 Tashkent (03:00 UTC) -> reply at 09:15 Tashkent (04:15 UTC):
    # elapsed = 75m (>30m), business_minutes = 15m (<=30m)!
    t_08_00_utc = datetime(2026, 11, 28, 8, 0, tzinfo=TZ).astimezone(ZoneInfo("UTC"))
    t_09_15_utc = datetime(2026, 11, 28, 9, 15, tzinfo=TZ).astimezone(ZoneInfo("UTC"))
    t_11_00_utc = datetime(2026, 11, 28, 11, 0, tzinfo=TZ).astimezone(ZoneInfo("UTC"))
    three_days_ago_utc = t_11_00_utc - timedelta(days=3)

    dialer_db = tmp_path / "crm_dialer.db"
    with sqlite3.connect(dialer_db) as conn:
        conn.execute(
            "CREATE TABLE dialer_leads (id INTEGER PRIMARY KEY, pipeline_id INTEGER, name TEXT, "
            "status_slug TEXT, price REAL, responsible_user_id INTEGER, responsible_name TEXT, "
            "last_called_at TEXT, updated_at TEXT, is_active INTEGER)"
        )
        # 265 active sales deals + 3 HR active deals (HR must be excluded!)
        conn.executemany(
            "INSERT INTO dialer_leads VALUES (?, ?, ?, 'jarayonda', 10000000, 1, 'Sardor', NULL, ?, 1)",
            [(i, SALES_PIPELINE_ID, f"Faol Bitim {i}", three_days_ago_utc.strftime("%Y-%m-%d %H:%M:%S")) for i in range(1, 266)],
        )
        conn.executemany(
            "INSERT INTO dialer_leads VALUES (?, ?, 'HR Nomzod', 'jarayonda', 0, 1, 'HR', NULL, ?, 1)",
            [(800 + i, HR_PIPELINE_ID, three_days_ago_utc.strftime("%Y-%m-%d %H:%M:%S")) for i in range(3)],
        )

        # 901 won TODAY via dialer_call_logs transition; 902 won 3 days ago but edited today (must NOT count!)
        conn.execute(
            "INSERT INTO dialer_leads VALUES (901, ?, 'Bugungi Sotuv', 'sotuv', 12000000, 1, 'Sardor', NULL, ?, 0)",
            (SALES_PIPELINE_ID, t_11_00_utc.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.execute(
            "INSERT INTO dialer_leads VALUES (902, ?, 'Eski Sotuv Tahrirlangan', 'sotuv', 80000000, 1, 'Sardor', NULL, ?, 0)",
            (SALES_PIPELINE_ID, t_11_00_utc.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.execute(
            "CREATE TABLE dialer_call_logs (id INTEGER PRIMARY KEY, lead_id INTEGER, "
            "seller_name TEXT, old_status TEXT, new_status TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO dialer_call_logs VALUES (1, 901, 'Sardor', 'muzokara', 'sotuv', ?)",
            (t_11_00_utc.strftime("%Y-%m-%d %H:%M:%S"),),
        )
        conn.execute(
            "INSERT INTO dialer_call_logs VALUES (2, 902, 'Sardor', 'muzokara', 'sotuv', ?)",
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
        in_s = t_08_00_utc.strftime("%Y-%m-%d %H:%M:%S")
        out_s = t_09_15_utc.strftime("%Y-%m-%d %H:%M:%S")
        old_s = three_days_ago_utc.strftime("%Y-%m-%d %H:%M:%S")
        today_11_s = t_11_00_utc.strftime("%Y-%m-%d %H:%M:%S")

        # Thread 1: New today (08:00), replied at 09:15 -> 15 business mins (<=30m SLA!)
        conn.execute("INSERT INTO crm_chat_threads VALUES (1, 55, 'telegram', 'Mijoz 1', 0, 'Sardor', ?, ?)", (in_s, out_s))
        conn.execute("INSERT INTO crm_chat_messages VALUES (1, 1, 'in', 'Mijoz', 'Salom', ?)", (in_s,))
        conn.execute("INSERT INTO crm_chat_messages VALUES (2, 1, 'out', 'Sardor', 'Javob', ?)", (out_s,))

        # Thread 2: New today (11:00), unread_count=0 but NO reply -> SLA miss
        conn.execute("INSERT INTO crm_chat_threads VALUES (2, 56, 'instagram', 'Mijoz 2', 0, 'Sardor', ?, ?)", (today_11_s, today_11_s))
        conn.execute("INSERT INTO crm_chat_messages VALUES (3, 2, 'in', 'Mijoz2', 'Narx?', ?)", (today_11_s,))

        # Thread 3: Existing thread from 3 days ago with a follow-up reply TODAY -> counts in worked leads, NOT new-lead SLA!
        conn.execute("INSERT INTO crm_chat_threads VALUES (3, 57, 'telegram', 'Eski Mijoz', 0, 'Sardor', ?, ?)", (old_s, today_11_s))
        conn.execute("INSERT INTO crm_chat_messages VALUES (4, 3, 'in', 'Eski', 'Salom', ?)", (old_s,))
        conn.execute("INSERT INTO crm_chat_messages VALUES (5, 3, 'out', 'Sardor', 'Oldingi javob', ?)", (old_s,))
        conn.execute("INSERT INTO crm_chat_messages VALUES (6, 3, 'out', 'Sardor', 'Bugungi follow-up', ?)", (today_11_s,))

        # Thread 4: Seller-initiated outbound chat today (no inbound message) -> worked lead, NOT inbound SLA!
        conn.execute("INSERT INTO crm_chat_threads VALUES (4, 58, 'telegram', 'Sotuvchi Yozdi', 0, 'Sardor', ?, ?)", (today_11_s, today_11_s))
        conn.execute("INSERT INTO crm_chat_messages VALUES (7, 4, 'out', 'Sardor', 'Assalomu alaykum', ?)", (today_11_s,))

        # Tasks: 1 Tashkent-naive overdue today ("2026-11-28 15:00"), 1 completed overdue (ignored), 1 future (ignored)
        conn.execute(
            "CREATE TABLE crm_tasks (id INTEGER PRIMARY KEY, lead_id INTEGER, lead_name TEXT, "
            "contact_name TEXT, title TEXT, responsible_name TEXT, due_at TEXT, is_completed INTEGER)"
        )
        conn.execute("INSERT INTO crm_tasks VALUES (1, 55, 'B', 'M', 'Aloqa', 'Sardor', '2026-11-28 15:00', 0)")
        conn.execute("INSERT INTO crm_tasks VALUES (2, 56, 'B', 'M', 'Yopilgan', 'Sardor', '2026-11-27 10:00', 1)")
        conn.execute("INSERT INTO crm_tasks VALUES (3, 57, 'B', 'M', 'Ertaga', 'Sardor', '2026-11-29 10:00', 0)")

    bridge = LiveDataBridge(
        db_connection=None,
        amocrm=None,
        dialer_db_path=str(dialer_db),
        ad_spend_db_path=str(tmp_path / "no_spend.db"),
        attribution_db_path=str(tmp_path / "no_attr.db"),
        use_local_files=True,
    )
    bridge._resolve_conn = lambda: None  # type: ignore[method-assign]

    text = await AutonomousCockpitEngine(bridge=bridge).build_evening_closing_card(now=now_local)

    assert "1 ta (12.0 mln soʻm)" in text
    assert "80.0 mln" not in text
    assert "265 ta" in text
    assert "50.0% (1/2 ta ≤30 daq)" in text
    # Worked sales leads today: 901 (won), 55 (replied), 57 (follow-up today), 58 (outbound today) = 4
    assert "Qayta ishlangan lidlar (bugun):</b> 4 ta" in text
    assert "Muddati oʻtgan ochiq vazifalar:</b> 1 ta" in text
    assert "trijaj navbatiga biriktirildi" not in text


@pytest.mark.asyncio
async def test_evening_wrapup_db_only_tasks_marks_revenue_and_activity_unknown(tmp_path):
    now_local = datetime(2026, 11, 28, 19, 30, tzinfo=TZ)
    dialer_db = tmp_path / "tasks_only.db"
    with sqlite3.connect(dialer_db) as conn:
        conn.execute("CREATE TABLE crm_tasks (id INTEGER PRIMARY KEY, due_at TEXT, is_completed INTEGER)")
        conn.execute("INSERT INTO crm_tasks VALUES (1, '2026-11-28T12:00:00+05:00', 0)")

    bridge = LiveDataBridge(
        db_connection=None,
        amocrm=None,
        dialer_db_path=str(dialer_db),
        ad_spend_db_path=str(tmp_path / "missing2.db"),
        attribution_db_path=str(tmp_path / "missing3.db"),
        use_local_files=True,
    )
    bridge._resolve_conn = lambda: None  # type: ignore[method-assign]
    text = await AutonomousCockpitEngine(bridge=bridge).build_evening_closing_card(now=now_local)

    assert "Kunlik Tushum / Yopilgan Bitimlar:</b> nomaʼlum" in text
    assert "Qayta ishlangan lidlar (bugun):</b> nomaʼlum" in text
    assert "Kunlik SLA foizi:</b> nomaʼlum" in text
    assert "Faol bitimlar soni:</b> nomaʼlum" in text
    assert "Muddati oʻtgan ochiq vazifalar:</b> 1 ta" in text
