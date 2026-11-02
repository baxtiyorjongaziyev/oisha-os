"""Shared text helpers for the Kirim topic handlers.

Pure helpers only (no I/O): message text, topic detection, seller display name,
payment-confirmation card parsing and congratulation builders.
"""
from __future__ import annotations

import random
import re
from typing import Any, Dict, Optional

CARD_MARKERS = ("to'lov tasdiqlash", "tolov tasdiqlash")

_FIELD_RE = re.compile(r"^\s*(?P<label>[^:\n]+?)\s*:\s*(?P<value>.+?)\s*$")
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{3,}")
_APPROVAL_RE = re.compile(
    r"\b(tasdiq\w*|qabul qilindi|tushdi|tushgan|okey|ok)\b", re.IGNORECASE
)
_REJECTION_RE = re.compile(
    r"\b(rad|bekor|tasdiqlanmadi|tasdiqlamayman|tushmadi|xato|yo'q)\b", re.IGNORECASE
)

_INDIVIDUAL_OPENERS = (
    "{name}, tabriklaymiz! 🎉",
    "Barakalla, {name}! 👏",
    "{name}, ajoyib ish! 🌟",
)
_APPROVED_OPENERS = (
    "To'lov tasdiqlandi! ✅ {name}, yana bir bor tabriklaymiz!",
    "Moliyachi to'lovni tasdiqladi ✅ {name}, barakalla!",
)


def normalize_text(text: str) -> str:
    """Lowercase text and unify apostrophes so card markers always match."""
    return (
        (text or "")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("`", "'")
        .lower()
    )


def message_text(message: Any) -> str:
    raw = getattr(message, "message", None)
    if raw is None:
        raw = getattr(message, "text", None)
    return (raw or "").strip()


def seller_display_name(sender: Any) -> str:
    username = (getattr(sender, "username", None) or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"

    full_name = " ".join(
        part
        for part in (
            getattr(sender, "first_name", None),
            getattr(sender, "last_name", None),
        )
        if part
    ).strip()
    return full_name or "Sotuvchi"


def is_kirim_topic_message(message: Any, topic_id: Optional[int]) -> bool:
    """True when the message belongs to the configured Kirim topic."""
    if not topic_id:
        return False

    direct_reply_id = getattr(message, "reply_to_msg_id", None)
    reply_to = getattr(message, "reply_to", None)
    reply_top_id = getattr(message, "reply_to_top_id", None) or getattr(
        reply_to, "reply_to_top_id", None
    )
    forum_topic = getattr(reply_to, "forum_topic", False)

    return bool(
        direct_reply_id == topic_id
        or reply_top_id == topic_id
        or (forum_topic and direct_reply_id == topic_id)
    )


def is_payment_confirmation_card(text: str) -> bool:
    """Detect a structured payment-confirmation card (not free-text income news)."""
    normalized = normalize_text(text).strip()
    if not normalized:
        return False
    if not any(marker in normalized for marker in CARD_MARKERS):
        return False
    return any(word in normalized for word in ("summa", "sotuvchi", "chek"))


def _clean_label(label: str) -> str:
    letters = "".join(ch for ch in label if ch.isalnum() or ch in " '/-()")
    return " ".join(letters.split()).lower()


def _strip_handle(value: str) -> str:
    return _HANDLE_RE.sub("", value).strip(" -—–")


def _format_amount(value: str, label: str) -> str:
    lowered = normalize_text(value)
    if any(token in lowered for token in ("so'm", "so'm", "sum", "uzs", "$", "usd")):
        return value
    if "usd" in label or "dollar" in label:
        return f"{value} USD"
    return f"{value} so'm"


def parse_payment_card(text: str) -> Dict[str, Any]:
    """Parse the sales-manager payment card into a compact dict."""
    card: Dict[str, Any] = {
        "seller_name": None,
        "seller_handle": None,
        "amount": None,
        "amount_label": None,
        "project": None,
        "payment_type": None,
    }

    for line in (text or "").splitlines():
        match = _FIELD_RE.match(line)
        if not match:
            continue
        label = _clean_label(match.group("label"))
        value = match.group("value").strip()
        if not label or not value:
            continue

        if "sotuvchi" in label:
            handle = _HANDLE_RE.search(value)
            card["seller_handle"] = handle.group(0) if handle else None
            card["seller_name"] = _strip_handle(value) or None
        elif "summa" in label:
            card["amount"] = value
            card["amount_label"] = _format_amount(value, label)
        elif "mijoz" in label or "loyiha" in label:
            card["project"] = value
        elif "turi" in label:
            card["payment_type"] = value

    return card


def is_rejection_reply(text: str) -> bool:
    return bool(_REJECTION_RE.search(normalize_text(text)))


def is_approval_reply(text: str) -> bool:
    normalized = normalize_text(text)
    if is_rejection_reply(normalized):
        return False
    return bool(_APPROVAL_RE.search(normalized))


def _card_details(card: Dict[str, Any]) -> str:
    details = []
    if card.get("project"):
        details.append(f"Loyiha: {card['project']}")
    if card.get("amount_label"):
        details.append(f"Summa: {card['amount_label']}")
    return "\n".join(details)


def build_individual_congratulation(
    card: Dict[str, Any], *, approved: bool = False
) -> str:
    """Personal (DM) congratulation for the seller."""
    name = (card.get("seller_name") or "Sotuvchi").strip()
    openers = _APPROVED_OPENERS if approved else _INDIVIDUAL_OPENERS
    opener = random.choice(openers).format(name=name)

    details = _card_details(card)
    footer = (
        "Summa hisobingizga tushdi. Rahmat — shu tempda davom etamiz! 💪"
        if approved
        else "To'lov qabul qilindi. Zo'r natija — shu tempda davom etamiz!"
    )
    if details:
        return f"{opener}\n\n{details}\n\n{footer}"
    return f"{opener}\n\n{footer}"


def build_finance_ask(
    seller_name: str, amount_label: Optional[str], mention: str
) -> str:
    """Group message that tags the finance person and asks for confirmation."""
    amount_line = f"\nSumma: {amount_label}" if amount_label else ""
    return (
        f"{mention}, {seller_name} yuborgan to'lovni tasdiqlaysizmi?{amount_line}\n\n"
        "Tasdiqlash uchun shu xabarga «tasdiqlandi», rad etish uchun «rad» deb javob bering."
    )
