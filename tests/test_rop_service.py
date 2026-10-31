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

@pytest.mark.asyncio
async def test_secondary_fetch_error_aborts_slot():
    class BoomTasks(FakeFetcher):
        async def fetch_open_tasks_for_leads(self, ids):
            raise RuntimeError("amocrm 500")
    leads = [{"id": 1, "name": "ABC", "status_id": 111, "price": 1_000_000,
              "responsible_user_id": 101, "updated_at": int(THU_630.timestamp()) - 100,
              "created_at": int(THU_630.timestamp()) - 3 * 86400}]
    svc = RopService(FakeRepo([_target(101, 555)]), BoomTasks(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    assert await svc.run("evening") == []

@pytest.mark.asyncio
async def test_service_integrates_call_stats():
    class FetcherWithCalls(FakeFetcher):
        async def fetch_today_calls(self, now):
            return {
                "s101": {
                    "total": 55,
                    "answered": 52,
                    "solid_calls": 50,
                    "talk_seconds": 18000,
                    "no_callback": 0,
                }
            }
    leads = [{"id": 1, "name": "ABC", "status_id": 111, "price": 1_000_000,
              "responsible_user_id": 101, "updated_at": int(THU_630.timestamp()) - 100,
              "created_at": int(THU_630.timestamp()) - 3 * 86400}]
    svc = RopService(FakeRepo([_target(101, 555)]), FetcherWithCalls(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("evening")
    assert any("50/50 ta" in text for _, text in plan if _ == 555)


@pytest.mark.asyncio
async def test_service_attributes_leads_by_seller_tag_on_shared_license():
    # Lead responsible_user_id is 13021974 (Shahnoza), but tag is "Rayxon" (amocrm_user_id=9000001)
    leads = [{
        "id": 99,
        "name": "Rayxon Mijozi",
        "status_id": 111,
        "price": 15_000_000,
        "responsible_user_id": 13021974,
        "updated_at": int(THU_630.timestamp()) - 100,
        "created_at": int(THU_630.timestamp()) - 2 * 86400,
        "_embedded": {"tags": [{"name": "Rayxon"}]},
    }]
    repo = FakeRepo([
        _target(13021974, 8802892610, seller_name="Shahnoza Abdijabborova"),
        _target(9000001, 8878762085, seller_name="Rayxona Rahimova"),
    ])
    svc = RopService(repo, FakeFetcher(leads), ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("morning")
    rayxona_dm = next(text for chat_id, text in plan if chat_id == 8878762085)
    assert "Rayxon Mijozi" in rayxona_dm
