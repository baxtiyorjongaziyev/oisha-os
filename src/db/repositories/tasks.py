"""Task repository for task-related database operations."""
from __future__ import annotations

import datetime
import structlog
from typing import Any, Dict, List

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class TaskRepository(BaseRepository):
    """Repository for task operations."""

    async def init_table(self) -> None:
        """Create tasks table."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                assigned_to INTEGER,
                deadline DATETIME,
                priority TEXT DEFAULT 'Medium',
                status TEXT DEFAULT 'Pending',
                profit_estimate INTEGER DEFAULT 0,
                source_manager TEXT DEFAULT 'oisha',
                external_task_id TEXT,
                is_frog BOOLEAN DEFAULT FALSE,
                created_by INTEGER,
                created_at DATETIME,
                completed_at DATETIME
            )
        """)
        await self._execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")

    async def get_task_count(self) -> int:
        """Return total number of tasks in the database."""
        conn = await self._get_conn()
        async with conn.execute("SELECT COUNT(*) FROM tasks") as cursor:
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Get all overdue tasks."""
        from src.time_utils import get_local_now

        conn = await self._get_conn()
        async with conn.execute(
            """SELECT t.id, t.title, t.description, t.assigned_to, t.deadline,
               t.priority, t.status, u.first_name, u.username
               FROM tasks t LEFT JOIN users u ON u.user_id = t.assigned_to
               WHERE t.deadline IS NOT NULL
               AND COALESCE(t.status, 'Pending') NOT IN ('Done', 'Completed', 'Closed', 'Cancelled')"""
        ) as cursor:
            rows = await cursor.fetchall()
        now = get_local_now()
        overdue = []
        for row in rows:
            try:
                deadline_dt = datetime.datetime.fromisoformat(
                    str(row[4]).replace("Z", "+00:00")
                )
            except ValueError:
                continue
            now_cmp = (
                now.replace(tzinfo=None)
                if deadline_dt.tzinfo is None
                else now.astimezone(datetime.timezone.utc)
            )
            if deadline_dt < now_cmp:
                overdue.append(
                    {
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "assigned_to": row[3],
                        "deadline": row[4],
                        "priority": row[5] or "Medium",
                        "status": row[6] or "Pending",
                        "name": row[7] or f"User_{row[3]}",
                        "username": row[8],
                    }
                )
        overdue.sort(key=lambda t: (t["priority"] != "High", t["deadline"]))
        return overdue

    async def save_daily_plan(
        self,
        manager_id: int,
        lead_id: int,
        lead_name: str,
        mission: str,
        source_pipeline: str = "HUNTER",
    ) -> bool:
        """Save a daily plan for a manager."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            "INSERT INTO daily_plans (report_date, manager_id, lead_id, lead_name, mission, source_pipeline, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (today, manager_id, lead_id, lead_name, mission, source_pipeline, now),
        )
        await conn.commit()
        return True
