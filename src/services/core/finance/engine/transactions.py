"""
Transaction fingerprinting, persistence, deduplication, and lookup mixin.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from src.services.core.finance.engine.helpers import (
    _normalize_card_suffix,
    _normalize_merchant,
)

logger = logging.getLogger(__name__)


class TransactionsMixin:
    """Handles transaction CRUD, deduplication, and monthly summary aggregation."""

    @staticmethod
    def _normalize_card_suffix(card_suffix: str) -> str:
        return _normalize_card_suffix(card_suffix)

    def transaction_fingerprint(
        cls,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        source_message_id: Optional[int] = None,
    ) -> str:
        if source_message_id is not None:
            canonical = (
                f"telegram-message|{source_bot.strip().lower()}|"
                f"{int(source_message_id)}"
            )
        else:
            canonical = "|".join(
                (
                    source_bot.strip().lower(),
                    direction.strip().lower(),
                    str(int(amount)),
                    _normalize_merchant(merchant),
                    _normalize_card_suffix(card_suffix),
                    " ".join((tx_time or "").split()),
                )
            )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def transaction_exists(
        self,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        source_message_id: Optional[int] = None,
    ) -> bool:
        if self._gs:
            fp = self.transaction_fingerprint(
                source_bot=source_bot, direction=direction, amount=amount,
                merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
                source_message_id=source_message_id,
            )
            return await self._gs.transaction_exists(fp)
        fingerprint = self.transaction_fingerprint(
            source_bot=source_bot,
            direction=direction,
            amount=amount,
            merchant=merchant,
            card_suffix=card_suffix,
            tx_time=tx_time,
            source_message_id=source_message_id,
        )
        rows = await self._db.execute(
            "SELECT id FROM hisobchi_transactions WHERE fingerprint=?",
            [fingerprint],
        )
        return bool(rows)

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
        reason: Optional[str] = None,
        source_message_id: Optional[int] = None,
    ) -> int:
        tx_id, _ = await self.save_transaction_once(
            source_bot=source_bot,
            direction=direction,
            amount=amount,
            merchant=merchant,
            card_suffix=card_suffix,
            tx_time=tx_time,
            balance=balance,
            raw_text=raw_text,
            category=category,
            ownership=ownership,
            finance_msg_id=finance_msg_id,
            finance_chat_id=finance_chat_id,
            status=status,
            reason=reason,
            source_message_id=source_message_id,
        )
        return tx_id

    async def save_transaction_once(
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
        currency: str = "UZS",
        finance_msg_id: Optional[int] = None,
        finance_chat_id: Optional[int] = None,
        status: str = "pending",
        reason: Optional[str] = None,
        source_message_id: Optional[int] = None,
    ) -> tuple[int, bool]:
        if self._gs:
            try:
                await self._gs.save_transaction_once(
                    source_bot=source_bot, direction=direction, amount=amount,
                    merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
                    balance=balance, raw_text=raw_text, category=category,
                    ownership=ownership, currency=currency,
                    finance_msg_id=finance_msg_id,
                    finance_chat_id=finance_chat_id, status=status,
                    reason=reason, source_message_id=source_message_id,
                )
            except Exception as exc:
                logger.warning("[HISOBCHI] GSheets save_transaction_once failed: %s", exc)

        fingerprint = self.transaction_fingerprint(
            source_bot=source_bot,
            direction=direction,
            amount=amount,
            merchant=merchant,
            card_suffix=card_suffix,
            tx_time=tx_time,
            source_message_id=source_message_id,
        )
        rows = await self._db.execute(
            """
            INSERT INTO hisobchi_transactions
                (source_bot, direction, amount, merchant, card_suffix,
                 tx_time, balance, raw_text, category, ownership, finance_msg_id,
                 finance_chat_id, status, fingerprint, reason, source_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO NOTHING
            RETURNING id
            """,
            [
                source_bot, direction, amount, merchant, card_suffix,
                tx_time, balance, raw_text, category, ownership, finance_msg_id,
                finance_chat_id, status, fingerprint, reason, source_message_id,
            ],
        )
        await self._db.commit()
        if rows:
            return int(rows[0]["id"]), True
        existing = await self._db.execute(
            "SELECT id FROM hisobchi_transactions WHERE fingerprint=?",
            [fingerprint],
        )
        if not existing:
            raise RuntimeError("hisobchi_transaction_insert_failed")
        return int(existing[0]["id"]), False

    async def update_finance_msg(
        self, tx_id: int, finance_msg_id: int, finance_chat_id: int
    ) -> None:
        if self._gs:
            try:
                await self._gs.update_finance_msg(tx_id, finance_msg_id, finance_chat_id)
            except Exception as exc:
                logger.warning("[HISOBCHI] GSheets update_finance_msg failed: %s", exc)
        if self._db:
            await self._db.execute(
                """UPDATE hisobchi_transactions
                   SET finance_msg_id=?, finance_chat_id=?
                   WHERE id=?""",
                [finance_msg_id, finance_chat_id, tx_id],
            )
            await self._db.commit()

    async def get_pending_by_finance_msg(
        self, finance_chat_id: int, finance_msg_id: int
    ) -> Optional[dict]:
        if self._gs:
            res = await self._gs.get_pending_by_finance_msg(finance_chat_id, finance_msg_id)
            if res:
                return res
        if self._db:
            rows = await self._db.execute(
                """
                SELECT * FROM hisobchi_transactions
                WHERE finance_chat_id=? AND finance_msg_id=? AND status='pending'
                """,
                [finance_chat_id, finance_msg_id],
            )
            return dict(rows[0]) if rows else None
        return None

    async def get_transaction(self, tx_id: int) -> Optional[dict]:
        if self._gs:
            res = await self._gs.get_transaction(tx_id)
            if res:
                return res
        if self._db:
            rows = await self._db.execute(
                "SELECT * FROM hisobchi_transactions WHERE id=?", [tx_id]
            )
            return dict(rows[0]) if rows else None
        return None

    async def get_transaction_status(self, tx_id: int) -> Optional[str]:
        if self._gs:
            status = await self._gs.get_transaction_status(tx_id)
            if status:
                return status
        if self._db:
            rows = await self._db.execute(
                "SELECT status FROM hisobchi_transactions WHERE id=?", [tx_id]
            )
            return rows[0]["status"] if rows else None
        return None

    async def get_monthly_summary(self, period: str) -> dict:
        """period = 'YYYY-MM'"""
        if self._gs:
            return await self._gs.get_monthly_summary(
                period, tracking_start_date=self._tracking_start_date.isoformat()
            )
        rows = await self._db.execute(
            """
            SELECT direction, category, ownership, SUM(amount) AS total, COUNT(*) AS cnt
            FROM hisobchi_transactions
            WHERE created_at LIKE ? AND created_at >= ?
            GROUP BY direction, category, ownership
            ORDER BY total DESC
            """,
            [f"{period}%", self._tracking_start_date.isoformat()],
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
