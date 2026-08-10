"""`call_analyses` jadvalining yagona (kanonik) sxemasi.

MUAMMO (2026-08-10 gacha):
    `call_analyzer` har bir qo'ng'iroqni to'liq rubrik bo'yicha baholaydi
    (`sifat_bahosi`, `rubrik_baholar`, `lead_bahosi`) va natijani AmoCRM
    notasiga yozadi — lekin bazaga FAQAT matnli ustunlarni saqlardi.
    `sales_quality_coach` esa aynan `overall_score`, `manager_name`,
    `strengths`, `weaknesses`, `outcome`, `duration_seconds` ustunlarini
    o'qiydi. Ya'ni murabbiylik qatlami (kunlik hisobot, ideal skript,
    playbook takliflari) BO'SH ma'lumot ustida ishlagan va sotuvchi
    konversiyasiga hech qanday ta'sir qila olmagan.

Bu modul shu uzilishni yopadi: jadval bir joyda, to'liq ustunlar bilan
e'lon qilinadi va yetishmayotgan ustunlar mavjud bazaga idempotent
`ALTER TABLE` orqali qo'shiladi (namuna: `hisobchi_schema.py`).

Sxemani o'zgartirish kerak bo'lsa — FAQAT shu faylni o'zgartiring.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)

TABLE = "call_analyses"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS call_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT,
    lead_id INTEGER,
    manager_id INTEGER,
    manager_name TEXT,
    client_name TEXT,
    caller_phone TEXT,
    duration_seconds INTEGER DEFAULT 0,
    overall_score INTEGER DEFAULT 0,
    category TEXT,
    scores TEXT,
    summary TEXT,
    strengths TEXT,
    weaknesses TEXT,
    objections TEXT,
    client_mood TEXT,
    client_interest_level INTEGER DEFAULT 0,
    outcome TEXT,
    converted INTEGER DEFAULT 0,
    breakdown_at TEXT,
    breakdown_reason TEXT,
    longest_pause_seconds REAL DEFAULT 0,
    pauses TEXT,
    lead_price REAL DEFAULT 0,
    lead_won INTEGER,
    revenue_synced_at TEXT,
    next_steps TEXT,
    recommended_tasks TEXT,
    transcript TEXT,
    audio_url TEXT,
    task_id TEXT,
    task_created_at TEXT,
    source TEXT,
    analyzed_at TEXT,
    created_at TEXT
)
"""

# Mavjud (eski, tor) jadvalga qo'shiladigan ustunlar. Tartib muhim emas —
# har biri alohida, borligi tekshirilgandan keyin qo'shiladi.
_COLUMN_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("call_id", "TEXT"),
    ("lead_id", "INTEGER"),
    ("manager_id", "INTEGER"),
    ("manager_name", "TEXT"),
    ("client_name", "TEXT"),
    ("caller_phone", "TEXT"),
    ("duration_seconds", "INTEGER DEFAULT 0"),
    ("overall_score", "INTEGER DEFAULT 0"),
    ("category", "TEXT"),
    ("scores", "TEXT"),
    ("summary", "TEXT"),
    ("strengths", "TEXT"),
    ("weaknesses", "TEXT"),
    ("objections", "TEXT"),
    ("client_mood", "TEXT"),
    ("client_interest_level", "INTEGER DEFAULT 0"),
    ("outcome", "TEXT"),
    ("converted", "INTEGER DEFAULT 0"),
    # Uzilish lahzasi — "mijoz qaysi soniyada yo'qoldi"
    ("breakdown_at", "TEXT"),
    ("breakdown_reason", "TEXT"),
    ("longest_pause_seconds", "REAL DEFAULT 0"),
    ("pauses", "TEXT"),
    # Daromad — AmoCRM lead'idan sinxronlanadi (metasell_revenue.py)
    ("lead_price", "REAL DEFAULT 0"),
    ("lead_won", "INTEGER"),
    ("revenue_synced_at", "TEXT"),
    ("next_steps", "TEXT"),
    ("recommended_tasks", "TEXT"),
    ("transcript", "TEXT"),
    ("audio_url", "TEXT"),
    ("task_id", "TEXT"),
    ("task_created_at", "TEXT"),
    ("source", "TEXT"),
    ("analyzed_at", "TEXT"),
    ("created_at", "TEXT"),
)

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_call_analyses_call_id ON call_analyses(call_id)",
    "CREATE INDEX IF NOT EXISTS idx_call_analyses_created_at ON call_analyses(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_call_analyses_manager ON call_analyses(manager_name)",
    "CREATE INDEX IF NOT EXISTS idx_call_analyses_lead_id ON call_analyses(lead_id)",
)

