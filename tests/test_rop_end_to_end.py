# tests/test_rop_end_to_end.py
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from src.db import Database
from src.services.core.rop.service import RopService
from src.services.core.rop.targets import seed_default

TZ = ZoneInfo("Asia/Tashkent")
THU_630 = datetime(2026, 9, 10, 18, 30, tzinfo=TZ)
E = int(THU_630.timestamp())


class FakeFetcher:
    def __init__(self, leads, completed_by_user, won_today):
        self._leads = leads
        self._cbu = completed_by_user
        self._won = won_today
    async def fetch_active_sales_leads(self): return list(self._leads)
    async def fetch_open_tasks_for_leads(self, ids): return {}
    async def fetch_today_completed_tasks(self, uids, now=None):
        by_entity = {}
        return by_entity, {u: list(v) for u, v in self._cbu.items()}
    async def fetch_today_events(self, ids, now=None): return {}
    async def fetch_notes_for_leads(self, ids): return {}
    async def fetch_recent_events(self, ids, since): return {}
    async def fetch_won_leads_since(self, since): return list(self._won)


@pytest.fixture
async def db(tmp_path):
    d = Database(db_path=str(tmp_path / "e2e.db"))
    await d.rop.init_table()
    yield d
    await d.close()

@pytest.mark.asyncio
async def test_evening_run_produces_seller_and_ceo_messages(db):
    await seed_default(db.rop, 101, 555, "Oydin")
    await seed_default(db.rop, 102, 556, "Shahnoza")
    leads = [
        {"id": 1, "name": "ABC", "status_id": 111, "price": 12_000_000,
         "responsible_user_id": 101, "updated_at": E - 3600, "created_at": E - 4 * 86400},
        {"id": 2, "name": "XYZ", "status_id": 111, "price": 6_000_000,
         "responsible_user_id": 102, "updated_at": E - 200 * 3600, "created_at": E - 30 * 86400},
    ]
    completed = {101: [{"task_type_id": 1, "is_completed": True} for _ in range(9)]}
    won_today = [{"responsible_user_id": 101, "status_id": 142, "price": 12_000_000}]
    svc = RopService(db.rop, FakeFetcher(leads, completed, won_today),
                     ceo_chat_id=42, now_fn=lambda: THU_630)
    plan = await svc.run("evening")
    chat_ids = {c for c, _ in plan}
    assert 555 in chat_ids and 556 in chat_ids and 42 in chat_ids
    ceo_msg = next(t for c, t in plan if c == 42)
    assert "Sales Department" in ceo_msg
    assert "Haftalik" in ceo_msg
