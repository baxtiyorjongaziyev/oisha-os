"""Match card sends against Airtable income (``Turi = Kirim``) rows."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from src.services.core.card_watch.detector import CardSend

AMOUNT_TOLERANCE = 0.02
_STOP = {"jon", "branding", "mchj", "ooo", "llc", "group", "va", "and"}
_TEXT_FIELDS = ("Tranzaksiya", "Izoh", "Mijoz", "Kontragent", "Loyiha nomi", "Brend")


def _norm_tokens(text: str) -> set[str]:
    words = re.findall(r"[\wʻʼ']+", (text or "").lower())
    return {w.strip("ʻʼ'") for w in words if len(w) >= 3 and w not in _STOP}


def _select(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return str(value or "")


def _record_text(fields: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in _TEXT_FIELDS:
        val = fields.get(key)
        if isinstance(val, list):
            parts.extend(str(v) for v in val if not str(v).startswith("rec"))
        elif val:
            parts.append(str(val))
    return " ".join(parts)


def _record_date(fields: Dict[str, Any]) -> Optional[date]:
    raw = str(fields.get("Sana") or "")[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _record_amount(fields: Dict[str, Any]) -> Optional[float]:
    for key in ("Summa UZS", "Summa"):
        try:
            return float(fields.get(key))
        except (TypeError, ValueError):
            continue
    return None


def income_rows(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in records:
        f = r.get("fields") or {}
        if _select(f.get("Turi")) != "Kirim" or _select(f.get("Holat")) == "Bekor qilingan":
            continue
        out.append(f)
    return out


def is_paid(send: CardSend, incomes: Iterable[Dict[str, Any]]) -> bool:
    """True when an income on/after the send date matches by name or by amount."""
    since = send.sent_at.date() - timedelta(days=1)
    names = _norm_tokens(f"{send.client_name} {send.chat_title}")
    for f in incomes:
        d = _record_date(f)
        if d is None or d < since:
            continue
        amount = _record_amount(f)
        amount_ok = bool(
            send.amount and amount and abs(amount - send.amount) <= send.amount * AMOUNT_TOLERANCE
        )
        name_ok = bool(names & _norm_tokens(_record_text(f)))
        if name_ok or amount_ok:
            return True
    return False
