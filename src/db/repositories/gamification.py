"""Repository for gamification and Oisha Coins."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.db.repositories.base import BaseRepository


class GamificationRepository(BaseRepository):
    """Repository for Oisha Coins and gamification."""

    async def init_table(self) -> None:
        """Create gamification tables."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS user_coins (
                user_id INTEGER PRIMARY KEY,
                total_coins INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS coin_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                task_id INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        await self._execute(
            "CREATE INDEX IF NOT EXISTS idx_coin_txn_user ON coin_transactions(user_id)"
        )

    async def add_coins(
        self,
        user_id: int,
        amount: int,
        reason: str,
        task_id: Optional[int] = None,
    ) -> int:
        """Add or deduct coins for a user and log the transaction atomically.

        The balance upsert and the journal row are wrapped in a SAVEPOINT so a
        failure can never leave the balance and the transaction log out of sync.
        """
        if not reason.strip():
            raise ValueError("reason is required")
        now = datetime.now(timezone.utc).isoformat()
        conn = await self._get_conn()
        try:
            # SAVEPOINT is safe both inside and outside an existing transaction.
            await conn.execute("SAVEPOINT gamification_add")
            await conn.execute(
                """
                INSERT INTO user_coins (user_id, total_coins, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_coins = user_coins.total_coins + excluded.total_coins,
                    updated_at = excluded.updated_at
                """,
                (user_id, amount, now),
            )
            await conn.execute(
                """
                INSERT INTO coin_transactions (user_id, amount, reason, task_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, amount, reason.strip(), task_id, now),
            )
            await conn.execute("RELEASE SAVEPOINT gamification_add")
        except Exception:
            await conn.execute("ROLLBACK TO SAVEPOINT gamification_add")
            await conn.execute("RELEASE SAVEPOINT gamification_add")
            raise
        await conn.commit()
        return await self.get_user_coins(user_id)

    async def get_user_coins(self, user_id: int) -> int:
        """Get current coin balance for a user."""
        row = await self._fetch_one(
            "SELECT total_coins FROM user_coins WHERE user_id = ?", (user_id,)
        )
        if row is None:
            return 0
        if isinstance(row, dict):
            return int(row["total_coins"])
        return int(row[0])
