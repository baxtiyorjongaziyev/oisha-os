#!/usr/bin/env python
"""
Har kecha eski leadlarni arxivlab, SQLite ma'lumotlar bazalarini VACUUM qilish skripti.

Vazifalari:
1. data/leadgen_delivery.db dagi eski yetkazilgan (completed) yoki muddati o'tgan
   leadlarni deliveries_archive jadvaliga ko'chiradi va asosiy jadvaldan tozalaydi.
2. 24 soatdan eski stale leadgen_claims qatorlarini tozalaydi.
3. data/bot.db dagi 60 kundan eski processed_messages va message_logs yozuvlarini tozalaydi.
4. Barcha asosiy SQLite bazalarida (leadgen_delivery.db, bot.db, meta_ad_spend.db va h.k.)
   VACUUM buyrug'ini bajarib, disk hajmini optimallashtiradi.
5. Natijalar haqida Telegram orqali qisqa hisobot yuboradi.

Ishga tushirish:
    python -m scripts.archive_old_leads [--days 60] [--notify]
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("LeadArchiver")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

TARGET_DATABASES = [
    "leadgen_delivery.db",
    "bot.db",
    "meta_ad_spend.db",
    "meta_ad_attribution.db",
    "meta_ad_names.db",
]


def _get_file_size_kb(path: Path) -> float:
    """Fayl hajmini KB da qaytaradi."""
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / 1024, 2)


def archive_leadgen_deliveries(days: int = 60) -> Tuple[int, int]:
    """
    leadgen_delivery.db dagi eski yozuvlarni arxivlaydi va stale claimlarni tozalaydi.
    Qaytaradi: (arxivlangan_leadlar_soni, tozalangan_claimlar_soni)
    """
    db_path = DATA_DIR / "leadgen_delivery.db"
    if not db_path.exists():
        logger.warning(f"{db_path} topilmadi.")
        return 0, 0

    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
    stale_claim_cutoff = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()
    now_str = datetime.datetime.now().isoformat()

    archived_count = 0
    claims_deleted = 0

    with sqlite3.connect(db_path, timeout=15) as conn:
        cursor = conn.cursor()

        # 1. Arxiv jadvalini yaratish (mavjud bo'lmasa)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS deliveries_archive (
                leadgen_id TEXT PRIMARY KEY,
                lead_id INTEGER,
                amocrm_ok INTEGER,
                sheets_ok INTEGER,
                telegram_ok INTEGER,
                destination TEXT,
                retries INTEGER,
                last_error TEXT,
                updated_at TEXT,
                archived_at TEXT
            )
            """
        )

        # 2. Eski yozuvlarni tanlab olish
        # - Yetkazilgan (100% ok) va muddati o'tgan
        cursor.execute(
            """
            SELECT leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, destination, retries, last_error, updated_at
            FROM deliveries
            WHERE (updated_at <= ? AND sheets_ok = 1 AND telegram_ok = 1 AND amocrm_ok = 1)
               OR (updated_at <= ? AND retries >= 10)
            """,
            (cutoff_date, cutoff_date),
        )
        rows = cursor.fetchall()

        if rows:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO deliveries_archive
                (leadgen_id, lead_id, amocrm_ok, sheets_ok, telegram_ok, destination, retries, last_error, updated_at, archived_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [r + (now_str,) for r in rows],
            )
            leadgen_ids = [(r[0],) for r in rows]
            cursor.executemany("DELETE FROM deliveries WHERE leadgen_id = ?", leadgen_ids)
            archived_count = len(rows)
            logger.info(f"[leadgen_delivery.db] {archived_count} ta lead deliveries_archive ga ko'chirildi.")

        # 3. 24 soatdan eski stale claimlarni tozalash
        try:
            cursor.execute("DELETE FROM leadgen_claims WHERE claimed_at <= ?", (stale_claim_cutoff,))
            claims_deleted = cursor.rowcount
            if claims_deleted > 0:
                logger.info(f"[leadgen_delivery.db] {claims_deleted} ta eski leadgen_claim tozalandi.")
        except sqlite3.OperationalError:
            pass

        conn.commit()

    return archived_count, claims_deleted


