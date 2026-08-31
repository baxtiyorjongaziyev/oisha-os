"""Hisobchi AI — Google Sheets storage backend."""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import logging
import os
import re
from typing import Any, Optional

import gspread
from gspread.spreadsheet import Spreadsheet
from gspread.worksheet import Worksheet
try:
    from google.oauth2.service_account import Credentials
except ImportError:
    Credentials = None

logger = logging.getLogger(__name__)

_GSHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_PUL_OQIMI = "Pul oqimi"
SHEET_SHAXSIY = "Shaxsiy"
SHEET_FOYDA_ZARAR = "Foyda/zarar"
SHEET_BALANS = "Balans"
SHEET_XOTIRA = "Xotira"
SHEET_QOIDALAR = "Qoidalar"
SHEET_QARZ = "Qarz"
SHEET_BYUDJET = "Byudjet"
SHEET_MAOSH = "Maosh"
SHEET_HISOBOT = "Hisobot"
SHEET_VALYUTA = "Valyuta"
SHEET_XODIMLAR = "Xodimlar"
SHEET_KASSA = "Kassa"

PUL_OQIMI_COLUMNS = [
    ("#", "id"),
    ("Sana", "date"),
    ("Yonalish", "direction"),
    ("Summa", "amount"),
    ("Valyuta", "currency"),
    ("Nomi", "merchant"),
    ("Kategoriya", "category"),
    ("Karta", "card_suffix"),
    ("Vaqt", "tx_time"),
    ("Qoldiq", "balance"),
    ("Izoh", "reason"),
    ("Holat", "status"),
    ("Manba", "source_bot"),
    ("Xabar", "raw_text"),
    ("Fingerprint", "fingerprint"),
    ("Xabar ID", "source_message_id"),
    ("Finansi chat ID", "finance_chat_id"),
    ("Finansi xabar ID", "finance_msg_id"),
]

SHAXSIY_COLUMNS = list(PUL_OQIMI_COLUMNS)

FOYDA_ZARAR_COLUMNS = [
    ("#", "id"),
    ("Davr", "period"),
    ("Biznes kirim", "business_income"),
    ("Biznes chiqim", "business_expense"),
    ("Biznes sof", "business_net"),
    ("Shaxsiy kirim", "personal_income"),
    ("Shaxsiy chiqim", "personal_expense"),
    ("Shaxsiy sof", "personal_net"),
    ("Yaratilgan", "created_at"),
]

BALANS_COLUMNS = [
    ("#", "id"),
    ("Karta raqami", "card_suffix"),
    ("Karta turi", "card_type"),
    ("Balans (UZS)", "balance"),
    ("Yangilangan", "updated_at"),
]

XOTIRA_COLUMNS = [
    ("#", "id"),
    ("Nomi", "merchant_pattern"),
    ("Kategoriya", "category"),
    ("Ishlatilgan", "use_count"),
    ("Yangilangan", "updated_at"),
]

QOIDALAR_COLUMNS = [
    ("#", "id"),
    ("Nomi", "merchant_pattern"),
    ("Karta", "card_suffix"),
    ("Yonalish", "direction"),
    ("Summa (UZS)", "amount"),
    ("Kategoriya", "category"),
    ("Tegishlilik", "ownership"),
    ("Tasdiqlar", "confirmations"),
    ("Ziddiyat", "conflicts"),
    ("Faol", "active"),
    ("Yangilangan", "updated_at"),
]

QARZ_COLUMNS = [
    ("#", "id"),
    ("Tur", "debt_type"),
    ("Kimdan/Kimga", "person"),
    ("Summa (UZS)", "amount"),
    ("Sana", "date"),
    ("Qaytgan (UZS)", "repaid"),
    ("Qoldiq (UZS)", "remaining"),
    ("Muddat", "due_date"),
    ("Izoh", "note"),
    ("Holat", "status"),
    ("Yangilangan", "updated_at"),
]

