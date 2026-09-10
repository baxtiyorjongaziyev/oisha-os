# tests/test_rop_service.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from src.services.core.rop.service import RopService

TZ = ZoneInfo("Asia/Tashkent")
MON_9AM = datetime(2026, 9, 7, 9, 0, tzinfo=TZ)   # Monday
THU_630 = datetime(2026, 9, 10, 18, 30, tzinfo=TZ)


class FakeRepo:
    def __init__(self, targets):
        self._targets = targets
        self.cfg = {}
    async def all_config(self): return dict(self.cfg)
    async def set_config(self, k, v): self.cfg[k] = v
    async def get_config(self, k, d=None): return self.cfg.get(k, d)
    async def list_active_targets(self): return [dict(t) for t in self._targets]


def _target(uid, tg, **over):
    t = {"responsible_user_id": uid, "seller_name": f"S{uid}", "telegram_user_id": tg,
         "expected_sales": 1, "calls": 10, "follow_ups": 20, "meetings": 2,
         "proposals": 0, "payments": 1, "max_overdue": 0, "active": 1, "updated_at": "x"}
    t.update(over)
    return t


class FakeFetcher:
    def __init__(self, leads):
        self._leads = leads
        self.raised = False
    async def fetch_active_sales_leads(self): return list(self._leads)
    async def fetch_open_tasks_for_leads(self, ids): return {}
    async def fetch_today_completed_tasks(self, uids, now=None): return {}, {}
    async def fetch_today_events(self, ids, now=None): return {}
    async def fetch_notes_for_leads(self, ids): return {}
    async def fetch_recent_events(self, ids, since): return {}
    async def fetch_won_leads_since(self, since): return []


@pytest.mark.asyncio
async def test_empty_roster_returns_ceo_notice():
    svc = RopService(FakeRepo([]), FakeFetcher([]), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("evening")
    assert plan == [(42, "ROP: hech qanday sotuvchi sozlanmagan.")]

@pytest.mark.asyncio
async def test_empty_roster_no_ceo_returns_empty():
    svc = RopService(FakeRepo([]), FakeFetcher([]), ceo_chat_id=None, now_fn=lambda: THU_630)
    assert await svc.run("evening") == []

@pytest.mark.asyncio
async def test_morning_sends_seller_dm_and_ceo():
    leads = [{"id": 1, "name": "ABC", "status_id": 111, "price": 5_000_000,
              "responsible_user_id": 101, "updated_at": int(THU_630.timestamp()) - 100,
              "created_at": int(THU_630.timestamp()) - 5 * 86400}]
    repo = FakeRepo([_target(101, 555)])
    svc = RopService(repo, FakeFetcher(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("morning")
    chat_ids = [c for c, _ in plan]
    assert 555 in chat_ids and 42 in chat_ids
    # snapshot written
    assert any(k.startswith("snapshot.2026-09-10") for k in repo.cfg)

@pytest.mark.asyncio
async def test_midday_suppresses_on_track_seller():
    leads = [{"id": 1, "name": "ABC", "status_id": 111, "price": 1_000_000,
              "responsible_user_id": 101, "updated_at": int(THU_630.timestamp()) - 100,
              "created_at": int(THU_630.timestamp()) - 3 * 86400}]
    repo = FakeRepo([_target(101, 555, calls=0, follow_ups=0, meetings=0)])
    # COLD lead + zero targets pressure: seller on track -> no seller DM
    svc = RopService(repo, FakeFetcher(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("midday")
    assert 555 not in [c for c, _ in plan]

@pytest.mark.asyncio
async def test_fetch_error_aborts_slot():
    class Boom(FakeFetcher):
        async def fetch_active_sales_leads(self):
            from src.services.core.rop.fetchers import RopFetchError
            raise RopFetchError("boom")
    svc = RopService(FakeRepo([_target(101, 555)]), Boom([]), ceo_chat_id=42, now_fn=lambda: THU_630)
    assert await svc.run("evening") == []
