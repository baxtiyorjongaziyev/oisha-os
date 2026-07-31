"""Uzbek Entrepreneurs DB Schema - Global diaspora lead database."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

logger = __import__("logging").getLogger(__name__)


@dataclass
class UzbekEntrepreneur:
    id: int
    full_name: str
    first_name: str
    last_name: str
    phone: Optional[str]
    email: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    country: str
    city: Optional[str]
    linkedin_url: Optional[str]
    instagram_url: Optional[str]
    telegram_username: Optional[str]
    facebook_url: Optional[str]
    scraping_source: str  # 'linkedin', 'instagram', 'telegram', 'facebook', 'manual'
    source_url: Optional[str]
    lead_score: int  # 0-100, based on profile quality
    call_status: str  # 'pending', 'called', 'interested', 'not_interested', 'disconnected'
    call_attempts: int
    last_call_date: Optional[str]
    amocrm_lead_id: Optional[int]
    notes: Optional[str]
    created_at: str
    updated_at: str


_CREATE_UZBEK_ENTREPRENEURS = """
CREATE TABLE IF NOT EXISTS uzbek_entrepreneurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    company TEXT,
    industry TEXT,
    country TEXT NOT NULL,
    city TEXT,
    linkedin_url TEXT UNIQUE,
    instagram_url TEXT UNIQUE,
    telegram_username TEXT UNIQUE,
    facebook_url TEXT UNIQUE,
    scraping_source TEXT NOT NULL,
    source_url TEXT,
    lead_score INTEGER DEFAULT 50,
    call_status TEXT DEFAULT 'pending',
    call_attempts INTEGER DEFAULT 0,
    last_call_date TEXT,
    amocrm_lead_id INTEGER UNIQUE,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_CALL_LOGS = """
CREATE TABLE IF NOT EXISTS entrepreneur_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entrepreneur_id INTEGER NOT NULL,
    call_date TEXT NOT NULL,
    call_duration_seconds INTEGER,
    call_result TEXT NOT NULL,  -- 'interested', 'not_interested', 'disconnected', 'callback'
    pressed_digit TEXT,  -- '1' or '2'
    transferred_to_operator BOOLEAN DEFAULT 0,
    operator_id INTEGER,
    notes TEXT,
    vapi_call_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entrepreneur_id) REFERENCES uzbek_entrepreneurs(id)
)
"""

_CREATE_SCRAPING_QUEUE = """
CREATE TABLE IF NOT EXISTS entrepreneur_scraping_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- 'linkedin', 'instagram', 'telegram', 'facebook'
    search_query TEXT,
    target_country TEXT,
    status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    started_at TEXT,
    completed_at TEXT,
    found_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_MIGRATIONS = [
    _CREATE_UZBEK_ENTREPRENEURS,
    _CREATE_CALL_LOGS,
    _CREATE_SCRAPING_QUEUE,
    # Call queue tables (from uzbek_call_queue.py)
    """CREATE TABLE IF NOT EXISTS entrepreneur_call_queue (
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
        FOREIGN KEY (entrepreneur_id) REFERENCES uzbek_entrepreneurs(id)
    )""",
    """CREATE TABLE IF NOT EXISTS call_operators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        telegram_id INTEGER UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        current_call_id INTEGER,
        total_calls_today INTEGER DEFAULT 0,
        last_call_time TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
]

_COLUMN_MIGRATIONS = [
    "ALTER TABLE uzbek_entrepreneurs ADD COLUMN whatsapp_number TEXT",
    "ALTER TABLE uzbek_entrepreneurs ADD COLUMN website TEXT",
    "ALTER TABLE uzbek_entrepreneurs ADD COLUMN employees_count INTEGER",
    "ALTER TABLE uzbek_entrepreneurs ADD COLUMN revenue_range TEXT",
]


async def init_uzbek_entrepreneurs_tables(db=None) -> None:
    """Initialize all tables for Uzbek Entrepreneurs system."""
    from src.database_pool import db_pool
    from src.services.core.finance.hisobchi_schema import ensure_hisobchi_db

    _db = ensure_hisobchi_db(db if db is not None else db_pool)

    for ddl in _MIGRATIONS:
        await _db.execute(ddl)

    for ddl in _COLUMN_MIGRATIONS:
        try:
            await _db.execute(ddl)
        except Exception as exc:
            message = str(exc).casefold()
            if not any(
                marker in message
                for marker in ("duplicate column", "already exists", "duplicate key")
            ):
                raise

    # Indexes for performance
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_uzbek_call_status "
        "ON uzbek_entrepreneurs(call_status)"
    )
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_uzbek_country "
        "ON uzbek_entrepreneurs(country)"
    )
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_uzbek_lead_score "
        "ON uzbek_entrepreneurs(lead_score)"
    )
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_call_logs_entrepreneur "
        "ON entrepreneur_call_logs(entrepreneur_id)"
    )

    await _db.commit()
    logger.info("[UZBEK_ENTREPRENEURS] Database tables initialized")
