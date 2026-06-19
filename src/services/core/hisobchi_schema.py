"""Hisobchi AI — DB schema and dataclasses for card transaction tracking."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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

_MIGRATIONS = [_CREATE_TRANSACTIONS, _CREATE_MERCHANT_MEMORY]


async def init_hisobchi_tables(db=None) -> None:
    from src.database_pool import DatabasePool, db_pool

    _db = db if isinstance(db, DatabasePool) else db_pool
    for ddl in _MIGRATIONS:
        await _db.execute(ddl)
    await _db.commit()
