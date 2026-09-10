import pytest
from src.services.core.rop.config import DEFAULTS, load_config, seed_config


class FakeRepo:
    def __init__(self, stored=None):
        self.stored = dict(stored or {})
    async def all_config(self):
        return dict(self.stored)
    async def set_config(self, k, v):
        self.stored[k] = v


@pytest.mark.asyncio
async def test_load_config_fills_all_defaults():
    cfg = await load_config(FakeRepo())
    for key in DEFAULTS:
        assert key in cfg
    assert cfg["score.band_cutoffs"] == {"hot": 70, "warm": 40}
    assert cfg["weekly.sales_target"] == 10
    assert cfg["traffic.red_no_result_days"] == 3

@pytest.mark.asyncio
async def test_stored_value_overrides_default():
    repo = FakeRepo({"weekly.sales_target": 15})
    cfg = await load_config(repo)
    assert cfg["weekly.sales_target"] == 15
    assert cfg["weekly.revenue_target"] == DEFAULTS["weekly.revenue_target"]

@pytest.mark.asyncio
async def test_seed_config_writes_only_missing():
    repo = FakeRepo({"weekly.sales_target": 15})
    await seed_config(repo)
    assert repo.stored["weekly.sales_target"] == 15          # untouched
    assert repo.stored["traffic.red_overdue_count"] == 5      # seeded
    assert set(repo.stored) == set(DEFAULTS)