BYUDJET_COLUMNS = [
    ("#", "id"),
    ("Kategoriya", "category"),
    ("Oy", "period"),
    ("Limit (UZS)", "budget_limit"),
    ("Sarflangan (UZS)", "spent"),
    ("Qoldiq (UZS)", "remaining"),
    ("Holat", "status"),
    ("Yangilangan", "updated_at"),
]

MAOSH_COLUMNS = [
    ("#", "id"),
    ("Xodim", "employee_name"),
    ("Tur", "type"),
    ("Summa (UZS)", "amount"),
    ("Sana", "date"),
    ("Davr", "period"),
    ("Izoh", "note"),
    ("Holat", "status"),
    ("Yangilangan", "updated_at"),
]

VALYUTA_COLUMNS = [
    ("#", "id"),
    ("Valyuta", "currency"),
    ("Sotib olish", "buy_rate"),
    ("Sotish", "sell_rate"),
    ("Markaziy bank", "cb_rate"),
    ("Sana", "date"),
    ("Yangilangan", "updated_at"),
]

XODIMLAR_COLUMNS = [
    ("#", "id"),
    ("Ism", "name"),
    ("Rol", "role"),
    ("Telegram ID", "telegram_id"),
    ("Telefon", "phone"),
    ("Ruxsat", "permission"),
    ("Faol", "active"),
    ("Yangilangan", "updated_at"),
]

KASSA_COLUMNS = [
    ("#", "id"),
    ("Nomi", "name"),
    ("Valyuta", "currency"),
    ("Balans", "balance"),
    ("Turi", "type"),
    ("Izoh", "note"),
    ("Faol", "active"),
    ("Yangilangan", "updated_at"),
]

SHEET_CONFIG_DISPLAY = {
    SHEET_PUL_OQIMI: PUL_OQIMI_COLUMNS,
    SHEET_SHAXSIY: SHAXSIY_COLUMNS,
    SHEET_FOYDA_ZARAR: FOYDA_ZARAR_COLUMNS,
    SHEET_BALANS: BALANS_COLUMNS,
    SHEET_XOTIRA: XOTIRA_COLUMNS,
    SHEET_QOIDALAR: QOIDALAR_COLUMNS,
    SHEET_QARZ: QARZ_COLUMNS,
    SHEET_BYUDJET: BYUDJET_COLUMNS,
    SHEET_MAOSH: MAOSH_COLUMNS,
    SHEET_VALYUTA: VALYUTA_COLUMNS,
    SHEET_XODIMLAR: XODIMLAR_COLUMNS,
    SHEET_KASSA: KASSA_COLUMNS,
}

SHEET_HEADERS: dict[str, list[str]] = {}
SHEET_KEYS: dict[str, list[str]] = {}
SHEET_KEY_TO_HEADER: dict[str, dict[str, str]] = {}
SHEET_HEADER_TO_KEY: dict[str, dict[str, str]] = {}

for sheet_name, cols in SHEET_CONFIG_DISPLAY.items():
    headers = [c[0] for c in cols]
    keys = [c[1] for c in cols]
    SHEET_HEADERS[sheet_name] = headers
    SHEET_KEYS[sheet_name] = keys
    SHEET_KEY_TO_HEADER[sheet_name] = dict(cols)
    SHEET_HEADER_TO_KEY[sheet_name] = {h: k for h, k in cols}


def _normalize_card_suffix(card_suffix: str) -> str:
    digits = re.sub(r"\D", "", card_suffix or "")
    return digits[-4:]


def _normalize_merchant(merchant: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {" ", "'", "\u2018", "\u2019"} else " "
        for char in merchant.upper()
    )
    parts = cleaned.split()
    key_parts = [p for p in parts if len(p) > 2]
    if not key_parts:
        key_parts = parts
    return " ".join(key_parts[:3])


def _fingerprint(
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


def _h2k(sheet: str, header: str) -> str:
    return SHEET_HEADER_TO_KEY[sheet].get(header, header)


def _k2h(sheet: str, key: str) -> str:
    return SHEET_KEY_TO_HEADER[sheet].get(key, key)


def _get(sheet: str, row: dict, key: str, default: Any = "") -> Any:
    h = _k2h(sheet, key)
    return row.get(h, default)