# Har bir jarayonda bir marta bajariladi — `_log_call_analysis` har
# qo'ng'iroqda PRAGMA yugurtirmasligi uchun.
_ensured: Set[int] = set()


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _is_benign(exc: Exception) -> bool:
    """"Allaqachon bor" turidagi xatolar — migratsiya uchun normal holat."""
    text = str(exc).lower()
    return (
        "duplicate column" in text
        or "already exists" in text
        or "duplicate key" in text
    )


async def _existing_columns(conn: Any) -> Set[str]:
    try:
        cursor = await _maybe_await(conn.execute(f"PRAGMA table_info({TABLE})"))
        rows = await _maybe_await(cursor.fetchall())
    except Exception as exc:
        logger.warning("[CALL SCHEMA] PRAGMA o'qilmadi: %s", exc)
        return set()

    columns: Set[str] = set()
    for row in rows or []:
        # Turso dict, aiosqlite tuple qaytaradi — ikkalasi ham qo'llanadi.
        if isinstance(row, dict):
            name = row.get("name")
        else:
            try:
                name = row[1]
            except (IndexError, TypeError):
                name = None
        if name:
            columns.add(str(name))
    return columns


async def ensure_call_analysis_schema(db: Any, *, force: bool = False) -> bool:
    """Jadval va barcha MetaSell ustunlari borligiga kafolat beradi.

    Idempotent va "fail-soft": migratsiya yiqilsa ham chaqiruvchi oqim
    (qo'ng'iroq tahlili) to'xtamasligi kerak — shuning uchun False
    qaytaradi, exception ko'tarmaydi.
    """
    if db is None:
        return False
    if not force and id(db) in _ensured:
        return True

    try:
        conn = await _maybe_await(db.get_connection())
    except Exception as exc:
        logger.warning("[CALL SCHEMA] DB ulanmadi: %s", exc)
        return False
    if conn is None:
        return False

    try:
        await _maybe_await(conn.execute(_CREATE_TABLE))

        existing = await _existing_columns(conn)
        for column, col_type in _COLUMN_MIGRATIONS:
            if existing and column in existing:
                continue
            try:
                await _maybe_await(
                    conn.execute(
                        f"ALTER TABLE {TABLE} ADD COLUMN {column} {col_type}"
                    )
                )
                logger.info("[CALL SCHEMA] Ustun qo'shildi: %s", column)
            except Exception as exc:
                if not _is_benign(exc):
                    logger.warning(
                        "[CALL SCHEMA] '%s' ustunini qo'shib bo'lmadi: %s", column, exc
                    )

        for statement in _INDEXES:
            try:
                await _maybe_await(conn.execute(statement))
            except Exception as exc:
                if not _is_benign(exc):
                    logger.warning("[CALL SCHEMA] Indeks yaratilmadi: %s", exc)

        await _maybe_await(conn.commit())
    except Exception as exc:
        logger.warning("[CALL SCHEMA] Migratsiya yiqildi: %s", exc)
        return False

    _ensured.add(id(db))
    return True


def reset_schema_cache() -> None:
    """Testlar uchun: har bir yangi DB'da migratsiya qayta yugursin."""
    _ensured.clear()


def analysis_row_defaults() -> Dict[str, Any]:
    """Yozuvdan oldin to'ldiriladigan bo'sh qiymatlar."""
    return {
        "manager_id": None,
        "manager_name": "",
        "client_name": "",
        "duration_seconds": 0,
        "overall_score": 0,
        "scores": "{}",
        "strengths": "[]",
        "weaknesses": "[]",
        "objections": "[]",
        "client_interest_level": 0,
        "outcome": "unknown",
        "converted": 0,
        "breakdown_at": None,
        "breakdown_reason": "",
        "longest_pause_seconds": 0.0,
        "pauses": "[]",
        "lead_price": 0.0,
        "lead_won": None,
    }
