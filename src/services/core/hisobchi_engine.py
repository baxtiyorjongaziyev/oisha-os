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
        self._db = db if db is not None else db_pool

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
        ownership: str = "business",
        finance_msg_id: Optional[int] = None,
        finance_chat_id: Optional[int] = None,
        status: str = "pending",
    ) -> int:
        rows = await self._db.execute(
            """
            INSERT INTO hisobchi_transactions
                (source_bot, direction, amount, merchant, card_suffix,
                 tx_time, balance, raw_text, category, ownership, finance_msg_id,
                 finance_chat_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            [
                source_bot, direction, amount, merchant, card_suffix,
                tx_time, balance, raw_text, category, ownership, finance_msg_id,
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

    async def categorize(self, tx_id: int, category: str, ownership: Optional[str] = None) -> None:
        if ownership:
            await self._db.execute(
                "UPDATE hisobchi_transactions SET category=?, ownership=?, status='categorized' WHERE id=?",
                [category, ownership, tx_id],
            )
        else:
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
            SELECT direction, category, ownership, SUM(amount) AS total, COUNT(*) AS cnt
            FROM hisobchi_transactions
            WHERE created_at LIKE ?
            GROUP BY direction, category, ownership
            ORDER BY total DESC
            """,
            [f"{period}%"],
        )
        summary = {
            "business": {"income": 0, "expense": 0, "net": 0, "categories": {}},
            "personal": {"income": 0, "expense": 0, "net": 0, "categories": {}}
        }
        for row in rows:
            own = row["ownership"] or "business"
            if own not in summary:
                own = "business"
            
            direc = row["direction"]
            total = int(row["total"])
            cat = row["category"] or "Noma'lum"
            
            if direc == "in":
                summary[own]["income"] += total
            else:
                summary[own]["expense"] += total
                summary[own]["categories"][cat] = summary[own]["categories"].get(cat, 0) + total
                
        for own in ["business", "personal"]:
            summary[own]["net"] = summary[own]["income"] - summary[own]["expense"]
            summary[own]["categories"] = dict(
                sorted(summary[own]["categories"].items(), key=lambda x: -x[1])
            )
        return summary

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

    def build_auto_msg(self, tx, category: str, ownership: str = "business") -> str:
        dir_icon = "➖" if tx.direction == "out" else "➕"
        card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
        own_label = "Biznes" if ownership == "business" else "Shaxsiy"
        return (
            f"✅ <b>Avtomatik saqlandi ({own_label})</b>\n"
            f"{dir_icon} {_fmt_money(tx.amount)} UZS — {card_label} {tx.card_suffix}\n"
            f"📍 {tx.merchant}\n"
            f"🗂 <b>{category}</b>"
        )

    def build_monthly_report(self, period: str, summary: dict) -> str:
        if "business" in summary:
            b_sum = summary["business"]
            p_sum = summary["personal"]
            b_net_icon = "📈" if b_sum["net"] >= 0 else "📉"
            p_net_icon = "📈" if p_sum["net"] >= 0 else "📉"
            
            b_cat_lines = "\n".join(
                f"  • {cat}: {_fmt_money(total)} UZS"
                for cat, total in list(b_sum["categories"].items())[:10]
            )
            p_cat_lines = "\n".join(
                f"  • {cat}: {_fmt_money(total)} UZS"
                for cat, total in list(p_sum["categories"].items())[:10]
            )
            return (
                f"📊 <b>Hisobchi hisoboti — {period}</b>\n\n"
                f"💼 <b>Biznes moliyasi:</b>\n"
                f"  ➕ Kirim:   <b>{_fmt_money(b_sum['income'])} UZS</b>\n"
                f"  ➖ Chiqim:  <b>{_fmt_money(b_sum['expense'])} UZS</b>\n"
                f"  {b_net_icon} Balans:  <b>{_fmt_money(b_sum['net'])} UZS</b>\n"
                f"  🗂 <b>Kategoriyalar:</b>\n{b_cat_lines or '  —'}\n\n"
                f"👤 <b>Shaxsiy moliya:</b>\n"
                f"  ➕ Kirim:   <b>{_fmt_money(p_sum['income'])} UZS</b>\n"
                f"  ➖ Chiqim:  <b>{_fmt_money(p_sum['expense'])} UZS</b>\n"
                f"  {p_net_icon} Balans:  <b>{_fmt_money(p_sum['net'])} UZS</b>\n"
                f"  🗂 <b>Kategoriyalar:</b>\n{p_cat_lines or '  —'}"
            )
        else:
            cat_lines = "\n".join(
                f"  • {cat}: {_fmt_money(total)} UZS"
                for cat, total in list(summary.get("categories", {}).items())[:10]
            )
            net_val = summary.get("net", 0)
            net_icon = "📈" if net_val >= 0 else "📉"
            return (
                f"📊 <b>Hisobchi hisoboti — {period}</b>\n\n"
                f"➕ Kirim:   <b>{_fmt_money(summary.get('income', 0))} UZS</b>\n"
                f"➖ Chiqim:  <b>{_fmt_money(summary.get('expense', 0))} UZS</b>\n"
                f"{net_icon} Balans:  <b>{_fmt_money(net_val)} UZS</b>\n\n"
                f"🗂 <b>Kategoriyalar:</b>\n{cat_lines or '  —'}"
            )
