"""Match card sends against Airtable income (``Turi = Kirim``) rows."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from src.services.core.card_watch.detector import CardSend

AMOUNT_TOLERANCE = 0.02
MATCH_WINDOW_DAYS = 30
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


def _amount_ok(expected: Optional[float], actual: Optional[float]) -> bool:
    return bool(expected and actual and abs(actual - expected) <= expected * AMOUNT_TOLERANCE)


def is_paid(send: CardSend, incomes: Iterable[Dict[str, Any]]) -> bool:
    """Income within [sent-1d, sent+MATCH_WINDOW_DAYS] that matches the send.

    Rules (checked on real data, 2026-11-17):
    * name match counts only when amounts do not contradict (person names like
      "Muhammad" are common, so a 7.64M income must not pay an 880k card send);
    * amount-only match counts only when exactly one income with that amount is
      in the window (880 000 is a common price, several rows => ambiguous).
    """
    since = send.sent_at.date() - timedelta(days=1)
    until = send.sent_at.date() + timedelta(days=MATCH_WINDOW_DAYS)
    names = _norm_tokens(f"{send.client_name} {send.chat_title}")
    amount_hits = 0
    for f in incomes:
        d = _record_date(f)
        if d is None or not since <= d <= until:
            continue
        amount = _record_amount(f)
        amount_ok = _amount_ok(send.amount, amount)
        contradicts = bool(send.amount and amount) and not amount_ok
        if names & _norm_tokens(_record_text(f)) and not contradicts:
            return True
        amount_hits += amount_ok
    return amount_hits == 1
