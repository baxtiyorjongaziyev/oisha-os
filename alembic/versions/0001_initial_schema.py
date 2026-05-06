"""Initial schema — baseline for all existing tables.

Revision ID: 0001
Revises: None
Create Date: 2026-05-06
"""
from __future__ import annotations

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            role TEXT DEFAULT 'client',
            amo_lead_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            is_ai BOOLEAN,
            created_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS message_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_text TEXT,
            is_ai_reply BOOLEAN,
            created_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            assigned_to INTEGER,
            deadline DATETIME,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending',
            created_by INTEGER,
            created_at DATETIME,
            completed_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS advisor_logs (
            chat_id INTEGER,
            message_id INTEGER,
            advice_type TEXT,
            content TEXT,
            created_at DATETIME,
            PRIMARY KEY (chat_id, message_id, advice_type)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm_sync_status (
            user_id INTEGER PRIMARY KEY,
            amo_lead_id INTEGER,
            status TEXT DEFAULT 'synced',
            synced_at DATETIME
        )
    """)
    op.execute("""
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
    op.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            job_name TEXT,
            run_date TEXT,
            created_at DATETIME,
            PRIMARY KEY (job_name, run_date)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS kv_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action_type TEXT,
            action_data TEXT,
            success BOOLEAN DEFAULT 1,
            created_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learned_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_key TEXT,
            fact_value TEXT,
            user_id INTEGER,
            created_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS call_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT UNIQUE,
            lead_id INTEGER,
            manager_id INTEGER,
            manager_name TEXT,
            client_name TEXT,
            duration_seconds INTEGER DEFAULT 0,
            overall_score INTEGER DEFAULT 0,
            category TEXT DEFAULT 'unknown',
            scores TEXT DEFAULT '[]',
            summary TEXT DEFAULT '',
            strengths TEXT DEFAULT '[]',
            weaknesses TEXT DEFAULT '[]',
            client_mood TEXT DEFAULT 'neutral',
            client_interest_level INTEGER DEFAULT 0,
            objections TEXT DEFAULT '[]',
            outcome TEXT DEFAULT 'unknown',
            next_steps TEXT DEFAULT '[]',
            recommended_tasks TEXT DEFAULT '[]',
            transcript TEXT DEFAULT '',
            audio_url TEXT,
            source TEXT DEFAULT 'external',
            analyzed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS service_checkpoints (
            service_name TEXT PRIMARY KEY,
            last_run_at DATETIME,
            last_success_at DATETIME,
            metadata TEXT DEFAULT '{}'
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_date TEXT,
            content TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_summaries (
            user_id INTEGER PRIMARY KEY,
            summary TEXT,
            updated_at DATETIME
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_intelligence (
            user_id INTEGER PRIMARY KEY,
            profile TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            last_intent TEXT,
            lead_score INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS department_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT,
            target_month TEXT,
            target_value REAL,
            actual_value REAL DEFAULT 0,
            currency TEXT DEFAULT 'UZS',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_checkpoints (
            chat_id INTEGER PRIMARY KEY,
            last_processed_msg_id INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    for table in [
        "chat_checkpoints", "department_targets", "user_intelligence",
        "chat_summaries", "daily_plans", "service_checkpoints",
        "call_analyses", "learned_facts", "agent_actions", "kv_settings",
        "scheduled_jobs", "team_reports", "crm_sync_status", "advisor_logs",
        "tasks", "message_logs", "messages", "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table}")
