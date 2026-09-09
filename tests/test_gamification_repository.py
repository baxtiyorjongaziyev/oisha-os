import pytest

from src.db import Database


@pytest.mark.asyncio
async def test_database_initializes_and_exposes_gamification(tmp_path):
    db = Database(str(tmp_path / "coins.db"))
    try:
        await db.init_db()
        assert await db.gamification.get_user_coins(42) == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_coin_update_and_ledger_are_committed_together(tmp_path):
    db = Database(str(tmp_path / "coins.db"))
    try:
        await db.init_db()
        assert await db.gamification.add_coins(42, 10, "task completed", 7) == 10
        assert await db.gamification.add_coins(42, -3, "penalty") == 7

        conn = await db.get_connection()
        cursor = await conn.execute(
            "SELECT amount, reason FROM coin_transactions WHERE user_id = ? ORDER BY id",
            (42,),
        )
        assert await cursor.fetchall() == [(10, "task completed"), (-3, "penalty")]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_empty_reason_cannot_change_balance(tmp_path):
    db = Database(str(tmp_path / "coins.db"))
    try:
        await db.init_db()
        with pytest.raises(ValueError, match="reason"):
            await db.gamification.add_coins(42, 10, "  ")
        assert await db.gamification.get_user_coins(42) == 0
    finally:
        await db.close()
