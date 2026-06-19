"""Card transaction intake and learning accountant for Telegram bank bots."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TASHKENT = ZoneInfo("Asia/Tashkent")


@dataclass(frozen=True)
class CardTransaction:
    source_bot: str
    direction: str
    amount_uzs: int
    balance_uzs: Optional[int]
    merchant: str
    card_last4: str
    occurred_at: str
    raw_text: str

    @property
    def merchant_key(self) -> str:
        value = re.sub(r"[^A-Z0-9]+", " ", self.merchant.upper())
        return " ".join(value.split())

    @property
    def fingerprint(self) -> str:
        material = "|".join(
            (
                self.source_bot.casefold(),
                self.direction,
                str(self.amount_uzs),
                self.card_last4,
                self.merchant_key,
                self.occurred_at,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _parse_uzs(line: str) -> Optional[int]:
    value = re.sub(r"(?i)UZS|SO['‘’`]?M", "", line)
    value = re.sub(r"[^0-9.,]", "", value)
    if not value:
        return None

    last_separator = max(value.rfind("."), value.rfind(","))
    if last_separator >= 0 and len(value) - last_separator - 1 == 2:
        value = value[:last_separator]
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else None


def _parse_occurred_at(text: str) -> Optional[str]:
    patterns = (
        (r"(\d{2}):(\d{2})\s+(\d{2})\.(\d{2})\.(\d{4})", "time_first"),
        (r"(\d{2})\.(\d{2})\.(\d{2,4})\s+(\d{2}):(\d{2})", "date_first"),
    )
    for pattern, order in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        parts = [int(part) for part in match.groups()]
        if order == "time_first":
            hour, minute, day, month, year = parts
        else:
            day, month, year, hour, minute = parts
            if year < 100:
                year += 2000
        try:
            return datetime(year, month, day, hour, minute, tzinfo=TASHKENT).isoformat()
        except ValueError:
            return None
    return None


def parse_card_transaction(text: str, source_bot: str) -> Optional[CardTransaction]:
    """Parse Humo/Uzcard notifications while keeping amount and balance separate."""
    raw_text = (text or "").strip()
    if not raw_text:
        return None

    lowered = raw_text.casefold()
    income_markers = (
        "kirim",
        "zachislen",
        "popolnen",
        "зачислен",
        "пополнен",
        "➕",
        "kredit",
    )
    expense_markers = (
        "to'lov",
        "to‘lov",
        "platezh",
        "spisanie",
        "oplata",
        "платеж",
        "списание",
        "оплата",
        "➖",
    )
    if any(marker in lowered for marker in income_markers):
        direction = "income"
        amount_symbol = "➕"
    elif any(marker in lowered for marker in expense_markers):
        direction = "expense"
        amount_symbol = "➖"
    else:
        return None

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    amount_line = next((line for line in lines if amount_symbol in line), "")
    amount = _parse_uzs(amount_line)
    if amount is None:
        return None

    balance_line = next(
        (line for line in lines if line.startswith("💰") or line.startswith("💵")),
        "",
    )
    balance = _parse_uzs(balance_line) if balance_line else None
    merchant_line = next((line for line in lines if line.startswith("📍")), "")
    merchant = merchant_line.lstrip("📍 ").strip() or "Noma'lum merchant"
    card_line = next((line for line in lines if line.startswith("💳")), "")
    card_match = re.search(r"(\d{4})\s*$", card_line)
    card_last4 = card_match.group(1) if card_match else ""
    occurred_at = _parse_occurred_at(raw_text)
    if not occurred_at:
        return None

    return CardTransaction(
        source_bot=source_bot.lstrip("@"),
        direction=direction,
        amount_uzs=amount,
        balance_uzs=balance,
        merchant=merchant,
        card_last4=card_last4,
        occurred_at=occurred_at,
        raw_text=raw_text,
    )


def _format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def _extract_category_and_reason(text: str) -> tuple[str, str]:
    category_match = re.search(
        r"(?im)^\s*kategoriya\s*:\s*(.+?)\s*$", text or ""
    )
    reason_match = re.search(r"(?im)^\s*sabab\s*:\s*(.+?)\s*$", text or "")
    reason = (reason_match.group(1).strip() if reason_match else (text or "").strip())
    if category_match:
        return category_match.group(1).strip(), reason

    lowered = reason.casefold()
    categories = (
        ("Marketing", ("reklama", "marketing", "target", "smm")),
        ("Ofis xarajati", ("ofis", "kants", "choy", "suv")),
        ("Dastur va obuna", ("obuna", "subscription", "server", "hosting", "domen")),
        ("Transport", ("taksi", "taxi", "benzin", "yoqilg", "transport")),
        ("Oziq-ovqat", ("ovqat", "restoran", "kafe", "tushlik")),
        ("Soliq va davlat", ("soliq", "nalog", "boj", "davlat")),
        ("Ish haqi", ("oylik", "maosh", "avans")),
        ("Mijozdan kirim", ("mijoz", "kirim", "to'lov tushdi", "tushum")),
    )
    for category, markers in categories:
        if any(marker in lowered for marker in markers):
            return category, reason
    return "Boshqa", reason


class CardTransactionAccountant:
    def __init__(
        self,
        *,
        db,
        user_client,
        finance_group_id: Optional[int] = None,
        finance_topic_id: Optional[int] = None,
        fallback_group_id: Optional[int] = None,
        fallback_topic_id: Optional[int] = None,
        allowed_bots: Optional[set[str]] = None,
    ) -> None:
        self.db = db
        self.user_client = user_client
        self.finance_group_id = finance_group_id
        self.finance_topic_id = finance_topic_id
        self.fallback_group_id = fallback_group_id
        self.fallback_topic_id = fallback_topic_id
        self.allowed_bots = {
            bot.lstrip("@").casefold()
            for bot in (allowed_bots or {"HUMOcardbot", "CardXabarBot"})
        }

    async def initialize(self) -> None:
        conn = await self.db.get_connection()
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                source_bot TEXT NOT NULL,
                source_chat_id INTEGER,
                source_message_id INTEGER,
                direction TEXT NOT NULL,
                amount_uzs INTEGER NOT NULL,
                balance_uzs INTEGER,
                merchant TEXT NOT NULL,
                merchant_key TEXT NOT NULL,
                card_last4 TEXT,
                occurred_at TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                category TEXT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                question_chat_id INTEGER,
                question_message_id INTEGER,
                categorized_by INTEGER,
                categorized_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS finance_category_rules (
                rule_key TEXT PRIMARY KEY,
                merchant_key TEXT NOT NULL,
                direction TEXT NOT NULL,
                card_last4 TEXT,
                amount_uzs INTEGER,
                category TEXT NOT NULL,
                reason TEXT,
                confirmations INTEGER NOT NULL DEFAULT 1,
                conflicts INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_card_transactions_question ON card_transactions(question_chat_id, question_message_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_finance_rules_lookup ON finance_category_rules(merchant_key, direction, card_last4, amount_uzs, active)"
        )
        await conn.commit()

    async def _ensure_destination(self) -> bool:
        if self.finance_group_id:
            return True
        try:
            dialogs = await self.user_client.get_dialogs(limit=500)
            for dialog in dialogs:
                title = (getattr(dialog, "name", None) or "").casefold()
                if any(
                    word in title
                    for word in (
                        "moliya",
                        "finance",
                        "buxgalter",
                        "accounting",
                        "hisobchi",
                    )
                ):
                    self.finance_group_id = int(dialog.id)
                    logger.info("[CARD FINANCE] Moliya guruhi topildi: %s", dialog.name)
                    return True
        except Exception as exc:
            logger.warning("[CARD FINANCE] Moliya guruhini qidirib bo'lmadi: %s", exc)
        if self.fallback_group_id:
            self.finance_group_id = int(self.fallback_group_id)
            if not self.finance_topic_id and self.fallback_topic_id:
                self.finance_topic_id = int(self.fallback_topic_id)
            logger.warning(
                "[CARD FINANCE] Alohida moliya guruhi topilmadi; fallback ishlatiladi: %s",
                self.finance_group_id,
            )
            return True
        return False

    async def _find_rule(self, tx: CardTransaction) -> Optional[dict[str, Any]]:
        conn = await self.db.get_connection()
        params = (tx.merchant_key, tx.direction, tx.card_last4)
        async with conn.execute(
            """
            SELECT category, reason, confirmations, amount_uzs
            FROM finance_category_rules
            WHERE merchant_key = ? AND direction = ? AND card_last4 = ?
              AND active = 1
              AND ((amount_uzs = ? AND confirmations >= 1)
                   OR (amount_uzs IS NULL AND confirmations >= 2))
            ORDER BY CASE WHEN amount_uzs = ? THEN 0 ELSE 1 END, confirmations DESC
            LIMIT 1
            """,
            params + (tx.amount_uzs, tx.amount_uzs),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return {
            "category": row[0],
            "reason": row[1],
            "confirmations": row[2],
            "match": "exact" if row[3] is not None else "merchant",
        }

    async def _existing_transaction(self, fingerprint: str):
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT id, status, category FROM card_transactions WHERE fingerprint = ?",
            (fingerprint,),
        ) as cursor:
            return await cursor.fetchone()

    async def _insert_transaction(self, tx: CardTransaction, event) -> int:
        now = datetime.now(TASHKENT).isoformat()
        conn = await self.db.get_connection()
        await conn.execute(
            """
            INSERT INTO card_transactions (
                fingerprint, source_bot, source_chat_id, source_message_id,
                direction, amount_uzs, balance_uzs, merchant, merchant_key,
                card_last4, occurred_at, raw_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.fingerprint,
                tx.source_bot,
                getattr(event, "chat_id", None),
                getattr(event, "id", None),
                tx.direction,
                tx.amount_uzs,
                tx.balance_uzs,
                tx.merchant,
                tx.merchant_key,
                tx.card_last4,
                tx.occurred_at,
                tx.raw_text,
                now,
                now,
            ),
        )
        await conn.commit()
        async with conn.execute(
            "SELECT id FROM card_transactions WHERE fingerprint = ?", (tx.fingerprint,)
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0])

    async def _set_status(self, tx_id: int, status: str) -> None:
        conn = await self.db.get_connection()
        await conn.execute(
            "UPDATE card_transactions SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(TASHKENT).isoformat(), tx_id),
        )
        await conn.commit()

    async def _set_question(self, tx_id: int, chat_id: int, message_id: int) -> None:
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE card_transactions
            SET status = 'awaiting_reason', question_chat_id = ?,
                question_message_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (chat_id, message_id, datetime.now(TASHKENT).isoformat(), tx_id),
        )
        await conn.commit()

    async def _set_category(
        self,
        tx_id: int,
        *,
        status: str,
        category: str,
        reason: Optional[str],
        categorized_by: Optional[int] = None,
    ) -> None:
        now = datetime.now(TASHKENT).isoformat()
        conn = await self.db.get_connection()
        await conn.execute(
            """
            UPDATE card_transactions
            SET status = ?, category = ?, reason = ?, categorized_by = ?,
                categorized_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, category, reason, categorized_by, now, now, tx_id),
        )
        await conn.commit()

    async def handle_bank_message(self, event) -> dict[str, Any]:
        try:
            sender = await event.get_sender()
        except Exception:
            return {"status": "ignored_sender"}
        username = (getattr(sender, "username", None) or "").lstrip("@").casefold()
        if username not in self.allowed_bots:
            return {"status": "ignored_sender"}

        text = getattr(event, "raw_text", None) or getattr(event, "text", "") or ""
        tx = parse_card_transaction(text, username)
        if not tx:
            return {"status": "ignored_message"}
        existing = await self._existing_transaction(tx.fingerprint)
        if existing:
            return {
                "status": "duplicate",
                "transaction_id": existing[0],
                "fingerprint": tx.fingerprint,
            }

        tx_id = await self._insert_transaction(tx, event)
        rule = await self._find_rule(tx)
        destination_ready = await self._ensure_destination()
        if rule:
            await self._set_category(
                tx_id,
                status="auto_categorized",
                category=rule["category"],
                reason=rule["reason"],
            )
            if destination_ready:
                await self.user_client.send_message(
                    self.finance_group_id,
                    self._auto_message(tx, rule),
                    **self._topic_kwargs(),
                )
            return {
                "status": "auto_categorized",
                "category": rule["category"],
                "fingerprint": tx.fingerprint,
                "transaction_id": tx_id,
            }

        if not destination_ready:
            await self._set_status(tx_id, "awaiting_destination")
            return {
                "status": "awaiting_destination",
                "fingerprint": tx.fingerprint,
                "transaction_id": tx_id,
            }

        question = await self.user_client.send_message(
            self.finance_group_id,
            self._question_message(tx, tx_id),
            **self._topic_kwargs(),
        )
        await self._set_question(
            tx_id, int(self.finance_group_id), int(question.id)
        )
        return {
            "status": "awaiting_reason",
            "fingerprint": tx.fingerprint,
            "transaction_id": tx_id,
        }

    async def backfill_recent(
        self,
        limit_per_bot: int = 50,
        max_age_hours: Optional[int] = None,
    ) -> dict[str, int]:
        """Replay recent bank-bot history; fingerprints make this idempotent."""
        summary = {"processed": 0, "duplicates": 0, "errors": 0, "stale": 0}
        cutoff = (
            datetime.now(TASHKENT) - timedelta(hours=max_age_hours)
            if max_age_hours
            else None
        )
        for bot in sorted(self.allowed_bots):
            try:
                messages = []
                async for message in self.user_client.iter_messages(
                    f"@{bot}", limit=limit_per_bot
                ):
                    messages.append(message)
                for message in reversed(messages):
                    if cutoff:
                        text = (
                            getattr(message, "raw_text", None)
                            or getattr(message, "text", "")
                            or ""
                        )
                        parsed = parse_card_transaction(text, bot)
                        if parsed and datetime.fromisoformat(parsed.occurred_at) < cutoff:
                            summary["stale"] += 1
                            continue
                    result = await self.handle_bank_message(message)
                    if result.get("status") == "duplicate":
                        summary["duplicates"] += 1
                    elif result.get("status") not in {
                        "ignored_sender",
                        "ignored_message",
                    }:
                        summary["processed"] += 1
            except Exception as exc:
                summary["errors"] += 1
                logger.warning("[CARD FINANCE] @%s backfill xatosi: %s", bot, exc)
        logger.info("[CARD FINANCE] Backfill natijasi: %s", summary)
        return summary

    def _topic_kwargs(self) -> dict[str, int]:
        return {"reply_to": int(self.finance_topic_id)} if self.finance_topic_id else {}

    @staticmethod
    def _question_message(tx: CardTransaction, tx_id: int) -> str:
        flow = "Kirim" if tx.direction == "income" else "Chiqim"
        return (
            f"🧾 Karta tranzaksiyasi #{tx_id}\n"
            f"{flow}: {_format_money(tx.amount_uzs)} UZS\n"
            f"Karta: *{tx.card_last4 or 'noma’lum'} | {tx.source_bot}\n"
            f"Joy: {tx.merchant}\n"
            f"Vaqt: {tx.occurred_at[0:16].replace('T', ' ')}\n\n"
            "Bu pul nima uchun kirim/chiqim bo‘ldi? Shu xabarga reply qiling:\n"
            "Kategoriya: ...\nSabab: ..."
        )

    @staticmethod
    def _auto_message(tx: CardTransaction, rule: dict[str, Any]) -> str:
        flow = "Kirim" if tx.direction == "income" else "Chiqim"
        return (
            "🤖 Avtomatik kategoriya\n"
            f"{flow}: {_format_money(tx.amount_uzs)} UZS | *{tx.card_last4}\n"
            f"Joy: {tx.merchant}\n"
            f"Kategoriya: {rule['category']}\n"
            f"Sabab: {rule.get('reason') or 'oldingi tasdiqlangan qoida'}"
        )

    async def handle_finance_reply(self, event) -> bool:
        if not self.finance_group_id or int(getattr(event, "chat_id", 0)) != int(
            self.finance_group_id
        ):
            return False
        reply_to = getattr(event, "reply_to_msg_id", None)
        if not reply_to:
            return False
        conn = await self.db.get_connection()
        async with conn.execute(
            """
            SELECT id, merchant_key, direction, card_last4, amount_uzs
            FROM card_transactions
            WHERE question_chat_id = ? AND question_message_id = ?
              AND status = 'awaiting_reason'
            """,
            (int(self.finance_group_id), int(reply_to)),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False

        text = getattr(event, "raw_text", None) or getattr(event, "text", "") or ""
        category, reason = _extract_category_and_reason(text)
        tx_id, merchant_key, direction, card_last4, amount_uzs = row
        await self._learn_rule(
            merchant_key=merchant_key,
            direction=direction,
            card_last4=card_last4 or "",
            amount_uzs=int(amount_uzs),
            category=category,
            reason=reason,
        )
        await self._set_category(
            int(tx_id),
            status="categorized",
            category=category,
            reason=reason,
            categorized_by=getattr(event, "sender_id", None),
        )
        await event.reply(
            f"✅ Saqlandi: {category}. Keyingi aynan o‘xshash tranzaksiyani Oisha avtomatik taniydi."
        )
        return True

    async def _learn_rule(
        self,
        *,
        merchant_key: str,
        direction: str,
        card_last4: str,
        amount_uzs: int,
        category: str,
        reason: str,
    ) -> None:
        await self._upsert_rule(
            merchant_key, direction, card_last4, amount_uzs, category, reason
        )
        await self._upsert_rule(
            merchant_key, direction, card_last4, None, category, reason
        )

    async def _upsert_rule(
        self,
        merchant_key: str,
        direction: str,
        card_last4: str,
        amount_uzs: Optional[int],
        category: str,
        reason: str,
    ) -> None:
        amount_key = "*" if amount_uzs is None else str(amount_uzs)
        rule_key = hashlib.sha256(
            f"{merchant_key}|{direction}|{card_last4}|{amount_key}".encode("utf-8")
        ).hexdigest()
        conn = await self.db.get_connection()
        async with conn.execute(
            "SELECT category, confirmations FROM finance_category_rules WHERE rule_key = ?",
            (rule_key,),
        ) as cursor:
            existing = await cursor.fetchone()
        now = datetime.now(TASHKENT).isoformat()
        if not existing:
            await conn.execute(
                """
                INSERT INTO finance_category_rules (
                    rule_key, merchant_key, direction, card_last4, amount_uzs,
                    category, reason, confirmations, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    rule_key,
                    merchant_key,
                    direction,
                    card_last4,
                    amount_uzs,
                    category,
                    reason,
                    now,
                    now,
                ),
            )
        elif existing[0] == category:
            await conn.execute(
                """
                UPDATE finance_category_rules
                SET confirmations = confirmations + 1, reason = ?, active = 1, updated_at = ?
                WHERE rule_key = ?
                """,
                (reason, now, rule_key),
            )
        else:
            await conn.execute(
                """
                UPDATE finance_category_rules
                SET conflicts = conflicts + 1, active = 0, updated_at = ?
                WHERE rule_key = ?
                """,
                (now, rule_key),
            )
        await conn.commit()
