"""Repository for gamification and Oisha Coins."""
from __future__ import annotations
import structlog
import datetime

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()

class GamificationRepository(BaseRepository):
    """Repository for Oisha Coins and gamification."""

    async def init_table(self) -> None:
        """Create gamification tables."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS user_coins (
                user_id INTEGER PRIMARY KEY,
                total_coins INTEGER DEFAULT 0,
                updated_at DATETIME
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS coin_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                task_id INTEGER,
                created_at DATETIME
            )
        """)
        await self._execute("CREATE INDEX IF NOT EXISTS idx_coin_txn_user ON coin_transactions(user_id)")

    async def add_coins(self, user_id: int, amount: int, reason: str, task_id: int = None) -> int:
        """Add or deduct coins for a user and log transaction."""
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        
        # Upsert user_coins
        await conn.execute("""
            INSERT INTO user_coins (user_id, total_coins, updated_at) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
                total_coins = total_coins + ?,
                updated_at = ?
        """, (user_id, amount, now, amount, now))
        
        # Log transaction
        await conn.execute("""
            INSERT INTO coin_transactions (user_id, amount, reason, task_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, amount, reason, task_id, now))
        
        await conn.commit()
        
        # Return new total
        async with conn.execute("SELECT total_coins FROM user_coins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_user_coins(self, user_id: int) -> int:
        """Get current coin balance for a user."""
        conn = await self._get_conn()
        async with conn.execute("SELECT total_coins FROM user_coins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