def prune_bot_logs(days: int = 60) -> Tuple[int, int]:
    """
    bot.db dagi eski log va xabarlarni tozalaydi.
    Qaytaradi: (tozalangan_messages, tozalangan_logs)
    """
    db_path = DATA_DIR / "bot.db"
    if not db_path.exists():
        return 0, 0

    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    deleted_msgs = 0
    deleted_logs = 0

    with sqlite3.connect(db_path, timeout=15) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM processed_messages WHERE processed_at <= ?", (cutoff,))
            deleted_msgs = cursor.rowcount
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("DELETE FROM message_logs WHERE created_at <= ?", (cutoff,))
            deleted_logs = cursor.rowcount
        except sqlite3.OperationalError:
            pass

        conn.commit()

    if deleted_msgs > 0 or deleted_logs > 0:
        logger.info(f"[bot.db] Tozalandi: {deleted_msgs} ta processed_messages, {deleted_logs} ta message_logs.")

    return deleted_msgs, deleted_logs


def vacuum_databases() -> List[Dict[str, Any]]:
    """Ro'yxatdagi barcha bazalarni VACUUM qilib o'lchov natijalarini qaytaradi."""
    results: List[Dict[str, Any]] = []

    for filename in TARGET_DATABASES:
        db_path = DATA_DIR / filename
        if not db_path.exists():
            continue

        size_before = _get_file_size_kb(db_path)
        try:
            with sqlite3.connect(db_path, timeout=30) as conn:
                conn.execute("VACUUM")
            size_after = _get_file_size_kb(db_path)
            saved_kb = round(size_before - size_after, 2)
            results.append({
                "db": filename,
                "before_kb": size_before,
                "after_kb": size_after,
                "saved_kb": saved_kb,
                "status": "OK",
            })
            logger.info(f"[VACUUM] {filename}: {size_before} KB -> {size_after} KB (tejaldi: {saved_kb} KB)")
        except Exception as exc:
            logger.error(f"[VACUUM] {filename} xatosi: {exc}")
            results.append({
                "db": filename,
                "before_kb": size_before,
                "after_kb": size_before,
                "saved_kb": 0.0,
                "status": f"Xato: {exc}",
            })

    return results


def send_archive_notification(
    archived_leads: int,
    cleaned_claims: int,
    deleted_msgs: int,
    vacuum_results: List[Dict[str, Any]],
) -> None:
    """Tungi tozalash natijalarini Telegram kanalga yuboradi."""
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""
    chat_id = os.getenv("TARGET_LEADS_GROUP_ID") or "-1003854308552"
    topic_id = os.getenv("TARGET_LEADS_TOPIC_ID") or "1020"

    if not token or not chat_id:
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_saved_kb = sum(r.get("saved_kb", 0.0) for r in vacuum_results if r.get("saved_kb", 0) > 0)

    lines = [
        "🧹 <b>[OISHA: TUNGI BAZA TOZALASH VA ARXIV HISOBOTI]</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🕒 <b>Sana va vaqt:</b> <code>{now_str}</code>",
        f"📦 <b>Arxivlangan leadlar:</b> <b>{archived_leads} ta</b>",
        f"🗑 <b>Tozalangan eski yozuvlar:</b> <b>{cleaned_claims + deleted_msgs} ta</b>",
        f"💾 <b>Tejalgan disk hajmi:</b> <b>{total_saved_kb:.1f} KB</b>",
        "",
        "📊 <b>Bazalar holati (VACUUM):</b>",
    ]
    for r in vacuum_results:
        lines.append(f"• <code>{r['db']}</code>: {r['after_kb']} KB ({r['status']})")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "✅ <i>SQLite ma'lumotlar bazasi to'liq optimallashtirildi.</i>",
    ])

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
    }
    if topic_id:
        try:
            payload["message_thread_id"] = int(topic_id)
        except ValueError:
            pass

    try:
        requests.post(url, json=payload, timeout=15)
        logger.info("[TG] Arxivlash hisoboti Telegramga yuborildi.")
    except Exception as exc:
        logger.error(f"[TG] Hisobot yuborishda xato: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tungi lead arxivlash va VACUUM jarayoni")
    parser.add_argument("--days", type=int, default=60, help="Necha kundan eski leadlarni arxivlash (standart: 60)")
    parser.add_argument("--notify", action="store_true", help="Telegram orqali natijani xabar qilish")
    args = parser.parse_args()

    logger.info(f"Tungi arxivlash va VACUUM boshlandi (Chegara: {args.days} kun)...")

    archived_leads, cleaned_claims = archive_leadgen_deliveries(days=args.days)
    deleted_msgs, deleted_logs = prune_bot_logs(days=args.days)
    vacuum_results = vacuum_databases()

    if args.notify or archived_leads > 0:
        send_archive_notification(
            archived_leads=archived_leads,
            cleaned_claims=cleaned_claims,
            deleted_msgs=deleted_msgs + deleted_logs,
            vacuum_results=vacuum_results,
        )

    logger.info("Tungi arxivlash va VACUUM yakunlandi.")


if __name__ == "__main__":
    main()
