import aiosqlite
import sqlite3
import datetime
import asyncio
import logging
import json
from contextlib import asynccontextmanager

try:
    import libsql

    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False
from typing import List, Dict, Any, Optional
from src.settings import settings
from src import config
from src.database_pool import db_pool

logger = logging.getLogger(__name__)


def _normalize_cursor_description(result_set: Any) -> List[Any]:
    description = getattr(result_set, "description", None)
    if description:
        return list(description)

    columns = getattr(result_set, "columns", None) or []
    return [(str(col), None, None, None, None, None, None) for col in columns]


def _extract_prefetched_rows(result_set: Any) -> List[Any]:
    if result_set is None:
        return []

    rows = getattr(result_set, "rows", None)
    if rows is not None:
        try:
            return list(rows)
        except TypeError:
            return []

    try:
        return list(result_set)
    except TypeError:
        return []


def _is_benign_schema_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if not message:
        return False

    markers = (
        "duplicate column name",
        "already exists",
        "duplicate key name",
        "column already exists",
    )
    return any(marker in message for marker in markers)


def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            value = str(value)
    return str(value).lstrip("\ufeff").strip()


def _normalize_turso_url(url: str) -> str:
    if url.startswith("libsql://"):
        return "https://" + url[len("libsql://") :]
    return url


