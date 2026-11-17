"""Timing rules -> internal alerts for managers (never messages to clients).

* client waiting > 5 min for a reply -> "reply" alert
* price sent, client silent 6 h -> follow-up suggestion
* card sent, unpaid 12 h -> payment reminder suggestion
* at most 2 follow-up suggestions per chat event (price / card)

State (``data/sales_copilot_state.json``) keeps per-chat dedupe and the manager key.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.services.core.sales_copilot.signals import Signals
from src.services.core.sales_copilot.transcript import Transcript

STATE_FILE = "data/sales_copilot_state.json"
REPLY_AFTER = timedelta(minutes=5)
REPLY_MAX_AGE = timedelta(hours=12)  # older silence is a ghost, not a "reply now"
PRICE_FOLLOWUP_AFTER = timedelta(hours=6)
CARD_REMINDER_AFTER = timedelta(hours=12)
MAX_FOLLOWUPS = 2


@dataclass(frozen=True)
class Alert:
    kind: str  # "reply" | "price_followup" | "card_reminder"
    uid: str
    manager_key: str
    client: str
    since: datetime
    draft: str = ""


def load_state(path: str = STATE_FILE) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: Dict[str, Any], path: str = STATE_FILE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _entry(state: Dict[str, Any], t: Transcript) -> Dict[str, Any]:
    chats = state.setdefault("chats", {})
    e = chats.setdefault(t.uid, {})
    e["manager"] = t.manager_key
    e["client"] = t.client_name or t.chat_title
    return e


def _followup(e: Dict[str, Any], kind: str, event_at: datetime, now: datetime,
              after: timedelta, s: Signals) -> bool:
    """Suggest a follow-up once per ``after`` window, max MAX_FOLLOWUPS per event."""
    if s.last_side != "us" or s.last_at is None or now - s.last_at < after:
        return False
    if s.client_last_at and s.client_last_at > event_at:
        return False  # client already answered after the price/card
    rec = e.setdefault(kind, {})
    if rec.get("event") != event_at.isoformat():
        rec.clear()
        rec.update(event=event_at.isoformat(), count=0)
    if rec["count"] >= MAX_FOLLOWUPS or s.followups > MAX_FOLLOWUPS:
        return False
    last = rec.get("last")
    if last and now - datetime.fromisoformat(last) < after:
        return False
    rec["count"] += 1
    rec["last"] = now.isoformat()
    return True


def evaluate(
    t: Transcript,
    s: Signals,
    state: Dict[str, Any],
    now: datetime,
    paid: bool = False,
    draft: str = "",
) -> List[Alert]:
    """Alerts due now for one chat; mutates ``state`` for dedupe."""
    if not t.messages or t.manager_key in ("", "owner"):
        return []
    e = _entry(state, t)
    client = t.client_name or t.chat_title
    out: List[Alert] = []
    if s.last_side == "client" and s.last_at and REPLY_AFTER <= now - s.last_at <= REPLY_MAX_AGE:
        if e.get("reply_alerted_for") != s.last_at.isoformat():
            e["reply_alerted_for"] = s.last_at.isoformat()
            out.append(Alert("reply", t.uid, t.manager_key, client, s.last_at))
    if paid:
        return out
    if s.card_at and _followup(e, "card", s.card_at, now, CARD_REMINDER_AFTER, s):
        out.append(Alert("card_reminder", t.uid, t.manager_key, client, s.card_at, draft))
    elif s.price_at and not s.card_at and _followup(e, "price", s.price_at, now, PRICE_FOLLOWUP_AFTER, s):
        out.append(Alert("price_followup", t.uid, t.manager_key, client, s.price_at, draft))
    return out


def reply_alert_from_last(
    uid: str, manager_key: str, client: str, last_out: bool, last_at: Optional[datetime],
    state: Dict[str, Any], now: datetime,
) -> Optional[Alert]:
    """Cheap 5-minute check from a dialog's last message only (no history fetch)."""
    if last_out or last_at is None or manager_key in ("", "owner"):
        return None
    if not REPLY_AFTER <= now - last_at <= REPLY_MAX_AGE:
        return None
    e = state.setdefault("chats", {}).setdefault(uid, {"manager": manager_key, "client": client})
    if e.get("reply_alerted_for") == last_at.isoformat():
        return None
    e["reply_alerted_for"] = last_at.isoformat()
    return Alert("reply", uid, manager_key, client, last_at)
