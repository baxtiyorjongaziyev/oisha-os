"""Sotuv sifati hisobotlarida sotuvchi boʻlmagan menejerlarni chiqarib tashlash."""

from __future__ import annotations

from typing import Any, List

# Admin/owner/founder sotuvchi emas — uning qoʻngʻiroqlari reytingga,
# oʻrtacha ballga va tavsiyalarga kirmaydi. Nom normallashtirilib
# (kichik harf, faqat harflar) qismi boʻyicha solishtiriladi.
NON_SALES_NAME_KEYS = ("baxtiyorjon",)


def norm_name(name: Any) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalpha())


def is_non_sales(name: Any) -> bool:
    key = norm_name(name)
    return any(k in key for k in NON_SALES_NAME_KEYS)


def _manager_name(row: Any) -> Any:
    if isinstance(row, dict):
        return row.get("manager_name")
    getter = getattr(row, "get", None)
    if callable(getter):
        try:
            return getter("manager_name", None)
        except Exception:
            return None
    return getattr(row, "manager_name", None)


def exclude_non_sales(rows: List[Any]) -> List[Any]:
    return [r for r in rows if not is_non_sales(_manager_name(r))]
