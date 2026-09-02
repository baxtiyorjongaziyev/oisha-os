"""
Keyboard builders, callback key encoders, and approval message formatters.
"""
from __future__ import annotations

import html
import logging
from typing import Any

logger = logging.getLogger("HisobchiApproval")

# Common categories for quick selection
QUICK_CATEGORIES = [
    "🍽 Taom",
    "🚕 Taksi",
    "🛒 Oziq-ovqat",
    "⛽ Yonilg'i",
    "📱 Aloqa",
    "🏠 Ijara",
    "💰 Maosh",
    "📦 Xarid",
    "🔧 Xizmat",
    "❓ Noma'lum",
]

def _approval_key(tx_id: int, ownership: str) -> str:
    return f"happrove:{tx_id}:{ownership}"


def _edit_key(tx_id: int) -> str:
    return f"hedit:{tx_id}"


def _skip_key(tx_id: int) -> str:
    return f"hskip:{tx_id}"


def _category_key(tx_id: int, category: str) -> str:
    safe_cat = category[:20].replace(":", ";").replace("|", ";")
    return f"hcat:{tx_id}:{safe_cat}"


def _change_owner_key(tx_id: int, current: str) -> str:
    new_owner = "personal" if current == "business" else "business"
    return f"howner:{tx_id}:{new_owner}"


def build_approval_keyboard(tx_id: int, ownership: str = "business"):
    """Telethon Button inline keyboard yaratadi."""
    try:
        from telethon import Button

        owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
        owner_cb = _change_owner_key(tx_id, ownership)

        buttons = [
            [
                Button.inline(owner_label, data=owner_cb),
            ],
            [
                Button.inline("✅ Tasdiqlash", data=_approval_key(tx_id, ownership)),
                Button.inline("✏️ Tahrirlash", data=_edit_key(tx_id)),
            ],
            [
                Button.inline("❌ Rad etish", data=_skip_key(tx_id)),
            ],
        ]
        return buttons
    except ImportError:
        return None


def build_category_keyboard(tx_id: int) -> list:
    """Kategoriya tanlash uchun inline keyboard."""
    try:
        from telethon import Button

        buttons = []
        row = []
        for cat in QUICK_CATEGORIES:
            row.append(Button.inline(cat, data=_category_key(tx_id, cat)))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([Button.inline("🔙 Ortga", data=f"hback:{tx_id}")])
        return buttons
    except ImportError:
        return None


def build_approval_message(tx: Any, tx_id: int, ownership: str = "business") -> str:
    """Admin uchun tasdiqlash xabarini formatlaydi."""
    dir_icon = "➖ Chiqim" if tx.direction == "out" else "➕ Kirim"
    card_label = "HUMO" if tx.source_bot == "humo" else "UZCARD"
    owner_label = "🏢 Biznes" if ownership == "business" else "🏠 Shaxsiy"
    question = (
        "Bu to'lov nima uchun ketdi?"
        if tx.direction == "out"
        else "Bu pul nima uchun keldi?"
    )
    balance_line = (
        f"\n💰 Qoldiq: {_fmt_money(tx.balance)} UZS" if tx.balance else ""
    )
    return (
        f"💳 <b>Yangi to'lov #{tx_id}</b>\n\n"
        f"{dir_icon}: <b>{_fmt_money(tx.amount)} UZS</b>\n"
        f"📍 {html.escape(tx.merchant)}\n"
        f"🏦 {card_label} {html.escape(tx.card_suffix)}\n"
        f"🕓 {html.escape(tx.tx_time)}"
        f"{balance_line}\n\n"
        f"📊 {owner_label}\n\n"
        f"❓ <b>{question}</b>\n"
        f"Kategoriyani tanlang yoki javob yozing"
    )


def _fmt_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")

