import aiosqlite
import sqlite3
import datetime
import logging
import json
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
            except:
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
                    meeting_status TEXT DEFAULT 'pending'
                )
            """)
            
            # Migration helper for missing columns
            cols_needed = [
                ("last_name", "TEXT"), ("contact_name", "TEXT"), ("bio", "TEXT"),
                ("avatar_analysis", "TEXT"), ("mutual_groups_count", "INTEGER DEFAULT 0"),
                ("social_analysis", "TEXT"), ("lead_score", "INTEGER DEFAULT 0"),
                ("position", "TEXT"), ("intent", "TEXT"), ("crm_synced", "BOOLEAN DEFAULT 0"),
                ("processed_at", "DATETIME"), ("detailed_role", "TEXT"),
                ("meeting_time", "TEXT"), ("meeting_status", "TEXT DEFAULT 'pending'")
            ]
            for col, col_type in cols_needed:
                try: await conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except: pass

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
        async with conn.execute("SELECT user_id, first_name, username, role, detailed_role FROM users WHERE role IS NOT NULL") as cursor:
            rows = await cursor.fetchall()
            return [{"user_id": r[0], "name": r[1], "username": r[2], "role": r[3], "detailed_role": r[4]} for r in rows]

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
        async with conn.execute("SELECT first_name, username, phone, business_type, region, brand_name, service_type, deadline, role, detailed_role FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"first_name": row[0], "username": row[1], "phone": row[2], "business_type": row[3], "region": row[4], "brand_name": row[5], "service_type": row[6], "deadline": row[7], "role": row[8], "detailed_role": row[9]}
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
            return chats

    async def get_stats(self):
        conn = await self.get_connection()
        async with conn.execute("SELECT (SELECT COUNT(*) FROM users), (SELECT COUNT(*) FROM message_logs)") as cursor:
            row = await cursor.fetchone()
            return {"total_users": row[0], "total_messages": row[1]}

    async def log_agent_action(self, user_id, action_type, data, success=True):
        now = datetime.datetime.now().isoformat()
        conn = await self.get_connection()
        await conn.execute("INSERT INTO agent_actions (user_id, action_type, action_data, success, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, action_type, json.dumps(data), success, now))
        await conn.commit()
