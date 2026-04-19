"""
Lokal SQLite -> Turso migration.

Usage (lokal machine'dan ishlatiladi, Turso env o'zgaruvchilari bilan):

    # .env faylida:
    # TURSO_DATABASE_URL=libsql://oisha-os-db-...
    # TURSO_AUTH_TOKEN=...

    python -m src.services.debug.migrate_to_turso --source data/bot.db

Bu skript ikki bosqichda ishlaydi:
  1. Lokaldagi SQLite DB faylini ochadi (read-only).
  2. Turso'da schema init qiladi (Database.init_db), so'ng har bir jadvalni
     INSERT OR IGNORE bilan ko'chiradi. PRAGMA'lar skip qilinadi.

Turso auto-commits per execute, shuning uchun alohida commit kerak emas.
"""

import argparse
import asyncio
import os
import sqlite3
import sys

from dotenv import load_dotenv

# Agar skript `python src/services/debug/migrate_to_turso.py` bilan chaqirilsa,
# `src` packagesini topishi uchun loyiha root'ini sys.path'ga qo'shamiz.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.database import Database  # noqa: E402
from src.settings import settings  # noqa: E402


TABLES_IN_MIGRATION_ORDER = [
    # Users avval, chunki boshqa jadvallar FK qilishi mumkin
    "users",
    # Core conversation history
    "message_logs",
    "chat_summaries",
    "advisor_logs",
    # Intel / learnings
    "user_intel",
    "learned_facts",
    # Tasks / operational
    "tasks",
    "daily_plans",
    "team_reports",
    "scheduled_jobs",
    "agent_actions",
    "service_checkpoints",
    # Purchases / CRM
    "purchases",
    "kv_settings",
    "department_targets",
]


def _sqlite_columns(cursor, table: str) -> list[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _sqlite_table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


async def migrate(source_path: str, dry_run: bool = False) -> None:
    if not (settings.TURSO_DATABASE_URL and settings.TURSO_AUTH_TOKEN):
        raise SystemExit(
            "❌ TURSO_DATABASE_URL / TURSO_AUTH_TOKEN muhit o'zgaruvchilari topilmadi. "
            ".env faylni tekshiring."
        )

    if not os.path.exists(source_path):
        raise SystemExit(f"❌ Lokal DB fayl topilmadi: {source_path}")

    print(f"📂 Lokal SQLite: {source_path}")
    print(f"☁️  Turso: {settings.TURSO_DATABASE_URL}")
    if dry_run:
        print("🧪 DRY RUN — yozish yo'q, faqat rejalashtirish.")

    # 1. Turso tomonda schema yaratish
    db = Database()  # TURSO env set bo'lsa avtomat Turso'ga ulanadi
    await db.init_db()
    turso_conn = await db.get_connection()
    print("✅ Turso schema tayyor.")

    # 2. Lokal SQLite'ni ochish
    local = sqlite3.connect(source_path)
    local.row_factory = sqlite3.Row
    local_cur = local.cursor()

    total_rows = 0
    for table in TABLES_IN_MIGRATION_ORDER:
        if not _sqlite_table_exists(local_cur, table):
            print(f"  ⏭️  {table}: lokal DB'da mavjud emas, skip.")
            continue

        cols = _sqlite_columns(local_cur, table)
        if not cols:
            print(f"  ⏭️  {table}: ustunlar aniqlanmadi, skip.")
            continue

        local_cur.execute(f"SELECT * FROM {table}")
        rows = local_cur.fetchall()
        if not rows:
            print(f"  ⏭️  {table}: bo'sh.")
            continue

        placeholders = ",".join(["?"] * len(cols))
        col_list = ",".join(cols)
        insert_sql = (
            f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"
        )

        if dry_run:
            print(f"  🧪 {table}: {len(rows)} qator ko'chiriladi (dry run).")
            total_rows += len(rows)
            continue

        # Batching — Turso HTTP API har so'rovda maksimal sonli statement
        BATCH = 200
        moved = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i : i + BATCH]
            params_list = [tuple(r) for r in chunk]
            try:
                await turso_conn.executemany(insert_sql, params_list)
                moved += len(chunk)
            except Exception as exc:
                print(f"  ⚠️  {table}: batch xatosi @ row {i}: {exc}")
                continue
        print(f"  ✅ {table}: {moved}/{len(rows)} qator ko'chirildi.")
        total_rows += moved

    local.close()
    await db.close()
    print(f"🎉 Migratsiya tugadi. Jami ko'chirilgan: {total_rows} qator.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lokal SQLite -> Turso migratsiya")
    parser.add_argument(
        "--source",
        default=os.path.join(os.getcwd(), "data", "bot.db"),
        help="Lokal SQLite DB fayliga yo'l (default: data/bot.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Faqat sanab chiqish, yozmaslik",
    )
    return parser.parse_args()


if __name__ == "__main__":
    load_dotenv()
    args = _parse_args()
    asyncio.run(migrate(args.source, dry_run=args.dry_run))
