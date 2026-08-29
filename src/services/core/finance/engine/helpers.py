"""
Normalization and formatting helpers for Hisobchi engine.
"""
from __future__ import annotations

import re
from typing import Any, Optional


def _normalize_merchant(merchant: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {" ", "'", "‘", "’"} else " "
        for char in merchant.upper()
    )
    parts = cleaned.split()
    key_parts = [p for p in parts if len(p) > 2]
    if not key_parts:
        key_parts = parts
    return " ".join(key_parts[:3])


def _fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def _normalize_card_suffix(card_suffix: str) -> str:
    digits = re.sub(r"\D", "", card_suffix or "")
    return digits[-4:]
