"""
Rules learning, category resolution, AI gap tracking, and categorization mixin.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.services.core.finance.engine.helpers import (
    _normalize_card_suffix,
    _normalize_merchant,
)

logger = logging.getLogger(__name__)


class RulesLearningMixin:
    """Handles category learning, rule caching, and AI gap tracking."""

    async def get_known_category(self, merchant: str) -> Optional[str]:
        if self._gs:
            res = await self._gs.get_known_category(merchant)
            if res:
                return res
        if self._db:
            normalized = _normalize_merchant(merchant)
            rows = await self._db.execute(
                "SELECT category FROM hisobchi_merchant_memory WHERE merchant_pattern = ?",
                [normalized],
            )
            return rows[0]["category"] if rows else None
        return None

    async def learn_category(self, merchant: str, category: str) -> None:
        if self._gs:
            try:
                await self._gs.learn_category(merchant, category)
            except Exception as exc:
                logger.warning("[HISOBCHI] GSheets learn_category failed: %s", exc)
        if self._db:
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

    async def get_known_rule(
        self,
        merchant: str,
        card_suffix: str,
        direction: str,
        amount: int,
    ) -> Optional[dict]:
        if self._gs:
            res = await self._gs.get_known_rule(merchant, card_suffix, direction, amount)
            if res:
                return res
        if self._db:
            rows = await self._db.execute(
                """
                SELECT category, ownership
                FROM hisobchi_category_rules
                WHERE merchant_pattern=? AND card_suffix=? AND direction=? AND amount=?
                  AND active=1 AND conflicts=0 AND confirmations>=1
                """,
                [
                    _normalize_merchant(merchant),
                    _normalize_card_suffix(card_suffix),
                    direction,
                    amount,
                ],
            )
            return {
                "category": rows[0]["category"],
                "ownership": rows[0]["ownership"] or "business",
            } if rows else None
        return None

    async def learn_rule(
        self,
        *,
        merchant: str,
        card_suffix: str,
        direction: str,
        amount: int,
        category: str,
        ownership: str,
    ) -> None:
        if self._gs:
            return await self._gs.learn_rule(
                merchant=merchant, card_suffix=card_suffix,
                direction=direction, amount=amount,
                category=category, ownership=ownership,
            )
        key = [
            _normalize_merchant(merchant),
            _normalize_card_suffix(card_suffix),
            direction,
            amount,
        ]
        rows = await self._db.execute(
            """
            SELECT category, ownership
            FROM hisobchi_category_rules
            WHERE merchant_pattern=? AND card_suffix=? AND direction=? AND amount=?
            """,
            key,
        )
        if rows and (
            rows[0]["category"] != category
            or (rows[0]["ownership"] or "business") != ownership
        ):
            await self._db.execute(
                """
                UPDATE hisobchi_category_rules
                SET conflicts=conflicts+1, active=0, updated_at=CURRENT_TIMESTAMP
                WHERE merchant_pattern=? AND card_suffix=? AND direction=? AND amount=?
                """,
                key,
            )
        else:
            await self._db.execute(
                """
                INSERT INTO hisobchi_category_rules
                    (merchant_pattern, card_suffix, direction, amount, category,
                     ownership, confirmations, conflicts, active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(merchant_pattern, card_suffix, direction, amount)
                DO UPDATE SET
                    confirmations=confirmations+1,
                    updated_at=CURRENT_TIMESTAMP
                """,
                [*key, category, ownership],
            )
        await self._db.commit()

    async def reset_learning_and_transactions(self) -> None:
        """Full reset: clear all transactions and everything the system has
        learned (merchant memory + exact-match rules), so categorization
        starts from zero on the next card-bot message."""
        if self._gs:
            return await self._gs.reset_learning_and_transactions()
        await self._db.execute("DELETE FROM hisobchi_transactions")
        await self._db.execute("DELETE FROM hisobchi_merchant_memory")
        await self._db.execute("DELETE FROM hisobchi_category_rules")
        await self._db.commit()
        logger.info("[HISOBCHI] Reset: transactions + merchant memory + rules cleared.")

    async def categorize(
        self,
        tx_id: int,
        category: str,
        ownership: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        if self._gs:
            try:
                await self._gs.categorize(tx_id, category, ownership, reason)
            except Exception as exc:
                logger.warning("[HISOBCHI] GSheets categorize failed: %s", exc)
        if self._db:
            if ownership and reason:
                await self._db.execute(
                    "UPDATE hisobchi_transactions SET category=?, ownership=?, reason=?, status='categorized' WHERE id=?",
                    [category, ownership, reason, tx_id],
                )
            elif ownership:
                await self._db.execute(
                    "UPDATE hisobchi_transactions SET category=?, ownership=?, status='categorized' WHERE id=?",
                    [category, ownership, tx_id],
                )
            elif reason:
                await self._db.execute(
                    "UPDATE hisobchi_transactions SET category=?, reason=?, status='categorized' WHERE id=?",
                    [category, reason, tx_id],
                )
            else:
                await self._db.execute(
                    "UPDATE hisobchi_transactions SET category=?, status='categorized' WHERE id=?",
                    [category, tx_id],
                )
            await self._db.commit()

    async def log_ai_gap(
        self,
        kind: str,
        reason: str,
        source: str = "",
        raw_text: str = "",
        confidence: Optional[float] = None,
        tx_id: Optional[int] = None,
        chat_id: Optional[int] = None,
    ) -> None:
        """Record a case where the AI couldn't confidently handle a message
        (low-confidence parse, rejected/deferred input, parse failure).
        Best-effort — never raises, so a logging hiccup can't break the
        actual transaction flow. GSheets backend has no gaps sheet, so this
        is a no-op there.
        """
        if self._gs or self._db is None:
            return
        try:
            await self._db.execute(
                "INSERT INTO hisobchi_ai_gaps (kind, source, raw_text, reason, confidence, tx_id, chat_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [kind, source, raw_text[:2000], reason, confidence, tx_id, chat_id],
            )
            await self._db.commit()
        except Exception:
            logger.warning("[HISOBCHI] Failed to log AI gap (kind=%s)", kind, exc_info=True)

    async def get_ai_gaps_summary(self, since_days: int = 7) -> dict:
        """Summarize recent hisobchi_ai_gaps entries for reporting: total
        count and a breakdown by (kind, source). Empty/no-op on GSheets
        backend, matching log_ai_gap.
        """
        empty = {"total": 0, "by_kind_source": [], "since_days": since_days}
        if self._gs or self._db is None:
            return empty
        try:
            rows = await self._db.execute(
                "SELECT kind, source, COUNT(*) as cnt FROM hisobchi_ai_gaps "
                "WHERE created_at >= datetime('now', ?) "
                "GROUP BY kind, source ORDER BY cnt DESC",
                [f"-{since_days} days"],
            )
        except Exception:
            logger.warning("[HISOBCHI] Failed to summarize AI gaps", exc_info=True)
            return empty
        breakdown = [
            {"kind": r["kind"], "source": r["source"] or "noma'lum", "count": int(r["cnt"])}
            for r in rows
        ]
        total = sum(item["count"] for item in breakdown)
        return {"total": total, "by_kind_source": breakdown, "since_days": since_days}

    async def format_ai_gaps_report_uz(self, since_days: int = 7) -> str:
        """Render get_ai_gaps_summary as a short Uzbek-language report block."""
        summary = await self.get_ai_gaps_summary(since_days=since_days)
        if summary["total"] == 0:
            return f"🧠 Hisobchi AI: so'nggi {since_days} kunda noaniq holat bo'lmadi."

        lines = [f"🧠 Hisobchi AI — so'nggi {since_days} kunda {summary['total']} marta noaniq/rad etilgan holat:"]
        _kind_labels = {
            "rejected": "rad etildi",
            "low_confidence": "ishonch past",
            "parse_failed": "tushunolmadi",
        }
        for item in summary["by_kind_source"]:
            label = _kind_labels.get(item["kind"], item["kind"])
            lines.append(f"  • {label} ({item['source']}): {item['count']} marta")
        return "\n".join(lines)

    async def skip(self, tx_id: int) -> None:
        if self._gs:
            try:
                await self._gs.skip(tx_id)
            except Exception as exc:
                logger.warning("[HISOBCHI] GSheets skip failed: %s", exc)
        if self._db:
            await self._db.execute(
                "UPDATE hisobchi_transactions SET status='skipped' WHERE id=?",
                [tx_id],
            )
            await self._db.commit()
