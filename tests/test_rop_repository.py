import pytest
from src.db import Database

@pytest.fixture
async def db(tmp_path):
    d = Database(db_path=str(tmp_path / "rop.db"))
    await d.rop.init_table()
    yield d
    await d.close()

@pytest.mark.asyncio
async def test_init_table_idempotent(db):
    await db.rop.init_table()  # second call must not raise

@pytest.mark.asyncio
async def test_upsert_and_list_targets(db):
    await db.rop.upsert_target(101, seller_name="Oydin", telegram_user_id=555)
    await db.rop.upsert_target(102, seller_name="Shahnoza", telegram_user_id=None, active=0)
    rows = await db.rop.list_active_targets()
    assert [r["responsible_user_id"] for r in rows] == [101]
    assert rows[0]["calls"] == 10
    assert rows[0]["telegram_user_id"] == 555

@pytest.mark.asyncio
async def test_upsert_updates_existing(db):
    await db.rop.upsert_target(101, seller_name="Oydin", telegram_user_id=555)
    await db.rop.upsert_target(101, seller_name="Oydin K", telegram_user_id=777, calls=15)
    rows = await db.rop.list_active_targets()
    assert len(rows) == 1
    assert rows[0]["seller_name"] == "Oydin K"
    assert rows[0]["calls"] == 15
    assert rows[0]["telegram_user_id"] == 777

@pytest.mark.asyncio
async def test_config_roundtrip_and_default(db):
    assert await db.rop.get_config("missing", {"a": 1}) == {"a": 1}
    await db.rop.set_config("score.band_cutoffs", {"hot": 70, "warm": 40})
    assert await db.rop.get_config("score.band_cutoffs") == {"hot": 70, "warm": 40}
    dump = await db.rop.all_config()
    assert dump["score.band_cutoffs"]["hot"] == 70
