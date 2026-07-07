"""Uzbek Entrepreneurs Call Queue Manager - Manages call distribution and operator routing."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.database_pool import db_pool
from src.services.core.hisobchi_schema import ensure_hisobchi_db

logger = logging.getLogger(__name__)


@dataclass
class Operator:
    id: int
    name: str
    telegram_id: int
    phone: str
    is_active: bool
    current_call_id: Optional[int]
    total_calls_today: int
    last_call_time: Optional[str]


@dataclass
class QueuedCall:
    id: int
    entrepreneur_id: int
    entrepreneur_name: str
    entrepreneur_phone: str
    priority: int  # 1-10, higher = more urgent
    status: str  # 'queued', 'assigned', 'in_progress', 'completed', 'cancelled'
    assigned_operator_id: Optional[int]
    queued_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class CallQueueManager:
    """Manages call queue distribution to human operators."""

    def __init__(self, db=None):
        self._db = ensure_hisobchi_db(db if db is not None else db_pool)

    async def add_to_queue(
        self,
        entrepreneur_id: int,
        entrepreneur_name: str,
        entrepreneur_phone: str,
        priority: int = 5,
    ) -> Optional[int]:
        """Add entrepreneur to call queue."""
        try:
            result = await self._db.execute(
                """
                INSERT INTO entrepreneur_call_queue
                (entrepreneur_id, entrepreneur_name, entrepreneur_phone, priority, status, queued_at)
                VALUES (?, ?, ?, ?, 'queued', CURRENT_TIMESTAMP)
                """,
                [entrepreneur_id, entrepreneur_name, entrepreneur_phone, priority],
            )
            await self._db.commit()

            queue_id = result[0]["id"] if result else None
            logger.info(
                "[CALL_QUEUE] Added to queue: #%s (%s, priority: %s)",
                queue_id,
                entrepreneur_name,
                priority,
            )
            return queue_id

        except Exception as e:
            logger.error("[CALL_QUEUE] Failed to add to queue: %s", e)
            return None

    async def get_next_queued_call(self) -> Optional[QueuedCall]:
        """Get next call from queue (highest priority first)."""
        try:
            rows = await self._db.execute(
                """
                SELECT id, entrepreneur_id, entrepreneur_name, entrepreneur_phone,
                       priority, status, assigned_operator_id, queued_at, started_at, completed_at
                FROM entrepreneur_call_queue
                WHERE status = 'queued'
                ORDER BY priority DESC, queued_at ASC
                LIMIT 1
                """
            )

            if not rows:
                return None

            row = rows[0]
            return QueuedCall(
                id=row["id"],
                entrepreneur_id=row["entrepreneur_id"],
                entrepreneur_name=row["entrepreneur_name"],
                entrepreneur_phone=row["entrepreneur_phone"],
                priority=row["priority"],
                status=row["status"],
                assigned_operator_id=row["assigned_operator_id"],
                queued_at=row["queued_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )

        except Exception as e:
            logger.error("[CALL_QUEUE] Failed to get next call: %s", e)
            return None

    async def assign_to_operator(
        self, queue_id: int, operator_id: int
    ) -> bool:
        """Assign queued call to an operator."""
        try:
            await self._db.execute(
                """
                UPDATE entrepreneur_call_queue
                SET status = 'assigned',
                    assigned_operator_id = ?,
                    started_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [operator_id, queue_id],
            )
            await self._db.commit()

            logger.info(
                "[CALL_QUEUE] Assigned queue #%s to operator #%s", queue_id, operator_id
            )
            return True

        except Exception as e:
            logger.error("[CALL_QUEUE] Failed to assign: %s", e)
            return False

    async def mark_completed(
        self, queue_id: int, result: str, notes: Optional[str] = None
    ) -> bool:
        """Mark call as completed."""
        try:
            await self._db.execute(
                """
                UPDATE entrepreneur_call_queue
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [queue_id],
            )
            await self._db.commit()

            logger.info("[CALL_QUEUE] Completed queue #%s (result: %s)", queue_id, result)
            return True

        except Exception as e:
            logger.error("[CALL_QUEUE] Failed to mark completed: %s", e)
            return False

    async def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        try:
            rows = await self._db.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued,
                    SUM(CASE WHEN status = 'assigned' THEN 1 ELSE 0 END) as assigned,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM entrepreneur_call_queue
                """
            )

            if rows:
                return dict(rows[0])
            return {}

        except Exception as e:
            logger.error("[CALL_QUEUE] Failed to get stats: %s", e)
            return {}

    async def auto_assign_interested_calls(self) -> int:
        """Auto-assign calls where entrepreneur pressed '1' (interested)."""
        try:
            # Find entrepreneurs who pressed '1' but not assigned to operator
            rows = await self._db.execute(
                """
                SELECT e.id, e.full_name, e.phone, l.pressed_digit
                FROM uzbek_entrepreneurs e
                JOIN entrepreneur_call_logs l ON e.id = l.entrepreneur_id
                WHERE l.pressed_digit = '1'
                  AND e.call_status = 'interested'
                  AND NOT EXISTS (
                      SELECT 1 FROM entrepreneur_call_queue q
                      WHERE q.entrepreneur_id = e.id
                  )
                LIMIT 10
                """
            )

            assigned_count = 0
            for row in rows:
                queue_id = await self.add_to_queue(
                    entrepreneur_id=row["id"],
                    entrepreneur_name=row["full_name"],
                    entrepreneur_phone=row["phone"],
                    priority=10,  # High priority for interested leads
                )
                if queue_id:
                    assigned_count += 1

            logger.info(
                "[CALL_QUEUE] Auto-assigned %s interested calls to queue", assigned_count
            )
            return assigned_count

        except Exception as e:
            logger.error("[CALL_QUEUE] Auto-assign failed: %s", e)
            return 0

    async def notify_operator(self, operator_id: int, call: QueuedCall) -> bool:
        """Send notification to operator via Telegram."""
        try:
            # TODO: Implement Telegram notification
            # This would send a message to the operator's Telegram with call details
            logger.info(
                "[CALL_QUEUE] Notified operator #%s about call: %s",
                operator_id,
                call.entrepreneur_name,
            )
            return True

        except Exception as e:
            logger.error("[CALL_QUEUE] Notification failed: %s", e)
            return False

    async def run_assignment_loop(self, interval_seconds: int = 30) -> None:
        """Continuous loop to auto-assign calls to available operators."""
        logger.info("[CALL_QUEUE] Starting assignment loop (interval: %s sec)", interval_seconds)

        while True:
            try:
                # Auto-assign interested calls
                await self.auto_assign_interested_calls()

                # Get next queued call
                call = await self.get_next_queued_call()
                if call:
                    # Find available operator
                    operator = await self._get_available_operator()
                    if operator:
                        await self.assign_to_operator(call.id, operator.id)
                        await self.notify_operator(operator.id, call)

                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error("[CALL_QUEUE] Assignment loop error: %s", e)
                await asyncio.sleep(interval_seconds)

    async def _get_available_operator(self) -> Optional[Operator]:
        """Get next available operator."""
        try:
            rows = await self._db.execute(
                """
                SELECT id, name, telegram_id, phone, is_active, current_call_id,
                       total_calls_today, last_call_time
                FROM call_operators
                WHERE is_active = 1 AND current_call_id IS NULL
                ORDER BY total_calls_today ASC, last_call_time ASC
                LIMIT 1
                """
            )

            if rows:
                row = rows[0]
                return Operator(
                    id=row["id"],
                    name=row["name"],
                    telegram_id=row["telegram_id"],
                    phone=row["phone"],
                    is_active=row["is_active"],
                    current_call_id=row["current_call_id"],
                    total_calls_today=row["total_calls_today"],
                    last_call_time=row["last_call_time"],
                )
            return None

        except Exception as e:
            logger.error("[CALL_QUEUE] Failed to get operator: %s", e)
            return None


