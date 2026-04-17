import aiosqlite
import sqlite3
import datetime
import logging
import json
from google import genai
from typing import List, Dict, Any, Optional, Union
from src.settings import settings
from src import config 

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            import os
            db_path = os.path.join(os.getcwd(), 'data', 'bot.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        logger.info(f"👸 [DATABASE] Oisha connected to her REAL memory: {self.db_path} 🛡️")

    async def init_instance(self):
        """Async initialization for aiosqlite."""
        await self.init_db()

    async def get_connection(self):
        """Asenkron SQLite ulanishini olish (Persistent connection pattern)."""
        if hasattr(self, '_conn') and self._conn:
            try:
                # Test connection
                await self._conn.execute("SELECT 1")
                return self._conn
            except (aiosqlite.Error, asyncio.TimeoutError):
                # Connection is dead, will recreate
                self._conn = None
        
        self._conn = await aiosqlite.connect(self.db_path, timeout=30)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    async def close(self):
        """Ulanishni yopish."""
        if hasattr(self, '_conn') and self._conn:
            await self._conn.close()
            self._conn = None

    async def init_db(self):
        """Ma'lumotlar bazasini va jadvallarni yaratish (Asenkron)."""
        conn = await self.get_connection()
        async with conn.cursor() as cursor:
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
                    lead_quality TEXT
                )
            """)
            
            # Migration helper for missing columns
            cols_needed = [
                ("last_name", "TEXT"), ("contact_name", "TEXT"), ("bio", "TEXT"),
                ("avatar_analysis", "TEXT"), ("mutual_groups_count", "INTEGER DEFAULT 0"),
                ("social_analysis", "TEXT"), ("lead_score", "INTEGER DEFAULT 0"),
                ("position", "TEXT"), ("intent", "TEXT"), ("crm_synced", "BOOLEAN DEFAULT 0"),
                ("processed_at", "DATETIME"), ("detailed_role", "TEXT"),
                ("meeting_time", "TEXT"), ("meeting_status", "TEXT DEFAULT 'pending'"),
                ("lead_quality", "TEXT")
            ]
            for col, col_type in cols_needed:
                try:
                    await conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except aiosqlite.Error:
                    # Column already exists - safe to ignore
                    pass

            # Other tables
            await conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, is_ai BOOLEAN, created_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS message_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message_text TEXT, is_ai_reply BOOLEAN, created_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, assigned_to INTEGER, deadline DATETIME, priority TEXT DEFAULT 'Medium', status TEXT DEFAULT 'Pending', created_by INTEGER, created_at DATETIME, completed_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS advisor_logs (chat_id INTEGER, message_id INTEGER, advice_type TEXT, content TEXT, created_at DATETIME, PRIMARY KEY (chat_id, message_id, advice_type))")
            await conn.execute("CREATE TABLE IF NOT EXISTS crm_sync_status (user_id INTEGER PRIMARY KEY, amo_lead_id INTEGER, status TEXT DEFAULT 'synced', synced_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS team_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, report_date TEXT, report_type TEXT, content TEXT, status TEXT DEFAULT 'submitted', created_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS scheduled_jobs (job_name TEXT, run_date TEXT, created_at DATETIME, PRIMARY KEY (job_name, run_date))")
            await conn.execute("CREATE TABLE IF NOT EXISTS kv_settings (key TEXT PRIMARY KEY, value TEXT, updated_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS agent_actions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action_type TEXT, action_data TEXT, success BOOLEAN DEFAULT 1, created_at DATETIME)")
            await conn.execute("CREATE TABLE IF NOT EXISTS learned_facts (id INTEGER PRIMARY KEY AUTOINCREMENT, fact_key TEXT, fact_value TEXT, user_id INTEGER, created_at DATETIME)")
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
            try:
                await conn.execute("ALTER TABLE daily_plans ADD COLUMN source_pipeline TEXT")
            except aiosqlite.Error:
                # Column already exists or other SQLite error - safe to ignore
                pass
            
            # [PERFORMANCE] Create indexes for frequently queried columns
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_intent ON users(intent)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_crm_synced ON users(crm_synced)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_message_logs_user_id ON message_logs(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_team_reports_user_id ON team_reports(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_service_checkpoints_ext_id ON service_checkpoints(external_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_team_reports_date ON team_reports(report_date)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_actions_user_id ON agent_actions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_actions_created ON agent_actions(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_learned_facts_user ON learned_facts(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_plans_manager ON daily_plans(manager_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_plans_date ON daily_plans(report_date)")
            
            await conn.commit()
            logger.info("[DB] Async Base Ready.")
            if hasattr(config, 'OWNER_ID'):
                await self.ensure_owner_admin(int(config.OWNER_ID))

    async def ensure_owner_admin(self, owner_id: int):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        async with conn.execute("SELECT user_id FROM users WHERE user_id = ?", (owner_id,)) as cursor:
            if not await cursor.fetchone():
                await conn.execute("INSERT INTO users (user_id, first_name, role, created_at) VALUES (?, 'Owner', 'admin', ?)", (owner_id, now))
            else:
                await conn.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (owner_id,))
        await conn.commit()

    async def get_state(self, key: str, default: Any = None):
        conn = await self.get_connection()
        async with conn.execute("SELECT value FROM kv_settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_state(self, key: str, value: Any):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute("INSERT OR REPLACE INTO kv_settings (key, value, updated_at) VALUES (?, ?, ?)", (key, str(value), now))
        await conn.commit()
        return True

    async def upsert_user(self, user_id, first_name, username=None, phone=None, **kwargs):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        update_fields = ["first_name=excluded.first_name", "username=excluded.username", "last_seen=excluded.last_seen"]
        if phone: update_fields.append("phone=COALESCE(excluded.phone, users.phone)")
        
        valid_keys = ["business_type", "region", "brand_name", "service_type", "deadline", "last_name", "contact_name", "bio", "avatar_analysis", "social_analysis", "meeting_time", "meeting_status", "lead_score", "position", "role", "intent", "detailed_role"]
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
        """
        params = (user_id, first_name, username, phone, 
                  kwargs.get("business_type"), kwargs.get("region"), kwargs.get("brand_name"), 
                  kwargs.get("service_type"), kwargs.get("deadline"), 
                  kwargs.get("last_name"), kwargs.get("contact_name"), kwargs.get("bio"), 
                  kwargs.get("avatar_analysis"), kwargs.get("social_analysis"),
                  kwargs.get("role"), kwargs.get("position"), kwargs.get("intent"), kwargs.get("detailed_role"),
                  now, now)
        await conn.execute(query, params)
        await conn.commit()

    async def log_message(self, user_id, text, is_ai=False):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute("INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)", (user_id, text, is_ai, now))
        await conn.commit()

    async def get_recent_messages(self, user_id, limit=1000):
        conn = await self.get_connection()
        async with conn.execute("SELECT message_text, is_ai_reply FROM message_logs WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT ?", (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                history = []
                for text, is_ai in reversed(rows):
                    role = "model" if is_ai else "user"
                    if text.startswith("ERROR:"): continue
                    history.append({"role": role, "parts": [{"text": text}]})
                if history and history[0]["role"] == "model": history.pop(0)
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

    async def get_team_roles(self):
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT user_id, first_name, username, role, detailed_role, position
            FROM users
            WHERE role IS NOT NULL OR detailed_role IS NOT NULL OR position IS NOT NULL
            """
        ) as cursor:
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
        async with conn.execute("SELECT 1 FROM scheduled_jobs WHERE job_name = ? AND run_date = ?", (job_name, date_str)) as cursor:
            return await cursor.fetchone() is not None

    async def mark_job_run(self, job_name, date_str):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute("INSERT OR REPLACE INTO scheduled_jobs (job_name, run_date, created_at) VALUES (?, ?, ?)", (job_name, date_str, now))
        await conn.commit()

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
            (username,)
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
                    chats[uid] = {"name": name or f"User_{uid}", "username": uname or "n/a", "messages": []}
                role = "OISHA" if is_ai else "Client"
                chats[uid]["messages"].append(f"{role} ({time}): {text}")
    async def get_recent_all_messages(self, limit=50):
        """Barcha chatlardan oxirgi xabarlarni olish (Task extraction uchun)."""
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
        async with conn.execute("SELECT (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM message_logs)") as cursor:
            row = await cursor.fetchone()
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
            return {
                "leads_found": row[0] or 0,
                "messages_synced": row[1] or 0,
            }

    async def get_user_id_by_phone(self, phone: str) -> Optional[int]:
        conn = await self.get_connection()
        normalized_phone = "".join(ch for ch in (phone or "") if ch.isdigit())
        async with conn.execute("SELECT user_id, phone FROM users WHERE phone IS NOT NULL") as cursor:
            rows = await cursor.fetchall()
            for user_id, stored_phone in rows:
                stored_normalized = "".join(ch for ch in (stored_phone or "") if ch.isdigit())
                if stored_normalized and stored_normalized.endswith(normalized_phone):
                    return user_id
        return None

    async def get_user_by_phone_full(self, phone: str) -> Optional[Dict[str, Any]]:
        conn = await self.get_connection()
        normalized_phone = "".join(ch for ch in (phone or "") if ch.isdigit())
        async with conn.execute(
            """
            SELECT user_id, username, first_name, phone, last_name, business_type, region,
                   brand_name, intent, crm_synced
            FROM users
            WHERE phone IS NOT NULL
            """
        ) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                stored_normalized = "".join(ch for ch in (row[3] or "") if ch.isdigit())
                if stored_normalized and stored_normalized.endswith(normalized_phone):
                    return {
                        "user_id": row[0],
                        "username": row[1],
                        "first_name": row[2],
                        "phone": row[3],
                        "last_name": row[4],
                        "business_type": row[5],
                        "region": row[6],
                        "brand_name": row[7],
                        "intent": row[8],
                        "crm_synced": bool(row[9]),
                    }
        return None

    async def is_crm_synced(self, user_id: int) -> bool:
        conn = await self.get_connection()
        async with conn.execute("SELECT crm_synced FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

    async def mark_crm_synced(self, user_id: int) -> bool:
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "UPDATE users SET crm_synced = 1, processed_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        await conn.commit()
        return True

    async def set_crm_synced(self, user_id: int) -> bool:
        return await self.mark_crm_synced(user_id)

    async def get_synced_contacts_count(self) -> int:
        conn = await self.get_connection()
        async with conn.execute("SELECT COUNT(*) FROM users WHERE crm_synced = 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def is_message_processed(self, message_id: int) -> bool:
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT 1 FROM agent_actions WHERE action_type = 'processed_message' AND user_id = ? LIMIT 1",
            (message_id,),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_message_processed(self, message_id: int, group_id: int, status: str = "synced", reason: Optional[str] = None) -> bool:
        payload = {
            "group_id": group_id,
            "status": status,
            "reason": reason,
        }
        await self.log_agent_action(message_id, "processed_message", payload, success=(status == "synced"))
        return True

    async def analyze_text_with_ai(self, prompt: str) -> str:
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY.get_secret_value())
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt],
            )
            return response.text if response and response.text else ""
        except Exception as exc:
            logger.error(f"[DB AI ANALYSIS ERROR] {exc}")
            return ""

    async def log_agent_action(self, user_id, action_type, data, success=True):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute("INSERT INTO agent_actions (user_id, action_type, action_data, success, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, action_type, json.dumps(data), success, now))
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
            """
            INSERT INTO daily_plans (report_date, manager_id, lead_id, lead_name, mission, source_pipeline, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (today, manager_id, lead_id, lead_name, mission, source_pipeline, now),
        )
        await conn.commit()
        return True

    async def get_daily_plan(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        if not date_str:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT manager_id, lead_id, lead_name, mission, source_pipeline FROM daily_plans WHERE report_date = ?",
            (date_str,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "manager_id": r[0],
                    "lead_id": r[1],
                    "lead_name": r[2],
                    "mission": r[3],
                    "source_pipeline": r[4],
                }
                for r in rows
            ]

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
            """
            SELECT id
            FROM team_reports
            WHERE user_id = ? AND report_date = ? AND report_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, report_day, report_type),
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            await conn.execute(
                """
                UPDATE team_reports
                SET content = ?, status = ?, created_at = ?
                WHERE id = ?
                """,
                (content, status, now.isoformat(), existing[0]),
            )
        else:
            await conn.execute(
                """
                INSERT INTO team_reports (user_id, report_date, report_type, content, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, report_day, report_type, content, status, now.isoformat()),
            )
        await conn.commit()
        return True

    async def get_all_tasks(self, limit=10):
        conn = await self.get_connection()
        async with conn.execute("SELECT id, title, description, assigned_to, deadline, status FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "title": r[1], "description": r[2], "assigned_to": r[3], "deadline": r[4], "status": r[5]} for r in rows]

    async def get_recent_agent_actions(self, limit=5):
        conn = await self.get_connection()
        async with conn.execute("SELECT id, user_id, action_type, action_data, success, created_at FROM agent_actions ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "user_id": r[1], "action_type": r[2], "action_data": r[3], "success": r[4], "created_at": r[5]} for r in rows]

    async def get_missing_reports(
        self,
        report_type: str = "morning_plan",
        date_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from src.time_utils import get_local_now

        report_day = date_str or get_local_now().strftime("%Y-%m-%d")
        team = await self.get_team_roles()
        if not team:
            return []

        eligible = []
        for member in team:
            role_text = " ".join(
                str(member.get(key, "") or "").lower()
                for key in ("role", "detailed_role", "position")
            )
            if any(blocked in role_text for blocked in ("admin", "owner", "boss")):
                continue
            eligible.append(member)

        if not eligible:
            return []

        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT DISTINCT user_id
            FROM team_reports
            WHERE report_date = ? AND report_type = ? AND status != 'ignored'
            """,
            (report_day, report_type),
        ) as cursor:
            submitted_rows = await cursor.fetchall()

        submitted_ids = {row[0] for row in submitted_rows}
        return [member for member in eligible if member["user_id"] not in submitted_ids]

    async def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        from src.time_utils import get_local_now

        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT
                t.id,
                t.title,
                t.description,
                t.assigned_to,
                t.deadline,
                t.priority,
                t.status,
                u.first_name,
                u.username
            FROM tasks t
            LEFT JOIN users u ON u.user_id = t.assigned_to
            WHERE t.deadline IS NOT NULL
              AND COALESCE(t.status, 'Pending') NOT IN ('Done', 'Completed', 'Closed', 'Cancelled')
            """
        ) as cursor:
            rows = await cursor.fetchall()

        now = get_local_now()
        overdue: List[Dict[str, Any]] = []
        for task_id, title, description, assigned_to, deadline_raw, priority, status, first_name, username in rows:
            try:
                deadline_dt = datetime.datetime.fromisoformat(str(deadline_raw).replace("Z", "+00:00"))
            except ValueError:
                continue

            if deadline_dt.tzinfo is not None:
                now_cmp = now.astimezone(datetime.timezone.utc)
            else:
                now_cmp = now.replace(tzinfo=None)

            if deadline_dt < now_cmp:
                overdue.append(
                    {
                        "id": task_id,
                        "title": title,
                        "description": description,
                        "assigned_to": assigned_to,
                        "deadline": deadline_raw,
                        "priority": priority or "Medium",
                        "status": status or "Pending",
                        "name": first_name or f"User_{assigned_to}",
                        "username": username,
                    }
                )

        overdue.sort(key=lambda task: (task["priority"] != "High", task["deadline"]))
        return overdue

    async def get_priority_tasks(self, limit: int = 3) -> List[Dict[str, Any]]:
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT
                t.id,
                t.title,
                t.description,
                t.assigned_to,
                t.deadline,
                t.priority,
                t.status,
                u.first_name,
                u.username
            FROM tasks t
            LEFT JOIN users u ON u.user_id = t.assigned_to
            WHERE COALESCE(t.status, 'Pending') NOT IN ('Done', 'Completed', 'Closed', 'Cancelled')
            ORDER BY
                CASE COALESCE(t.priority, 'Medium')
                    WHEN 'High' THEN 0
                    WHEN 'Medium' THEN 1
                    ELSE 2
                END,
                COALESCE(t.deadline, '9999-12-31T23:59:59')
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "assigned_to": row[3],
                "deadline": row[4],
                "priority": row[5] or "Medium",
                "status": row[6] or "Pending",
                "name": row[7],
                "username": row[8],
            }
            for row in rows
        ]

    async def get_department_targets(self, month_str: Optional[str] = None) -> List[Dict[str, Any]]:
        key = f"department_targets:{month_str}" if month_str else "department_targets"
        raw_targets = await self.get_state(key, "")
        if raw_targets:
            try:
                parsed = json.loads(raw_targets)
                if isinstance(parsed, dict):
                    return [{"dept": dept, "value": value} for dept, value in parsed.items()]
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                logger.warning(f"[DB] Department targets could not be parsed for key={key}")

        return [
            {"dept": "Sales", "value": 80_000_000},
            {"dept": "Production", "value": 0},
            {"dept": "PM", "value": 0},
        ]

    def get_user_by_role(self, role: str) -> Optional[Dict[str, Any]]:
        normalized_role = (role or "").strip().lower()
        if not normalized_role:
            return None

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, first_name, username, role, detailed_role, position
                FROM users
                WHERE lower(COALESCE(role, '')) = ?
                   OR lower(COALESCE(detailed_role, '')) = ?
                   OR lower(COALESCE(position, '')) = ?
                LIMIT 1
                """,
                (normalized_role, normalized_role, normalized_role),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "name": row[1],
                "username": row[2],
                "role": row[3],
                "detailed_role": row[4],
                "position": row[5],
            }
        finally:
            conn.close()

    async def get_recent_job_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT job_name, run_date, created_at
            FROM scheduled_jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
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

    async def get_recent_agent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = await self.get_connection()
        async with conn.execute(
            """
            SELECT id, user_id, action_type, action_data, success, created_at
            FROM agent_actions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

        actions: List[Dict[str, Any]] = []
        for action_id, user_id, action_type, action_data, success, created_at in rows:
            try:
                parsed_data = json.loads(action_data) if action_data else {}
            except Exception:
                parsed_data = {"raw": action_data}

            actions.append(
                {
                    "id": action_id,
                    "user_id": user_id,
                    "action_type": action_type,
                    "action_data": parsed_data,
                    "success": bool(success),
                    "created_at": created_at,
                }
            )

        return actions

    async def get_checkpoint(self, external_id: str, checkpoint_key: str) -> Optional[Dict[str, Any]]:
        conn = await self.get_connection()
        async with conn.execute(
            "SELECT id, status, last_notified_at, created_at FROM service_checkpoints WHERE external_id = ? AND checkpoint_key = ?",
            (str(external_id), checkpoint_key)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "status": row[1], "last_notified_at": row[2], "created_at": row[3]}
        return None

    async def mark_checkpoint_done(self, external_id: str, checkpoint_key: str):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute(
            "INSERT OR REPLACE INTO service_checkpoints (external_id, checkpoint_key, status, created_at) VALUES (?, ?, 'Done', ?)",
            (str(external_id), checkpoint_key, now)
        )
        await conn.commit()

    async def mark_checkpoint_notified(self, external_id: str, checkpoint_key: str):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        # UPSERT style
        async with conn.execute("SELECT id FROM service_checkpoints WHERE external_id = ? AND checkpoint_key = ?", (str(external_id), checkpoint_key)) as cursor:
            if await cursor.fetchone():
                await conn.execute(
                    "UPDATE service_checkpoints SET last_notified_at = ? WHERE external_id = ? AND checkpoint_key = ?",
                    (now, str(external_id), checkpoint_key)
                )
            else:
                await conn.execute(
                    "INSERT INTO service_checkpoints (external_id, checkpoint_key, status, last_notified_at, created_at) VALUES (?, ?, 'Pending', ?, ?)",
                    (str(external_id), checkpoint_key, now, now)
                )
        await conn.commit()
