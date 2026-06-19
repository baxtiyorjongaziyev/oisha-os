"""
Hisobchi Engine — card transaction business logic.
Save → auto-categorize → learn from replies → report.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from src.database_pool import DatabasePool, db_pool

logger = logging.getLogger(__name__)


def _normalize_merchant(merchant: str) -> str:
    """Normalizes merchant name for memory key (first 3 meaningful words)."""
    parts = re.sub(r"[^A-Za-z0-9 ]", " ", merchant.upper()).split()
    key_parts = [p for p in parts if len(p) > 2]
    if not key_parts:
        key_parts = parts  # short names like "UZ" or "M B" — use as-is
    return " ".join(key_parts[:3])


def _fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


class HisobchiEngine:
    def __init__(self, db=None) -> None:
        self._db = db if isinstance(db, DatabasePool) else db_pool

    # ── MERCHANT MEMORY ───────────────────────────────────────────────────

    async def get_known_category(self, merchant: str) -> Optional[str]:
        normalized = _normalize_merchant(merchant)
        rows = await self._db.execute(
            "SELECT category FROM hisobchi_merchant_memory WHERE merchant_pattern = ?",
            [normalized],
        )
        return rows[0]["category"] if rows else None

    async def learn_category(self, merchant: str, category: str) -> None:
        normalized = _normalize_merchant(merchant)
        await self._db.execute(
            """
            INSERT INTO hisobchi_merchant_memory
                (merchant_pattern, category, use_count, updated_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(merchant_pattern) DO UPDATE SET
                category = excluded.category,
                use_count = use_count + 1,
                updated_at = excluded.updated_at
            """,
            [normalized, category],
        )
        await self._db.commit()
        logger.info("[HISOBCHI] Learned: %s → %s", normalized, category)

    # ── TRANSACTIONS ──────────────────────────────────────────────────────

    async def save_transaction(
        self,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        balance: Optional[int],
        raw_text: str,
        category: Optional[str] = None,
        finance_msg_id: Optional[int] = None,
        finance_chat_id: Optional[int] = None,
        status: str = "pending",
    ) -> int:
        rows = await self._db.execute(
            """
            INSERT INTO hisobchi_transactions
                (source_bot, direction, amount, merchant, card_suffix,
                 tx_time, balance, raw_text, category, finance_msg_id,
                 finance_chat_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            [
                source_bot, direction, amount, merchant, card_suffix,
                tx_time, balance, raw_text, category, finance_msg_id,
                finance_chat_id, status,
            ],
        )
        await self._db.commit()
        if rows:
            return int(rows[0]["id"])
        r2 = await self._db.execute("SELECT last_insert_rowid() AS id")
        return int(r2[0]["id"])

    async def update_finance_msg(
        self, tx_id: int, finance_msg_id: int, finance_chat_id: int
    ) -> None:
        await self._db.execute(
            """UPDATE hisobchi_transactions
               SET finance_msg_id=?, finance_chat_id=?
               WHERE id=?""",
            [finance_msg_id, finance_chat_id, tx_id],
        )
        await self._db.commit()

    async def categorize(self, tx_id: int, category: str) -> None:
        await self._db.execute(
            "UPDATE hisobchi_transactions SET category=?, status='categorized' WHERE id=?",
            [category, tx_id],
        )
        await self._db.commit()

    async def skip(self, tx_id: int) -> None:
        await self._db.execute(
            "UPDATE hisobchi_transactions SET status='skipped' WHERE id=?",
            [tx_id],
        )
        await self._db.commit()

    async def get_pending_by_finance_msg(
        self, finance_chat_id: int, finance_msg_id: int
    ) -> Optional[dict]:
        rows = await self._db.execute(
            """
            SELECT * FROM hisobchi_transactions
            WHERE finance_chat_id=? AND finance_msg_id=? AND status='pending'
            """,
            [finance_chat_id, finance_msg_id],
        )
        return dict(rows[0]) if rows else None

    async def get_monthly_summary(self, period: str) -> dict:
        """period = 'YYYY-MM'"""
        rows = await self._db.execute(
            """
            SELECT direction, category, SUM(amount) AS total, COUNT(*) AS cnt
            FROM hisobchi_transactions
            WHERE created_at LIKE ?
            GROUP BY direction, category
            ORDER BY total DESC
            """,
            [f"{period}%"],
        )
        income = 0
        expense = 0
        categories: dict[str, int] = {}
        for row in rows:
            if row["direction"] == "in":
                income += int(row["total"])
            else:
                expense += int(row["total"])
                cat = row["category"] or "Noma'lum"
                categories[cat] = categories.get(cat, 0) + int(row["total"])
        return {
            "income": income,
            "expense": expense,
            "net": income - expense,
            "categories": dict(
                sorted(categories.items(), key=lambda x: -x[1])
            ),
        }

    # ── MESSAGE BUILDERS ──────────────────────────────────────────────────

    def build_finance_question(self, tx, tx_id: int) -> str:
        """tx = ParsedTransaction"""
        dir_icon = "➖ Chiqim" if tx.direction == "out" else "➕ Kirim"
        card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
        balance_line = (
            f"\n💰 Qoldiq: {_fmt_money(tx.balance)} UZS" if tx.balance else ""
        )
        return (
            f"💳 <b>Yangi to'lov #{tx_id}</b>\n\n"
            f"{dir_icon}: <b>{_fmt_money(tx.amount)} UZS</b>\n"
            f"📍 {tx.merchant}\n"
            f"🏦 {card_label} {tx.card_suffix}\n"
            f"🕓 {tx.tx_time}"
            f"{balance_line}\n\n"
            f"❓ <b>Bu to'lov nima uchun?</b>\n"
            f"Javob bering yoki <code>/skip {tx_id}</code>"
        )

    def build_auto_msg(self, tx, category: str) -> str:
        dir_icon = "➖" if tx.direction == "out" else "➕"
        card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
        return (
            f"✅ <b>Avtomatik saqlandi</b>\n"
            f"{dir_icon} {_fmt_money(tx.amount)} UZS — {card_label} {tx.card_suffix}\n"
            f"📍 {tx.merchant}\n"
            f"🗂 <b>{category}</b>"
        )

    def build_monthly_report(self, period: str, summary: dict) -> str:
        cat_lines = "\n".join(
            f"  • {cat}: {_fmt_money(total)} UZS"
            for cat, total in list(summary["categories"].items())[:10]
        )
        net_icon = "📈" if summary["net"] >= 0 else "📉"
        return (
            f"📊 <b>Hisobchi hisoboti — {period}</b>\n\n"
            f"➕ Kirim:   <b>{_fmt_money(summary['income'])} UZS</b>\n"
            f"➖ Chiqim:  <b>{_fmt_money(summary['expense'])} UZS</b>\n"
            f"{net_icon} Balans:  <b>{_fmt_money(summary['net'])} UZS</b>\n\n"
            f"🗂 <b>Kategoriyalar:</b>\n{cat_lines or '  —'}"
        )
