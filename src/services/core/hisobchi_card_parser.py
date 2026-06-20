"""
Parses card notification messages from @HUMOcardbot and @CardXabarBot.

HUMO format:
    💸 To'lov
    ➖ 4.000,00 UZS
    📍 AO PAYNET QR DLYA S
    💳 HUMOCARD *6224
    🕓 22:26 18.06.2026
    💰 2.135,00 UZS

UzCard format:
    🔴 Platezh
    ➖ 8 000.00 UZS
    💳 ***1393
    📍 PAYNET AJ QR DLYA SAMOZANYATIX UZKARD, UZ
    🕓 18.06.26 22:26
    💵 700.00 UZS
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedTransaction:
    source_bot: str      # 'humo' | 'uzcard'
    direction: str       # 'out' | 'in'
    amount: int          # UZS butun son
    merchant: str
    card_suffix: str
    tx_time: str
    balance: Optional[int]


def _parse_amount(text: str) -> int:
    """'4.000,00 UZS' yoki '8 000.00 UZS' → 4000"""
    text = re.sub(r"\s*UZS\s*$", "", text.strip())
    text = re.sub(r"[,\.]\d{2}$", "", text)        # tiyinlarni olib tashlash
    text = re.sub(r"[\s,.]", "", text)               # ajratuvchilarni olib tashlash
    try:
        return int(text)
    except ValueError:
        return 0


def _extract_amount_line(line: str) -> tuple[int, str]:
    """Returns (amount, direction) from a ➖/➕ line."""
    m = re.search(r"([\d\s.,]+\s*UZS)", line)
    if not m:
        return 0, "out"
    amount = _parse_amount(m.group(1))
    direction = "out" if "➖" in line else "in"
    return amount, direction


def parse_humo_message(text: str) -> Optional[ParsedTransaction]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    direction = "out"
    amount = 0
    merchant = ""
    card_suffix = ""
    tx_time = ""
    balance = None

    for line in lines:
        if any(kw in line for kw in ["To'lov", "Tolov", "Platezh", "Chiqim"]):
            direction = "out"
        elif any(kw in line for kw in ["Kirim", "Zachislenie", "Popolnenie"]):
            direction = "in"

        if "➖" in line or "➕" in line:
            amt, dir_ = _extract_amount_line(line)
            if amt:
                amount = amt
                direction = dir_

        if "📍" in line:
            merchant = line.replace("📍", "").strip()

        if "💳" in line:
            card_suffix = re.sub(r"\D", "", line)[-4:]

        if "🕓" in line:
            tx_time = line.replace("🕓", "").strip()

        if "💰" in line:
            m = re.search(r"([\d\s.,]+\s*UZS)", line)
            if m:
                balance = _parse_amount(m.group(1))

    if not amount or not merchant:
        return None

    return ParsedTransaction(
        source_bot="humo",
        direction=direction,
        amount=amount,
        merchant=merchant,
        card_suffix=card_suffix,
        tx_time=tx_time,
        balance=balance,
    )


def parse_uzcard_message(text: str) -> Optional[ParsedTransaction]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    direction = "out"
    amount = 0
    merchant = ""
    card_suffix = ""
    tx_time = ""
    balance = None

    for line in lines:
        if any(c in line for c in ["🔴", "🟠"]):
            direction = "out"
        elif any(c in line for c in ["🟢", "💚"]):
            direction = "in"

        if "➖" in line or "➕" in line:
            amt, dir_ = _extract_amount_line(line)
            if amt:
                amount = amt
                direction = dir_

        if "📍" in line:
            merchant = line.replace("📍", "").strip()

        if "💳" in line:
            card_suffix = re.sub(r"\D", "", line)[-4:]

        if "🕓" in line:
            tx_time = line.replace("🕓", "").strip()

        if "💵" in line:
            m = re.search(r"([\d\s.,]+\s*UZS)", line)
            if m:
                balance = _parse_amount(m.group(1))

    if not amount or not merchant:
        return None

    return ParsedTransaction(
        source_bot="uzcard",
        direction=direction,
        amount=amount,
        merchant=merchant,
        card_suffix=card_suffix,
        tx_time=tx_time,
        balance=balance,
    )


CARD_BOT_PARSERS = {
    "humocardbot": parse_humo_message,
    "cardxabarbot": parse_uzcard_message,
}

CARD_BOT_USERNAMES = frozenset(CARD_BOT_PARSERS)


def parse_card_notification(
    sender_username: str, text: str
) -> Optional[ParsedTransaction]:
    key = sender_username.lower().lstrip("@")
    parser = CARD_BOT_PARSERS.get(key)
    return parser(text) if parser else None
