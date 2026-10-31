import pytest
from src.services.core.rop.targets import (
    SellerTarget,
    ensure_ssot_roster,
    load_roster,
    seed_default,
)


class FakeRepo:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.upserts = []

    async def list_active_targets(self):
        return [dict(r) for r in self.rows if r.get("active", 1)]

    async def upsert_target(self, uid, **kw):
        self.upserts.append((uid, kw))
        row = {"responsible_user_id": uid, **kw}
        self.rows.append(row)


@pytest.mark.asyncio
async def test_load_roster_maps_rows():
    repo = FakeRepo([{
        "responsible_user_id": 101, "seller_name": "Oydin", "telegram_user_id": 555,
        "expected_sales": 1, "calls": 10, "follow_ups": 20, "meetings": 2,
        "proposals": 0, "payments": 1, "max_overdue": 0, "active": 1,
        "updated_at": "x",
    }])
    roster = await load_roster(repo)
    assert roster == [SellerTarget(101, "Oydin", 555, 1, 10, 20, 2, 0, 1, 0)]


@pytest.mark.asyncio
async def test_load_roster_empty():
    assert await load_roster(FakeRepo([])) == []


@pytest.mark.asyncio
async def test_seed_default_uses_brief_defaults():
    repo = FakeRepo()
    await seed_default(repo, 101, 555, "Oydin")
    uid, kw = repo.upserts[0]
    assert uid == 101
    assert kw["calls"] == 10 and kw["follow_ups"] == 20 and kw["meetings"] == 2
    assert kw["expected_sales"] == 1 and kw["max_overdue"] == 0
    assert kw["telegram_user_id"] == 555 and kw["seller_name"] == "Oydin"


@pytest.mark.asyncio
async def test_ensure_ssot_roster_seeds_active_sellers_with_50_20_10_3_1():
    repo = FakeRepo()
    roster = await ensure_ssot_roster(repo)
    names = {s.seller_name for s in roster}
    assert "Shahnoza Abdijabborova" in names
    assert "Rayxona Rahimova" in names
    assert "Mumtozmaxal Normurodova" in names
    for s in roster:
        assert s.calls == 50
        assert s.follow_ups == 20
        assert s.proposals == 10
        assert s.meetings == 3
        assert s.expected_sales == 1
