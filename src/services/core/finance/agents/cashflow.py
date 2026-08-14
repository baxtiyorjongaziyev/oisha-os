"""Auditable cash-flow analysis; no synthetic or demo finance values."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .base import BaseFinanceAgent


class CashflowAnalysisAgent(BaseFinanceAgent):
    def process(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        transactions = payload.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            raise ValueError("transactions must be a non-empty list")

        income = Decimal("0")
        expense = Decimal("0")
        for index, item in enumerate(transactions):
            if not isinstance(item, Mapping):
                raise ValueError(f"transactions[{index}] must be an object")
            kind = item.get("type")
            if kind not in {"income", "expense"}:
                raise ValueError(f"transactions[{index}].type is invalid")
            try:
                amount = Decimal(str(item.get("amount")))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError(f"transactions[{index}].amount is invalid") from None
            if not amount.is_finite() or amount < 0:
                raise ValueError(f"transactions[{index}].amount is invalid")
            if kind == "income":
                income += amount
            else:
                expense += amount

        net = income - expense
        return {
            "currency": str(payload.get("currency") or "UZS").upper(),
            "income": str(income),
            "expense": str(expense),
            "net": str(net),
            "status": "positive" if net > 0 else "negative" if net < 0 else "balanced",
            "transaction_count": len(transactions),
        }
