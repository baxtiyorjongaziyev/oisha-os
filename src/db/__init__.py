"""Database package — refactored from monolithic database.py.

Usage:
    from src.db import Database
    db = Database()
    await db.init_db()
"""
from __future__ import annotations

import structlog
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from src.settings import settings
from src.db.connection import ConnectionManager
from src.db.repositories.users import UserRepository
from src.db.repositories.messages import MessageRepository
from src.db.repositories.kv import KVRepository
from src.db.repositories.crm import CRMRepository
from src.db.repositories.tasks import TaskRepository
from src.db.repositories.checkpoints import CheckpointRepository
from src.db.repositories.intelligence import IntelligenceRepository
from src.db.repositories.reports import ReportsRepository

logger = structlog.get_logger()

# Singleton
db: "Database | None" = None


def get_db() -> "Database":
    global db
    if db is None:
        db = Database()
    return db


class Database:
    """Main database facade — delegates to repositories for domain logic."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.getcwd(), "data", "bot.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn_manager = ConnectionManager(db_path)

        # Repositories
        self.users = UserRepository(self.conn_manager)
        self.messages = MessageRepository(self.conn_manager)
        self.kv = KVRepository(self.conn_manager)
        self.crm = CRMRepository(self.conn_manager)
        self.tasks = TaskRepository(self.conn_manager)
        self.checkpoints = CheckpointRepository(self.conn_manager)
        self.intelligence = IntelligenceRepository(self.conn_manager)
        self.reports = ReportsRepository(self.conn_manager)

        # Wire connection factory so monkeypatching db.get_connection works
        for repo in [
            self.users, self.messages, self.kv, self.crm,
            self.tasks, self.checkpoints, self.intelligence, self.reports,
        ]:
            repo.set_connection_factory(lambda: self.get_connection())

        logger.info("[DB] Database initialized: %s", self.db_path)

    # ─── Connection ───────────────────────────────────────────
    async def get_connection(self):
        return await self.conn_manager.get_connection()

    @asynccontextmanager
    async def get_conn(self):
        conn = await self.get_connection()
        yield conn

    async def close(self):
        await self.conn_manager.close()

    def get_backend_name(self) -> str:
        return self.conn_manager.get_backend_name()

    # ─── Initialization ───────────────────────────────────────
    async def init_db(self) -> None:
        try:
            from src.hisobchi_schema import init_hisobchi_tables
            conn = await self.get_connection()
            await init_hisobchi_tables(conn)
        except Exception as exc:
            logger.warning("[DB] Hisobchi tables init skipped: %s", exc)

        await self.users.init_table()
        await self.messages.init_tables()
        await self.kv.init_table()
        await self.crm.init_table()
        await self.tasks.init_table()
        await self.checkpoints.init_table()
        await self.intelligence.init_tables()
        await self.reports.init_tables()
        await self._init_legacy_tables()

        # Ensure owner exists
        try:
            from src import config
            if hasattr(config, "OWNER_ID") and config.OWNER_ID:
                await self.users.ensure_owner_admin(int(config.OWNER_ID))
        except Exception:
            pass

    async def _init_legacy_tables(self) -> None:
        conn = await self.get_connection()
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ambassador_journey_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, event_type TEXT, event_data TEXT, created_at DATETIME
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS juma_sent_logs (
                user_id INTEGER, run_date TEXT,
                PRIMARY KEY (user_id, run_date)
            )
        """)

    # ─── Backward-compatible delegates ────────────────────────
    async def init_instance(self) -> None:
        await self.init_db()

    async def ensure_owner_admin(self, owner_id: int) -> None:
        await self.users.ensure_owner_admin(owner_id)

    async def get_state(self, key: str, default: Any = None) -> Any:
        return await self.kv.get_state(key, default)

    async def set_state(self, key: str, value: Any) -> None:
        await self.kv.set_state(key, value)

    async def upsert_user(self, user_id: int, first_name: str = None, username: str = None, **kwargs) -> None:
        await self.users.upsert_user(user_id, first_name=first_name, username=username, **kwargs)

    async def log_message(self, user_id, text, is_ai=False) -> None:
        await self.messages.log_message(user_id, text, is_ai)

    async def log_messages_batch(self, messages_data: List[tuple]) -> None:
        await self.messages.log_messages_batch(messages_data)

    async def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        return await self.users.get_user_by_phone(phone)

    async def get_user_id_by_phone(self, phone: str) -> Optional[int]:
        return await self.users.get_user_id_by_phone(phone)

    async def get_chat_summary(self, user_id: int) -> Optional[str]:
        return await self.messages.get_chat_summary(user_id)

    async def set_chat_summary(self, user_id: int, summary: str) -> bool:
        return await self.messages.set_chat_summary(user_id, summary)

    async def get_recent_active_leads(self, hours: int = 72, limit: int = 12) -> List[Dict[str, Any]]:
        return await self.crm.get_recent_active_leads(hours, limit)

    async def get_recent_messages(self, user_id, limit=1000) -> List[Dict[str, Any]]:
        return await self.messages.get_recent_messages(user_id, limit)

    async def get_all_users(self) -> List[int]:
        return await self.users.get_all_user_ids()

    async def get_user_by_role(self, role: str) -> Optional[Dict[str, Any]]:
        return await self.users.get_user_by_role(role)

    async def get_team_roles(self) -> List[Dict[str, Any]]:
        return await self.users.get_team_roles()

    async def is_job_run(self, job_name, date_str) -> bool:
        return await self.reports.is_job_run(job_name, date_str)

    async def mark_job_run(self, job_name, date_str) -> None:
        await self.reports.mark_job_run(job_name, date_str)

    async def get_recent_job_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        return await self.reports.get_recent_job_runs(limit)

    async def get_storage_counts(self) -> Dict[str, int]:
        return await self.reports.get_storage_counts()

    async def get_recent_agent_actions(self, limit: int = 25) -> List[Dict[str, Any]]:
        return await self.reports.get_recent_agent_actions(limit)

    async def update_chat_checkpoint(self, chat_id: int, msg_id: int) -> None:
        await self.checkpoints.update_chat_checkpoint(chat_id, msg_id)

    async def get_recent_chat_checkpoints(self, since_days: int = 7) -> List[Dict[str, Any]]:
        return await self.checkpoints.get_recent_chat_checkpoints(since_days)

    async def get_checkpoint(self, external_id: Any, checkpoint_key: str) -> Optional[Dict[str, Any]]:
        return await self.checkpoints.get_checkpoint(external_id, checkpoint_key)

    async def mark_checkpoint_notified(self, external_id: Any, checkpoint_key: str, status: str = "Pending") -> None:
        await self.checkpoints.mark_checkpoint_notified(external_id, checkpoint_key, status)

    async def get_user_info(self, user_id) -> Optional[Dict[str, Any]]:
        return await self.users.get_user_info(user_id)

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return await self.users.get_user_by_username(username)

    async def get_daily_chats_summary(self) -> Dict[int, Dict[str, Any]]:
        return await self.messages.get_daily_chats_summary()

    async def get_recent_all_messages(self, limit=50) -> List[tuple]:
        return await self.messages.get_recent_all_messages(limit)

    async def get_stats(self) -> Dict[str, int]:
        return await self.messages.get_stats()

    async def get_today_stats(self) -> Dict[str, int]:
        return await self.messages.get_today_stats()

    async def is_crm_synced(self, user_id: int) -> bool:
        return await self.crm.is_crm_synced(user_id)

    async def mark_crm_synced(self, user_id: int) -> bool:
        return await self.crm.mark_crm_synced(user_id)

    async def log_agent_action(self, user_id, action_type, data, success=True) -> None:
        await self.reports.log_agent_action(user_id, action_type, data, success)

    async def save_daily_plan(self, manager_id, lead_id, lead_name, mission, source_pipeline="HUNTER") -> bool:
        return await self.reports.save_daily_plan(manager_id, lead_id, lead_name, mission, source_pipeline)

    async def save_team_report(self, user_id, report_type, content, report_date=None, status="submitted") -> bool:
        return await self.reports.save_team_report(user_id, report_type, content, report_date, status)

    async def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        return await self.tasks.get_overdue_tasks()

    async def update_lead_journey(self, user_id: int, *, stage, status, next_action, close_probability=0.0, lifecycle_updated_at=None) -> bool:
        return await self.users.update_lead_journey(
            user_id, stage=stage, status=status, next_action=next_action,
            close_probability=close_probability, lifecycle_updated_at=lifecycle_updated_at,
        )

    async def get_user_intelligence(self, user_id: int) -> Dict[str, Any]:
        return await self.intelligence.get_user_intelligence(user_id)

    async def upsert_user_intelligence(self, user_id: int, intel_data: Dict[str, Any]) -> bool:
        return await self.intelligence.upsert_user_intelligence(user_id, intel_data)

    async def get_latest_call_analysis(self, lead_id: int) -> Optional[Dict[str, Any]]:
        return await self.intelligence.get_latest_call_analysis(lead_id)

    def __iter__(self):
        return iter(())
