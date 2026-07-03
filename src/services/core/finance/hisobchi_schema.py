"""Hisobchi AI — DB schema, dataclasses, and storage factory."""

from __future__ import annotations

from collections.abc import Mapping
import structlog
from dataclasses import dataclass
from typing import Any, Optional

from src.database_pool import SmartRow

logger = structlog.get_logger()


@dataclass
class CardTransaction:
    id: int
    source_bot: str
    direction: str       # 'out' | 'in'
    amount: int          # UZS (butun son)
    merchant: str
    card_suffix: str
    tx_time: str
    balance: Optional[int]
    category: Optional[str]
    raw_text: str
    finance_msg_id: Optional[int]
    finance_chat_id: Optional[int]
    status: str          # 'pending' | 'categorized' | 'skipped'
    created_at: str
    ownership: str
    fingerprint: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class MerchantMemory:
    id: int
    merchant_pattern: str
    category: str
    use_count: int
    updated_at: str


_CREATE_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS hisobchi_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_bot TEXT NOT NULL,
    direction TEXT NOT NULL,
    amount INTEGER NOT NULL,
    merchant TEXT NOT NULL,
    card_suffix TEXT DEFAULT '',
    tx_time TEXT,
    balance INTEGER,
    category TEXT,
    ownership TEXT DEFAULT 'business',
    raw_text TEXT,
    finance_msg_id INTEGER,
    finance_chat_id INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_MERCHANT_MEMORY = """
CREATE TABLE IF NOT EXISTS hisobchi_merchant_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_pattern TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    use_count INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_CATEGORY_RULES = """
CREATE TABLE IF NOT EXISTS hisobchi_category_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_pattern TEXT NOT NULL,
    card_suffix TEXT NOT NULL,
    direction TEXT NOT NULL,
    amount INTEGER NOT NULL,
    category TEXT NOT NULL,
    ownership TEXT DEFAULT 'business',
    confirmations INTEGER DEFAULT 1,
    conflicts INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(merchant_pattern, card_suffix, direction, amount)
)
"""

_MIGRATIONS = [_CREATE_TRANSACTIONS, _CREATE_MERCHANT_MEMORY, _CREATE_CATEGORY_RULES]

_COLUMN_MIGRATIONS = (
    "ALTER TABLE hisobchi_transactions ADD COLUMN ownership TEXT DEFAULT 'business'",
    "ALTER TABLE hisobchi_transactions ADD COLUMN fingerprint TEXT",
    "ALTER TABLE hisobchi_transactions ADD COLUMN reason TEXT",
    "ALTER TABLE hisobchi_transactions ADD COLUMN source_message_id INTEGER",
)


class HisobchiDatabaseAdapter:
    """SQL database adapter (Turso/SQLite)."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def execute(self, query: str, params: Optional[list] = None) -> list:
        conn = await self.database.get_connection()
        async with conn.execute(query, params or []) as cursor:
            description = getattr(cursor, "description", None) or []
            columns = [desc[0] for desc in description]
            rows = await cursor.fetchall()
            if rows and not columns and isinstance(rows[0], Mapping):
                columns = list(rows[0].keys())
            return [
                SmartRow(
                    [row.get(column) for column in columns]
                    if isinstance(row, Mapping)
                    else row,
                    columns,
                )
                for row in (rows or [])
            ]

    async def commit(self) -> None:
        conn = await self.database.get_connection()
        await conn.commit()

    async def get_connection(self):
        return await self.database.get_connection()


def ensure_hisobchi_db(db: Any) -> Any:
    if callable(getattr(db, "execute", None)) and callable(
        getattr(db, "commit", None)
    ):
        return db
    if callable(getattr(db, "get_connection", None)):
        return HisobchiDatabaseAdapter(db)
    raise TypeError("Hisobchi database must support execute/commit or get_connection")


async def init_hisobchi_tables(db=None) -> None:
    """Initialize SQL tables (only needed for DB backend)."""
    from src.database_pool import db_pool

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

    await _db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_hisobchi_tx_fingerprint "
        "ON hisobchi_transactions(fingerprint)"
    )

    await _db.commit()


async def init_hisobchi_gsheets(
    spreadsheet_id: str,
    credentials_path: str = "service_account.json",
) -> Any:
    """Initialize Google Sheets backend for hisobchi."""
    from src.services.core.hisobchi_gsheets import HisobchiGsheetStore

    store = HisobchiGsheetStore(spreadsheet_id, credentials_path)
    await store.init()
    return store


def create_hisobchi_engine(
    db=None,
    gs_store: Any = None,
) -> Any:
    """Factory: creates HisobchiEngine with the right backend."""
    from src.services.core.finance.hisobchi_engine import HisobchiEngine
    return HisobchiEngine(db=db, gs_store=gs_store)
