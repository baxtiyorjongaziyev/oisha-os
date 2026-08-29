import logging
from typing import Any, Dict, List, Optional
from src.services.core.finance.gsheets.constants import *

logger = logging.getLogger(__name__)

class GsheetTransactionsMixin:
    def transaction_fingerprint(
        self,
        *,
        source_bot: str,
        direction: str,
        amount: int,
        merchant: str,
        card_suffix: str,
        tx_time: str,
        source_message_id: Optional[int] = None,
    ) -> str:
        return _fingerprint(
            source_bot=source_bot, direction=direction, amount=amount,
            merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
            source_message_id=source_message_id,
        )

    async def transaction_exists(self, fingerprint: str) -> bool:
        if not self._loaded:
            self._load_cache()
        return fingerprint in self._cache_fingerprints

    def _target_sheet(self, ownership: str) -> str:
        return SHEET_PUL_OQIMI if ownership == "business" else SHEET_SHAXSIY

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
        currency: str = "UZS",
        finance_msg_id: Optional[int] = None,
        finance_chat_id: Optional[int] = None,
        status: str = "pending",
        reason: Optional[str] = None,
        source_message_id: Optional[int] = None,
    ) -> int:
        tx_id, _ = await self.save_transaction_once(
            source_bot=source_bot, direction=direction, amount=amount,
            merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
            balance=balance, raw_text=raw_text, category=category,
            ownership=ownership, currency=currency,
            finance_msg_id=finance_msg_id,
            finance_chat_id=finance_chat_id, status=status,
            reason=reason, source_message_id=source_message_id,
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
        fp = self.transaction_fingerprint(
            source_bot=source_bot, direction=direction, amount=amount,
            merchant=merchant, card_suffix=card_suffix, tx_time=tx_time,
            source_message_id=source_message_id,
        )

        if await self.transaction_exists(fp):
            return 0, False

        sheet = self._target_sheet(ownership)
        nid = self._next_id(sheet)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txn = {
            "id": nid,
            "date": now,
            "source_bot": source_bot,
            "direction": "Kirim" if direction == "in" else "Chiqim",
            "amount": int(amount),
            "currency": currency.upper(),
            "merchant": merchant,
            "card_suffix": card_suffix,
            "tx_time": tx_time,
            "balance": str(balance) if balance is not None else "",
            "category": category or "",
            "raw_text": raw_text,
            "status": status,
            "fingerprint": fp,
            "reason": reason or "",
            "source_message_id": str(source_message_id) if source_message_id else "",
        }
        self._append_row(sheet, txn)
        self._cache_fingerprints.add(fp)
        self._cache_transactions[nid] = txn

        # Auto-update budget spent
        if direction == "out" or direction == "Chiqim":
            cat = category or ""
            if cat:
                period_ = now[:7]  # "YYYY-MM" from "YYYY-MM-DD HH:MM:SS"
                total_spent = sum(
                    t.get("amount", 0) for t in self._cache_transactions.values()
                    if str(t.get("direction", "")).lower() in ("chiqim", "out")
                    and str(t.get("category", "")).lower() == cat.lower()
                    and str(t.get("date", "")).startswith(period_)
                )
                await self.update_budget_spent(period_, cat, total_spent)

        return nid, True

    async def update_finance_msg(
        self, tx_id: int, finance_msg_id: int, finance_chat_id: int
    ) -> None:
        pass

    async def categorize(
        self,
        tx_id: int,
        category: str,
        ownership: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        cached = self._cache_transactions.get(tx_id)
        if not cached:
            return
        sheet = self._target_sheet(cached.get("ownership", "business"))
        ws = self._worksheets.get(sheet)
        if not ws:
            return
        row = self._find_row_by_col(
            ws, _k2h(sheet, "id"), tx_id
        )
        if not row:
            return

        new_own = ownership or cached.get("ownership", "business")
        cached["category"] = category
        cached["ownership"] = new_own
        cached["status"] = "categorized"
        if reason:
            cached["reason"] = reason

        self._update_row(sheet, row, cached)

    async def skip(self, tx_id: int) -> None:
        cached = self._cache_transactions.get(tx_id)
        if not cached:
            return
        cached["status"] = "skipped"
        sheet = self._target_sheet(cached.get("ownership", "business"))
        ws = self._worksheets.get(sheet)
        if not ws:
            return
        row = self._find_row_by_col(
            ws, _k2h(sheet, "id"), tx_id
        )
        if not row:
            return
        self._update_row(sheet, row, cached)

    async def get_pending_by_finance_msg(
        self, finance_chat_id: int, finance_msg_id: int
    ) -> Optional[dict]:
        for tx in self._cache_transactions.values():
            if str(tx.get("status", "")) == "pending":
                return {
                    "id": tx["id"],
                    "merchant": tx["merchant"],
                    "card_suffix": tx.get("card_suffix", ""),
                    "direction": "out" if tx.get("direction") == "Chiqim" else "in",
                    "amount": tx.get("amount", 0),
                    "ownership": tx.get("ownership", "business"),
                    "category": tx.get("category", ""),
                    "reason": tx.get("reason", ""),
                    "status": tx["status"],
                }
        return None

    async def get_transaction(self, tx_id: int) -> Optional[dict]:
        # Direct lookup by transaction ID in cache
        tx = self._cache_transactions.get(tx_id)
        # Fallback: some rows may store the ID under different header names (e.g., "ID" or "id")
        if not tx:
            for cand in self._cache_transactions.values():
                cand_id = cand.get("ID") or cand.get("id")
                if cand_id is not None and str(cand_id) == str(tx_id):
                    tx = cand
                    break
        if not tx:
            return None
        sheet = SHEET_SHAXSIY if str(_get(SHEET_SHAXSIY, tx, "ownership", "")).lower() == "personal" or "shaxsiy" in str(tx).lower() else SHEET_PUL_OQIMI
        direction_raw = str(_get(sheet, tx, "direction", "") or tx.get("direction", "")).lower()
        direction = "in" if ("kirim" in direction_raw or direction_raw == "in") else "out"
        amount_raw = _get(sheet, tx, "amount", 0) or tx.get("amount", 0)
        try:
            amount = int(str(amount_raw).replace(" ", "").replace(",", "").replace(".", "")) if amount_raw else 0
        except (ValueError, TypeError):
            amount = 0
        return {
            "id": tx_id,
            "merchant": _get(sheet, tx, "merchant", "") or tx.get("merchant", ""),
            "card_suffix": _get(sheet, tx, "card_suffix", "") or tx.get("card_suffix", ""),
            "direction": direction,
            "amount": amount,
            "ownership": "personal" if sheet == SHEET_SHAXSIY else "business",
            "category": _get(sheet, tx, "category", "") or tx.get("category", ""),
            "reason": _get(sheet, tx, "reason", "") or tx.get("reason", ""),
            "status": _get(sheet, tx, "status", "pending") or tx.get("status", "pending"),
            "source_bot": _get(sheet, tx, "source_bot", "uzcard") or tx.get("source_bot", "uzcard"),
            "tx_time": _get(sheet, tx, "tx_time", "") or tx.get("tx_time", ""),
            "balance": _get(sheet, tx, "balance") or tx.get("balance"),
        }

    async def get_transaction_status(self, tx_id: int) -> Optional[str]:
        tx = self._cache_transactions.get(tx_id)
        if not tx:
            return None
        sheet = SHEET_SHAXSIY if str(_get(SHEET_SHAXSIY, tx, "ownership", "")).lower() == "personal" or "shaxsiy" in str(tx).lower() else SHEET_PUL_OQIMI
        return _get(sheet, tx, "status", None) or tx.get("status")