# Queue table needs to be added to schema
_QUEUE_TABLE = """
CREATE TABLE IF NOT EXISTS entrepreneur_call_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entrepreneur_id INTEGER NOT NULL,
    entrepreneur_name TEXT NOT NULL,
    entrepreneur_phone TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    status TEXT DEFAULT 'queued',
    assigned_operator_id INTEGER,
    queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (entrepreneur_id) REFERENCES uzbek_entrepreneurs(id),
    FOREIGN KEY (assigned_operator_id) REFERENCES call_operators(id)
)
"""

_OPERATORS_TABLE = """
CREATE TABLE IF NOT EXISTS call_operators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    telegram_id INTEGER UNIQUE NOT NULL,
    phone TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    current_call_id INTEGER,
    total_calls_today INTEGER DEFAULT 0,
    last_call_time TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


async def init_call_queue_tables(db=None) -> None:
    """Initialize call queue tables."""
    from src.database_pool import db_pool
    from src.services.core.hisobchi_schema import ensure_hisobchi_db

    _db = ensure_hisobchi_db(db if db is not None else db_pool)

    for ddl in [_QUEUE_TABLE, _OPERATORS_TABLE]:
        await _db.execute(ddl)

    await _db.commit()
    logger.info("[CALL_QUEUE] Tables initialized")
