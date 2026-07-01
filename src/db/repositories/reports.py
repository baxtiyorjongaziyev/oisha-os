"""Reports repository for team reports, jobs, and agent actions."""
from __future__ import annotations

import json
import structlog
from typing import Any, Dict, List, Optional

from src.db.repositories.base import BaseRepository

logger = structlog.get_logger()


class ReportsRepository(BaseRepository):
    """Repository for reports, jobs, and agent actions."""

    async def init_tables(self) -> None:
        """Create report-related tables."""
        await self._execute("""
            CREATE TABLE IF NOT EXISTS team_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                report_date TEXT,
                report_type TEXT,
                content TEXT,
                status TEXT DEFAULT 'submitted',
                created_at DATETIME
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                job_name TEXT,
                run_date TEXT,
                created_at DATETIME,
                PRIMARY KEY (job_name, run_date)
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS agent_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT,
                action_data TEXT,
                success BOOLEAN DEFAULT 1,
                created_at DATETIME
            )
        """)
        await self._execute("""
            CREATE TABLE IF NOT EXISTS daily_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT,
                manager_id INTEGER,
                lead_id INTEGER,
                lead_name TEXT,
                mission TEXT,
                source_pipeline TEXT,
                created_at DATETIME
            )
        """)

        # Indexes
        await self._execute("CREATE INDEX IF NOT EXISTS idx_agent_actions_user_id ON agent_actions(user_id)")
        await self._execute("CREATE INDEX IF NOT EXISTS idx_daily_plans_manager ON daily_plans(manager_id)")

    async def is_job_run(self, job_name: str, date_str: str) -> bool:
        """Check if a job has already run today."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT 1 FROM scheduled_jobs WHERE job_name = ? AND run_date = ?",
            (job_name, date_str),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_job_run(self, job_name: str, date_str: str) -> None:
        """Mark a job as run."""
        import datetime
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            "INSERT OR REPLACE INTO scheduled_jobs (job_name, run_date, created_at) VALUES (?, ?, ?)",
            (job_name, date_str, now),
        )
        await conn.commit()

    async def get_recent_job_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent job runs."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT job_name, run_date, created_at FROM scheduled_jobs "
            "ORDER BY created_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "job_name": row[0],
                "run_date": row[1],
                "created_at": row[2],
            }
            for row in rows
        ]

    async def get_storage_counts(self) -> Dict[str, int]:
        """Get row counts for dashboard."""
        conn = await self._get_conn()
        query = """
            SELECT
                (SELECT COUNT(*) FROM scheduled_jobs) AS scheduled_jobs,
                (SELECT COUNT(*) FROM kv_settings) AS kv_settings,
                (SELECT COUNT(*) FROM agent_actions) AS agent_actions,
                (SELECT COUNT(*) FROM users) AS users,
                (SELECT COUNT(*) FROM call_analyses) AS call_analyses
        """
        async with conn.execute(query) as cursor:
            row = await cursor.fetchone()

        if row:
            return {
                "scheduled_jobs": int(row[0]),
                "kv_settings": int(row[1]),
                "agent_actions": int(row[2]),
                "users": int(row[3]),
                "call_analyses": int(row[4]),
            }
        return {
            "scheduled_jobs": 0,
            "kv_settings": 0,
            "agent_actions": 0,
            "users": 0,
            "call_analyses": 0,
        }

    async def get_recent_agent_actions(
        self, limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Get recent agent actions."""
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT id, user_id, action_type, action_data, success, created_at "
            "FROM agent_actions ORDER BY created_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ) as cursor:
            rows = await cursor.fetchall()

        actions = []
        for row in rows:
            try:
                action_data = json.loads(row[3]) if row[3] else {}
            except (TypeError, ValueError):
                action_data = row[3]
            actions.append(
                {
                    "id": row[0],
                    "user_id": row[1],
                    "action_type": row[2],
                    "action_data": action_data,
                    "success": bool(row[4]),
                    "created_at": row[5],
                }
            )
        return actions

    async def log_agent_action(
        self, user_id: int, action_type: str, data: Any, success: bool = True
    ) -> None:
        """Log an agent action."""
        import datetime
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            "INSERT INTO agent_actions (user_id, action_type, action_data, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action_type, json.dumps(data), success, now),
        )
        await conn.commit()

    async def save_team_report(
        self,
        user_id: int,
        report_type: str,
        content: str,
        report_date: Optional[str] = None,
        status: str = "submitted",
    ) -> bool:
        """Save or update a team report."""
        from src.time_utils import get_local_now

        now = get_local_now()
        report_day = report_date or now.strftime("%Y-%m-%d")
        conn = await self._get_conn()
        async with conn.execute(
            "SELECT id FROM team_reports WHERE user_id = ? AND report_date = ? AND report_type = ? ORDER BY id DESC LIMIT 1",
            (user_id, report_day, report_type),
        ) as cursor:
            existing = await cursor.fetchone()
        if existing:
            await conn.execute(
                "UPDATE team_reports SET content = ?, status = ?, created_at = ? WHERE id = ?",
                (content, status, now.isoformat(), existing[0]),
            )
        else:
            await conn.execute(
                "INSERT INTO team_reports (user_id, report_date, report_type, content, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, report_day, report_type, content, status, now.isoformat()),
            )
        await conn.commit()
        return True

    async def save_daily_plan(
        self,
        manager_id: int,
        lead_id: int,
        lead_name: str,
        mission: str,
        source_pipeline: str = "HUNTER",
    ) -> bool:
        """Save a daily plan."""
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        now = datetime.datetime.now().isoformat()
        conn = await self._get_conn()
        await conn.execute(
            "INSERT INTO daily_plans (report_date, manager_id, lead_id, lead_name, mission, source_pipeline, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (today, manager_id, lead_id, lead_name, mission, source_pipeline, now),
        )
        await conn.commit()
        return True