class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            import os

            db_path = os.path.join(os.getcwd(), "data", "bot.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._state_backend = "sqlite"
        logger.info(
            f"👸 [DATABASE] Oisha connected to her REAL memory: {self.db_path} 🛡️"
        )

    async def init_instance(self):
        """Async initialization for aiosqlite."""
        await self.init_db()

    async def get_connection(self):
        """
        Returns a TursoAdapter for Cloud Core or falls back to local SQLite.
        """
        turso_url = _normalize_turso_url(_setting_text(settings.TURSO_DATABASE_URL))
        turso_token = _setting_text(settings.TURSO_AUTH_TOKEN)

        if turso_url and turso_token and HAS_LIBSQL:
            if hasattr(self, "_conn") and isinstance(self._conn, TursoAdapter):
                self._state_backend = "turso"
                return self._conn

            try:
                db_pool.url = turso_url
                db_pool.auth_token = turso_token
                db_pool.close()

                def _probe_turso():
                    if turso_url == ":memory:":
                        conn = libsql.connect(turso_url)
                    else:
                        conn = libsql.connect(turso_url, auth_token=turso_token)
                    res = conn.execute("SELECT 1")
                    if hasattr(res, "fetchone"):
                        res.fetchone()
                    else:
                        list(res)
                    return conn

                probe_conn = await asyncio.wait_for(
                    asyncio.to_thread(_probe_turso), timeout=15.0
                )

                try:
                    pass
                finally:
                    try:
                        probe_conn.close()
                    except Exception:
                        pass

                self._conn = TursoAdapter()
                self._state_backend = "turso"
                return self._conn
            except Exception as exc:
                logger.warning(f"[DB] Turso probe failed, using SQLite fallback: {exc}")
                try:
                    db_pool.close()
                except Exception:
                    pass
                self._conn = None

        if (
            hasattr(self, "_conn")
            and self._conn
            and not isinstance(self._conn, TursoAdapter)
        ):
            try:
                await self._conn.execute("SELECT 1")
                self._state_backend = "sqlite"
                return self._conn
            except (aiosqlite.Error, asyncio.TimeoutError, Exception):
                self._conn = None

        self._conn = await aiosqlite.connect(self.db_path, timeout=30)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        self._state_backend = "sqlite"
        return self._conn

    def get_backend_name(self) -> str:
        return self._state_backend

    @asynccontextmanager
    async def get_conn(self):
        """Async context manager wrapper around get_connection() for code that
        uses `async with db.get_conn() as conn:` style (RetryQueue, FeedbackMemory)."""
        conn = await self.get_connection()
        yield conn

    async def close(self):
        """Ulanishni yopish."""
        if hasattr(self, "_conn") and self._conn:
            await self._conn.close()
            self._conn = None

    async def init_db(self):
        """Ma'lumotlar bazasini va jadvallarni yaratish (Asenkron)."""
        conn = await self.get_connection()
        async with conn.cursor():
            # Users
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    phone TEXT,
                    business_type TEXT,
                    region TEXT,
                    brand_name TEXT,
                    service_type TEXT,
                    deadline TEXT,
                    role TEXT,
                    is_lead_forwarded BOOLEAN DEFAULT 0,
                    last_seen DATETIME,
                    created_at DATETIME,
                    last_name TEXT,
                    contact_name TEXT,
                    bio TEXT,
                    avatar_analysis TEXT,
                    mutual_groups_count INTEGER DEFAULT 0,
                    social_analysis TEXT,
                    lead_score INTEGER DEFAULT 0,
                    position TEXT,
                    intent TEXT,
                    crm_synced BOOLEAN DEFAULT 0,
                    processed_at DATETIME,
                    detailed_role TEXT,
                    meeting_time TEXT,
                    meeting_status TEXT DEFAULT 'pending',
                    lead_quality TEXT,
                    journey_stage TEXT,
                    journey_status TEXT,
                    journey_next_action TEXT,
                    close_probability REAL DEFAULT 0,
                    last_client_message_at DATETIME,
                    last_ai_message_at DATETIME,
                    lifecycle_updated_at DATETIME
                )
            """)

            # Migration helper for missing columns
            cols_needed = [
                ("last_name", "TEXT"),
                ("contact_name", "TEXT"),
                ("bio", "TEXT"),
                ("avatar_analysis", "TEXT"),
                ("mutual_groups_count", "INTEGER DEFAULT 0"),
                ("social_analysis", "TEXT"),
                ("lead_score", "INTEGER DEFAULT 0"),
                ("position", "TEXT"),
                ("intent", "TEXT"),
                ("crm_synced", "BOOLEAN DEFAULT 0"),
                ("processed_at", "DATETIME"),
                ("detailed_role", "TEXT"),
                ("lead_quality", "TEXT"),
                ("journey_stage", "TEXT"),
                ("journey_status", "TEXT"),
                ("journey_next_action", "TEXT"),
                ("close_probability", "REAL DEFAULT 0"),
                ("last_client_message_at", "DATETIME"),
                ("last_ai_message_at", "DATETIME"),
                ("lifecycle_updated_at", "DATETIME"),
            ]
            existing_user_columns = await self._get_table_columns(conn, "users")
            for col, col_type in cols_needed:
                if col in existing_user_columns:
                    continue
                try:
                    await conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                    existing_user_columns.add(col)
                except (
                    aiosqlite.Error,
                    sqlite3.Error,
                    ValueError,
                    RuntimeError,
                ) as exc:
                    if _is_benign_schema_error(exc):
                        existing_user_columns.add(col)
                        continue
                    raise
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, is_ai BOOLEAN, created_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS message_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message_text TEXT, is_ai_reply BOOLEAN, created_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, assigned_to INTEGER, deadline DATETIME, priority TEXT DEFAULT 'Medium', status TEXT DEFAULT 'Pending', created_by INTEGER, created_at DATETIME, completed_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS advisor_logs (chat_id INTEGER, message_id INTEGER, advice_type TEXT, content TEXT, created_at DATETIME, PRIMARY KEY (chat_id, message_id, advice_type))"
            )
            # [PHASE 3.1] MetaSell-parity scoring columns
            advisor_scoring_cols = [
                ("quality_score", "REAL"),
                ("lead_score", "REAL"),
                ("conversation_family", "TEXT"),
                ("conversation_domain", "TEXT"),
                ("business_fit", "TEXT"),
                ("business_fit_reason", "TEXT"),
                ("service_tag", "TEXT"),
                ("analyst_version", "TEXT"),
            ]
            existing_advisor_columns = await self._get_table_columns(
                conn, "advisor_logs"
            )
            for col, col_type in advisor_scoring_cols:
                if col in existing_advisor_columns:
                    continue
                try:
                    await conn.execute(
                        f"ALTER TABLE advisor_logs ADD COLUMN {col} {col_type}"
                    )
                    existing_advisor_columns.add(col)
                except (
                    aiosqlite.Error,
                    sqlite3.Error,
                    ValueError,
                    RuntimeError,
                ) as exc:
                    if _is_benign_schema_error(exc):
                        existing_advisor_columns.add(col)
                        continue
                    raise
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS crm_sync_status (user_id INTEGER PRIMARY KEY, amo_lead_id INTEGER, status TEXT DEFAULT 'synced', synced_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS team_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, report_date TEXT, report_type TEXT, content TEXT, status TEXT DEFAULT 'submitted', created_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS scheduled_jobs (job_name TEXT, run_date TEXT, created_at DATETIME, PRIMARY KEY (job_name, run_date))"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS kv_settings (key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS juma_sent_logs (user_id INTEGER, run_date TEXT, PRIMARY KEY (user_id, run_date))"
            )
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ambassador_journey_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    lead_id INTEGER,
                    touchpoint_type TEXT,
                    sent_message TEXT,
                    response_text TEXT,
                    nps_score INTEGER,
                    status TEXT DEFAULT 'pending',
                    scheduled_at TEXT,
                    sent_at TEXT,
                    created_at TEXT
                )
            """)
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS agent_actions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action_type TEXT, action_data TEXT, success BOOLEAN DEFAULT 1, created_at DATETIME)"
            )
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS learned_facts (id INTEGER PRIMARY KEY AUTOINCREMENT, fact_key TEXT, fact_value TEXT, user_id INTEGER, created_at DATETIME)"
            )
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS call_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT UNIQUE NOT NULL,
                    lead_id INTEGER,
                    manager_id INTEGER,
                    manager_name TEXT,
                    client_name TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    overall_score INTEGER,
                    category TEXT,
                    scores TEXT,
                    summary TEXT,
                    strengths TEXT,
                    weaknesses TEXT,
                    client_mood TEXT,
                    client_interest_level INTEGER,
                    objections TEXT,
                    outcome TEXT,
                    next_steps TEXT,
                    recommended_tasks TEXT,
                    transcript TEXT,
                    audio_url TEXT,
                    caller_phone TEXT DEFAULT '',
                    task_id TEXT,
                    task_created_at TEXT,
                    source TEXT DEFAULT 'external',
                    analyzed_at TEXT,
                    created_at TEXT
                )
            """)
            call_analysis_cols = [
                ("client_name", "TEXT"),
                ("scores", "TEXT"),
                ("transcript", "TEXT"),
                ("audio_url", "TEXT"),
                ("source", "TEXT DEFAULT 'external'"),
                ("created_at", "TEXT"),
                ("caller_phone", "TEXT DEFAULT ''"),
                ("task_id", "TEXT"),
                ("task_created_at", "TEXT"),
            ]
            existing_call_analysis_columns = await self._get_table_columns(
                conn, "call_analyses"
            )
            for col, col_type in call_analysis_cols:
                if col in existing_call_analysis_columns:
                    continue
                try:
                    await conn.execute(
                        f"ALTER TABLE call_analyses ADD COLUMN {col} {col_type}"
                    )
                    existing_call_analysis_columns.add(col)
                except (
                    aiosqlite.Error,
                    sqlite3.Error,
                    ValueError,
                    RuntimeError,
                ) as exc:
                    if _is_benign_schema_error(exc):
                        existing_call_analysis_columns.add(col)
                        continue
                    raise
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS service_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    external_id TEXT, 
                    checkpoint_key TEXT, 
                    status TEXT DEFAULT 'Pending', 
                    last_notified_at DATETIME, 
                    created_at DATETIME,
                    UNIQUE(external_id, checkpoint_key)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT NOT NULL,
                    manager_id INTEGER NOT NULL,
                    lead_id INTEGER NOT NULL,
                    lead_name TEXT,
                    mission TEXT,
                    source_pipeline TEXT,
                    created_at TEXT
                )
            """)
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS chat_summaries (user_id INTEGER PRIMARY KEY, summary TEXT, updated_at DATETIME)"
            )
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_intelligence (
                    user_id INTEGER PRIMARY KEY,
                    psychotype TEXT,
                    pain_points TEXT,
                    objections_history TEXT,
                    buying_drivers TEXT,
                    communication_style TEXT,
                    negotiation_strategy TEXT,
                    facts_json TEXT,
                    updated_at DATETIME
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS department_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dept_name TEXT,
                    target_type TEXT,
                    target_value REAL,
                    month TEXT,
                    assigned_to TEXT
                )
            """)

            # [PHASE 1.6] Per-chat message checkpoint for boot-time catch-up.
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_checkpoints (
                    chat_id INTEGER PRIMARY KEY,
                    last_processed_msg_id INTEGER NOT NULL DEFAULT 0,
                    last_processed_at DATETIME
                )
            """)

            # [PERFORMANCE] Create indexes
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_intent ON users(intent)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_crm_synced ON users(crm_synced)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_last_client_message_at ON users(last_client_message_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_message_logs_user_id ON message_logs(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_message_logs_created_at ON message_logs(created_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_message_logs_user_ai_created ON message_logs(user_id, is_ai_reply, created_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_reports_user_id ON team_reports(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_service_checkpoints_ext_id ON service_checkpoints(external_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_team_reports_date ON team_reports(report_date)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_actions_user_id ON agent_actions(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_actions_created ON agent_actions(created_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learned_facts_user ON learned_facts(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_plans_manager ON daily_plans(manager_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans(report_date)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_summaries_user ON chat_summaries(user_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_call_analyses_analyzed_at ON call_analyses(analyzed_at)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_call_analyses_manager ON call_analyses(manager_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_call_analyses_outcome ON call_analyses(outcome)"
            )

            await conn.commit()
            logger.info("[DB] Async Base Ready.")
            if hasattr(config, "OWNER_ID"):
                await self.ensure_owner_admin(int(config.OWNER_ID))

    _ALLOWED_TABLES = frozenset(
        {
            "users",
            "messages",
            "message_logs",
            "tasks",
            "crm_sync_status",
            "call_analyses",
            "advisor_logs",
            "team_reports",
            "daily_plans",
            "chat_summaries",
            "user_intelligence",
            "kv_settings",
            "juma_sent_logs",
            "ambassador_journey_logs",
        }
    )

    async def _get_table_columns(self, conn, table_name: str) -> set[str]:
        if table_name not in self._ALLOWED_TABLES:
            raise ValueError(f"Unknown table: {table_name!r}")
        async with conn.execute(
            "SELECT name FROM pragma_table_info(?)", (table_name,)
        ) as cursor:
            rows = await cursor.fetchall()
        return {str(row[0]) for row in rows if row and row[0]}

    async def ensure_owner_admin(self, owner_id: int):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (owner_id,)
        ) as cursor:
            if not await cursor.fetchone():
                await conn.execute(
                    "INSERT INTO users (user_id, first_name, role, created_at) VALUES (?, 'Owner', 'admin', ?)",
                    (owner_id, now),
                )
            else:
                await conn.execute(
                    "UPDATE users SET role = 'admin' WHERE user_id = ?", (owner_id,)
                )
        await conn.commit()

    async def get_state(self, key: str, default: Any = None) -> Any:
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT value FROM kv_settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_state(self, key: str, value: Any):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO kv_settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, str(value), now),
        )
        await conn.commit()
        return True

    async def upsert_user(
        self, user_id, first_name, username=None, phone=None, **kwargs
    ):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        update_fields = [
            "first_name=excluded.first_name",
            "username=excluded.username",
            "last_seen=excluded.last_seen",
        ]
        if phone:
            update_fields.append("phone=COALESCE(excluded.phone, users.phone)")

        valid_keys = [
            "business_type",
            "region",
            "brand_name",
            "service_type",
            "deadline",
            "last_name",
            "contact_name",
            "bio",
            "avatar_analysis",
            "social_analysis",
            "meeting_time",
            "meeting_status",
            "lead_score",
            "position",
            "role",
            "intent",
            "detailed_role",
        ]
        for key in kwargs:
            if key in valid_keys:
                update_fields.append(f"{key}=COALESCE(excluded.{key}, users.{key})")

        query = f"""
            INSERT INTO users (user_id, first_name, username, phone,
                             business_type, region, brand_name, service_type, deadline,
                             last_name, contact_name, bio, avatar_analysis, social_analysis,
                             role, position, intent, detailed_role,
                             last_seen, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET {", ".join(update_fields)}
        """  # nosec
        params = (
            user_id,
            first_name,
            username,
            phone,
            kwargs.get("business_type"),
            kwargs.get("region"),
            kwargs.get("brand_name"),
            kwargs.get("service_type"),
            kwargs.get("deadline"),
            kwargs.get("last_name"),
            kwargs.get("contact_name"),
            kwargs.get("bio"),
            kwargs.get("avatar_analysis"),
            kwargs.get("social_analysis"),
            kwargs.get("role"),
            kwargs.get("position"),
            kwargs.get("intent"),
            kwargs.get("detailed_role"),
            now,
            now,
        )
        await conn.execute(query, params)
        await conn.commit()

    async def log_message(self, user_id, text, is_ai=False):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)",
            (user_id, text, is_ai, now),
        )
        if is_ai:
            await conn.execute(
                "UPDATE users SET last_ai_message_at = ?, last_seen = COALESCE(last_seen, ?) WHERE user_id = ?",
                (now, now, user_id),
            )
        else:
            await conn.execute(
                "UPDATE users SET last_client_message_at = ?, last_seen = COALESCE(last_seen, ?) WHERE user_id = ?",
                (now, now, user_id),
            )
        await conn.commit()

    async def log_messages_batch(self, messages_data: List[tuple]):
        """
        Xabarlarni ommaviy saqlash (Performance optimization for backlog sync).
        """
        if not messages_data:
            return
        conn = await self.get_connection()
        await conn.executemany(
            "INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)",
            messages_data,
        )
        await conn.commit()

    async def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        if not phone:
            return None
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT * FROM users WHERE phone = ? OR phone LIKE ?",
            (phone, f"%{phone[-9:]}"),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                cols = [description[0] for description in cursor.description]
                return dict(zip(cols, row))
        return None

    async def get_user_id_by_phone(self, phone: str) -> Optional[int]:
        user = await self.get_user_by_phone(phone)
        if not user:
            return None
        user_id = user.get("user_id")
        return int(user_id) if user_id is not None else None

    async def get_chat_summary(self, user_id: int) -> Optional[str]:
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT summary FROM chat_summaries WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_chat_summary(self, user_id: int, summary: str):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO chat_summaries (user_id, summary, updated_at) VALUES (?, ?, ?)",
            (user_id, summary, now),
        )
        await conn.commit()
        return True

    async def get_recent_active_leads(
        self, hours: int = 72, limit: int = 12
    ) -> List[Dict[str, Any]]:
        """Return recently active leads with their latest client message."""
        cutoff = (
            datetime.datetime.now()
            - datetime.timedelta(hours=max(1, int(hours)))
        ).isoformat()
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT
                u.user_id,
                u.first_name,
                u.username,
                u.phone,
                u.business_type,
                u.region,
                u.brand_name,
                u.service_type,
                u.intent,
                u.meeting_time,
                u.meeting_status,
                u.journey_stage,
                u.journey_status,
                u.journey_next_action,
                u.close_probability,
                u.last_client_message_at,
                u.last_ai_message_at,
                u.lifecycle_updated_at,
                (
                    SELECT ml.message_text
                    FROM message_logs ml
                    WHERE ml.user_id = u.user_id
                      AND COALESCE(ml.is_ai_reply, 0) = 0
                      AND ml.message_text IS NOT NULL
                      AND ml.message_text != ''
                    ORDER BY ml.created_at DESC, ml.id DESC
                    LIMIT 1
                ) AS last_client_message
            FROM users u
            WHERE u.last_client_message_at IS NOT NULL
              AND u.last_client_message_at >= ?
            ORDER BY u.last_client_message_at DESC
            LIMIT ?
            """,
            (cutoff, max(1, int(limit))),
        ) as cursor:
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    async def get_recent_messages(self, user_id, limit=1000):
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT message_text, is_ai_reply FROM message_logs WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            history = []
            for text, is_ai in reversed(rows):
                role = "model" if is_ai else "user"
                if text.startswith("ERROR:"):
                    continue
                history.append({"role": role, "parts": [{"text": text}]})
            if history and history[0]["role"] == "model":
                history.pop(0)
            sanitized = []
            last_role = None
            for entry in history:
                if entry["role"] != last_role:
                    sanitized.append(entry)
                    last_role = entry["role"]
            return sanitized

    async def get_all_users(self) -> List[int]:
        conn = await self.get_connection()
        async with conn.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def get_user_by_role(self, role: str) -> Optional[Dict[str, Any]]:
        """Return one team member matching a normalized operational role."""
        normalized = str(role or "").strip().lower()
        if not normalized:
            return None
        aliases = {
            "pm": ("pm", "project manager", "farmer"),
            "project manager": ("pm", "project manager", "farmer"),
            "farmer": ("pm", "project manager", "farmer"),
            "finance": ("finance", "moliya", "accountant", "buxgalter"),
            "moliya": ("finance", "moliya", "accountant", "buxgalter"),
            "accountant": ("finance", "moliya", "accountant", "buxgalter"),
            "buxgalter": ("finance", "moliya", "accountant", "buxgalter"),
        }.get(normalized, (normalized,))
        placeholders = ", ".join("?" for _ in aliases)
        params = tuple(aliases) * 3
        conn = await self.get_connection()
        async with conn.execute(
            f"""
            SELECT user_id, first_name, username, role, detailed_role, position
            FROM users
            WHERE LOWER(TRIM(COALESCE(role, ''))) IN ({placeholders})
               OR LOWER(TRIM(COALESCE(detailed_role, ''))) IN ({placeholders})
               OR LOWER(TRIM(COALESCE(position, ''))) IN ({placeholders})
            ORDER BY
                CASE WHEN LOWER(TRIM(COALESCE(role, ''))) = ? THEN 0 ELSE 1 END,
                user_id
            LIMIT 1
            """,  # nosec
            params + (normalized,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "name": row[1] or row[2] or f"User_{row[0]}",
            "first_name": row[1],
            "username": row[2],
            "role": row[3] or row[5] or row[4],
            "detailed_role": row[4],
            "position": row[5],
        }

    async def get_team_roles(self):
        conn = await self.get_connection()
        async with conn.execute("""
            SELECT user_id, first_name, username, role, detailed_role, position
            FROM users
            WHERE role IS NOT NULL OR detailed_role IS NOT NULL OR position IS NOT NULL
            """) as cursor:
            rows = await cursor.fetchall()

        members: list[Dict[str, Any]] = []
        seen_ids = set()
        for user_id, first_name, username, role, detailed_role, position in rows:
            member_role = role or position or detailed_role or "team"
            members.append(
                {
                    "user_id": user_id,
                    "name": first_name or username or f"User_{user_id}",
                    "username": username,
                    "role": member_role,
                    "detailed_role": detailed_role,
                    "position": position,
                }
            )
            seen_ids.add(user_id)

        manager_ids = set(settings.SALES_MANAGER_IDS or [])
        stored_managers = await self.get_state("sales_managers", "")
        if stored_managers:
            for raw_id in str(stored_managers).split(","):
                raw_id = raw_id.strip()
                if raw_id.isdigit():
                    manager_ids.add(int(raw_id))

        for manager_id in sorted(manager_ids):
            if manager_id in seen_ids:
                continue
            members.append(
                {
                    "user_id": manager_id,
                    "name": f"Manager_{manager_id}",
                    "username": None,
                    "role": "sales_manager",
                    "detailed_role": "sales_manager",
                    "position": "Sales Manager",
                }
            )
        return members

    async def is_job_run(self, job_name, date_str):
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT 1 FROM scheduled_jobs WHERE job_name = ? AND run_date = ?",
            (job_name, date_str),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_job_run(self, job_name, date_str):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO scheduled_jobs (job_name, run_date, created_at) VALUES (?, ?, ?)",
            (job_name, date_str, now),
        )
        await conn.commit()

    async def get_recent_job_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        conn = await self.get_connection()
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
        """Return dashboard-safe row counts from the active state backend."""
        conn = await self.get_connection()
        counts: Dict[str, int] = {}
        for table_name in (
            "scheduled_jobs",
            "kv_settings",
            "agent_actions",
            "users",
            "call_analyses",
        ):
            async with conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"  # nosec B608
            ) as cursor:
                row = await cursor.fetchone()
            counts[table_name] = int(row[0]) if row else 0
        return counts

    async def get_recent_agent_actions(
        self, limit: int = 25
    ) -> List[Dict[str, Any]]:
        conn = await self.get_connection()
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

    async def update_chat_checkpoint(self, chat_id: int, msg_id: int) -> None:
        if not chat_id or not msg_id:
            return
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = await self.get_connection()
        await conn.execute(
            """
            INSERT INTO chat_checkpoints (chat_id, last_processed_msg_id, last_processed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                last_processed_msg_id = MAX(chat_checkpoints.last_processed_msg_id, excluded.last_processed_msg_id),
                last_processed_at = excluded.last_processed_at
            """,
            (int(chat_id), int(msg_id), now),
        )
        await conn.commit()

    async def get_recent_chat_checkpoints(
        self, since_days: int = 7
    ) -> List[Dict[str, Any]]:
        since_dt = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=since_days)
        ).isoformat()
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT chat_id, last_processed_msg_id, last_processed_at FROM chat_checkpoints "
            "WHERE last_processed_at >= ? ORDER BY last_processed_at DESC",
            (since_dt,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "chat_id": r[0],
                    "last_processed_msg_id": r[1] or 0,
                    "last_processed_at": r[2],
                }
                for r in rows
            ]

    async def get_user_info(self, user_id):
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT first_name, username, phone, business_type, region, brand_name,
                   service_type, deadline, role, detailed_role, intent,
                   is_lead_forwarded, lead_quality
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "first_name": row[0],
                    "username": row[1],
                    "phone": row[2],
                    "business_type": row[3],
                    "region": row[4],
                    "brand_name": row[5],
                    "service_type": row[6],
                    "deadline": row[7],
                    "role": row[8],
                    "detailed_role": row[9],
                    "intent": row[10],
                    "is_lead_forwarded": row[11],
                    "lead_quality": row[12],
                }
            return None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT user_id, first_name, username FROM users WHERE username = ?",
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"user_id": row[0], "first_name": row[1], "username": row[2]}
        return None

    async def get_daily_chats_summary(self):
        one_day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        conn = await self.get_connection()
        query = """
            SELECT ml.user_id, u.first_name, u.username, ml.message_text, ml.is_ai_reply, ml.created_at
            FROM message_logs ml LEFT JOIN users u ON ml.user_id = u.user_id
            WHERE ml.created_at >= ? ORDER BY ml.user_id, ml.created_at ASC
        """
        async with conn.execute(query, (one_day_ago,)) as cursor:
            rows = await cursor.fetchall()
            chats = {}
            for uid, name, uname, text, is_ai, time in rows:
                if uid not in chats:
                    chats[uid] = {
                        "name": name or f"User_{uid}",
                        "username": uname or "n/a",
                        "messages": [],
                    }
                role = "OISHA" if is_ai else "Client"
                chats[uid]["messages"].append(f"{role} ({time}): {text}")
            return chats

    async def get_recent_all_messages(self, limit=50):
        conn = await self.get_connection()
        query = """
            SELECT user_id, message_text, is_ai_reply, created_at
            FROM message_logs
            WHERE message_text IS NOT NULL AND message_text != ''
            ORDER BY created_at DESC
            LIMIT ?
        """
        async with conn.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [(r[0], r[1], r[2], r[3]) for r in reversed(rows)]

    async def get_stats(self):
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM message_logs)"
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"total_users": 0, "total_messages": 0}
            return {"total_users": row[0], "total_messages": row[1]}

    async def get_today_stats(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users WHERE date(created_at) = ?),
                (SELECT COUNT(*) FROM message_logs WHERE date(created_at) = ?)
            """,
            (today, today),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return {"leads_found": 0, "messages_synced": 0}
            return {
                "leads_found": row[0] or 0,
                "messages_synced": row[1] or 0,
            }

    async def mark_crm_synced(self, user_id: int) -> bool:
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        cursor = await conn.execute(
            "UPDATE users SET crm_synced = 1, processed_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        if cursor.rowcount == 0:
            await conn.execute(
                """
                INSERT INTO users (user_id, first_name, crm_synced, processed_at, created_at, last_seen)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (user_id, f"User {user_id}", now, now, now),
            )
        await conn.commit()
        return True

    async def log_agent_action(self, user_id, action_type, data, success=True):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT INTO agent_actions (user_id, action_type, action_data, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action_type, json.dumps(data), success, now),
        )
        await conn.commit()

    async def save_daily_plan(
        self,
        manager_id: int,
        lead_id: int,
        lead_name: str,
        mission: str,
        source_pipeline: str = "HUNTER",
    ):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT INTO daily_plans (report_date, manager_id, lead_id, lead_name, mission, source_pipeline, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (today, manager_id, lead_id, lead_name, mission, source_pipeline, now),
        )
        await conn.commit()
        return True

    async def save_team_report(
        self,
        user_id: int,
        report_type: str,
        content: str,
        report_date: Optional[str] = None,
        status: str = "submitted",
    ) -> bool:
        from src.time_utils import get_local_now

        now = get_local_now()
        report_day = report_date or now.strftime("%Y-%m-%d")
        conn = await self.get_connection()
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

    async def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        from src.time_utils import get_local_now

        conn = await self.get_connection()
        async with conn.execute(
            "SELECT t.id, t.title, t.description, t.assigned_to, t.deadline, t.priority, t.status, u.first_name, u.username FROM tasks t LEFT JOIN users u ON u.user_id = t.assigned_to WHERE t.deadline IS NOT NULL AND COALESCE(t.status, 'Pending') NOT IN ('Done', 'Completed', 'Closed', 'Cancelled')"
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
                now
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

    async def update_lead_journey(
        self,
        user_id: int,
        *,
        stage: str,
        status: str,
        next_action: str,
        close_probability: float = 0.0,
        lifecycle_updated_at: Optional[str] = None,
    ) -> bool:
        now = lifecycle_updated_at or datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "UPDATE users SET journey_stage = ?, journey_status = ?, journey_next_action = ?, close_probability = ?, lifecycle_updated_at = ? WHERE user_id = ?",
            (stage, status, next_action, float(close_probability or 0.0), now, user_id),
        )
        await conn.commit()
        return True

    async def get_user_intelligence(self, user_id: int) -> Dict[str, Any]:
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT psychotype, pain_points, objections_history, buying_drivers, communication_style, negotiation_strategy, facts_json FROM user_intelligence WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "psychotype": row[0],
                    "pain_points": row[1],
                    "objections_history": row[2],
                    "buying_drivers": row[3],
                    "communication_style": row[4],
                    "negotiation_strategy": row[5],
                    "facts_json": json.loads(row[6]) if row[6] else {},
                }
            return {}

    async def upsert_user_intelligence(self, user_id: int, intel_data: Dict[str, Any]):
        conn = await self.get_connection()
        now = datetime.datetime.now().isoformat()
        existing = await self.get_user_intelligence(user_id)
        facts = existing.get("facts_json", {})
        if "facts" in intel_data:
            facts.update(intel_data["facts"])
        await conn.execute(
            """
            INSERT INTO user_intelligence (
                user_id, psychotype, pain_points, objections_history, 
                buying_drivers, communication_style, negotiation_strategy, 
                facts_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                psychotype = COALESCE(excluded.psychotype, user_intelligence.psychotype),
                pain_points = COALESCE(excluded.pain_points, user_intelligence.pain_points),
                objections_history = COALESCE(excluded.objections_history, user_intelligence.objections_history),
                buying_drivers = COALESCE(excluded.buying_drivers, user_intelligence.buying_drivers),
                communication_style = COALESCE(excluded.communication_style, user_intelligence.communication_style),
                negotiation_strategy = COALESCE(excluded.negotiation_strategy, user_intelligence.negotiation_strategy),
                facts_json = excluded.facts_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                intel_data.get("psychotype"),
                intel_data.get("pain_points"),
                intel_data.get("objections_history"),
                intel_data.get("buying_drivers"),
                intel_data.get("communication_style"),
                intel_data.get("negotiation_strategy"),
                json.dumps(facts),
                now,
            ),
        )
        await conn.commit()
        return True

    async def get_latest_call_analysis(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """
        Lid uchun oxirgi qo'ng'iroq tahlilini olish.
        
        Args:
            lead_id: amoCRM lead IDsi
            
        Returns:
            Dict formatidagi tahlil ma'lumotlari yoki None
        """
        if not lead_id:
            return None

        conn = await self.get_connection()
        if not conn:
            logger.error("[DB] Connection failed while fetching call analysis")
            return None

        query = """
            SELECT * FROM call_analyses 
            WHERE lead_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """
        try:
            async with conn.execute(query, (lead_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    cols = [description[0] for description in cursor.description]
                    data = dict(zip(cols, row))
                    
                    # JSON maydonlarni xavfsiz parse qilish
                    json_fields = [
                        "scores", "strengths", "weaknesses", 
                        "objections", "next_steps", "recommended_tasks"
                    ]
                    for json_col in json_fields:
                        val = data.get(json_col)
                        if val and isinstance(val, str):
                            try:
                                data[json_col] = json.loads(val)
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.warning(f"[DB] JSON parse error for {json_col} in lead {lead_id}: {e}")
                                # Keep as string or set to empty dict/list if needed
                    return data
        except Exception as e:
            logger.error(f"[DB] Error fetching call analysis for lead {lead_id}: {e}")
            
        return None

    def __iter__(self):
        return iter(())


class _TursoCursor:
    """
    aiosqlite.Cursor-compatible cursor for high-speed operation.
    """

    def __init__(self, rows=None, description=None):
        self._rows = _extract_prefetched_rows(rows)
        self._description = description or _normalize_cursor_description(rows)
        self._ptr = 0
        self.rowcount = len(self._rows)
        self.description = self._description

    async def fetchone(self):
        if self._ptr < len(self._rows):
            row = self._rows[self._ptr]
            self._ptr += 1
            return row
        return None

    async def fetchall(self):
        remaining = self._rows[self._ptr :]
        self._ptr = len(self._rows)
        return remaining

    async def fetchmany(self, size=1):
        end = min(self._ptr + size, len(self._rows))
        chunk = self._rows[self._ptr : end]
        self._ptr = end
        return chunk

    async def close(self):
        self._rows = []
        self._ptr = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        row = await self.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class _ExecuteProxy:
    """
    Dual-mode result of TursoAdapter.execute(sql, ...).
    """

    def __init__(self, sql, parameters):
        self._sql = sql
        self._params = parameters
        self._cursor = None

    async def _run(self):
        sql = self._sql or ""
        if sql.lstrip().upper().startswith("PRAGMA"):
            return _TursoCursor(_EmptyResultSet())
        rows = await db_pool.execute(sql, self._params)
        desc = None
        if rows:
            desc = [(k, None, None, None, None, None, None) for k in rows[0].keys()]
        return _TursoCursor(rows, desc)

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        self._cursor = await self._run()
        return self._cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class _EmptyResultSet:
    """Placeholder ResultSet for no-op PRAGMA responses."""

    columns = []
    description = []
    rows_affected = 0
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def fetchmany(self, size=1):
        return []

    def close(self):
        return None

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0


class TursoAdapter:
    def __init__(self):
        self.row_factory = None

    def execute(self, sql, parameters=None):
        return _ExecuteProxy(sql, parameters)

    async def executemany(self, sql, parameter_list):
        affected = 0
        for params in parameter_list or []:
            await db_pool.execute(sql, params)
            affected += 1
        cursor = _TursoCursor()
        cursor.rowcount = affected
        return cursor

    async def executescript(self, script):
        statements = [
            stmt.strip() for stmt in (script or "").split(";") if stmt.strip()
        ]
        for statement in statements:
            await db_pool.execute(statement, None)
        return _TursoCursor(_EmptyResultSet())

    async def commit(self):
        await db_pool.commit()

    async def rollback(self):
        await db_pool.rollback()

    async def close(self):
        try:
            db_pool.close()
        except Exception as exc:
            logger.debug(f"[DB] Turso pool close warning: {exc}")

    def cursor(self):
        return _CursorContext(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class _CursorContext:
    def __init__(self, conn):
        self._conn = conn
        self._cursor = _TursoCursor(_EmptyResultSet())

    async def __aenter__(self):
        return self._cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cursor.close()

    async def execute(self, sql, parameters=None):
        proxy = self._conn.execute(sql, parameters)
        self._cursor = await proxy
        return self._cursor

    async def executemany(self, sql, parameter_list):
        return await self._conn.executemany(sql, parameter_list)

    async def fetchone(self):
        return await self._cursor.fetchone()
