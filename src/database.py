import sqlite3
import datetime
import logging
from typing import List, Dict, Any, Optional, Union

try:
    import libsql
    HAS_LIBSQL = True
except ImportError:
    try:
        import libsql_client as libsql
        HAS_LIBSQL = True
    except ImportError:
        HAS_LIBSQL = False

# Assuming 'config' module exists and contains TURSO_DATABASE_URL and TURSO_AUTH_TOKEN
# If config is not a separate file, you might need to define these variables directly or load them differently.
from src.settings import settings
from src import config 

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path=None):
        # [AUDIT: RESTORATION] Hard-pinning to the project's data/bot.db
        if db_path is None:
            import os
            db_path = os.path.join(os.getcwd(), 'data', 'bot.db')
            # Ensure folder exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
        self.db_path = db_path
        logger.info(f"👸 [DATABASE] Oisha connected to her REAL memory: {self.db_path} 🛡️")
        self.init_db()

    def get_connection(self):
        # 1. Turso Cloud ulanishi (agar sozlamalar bo'lsa)
        url = getattr(config, "TURSO_DATABASE_URL", None)
        token = getattr(config, "TURSO_AUTH_TOKEN", None)
        
        # Re-check HAS_LIBSQL in case it was installed after first import
        global HAS_LIBSQL
        if not HAS_LIBSQL:
            try:
                import libsql
                HAS_LIBSQL = True
            except ImportError:
                try:
                    import libsql_client as libsql
                    HAS_LIBSQL = True
                except ImportError:
                    HAS_LIBSQL = False

        run_in_cloud = getattr(settings, "RUNNING_IN_CLOUD", False)
        
        if HAS_LIBSQL and url and token and ("turso.io" in url or run_in_cloud):
            try:
                # [GOD MODE] Force Turso if in cloud
                try:
                    import libsql
                except ImportError:
                    import libsql_client as libsql
                logger.info(f"👸 [DB] Cloud Mode Active! Connecting to Turso: {url}")
                return libsql.connect(url, auth_token=token)
            except Exception as e:
                if run_in_cloud:
                    logger.error(f"🚨 [CRITICAL] Turso connection failed in CLOUD: {e}")
                    raise e
                logger.error(f"[TURSO ERROR] Remote ulanishda xato: {e}. SQLite-ga qaytilyapti.")
        
        # 2. Standart SQLite ulanishi (lokal)
        # Enterprise optimization: timeout=30 and check_same_thread=False
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        
        # Enterprise optimization: WAL mode for concurrent reading/writing
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception as e:
            logger.warning(f"[DB WAL WARNING] WAL rejimini yoqishda xato: {e}")
            
        return conn

    def init_db(self):
        """Ma'lumotlar bazasini va jadvallarni yaratish."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Foydalanuvchilar jadvali
            cursor.execute("""
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
                    created_at DATETIME
                )
            """)
            
            # Enterprise: Processed messages table (to avoid duplicate scraping)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id INTEGER PRIMARY KEY,
                    chat_id INTEGER,
                    status TEXT, -- 'synced', 'skipped', 'irrelevant'
                    reason TEXT,
                    processed_at DATETIME
                )
            """)
            # Migratsiya: ustunlarni qo'shish (agar bo'lmasa)
            columns = [
                ("is_lead_forwarded", "BOOLEAN DEFAULT 0"),
                ("phone", "TEXT"),
                ("business_type", "TEXT"),
                ("region", "TEXT"),
                ("brand_name", "TEXT"),
                ("service_type", "TEXT"),
                ("deadline", "TEXT"),
                ("meeting_time", "TEXT"),
                ("meeting_status", "TEXT DEFAULT 'pending'"),
                ("last_name", "TEXT"),
                ("contact_name", "TEXT"),
                ("bio", "TEXT"),
                ("avatar_analysis", "TEXT"),
                ("mutual_groups_count", "INTEGER DEFAULT 0"),
                ("social_analysis", "TEXT"),
                ("lead_score", "INTEGER DEFAULT 0"),
                ("role", "TEXT"),
                ("position", "TEXT"),
                ("intent", "TEXT")
            ]
            for col_name, col_type in columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass 
            
            # Migration for Enterprise v2: detailed_role
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN detailed_role TEXT")
            except Exception:
                pass

            # New table for departmental targets (Sales quotas, etc.)
            cursor.execute('''CREATE TABLE IF NOT EXISTS department_targets
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                              dept_name TEXT, 
                              target_type TEXT, 
                              target_value REAL, 
                              month TEXT, 
                              assigned_to TEXT)''')

            # Yangi: Topshiriqlar jadvali (HR Task Manager uchun)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    description TEXT,
                    assigned_to INTEGER, -- Xodimning User ID si
                    deadline DATETIME,
                    priority TEXT DEFAULT 'Medium', -- Low, Medium, High
                    status TEXT DEFAULT 'Pending', -- Pending, In Progress, Completed, Overdue
                    created_by INTEGER,
                    created_at DATETIME,
                    completed_at DATETIME
                )
            """)
            
            # Xabarlar logi
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_text TEXT,
                    is_ai_reply BOOLEAN,
                    created_at DATETIME
                )
            """)
            
            # Strategik Mentor (Advisor) loglari
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS advisor_logs (
                    chat_id INTEGER,
                    message_id INTEGER,
                    advice_type TEXT, -- 'meeting', 'task', 'tactical'
                    content TEXT,
                    created_at DATETIME,
                    PRIMARY KEY (chat_id, message_id, advice_type)
                )
            """)
            
            # Telegram Stars xaridlari
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id TEXT,
                    amount_stars INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME
                )
            """)

            # O'rganilgan ma'lumotlar (Self-learning)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_key TEXT,
                    fact_value TEXT,
                    user_id INTEGER,
                    created_at DATETIME
                )
            """)

            # AI Agent amallar logi
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT,
                    action_data TEXT,
                    success BOOLEAN DEFAULT 1,
                    created_at DATETIME
                )
            """)

            # Yangi: Foydalanuvchi harakatlari logi (Activity Audit uchun)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT, -- 'text', 'forward', 'reply'
                    chat_id INTEGER, -- Qayerga yuborildi
                    chat_name TEXT, -- Chat nomi
                    source_chat_id INTEGER, -- Forward bo'lsa qayerdan keldi
                    source_name TEXT, -- Forward manba nomi
                    content TEXT, -- Xabar matni (preview)
                    metadata TEXT, -- JSON formatda qo'shimcha ma'lumotlar
                    created_at DATETIME
                )
            """)
            
            # Yangi: AmoCRMga sinxronizatsiya qilingan foydalanuvchilar (Deduplikatsiya uchun)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crm_sync_status (
                    user_id INTEGER PRIMARY KEY,
                    amo_lead_id INTEGER,
                    status TEXT DEFAULT 'synced',
                    synced_at DATETIME
                )
            """)

            # Yangi: Jamoa kunlik hisoboti (Systematic Enforcement)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    report_date TEXT, -- 'YYYY-MM-DD'
                    report_type TEXT, -- 'morning_plan', 'evening_result', 'kpi_update'
                    content TEXT,
                    status TEXT DEFAULT 'submitted', -- 'submitted', 'late', 'missing'
                    created_at DATETIME
                )
            """)
            
            # Yangi: Rejalashtirilgan vazifalar (Duplicate run oldini olish uchun)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    job_name TEXT,
                    run_date TEXT, -- 'YYYY-MM-DD'
                    created_at DATETIME,
                    PRIMARY KEY (job_name, run_date)
                )
            """)

            # Yangi: Kunlik planlar (Lead IDs assign qilingan)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT, -- 'YYYY-MM-DD'
                    manager_id INTEGER,
                    lead_id INTEGER,
                    lead_name TEXT,
                    mission TEXT,
                    status TEXT DEFAULT 'planned', -- 'planned', 'achieved', 'missed'
                    created_at DATETIME
                )
            """)
            
            # MetaSell: Call/Conversation Analysis (scoring, coaching)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS call_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    salesperson_id INTEGER,
                    salesperson_name TEXT,
                    conversation_text TEXT,
                    total_score INTEGER DEFAULT 0,
                    greeting_score INTEGER DEFAULT 0,
                    needs_discovery_score INTEGER DEFAULT 0,
                    pitch_score INTEGER DEFAULT 0,
                    objection_score INTEGER DEFAULT 0,
                    closing_score INTEGER DEFAULT 0,
                    strengths TEXT,
                    weaknesses TEXT,
                    next_steps TEXT,
                    coaching_tip TEXT,
                    summary TEXT,
                    source TEXT DEFAULT 'text',
                    analyzed_at DATETIME
                )
            """)

            # Yangi: Tizim sozlamalari (Round-robin index va boshqalar uchun)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kv_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME
                )
            """)
            
            conn.commit()
            logger.info("[DB] Baza tayyor.")
        except Exception as e:
            logger.error(f"[DB ERROR] init_db: {e}")
        finally:
            if conn: conn.close()

    def set_state(self, key: str, value: Any):
        """Tizim holati yoki sozlamasini saqlash."""
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO kv_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, str(value), now))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] set_state ({key}): {e}")
            return False

    def get_state(self, key: str, default: Any = None) -> Any:
        """Tizim holati yoki sozlamasini o'qish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM kv_settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception as e:
            logger.error(f"[DB ERROR] get_state ({key}): {e}")
            return default

    def get_synced_contacts_count(self) -> int:
        """Sinxronlangan (telefon raqami bor) kontaktlar sonini qaytarish."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL AND phone != ''")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"[DB ERROR] Sanoq olishda xato: {e}")
            return 0
        finally:
            if conn: conn.close()

    def is_crm_synced(self, user_id: int) -> bool:
        """Foydalanuvchi AmoCRMga allaqachon qo'shilganmi?"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM crm_sync_status WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[DB ERROR] is_crm_synced: {e}")
            return False
        finally:
            if conn: conn.close()

    def mark_crm_synced(self, user_id: int, lead_id: int = None):
        """Foydalanuvchini AmoCRMga qo'shilgan deb belgilash."""
        now = datetime.datetime.now().isoformat()
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO crm_sync_status (user_id, amo_lead_id, synced_at)
                VALUES (?, ?, ?)
            """, (user_id, lead_id, now))
            conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] mark_crm_synced: {e}")
        finally:
            if conn: conn.close()

    def is_message_processed(self, message_id: int) -> bool:
        """Xabar allaqachon qayta ishlanganligini tekshirish."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[DB ERROR] is_message_processed: {e}")
            return False
        finally:
            if conn: conn.close()

    def mark_message_processed(self, message_id: int, chat_id: int, status: str = 'synced', reason: str = None):
        """Xabarni qayta ishlangan deb belgilash."""
        now = datetime.datetime.now().isoformat()
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO processed_messages (message_id, chat_id, status, reason, processed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, chat_id, status, reason, now))
            conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] mark_message_processed: {e}")
        finally:
            if conn: conn.close()

    def upsert_user(self, user_id, first_name, username=None, phone=None, **kwargs):
        """Foydalanuvchi ma'lumotlarini yangilash yoki qo'shish."""
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                update_fields = ["first_name=excluded.first_name", "username=excluded.username", "last_seen=excluded.last_seen"]
                if phone: update_fields.append("phone=COALESCE(excluded.phone, users.phone)")
                
                for key in kwargs:
                    if key in ["business_type", "region", "brand_name", "service_type", "deadline", 
                                "last_name", "contact_name", "bio", "avatar_analysis", "social_analysis", 
                                "meeting_time", "meeting_status", "lead_score", "position", "role", "intent"]:
                        update_fields.append(f"{key}=COALESCE(excluded.{key}, users.{key})")

                query = f"""
                    INSERT INTO users (user_id, first_name, username, phone, 
                                     business_type, region, brand_name, service_type, deadline, 
                                     last_name, contact_name, bio, avatar_analysis, social_analysis,
                                     role, position, intent, 
                                     last_seen, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        {", ".join(update_fields)}
                """
                params = (user_id, first_name, username, phone, 
                          kwargs.get("business_type"), kwargs.get("region"), kwargs.get("brand_name"), 
                          kwargs.get("service_type"), kwargs.get("deadline"), 
                          kwargs.get("last_name"), kwargs.get("contact_name"), kwargs.get("bio"), 
                          kwargs.get("avatar_analysis"), kwargs.get("social_analysis"),
                          kwargs.get("role"), kwargs.get("position"), kwargs.get("intent"),
                          now, now)
                cursor.execute(query, params)
                conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] upsert_user: {e}")
        finally:
            if conn: conn.close()

    def log_message(self, user_id, text, is_ai=False):
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (?, ?, ?, ?)", (user_id, text, is_ai, now))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] log_message: {e}")
        finally:
            if conn: conn.close()

    def get_user_info(self, user_id):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, username, phone, business_type, region, brand_name, service_type, deadline, is_lead_forwarded, meeting_time, meeting_status FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return {"first_name": row[0], "username": row[1], "phone": row[2], "business_type": row[3], "region": row[4], "brand_name": row[5], "service_type": row[6], "deadline": row[7], "is_lead_forwarded": row[8], "meeting_time": row[9], "meeting_status": row[10]}
                return None
        except Exception as e:
            logger.error(f"[DB ERROR] get_user_info: {e}")
            return None
        finally:
            if conn: conn.close()

    def update_meeting(self, user_id, meeting_time, status='scheduled'):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET meeting_time = ?, meeting_status = ? WHERE user_id = ?", (meeting_time, status, user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] update_meeting: {e}")
            return False
        finally:
            if conn: conn.close()

    def get_recent_messages(self, user_id, limit=1000):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT message_text, is_ai_reply FROM message_logs WHERE user_id = ? AND message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT ?", (user_id, limit))
                rows = cursor.fetchall()
                history = []
                for text, is_ai in reversed(rows):
                    role = "model" if is_ai else "user"
                    if text.startswith("ERROR:"): continue
                    history.append({"role": role, "parts": [{"text": text}]})
                if history and history[0]["role"] == "model": history.pop(0)
                sanitized_history = []
                last_role = None
                for entry in history:
                    if entry["role"] != last_role:
                        sanitized_history.append(entry)
                        last_role = entry["role"]
                return sanitized_history
        except Exception as e:
            logger.error(f"[DB ERROR] get_recent_messages: {e}")
            return []
        finally:
            if conn: conn.close()

    def get_daily_chats_summary(self):
        """Oxirgi 24 soatlik muloqotlarni foydalanuvchilar bo'yicha guruhlab olish."""
        one_day_ago = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT 
                        ml.user_id, 
                        u.first_name, 
                        u.username,
                        ml.message_text, 
                        ml.is_ai_reply, 
                        ml.created_at
                    FROM message_logs ml
                    LEFT JOIN users u ON ml.user_id = u.user_id
                    WHERE ml.created_at >= ?
                    ORDER BY ml.user_id, ml.created_at ASC
                """
                print(f"[DEBUG REPORT] Query start time: {one_day_ago}")
                cursor.execute(query, (one_day_ago,))
                rows = cursor.fetchall()
                print(f"[DEBUG REPORT] Rows found: {len(rows)}")
                
                chats = {}
                for uid, name, uname, text, is_ai, time in rows:
                    if uid not in chats:
                        chats[uid] = {
                            "name": name or f"User_{uid}",
                            "username": uname or "yo'q",
                            "messages": []
                        }
                    role = "OISHA" if is_ai else "Mijoz"
                    chats[uid]["messages"].append(f"{role} ({time}): {text}")
                
                return chats
        except Exception as e:
            logger.error(f"[DB ERROR] get_daily_chats_summary: {e}")
            return {}
        finally:
            if conn: conn.close()

    def get_recent_all_messages(self, limit=50):
        """Barcha chatlardan oxirgi xabarlarni olish (Task analysis uchun)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, message_text, created_at FROM message_logs WHERE message_text IS NOT NULL AND message_text != '' ORDER BY created_at DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return rows # [(user_id, text, time), ...]
        except Exception as e:
            logger.error(f"[DB ERROR] get_recent_all_messages: {e}")
            return []
        finally:
            if conn: conn.close()

    def add_learned_fact(self, key, value, user_id=None):
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO learned_facts (fact_key, fact_value, user_id, created_at) VALUES (?, ?, ?, ?)", (key, value, user_id, now))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] add_learned_fact: {e}")
            return False
        finally:
            if conn: conn.close()

    def get_all_learned_facts(self, user_id=None, limit=100):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if user_id:
                    cursor.execute("SELECT fact_key, fact_value FROM learned_facts WHERE user_id IS NULL OR user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
                else:
                    cursor.execute("SELECT fact_key, fact_value FROM learned_facts WHERE user_id IS NULL ORDER BY created_at DESC LIMIT ?", (limit,))
                rows = cursor.fetchall() or []
                return [(str(r[0]), str(r[1])) for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_all_learned_facts: {e}")
            return []
        finally:
            if conn: conn.close()

    def get_all_users(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users")
                rows = cursor.fetchall() or []
                return [int(row[0]) for row in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_all_users: {e}")
            return []

    def get_stats(self):
        """Umumiy statistika."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM message_logs")
                total_messages = cursor.fetchone()[0] or 0
                return {"total_users": total_users, "total_messages": total_messages}
        except Exception as e:
            logger.error(f"[DB ERROR] get_stats: {e}")
            return {"total_users": 0, "total_messages": 0}
        finally:
            if conn: conn.close()

    def log_agent_action(self, user_id, action_type, action_data_json, success=True):
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO agent_actions (user_id, action_type, action_data, success, created_at) VALUES (?, ?, ?, ?, ?)", (user_id, action_type, action_data_json, success, now))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] log_agent_action: {e}")
        finally:
            if conn: conn.close()

    def log_user_activity(self, event_type, chat_id, chat_name=None, source_chat_id=None, source_name=None, content=None, metadata=None):
        """Foydalanuvchi harakatlarini loglash (Audit uchun)."""
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_activity_logs (event_type, chat_id, chat_name, source_chat_id, source_name, content, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (event_type, chat_id, chat_name, source_chat_id, source_name, content, metadata, now))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] log_user_activity: {e}")
        finally:
            if conn: conn.close()

    def get_recent_agent_actions(self, limit=20):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, action_type, action_data, success, created_at FROM agent_actions ORDER BY created_at DESC LIMIT ?", (limit,))
                rows = cursor.fetchall() or []
                return [{"user_id": r[0], "action_type": r[1], "action_data": r[2], "success": bool(r[3]), "created_at": r[4]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_recent_agent_actions: {e}")
            return []
        finally:
            if conn: conn.close()

    def get_recent_leads(self, limit=5):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, first_name, phone, business_type, service_type, last_seen FROM users WHERE phone IS NOT NULL ORDER BY last_seen DESC LIMIT ?", (limit,))
                rows = cursor.fetchall() or []
                return [{"user_id": r[0], "name": r[1], "phone": r[2], "business_type": r[3], "service_type": r[4], "last_seen": r[5]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_recent_leads: {e}")
            return []
        finally:
            if conn: conn.close()

    async def get_user_id_by_phone(self, phone: str) -> Optional[int]:
        """Telefon raqami orqali foydalanuvchi ID sini topish."""
        # Telefon raqamidagi ortiqcha belgi va bo'shliqlarni olib tashlaymiz
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # LIKE orqali qisman moslikni tekshirish (chunki ba'zan + bilan ba'zan + siz saqlanadi)
                cursor.execute("SELECT user_id FROM users WHERE phone LIKE ?", (f"%{clean_phone}",))
                row = cursor.fetchone()
                return int(row[0]) if row else None
        except Exception as e:
            logger.error(f"[DB ERROR] get_user_id_by_phone: {e}")
            return None
        finally:
            if conn: conn.close()

    def get_user_by_phone_full(self, phone: str) -> Optional[Dict[str, Any]]:
        """Telefon raqami orqali foydalanuvchi ma'lumotlarini to'liq topish."""
        # Telefon raqamidagi ortiqcha belgi va bo'shliqlarni olib tashlaymiz
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        if not clean_phone: return None
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # LIKE orqali qisman moslikni tekshirish
                cursor.execute("""
                    SELECT user_id, username, first_name, last_name 
                    FROM users 
                    WHERE phone LIKE ? 
                    LIMIT 1
                """, (f"%{clean_phone}",))
                row = cursor.fetchone()
                if row:
                    return {
                        "user_id": row[0],
                        "username": row[1],
                        "first_name": row[2],
                        "last_name": row[3]
                    }
                return None
        except Exception as e:
            logger.error(f"[DB ERROR] get_user_by_phone_full: {e}")
            return None
        finally:
            if conn: conn.close()

    def get_daily_report_stats(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen LIKE ?", (f"{today}%",))
                active_users_today = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM users WHERE meeting_status = 'scheduled' AND last_seen LIKE ?", (f"{today}%",))
                meetings_today = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM purchases WHERE status = 'pending' AND created_at LIKE ?", (f"{today}%",))
                pending_payments = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM purchases WHERE status = 'completed' AND created_at LIKE ?", (f"{today}%",))
                completed_payments = cursor.fetchone()[0] or 0
                cursor.execute("SELECT SUM(amount_stars) FROM purchases WHERE status = 'completed' AND created_at LIKE ?", (f"{today}%",))
                total_revenue = cursor.fetchone()[0] or 0
                return {"active_leads": active_users_today, "meetings": meetings_today, "pending_pays": pending_payments, "completed_pays": completed_payments, "revenue_stars": total_revenue}
        except Exception as e:
            logger.error(f"[DB ERROR] get_daily_report_stats: {e}")
            return {"active_leads": 0, "meetings": 0, "pending_pays": 0, "completed_pays": 0, "revenue_stars": 0}
        finally:
            if conn: conn.close()

    def get_today_stats(self) -> Dict[str, Any]:
        """Bugungi asosiy amallar va lidlar statistikasini qaytarish."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        stats = {
            "leads_found": 0,
            "messages_synced": 0,
            "private_chats": 0,
            "contacts_added": 0
        }
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM processed_messages WHERE status='synced' AND timestamp LIKE ?", (f"{today}%",))
                stats["leads_found"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM processed_messages WHERE status='synced_chat' AND timestamp LIKE ?", (f"{today}%",))
                stats["messages_synced"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM processed_messages WHERE status='synced_mass' AND timestamp LIKE ?", (f"{today}%",))
                stats["contacts_added"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM users WHERE crm_synced=1 AND last_seen LIKE ?", (f"{today}%",))
                stats["private_chats"] = cursor.fetchone()[0]
            return stats
        except Exception as e:
            logger.error(f"[DB STATS ERROR] {e}")
            return stats

    def add_task(self, assigned_to: int, description: str, deadline: str, title: str = None, created_by: int = None, priority: str = 'Medium'):
        """Vazifa qo'shish (Xavfsiz va to'liq)."""
        now = datetime.datetime.now().isoformat()
        if not title:
            title = description[:30] + "..." if len(description) > 30 else description
            
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (title, description, assigned_to, deadline, priority, created_by, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (title, description, assigned_to, deadline, priority, created_by, now))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"[DB ERROR] add_task: {e}")
            return None
        finally:
            if conn: conn.close()

    def complete_task(self, task_id: int):
        """Vazifani yakunlash."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tasks SET status = 'completed', completed_at = DATETIME('now') WHERE id = ?", (task_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[DB ERROR] complete_task: {e}")
            return False
        finally:
            if conn: conn.close()

    def save_daily_plan(self, manager_id: int, lead_id: int, lead_name: str, mission: str):
        """Kunlik plans saqlash."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO daily_plans (report_date, manager_id, lead_id, lead_name, mission, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (today, manager_id, lead_id, lead_name, mission, now))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] save_daily_plan: {e}")
            return False

    def get_daily_plan(self, date_str: str = None) -> List[Dict[str, Any]]:
        """Berilgan sana uchun planlarni olish."""
        if not date_str:
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT manager_id, lead_id, lead_name, mission, status FROM daily_plans WHERE report_date = ?", (date_str,))
                rows = cursor.fetchall()
                return [{"manager_id": r[0], "lead_id": r[1], "lead_name": r[2], "mission": r[3], "status": r[4]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_daily_plan: {e}")
            return []

    def get_pending_tasks(self, limit=10):
        """Barcha ochiq vazifalarni olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, assigned_to, description, deadline, created_at FROM tasks WHERE status = 'Pending' ORDER BY deadline ASC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return [{"task_id": r[0], "assigned_to": r[1], "description": r[2], "deadline": r[3], "created_at": r[4]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_pending_tasks: {e}")
            return []
        finally:
            if conn: conn.close()

    def get_all_tasks(self, limit=50):
        """Barcha vazifalarni olish (debug uchun)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title, description, assigned_to, deadline, status FROM tasks ORDER BY id DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return [{"id": r[0], "title": r[1], "description": r[2], "assigned_to": r[3], "deadline": r[4], "status": r[5]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_all_tasks: {e}")
            return []

    def set_user_role(self, user_id: int, role: str):
        """Foydalanuvchiga jamoaviy rol biriktirish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[DB ERROR] set_user_role: {e}")
            return False

    def get_team_roles(self):
        """Hamma xodimlar va ularning rollarini olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, username, first_name, role FROM users WHERE role IS NOT NULL")
                rows = cursor.fetchall() or []
                return [{"user_id": r[0], "username": r[1], "name": r[2], "role": r[3]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_team_roles: {e}")
            return []

    def get_user_by_role(self, role: str):
        """Berilgan roldagi foydalanuvchini olish (birinchi mos kelgani)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, username, first_name, role FROM users WHERE role = ? LIMIT 1", (role,))
                row = cursor.fetchone()
                if row:
                    return {"user_id": row[0], "username": row[1], "name": row[2], "role": row[3] if len(row)>3 else role}
                return None
        except Exception as e:
            logger.error(f"[DB ERROR] get_user_by_role: {e}")
            return None

    def get_overdue_tasks(self):
        """Muddati o'tgan (Completed bo'lmagan) vazifalarni olish."""
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.id, t.title, t.description, t.assigned_to, t.deadline, u.first_name, u.username
                    FROM tasks t
                    LEFT JOIN users u ON t.assigned_to = u.user_id
                    WHERE t.status != 'Completed' AND t.deadline < ?
                    ORDER BY t.deadline ASC
                """, (now,))
                rows = cursor.fetchall() or []
                return [
                    {
                        "id": r[0], "title": r[1], "description": r[2], 
                        "assigned_to": r[3], "deadline": r[4], 
                        "name": r[5] or "Unknown", "username": r[6]
                    } for r in rows
                ]
        except Exception as e:
            logger.error(f"[DB ERROR] get_overdue_tasks: {e}")
            return []

    def get_missing_reports(self, report_date=None):
        """Berilgan kunda hisobot topshirmagan jamoa a'zolarini topish."""
        if not report_date:
            report_date = datetime.datetime.now().strftime('%Y-%m-%d')
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Jamoa a'zolari (roli borlar)
                cursor.execute("""
                    SELECT user_id, first_name, username, role 
                    FROM users 
                    WHERE role IS NOT NULL AND role != ''
                """)
                team = cursor.fetchall() or []
                
                missing = []
                for uid, name, uname, role in team:
                    cursor.execute("SELECT 1 FROM team_reports WHERE user_id = ? AND report_date = ?", (uid, report_date))
                    if not cursor.fetchone():
                        missing.append({"user_id": uid, "name": name, "username": uname, "role": role})
                return missing
        except Exception as e:
            logger.error(f"[DB ERROR] get_missing_reports: {e}")
            return []

    def get_priority_tasks(self, limit: int = 3):
        """Bugun yoki ertaga tugaydigan eng muhim (High priority) vazifalarni olish."""
        now = datetime.datetime.now().isoformat()
        soon = (datetime.datetime.now() + datetime.timedelta(days=2)).isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.id, t.title, t.description, t.assigned_to, t.deadline, u.first_name, u.username
                    FROM tasks t
                    LEFT JOIN users u ON t.assigned_to = u.user_id
                    WHERE t.status != 'Completed' AND t.deadline BETWEEN ? AND ?
                    ORDER BY t.priority DESC, t.deadline ASC
                    LIMIT ?
                """, (now, soon, limit))
                rows = cursor.fetchall() or []
                return [
                    {
                        "id": r[0], "title": r[1], "description": r[2], 
                        "assigned_to": r[3], "deadline": r[4], 
                        "name": r[5], "username": r[6]
                    } for r in rows
                ]
        except Exception as e:
            logger.error(f"[DB ERROR] get_priority_tasks: {e}")
            return []

    def get_task_completion_stats(self, days=1):
        """Xodimlar bo'yicha vazifa bajarish statistikasini olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT assigned_username, 
                           COUNT(*) as total, 
                           SUM(CASE WHEN LOWER(status) = 'completed' THEN 1 ELSE 0 END) as completed
                    FROM tasks 
                    WHERE created_at >= date('now', ?)
                    GROUP BY assigned_username
                """
                cursor.execute(query, (f'-{days} days',))
                rows = cursor.fetchall() or []
                return [{"username": r[0], "total": r[1], "completed": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_task_completion_stats: {e}")
            return []

    def is_team_member(self, user_id: int):
        """Foydalanuvchi jamoada bor-yo'qligini tekshirish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role FROM users WHERE user_id = ? AND role IS NOT NULL", (user_id,))
                row = cursor.fetchone()
                return row is not None
        except Exception as e:
            logger.error(f"[DB ERROR] is_team_member: {e}")
            return False

    def get_recent_user_activity(self, limit=100):
        """Audit uchun foydalanuvchi loglarini olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event_type, chat_name, source_name, content, metadata, created_at 
                    FROM user_activity_logs 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall() or []
                return [
                    {"type": r[0], "chat": r[1], "source": r[2], "content": r[3], "meta": r[4], "time": r[5]} 
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"[DB ERROR] get_recent_user_activity: {e}")
            return []
        finally:
            if conn: conn.close()

    def update_user_detailed_role(self, identifier: str, detailed_role: str):
        """Foydalanuvchi identifikatori (ID yoki Username) orqali batafsil rolni yangilash."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if identifier.startswith('@'):
                    cursor.execute("UPDATE users SET detailed_role = ? WHERE username = ?", (detailed_role, identifier))
                else:
                    cursor.execute("UPDATE users SET detailed_role = ? WHERE user_id = ?", (detailed_role, identifier))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] update_user_detailed_role: {e}")
            return False

    def set_department_target(self, dept_name: str, target_type: str, value: float, month: str, assigned_to: str = None):
        """Departament yoki xodim uchun oylik rejani o'rnatish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO department_targets (dept_name, target_type, target_value, month, assigned_to)
                    VALUES (?, ?, ?, ?, ?)
                """, (dept_name, target_type, value, month, assigned_to))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] set_department_target: {e}")
            return False

    def get_department_targets(self, month: str):
        """Berilgan oy uchun barcha rejalar/kvotalarni olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT dept_name, target_type, target_value, assigned_to FROM department_targets WHERE month = ?", (month,))
                rows = cursor.fetchall() or []
                return [{"dept": r[0], "type": r[1], "value": r[2], "assigned": r[3]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_department_targets: {e}")
            return []

    def is_job_run(self, job_name: str, run_date: str) -> bool:
        """Berilgan kundagi vazifa bajarilganmi?"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM scheduled_jobs WHERE job_name = ? AND run_date = ?", (job_name, run_date))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[DB ERROR] is_job_run: {e}")
            return False
        finally:
            if conn: conn.close()

    def mark_job_run(self, job_name: str, run_date: str):
        """Vazifani bajarilgan deb belgilash."""
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO scheduled_jobs (job_name, run_date, created_at)
                    VALUES (?, ?, ?)
                """, (job_name, run_date, now))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] mark_job_run: {e}")
            return False
        finally:
            if conn: conn.close()

    def set_user_role(self, user_id: int, role: str):
        """Foydalanuvchiga professional rol (Designer, PM, etc.) biriktirish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] set_user_role: {e}")
            return False
        finally:
            if conn: conn.close()

    def log_message(self, user_id: int, text: str, is_ai: bool = False):
        """Xabarni bazaga yozish (Wazzup Killer tarixi uchun)."""
        now = datetime.datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        text TEXT,
                        is_ai BOOLEAN,
                        created_at DATETIME
                    )
                """)
                cursor.execute("""
                    INSERT INTO messages (user_id, text, is_ai, created_at)
                    VALUES (?, ?, ?, ?)
                """, (user_id, text, is_ai, now))
                conn.commit()
        except Exception as e:
            logger.error(f"[DB ERROR] log_message: {e}")

    def get_recent_messages(self, user_id: int, limit: int = 50):
        """Mijoz bilan ohirgi suhbat tarixini olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, user_id, text, is_ai, created_at 
                    FROM messages 
                    WHERE user_id = ? 
                    ORDER BY created_at ASC 
                    LIMIT ?
                """, (user_id, limit))
                rows = cursor.fetchall() or []
                return [{"role": "model" if r[3] else "user", "parts": [{"text": r[2]}], "time": r[4]} for r in rows]
        except Exception as e:
            logger.error(f"[DB ERROR] get_recent_messages: {e}")
            return []

    def set_state(self, key: str, value: str):
        """KV sozlamani bazada saqlash."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kv_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                cursor.execute("INSERT OR REPLACE INTO kv_settings (key, value) VALUES (?, ?)", (key, value))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[DB ERROR] set_state: {e}")
            return False

    def get_state(self, key: str, default: Any = None):
        """KV sozlamani bazadan olish."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM kv_settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else default
        except Exception as e:
            # logger.debug(f"[DB DEBUG] get_state for {key} fail (maybe table not exists): {e}")
            return default
