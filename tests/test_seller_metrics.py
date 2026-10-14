"""Sotuvchi metrikalari: ish soatidagi javob vaqti, birinchi harakat, yopish foizi."""
from __future__ import annotations

import asyncio
import datetime as dt

from src.services.core.marketing import attribution_store, attribution_sync, seller_metrics as sm

TZ = sm.TZ


def _ts(y, m, d, h, mi=0):
    return int(dt.datetime(y, m, d, h, mi, tzinfo=TZ).timestamp())


def test_business_minutes_skips_night_and_sunday():
    # Shanba 18:30 -> Dushanba 09:30: 30 daq (Sha) + 0 (Yak) + 30 daq (Du)
    start = dt.datetime(2026, 10, 10, 18, 30, tzinfo=TZ)
    end = dt.datetime(2026, 10, 12, 9, 30, tzinfo=TZ)
    assert sm.business_minutes(start, end) == 60


def test_first_touch_ignores_robot_and_old_events():
    created = _ts(2026, 10, 12, 10)
    events = [
        {"type": "lead_status_changed", "created_by": 0, "created_at": created + 10},   # robot
        {"type": "outgoing_call", "created_by": 5, "created_at": created - 100},        # oldin
        {"type": "outgoing_call", "created_by": 5, "created_at": created + 600},
        {"type": "incoming_call", "created_by": 5, "created_at": created + 60},         # kiruvchi
    ]
    assert sm.first_touch_ts(created, events) == created + 600


def test_aggregate_counts_untouched_until_now():
    created = _ts(2026, 10, 12, 10)
    rows = [
        {"responsible_user_id": 1, "lead_created_ts": created, "first_touch_ts": created + 300, "lead_won": 1},
        {"responsible_user_id": 1, "lead_created_ts": created, "first_touch_ts": None, "lead_won": 0},
    ]
    now = dt.datetime(2026, 10, 12, 11, 0, tzinfo=TZ)
    [s] = sm.aggregate(rows, now=now)
    assert s["leads"] == 2 and s["untouched"] == 1
    assert s["median_response_min"] == 32.5  # median(5, 60)
    assert s["close_rate"] == 50.0
    text = "\n".join(sm.format_lines([s], {1: "Rayxon"}, 7))
    assert "Rayxon" in text and "1 ta javobsiz" in text


class _FakeResp:
    status_code = 200

    def __init__(self, events):
        self._events = events

    def json(self):
        return {"_embedded": {"events": self._events}}


class _FakeAmo:
    base_url = "https://x.amocrm.ru"

    def __init__(self, events):
        self.events, self.calls = events, 0

    async def _request_with_auth(self, fn, url, **kw):
        self.calls += 1
        return _FakeResp(self.events)

    def get_user_name(self, uid):
        return "Rayxon"


def test_sync_seller_info_writes_once(monkeypatch, tmp_path):
    monkeypatch.setattr(attribution_store, "_DB_PATH", tmp_path / "a.db")
    created = int(dt.datetime.now(TZ).timestamp()) - 3600
    attribution_store.save_attribution("g1", 10, "c1", "C", "", "", "2026-10-12T10:00:00")
    amo = _FakeAmo([{"type": "outgoing_call", "created_by": 7, "created_at": created + 120}])
    lead = {"responsible_user_id": 7, "created_at": created}
    names: dict = {}
    asyncio.run(attribution_sync._sync_seller_info(amo, "g1", 10, lead, names))
    asyncio.run(attribution_sync._sync_seller_info(amo, "g1", 10, lead, names))
    assert amo.calls == 1  # birinchi javob topilgach qayta so'ralmaydi
    [row] = attribution_store.seller_rows("2026-10-01", "2026-10-31")
    assert row["responsible_name"] == "Rayxon" and row["first_touch_ts"] == created + 120
