"""One watcher cycle: scan -> match Airtable income -> remind overdue sends."""
from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from src.services.core.card_watch import config
from src.services.core.card_watch.detector import CardSend
from src.services.core.card_watch.matcher import income_rows, is_paid

logger = logging.getLogger("CardWatch")

OWNER_KEY = "owner"
STATE_FILE = "data/card_watch_state.json"
AIRTABLE_URL = f"https://api.airtable.com/v0/{config.AIRTABLE_BASE}/{config.AIRTABLE_TABLE}"


def load_state(path: str = STATE_FILE) -> Dict[str, Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: Dict[str, Dict[str, Any]], path: str = STATE_FILE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def fetch_income_records(since_days: int) -> List[Dict[str, Any]]:
    """Read recent Tranzaksiyalar rows (sync; call via asyncio.to_thread)."""
    import requests

    from src.services.core.airtable_config import airtable_request_headers

    formula = f"AND({{Turi}}='Kirim', IS_AFTER({{Sana}}, DATEADD(TODAY(), -{int(since_days)}, 'days')))"
    params: Dict[str, Any] = {"filterByFormula": formula, "pageSize": 100}
    records: List[Dict[str, Any]] = []
    for _ in range(50):
        resp = requests.get(AIRTABLE_URL, headers=airtable_request_headers(), params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        records.extend(payload.get("records") or [])
        offset = payload.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return records


def _fmt_amount(amount: Optional[float]) -> str:
    if not amount:
        return "nomaʼlum"
    return f"{amount:,.0f}".replace(",", " ") + " soʻm"


def format_reminder(manager_name: str, sends: Iterable[CardSend], grace_days: int) -> str:
    lines = [
        f"💳 <b>{html.escape(manager_name)}</b>, karta yuborilgan, lekin {grace_days} kundan "
        "beri Airtableʼda kirim topilmadi:",
    ]
    for s in sends:
        lines.append(
            f"• {html.escape(s.client_name or s.chat_title)} — {_fmt_amount(s.amount)}, "
            f"{s.sent_at.strftime('%d.%m %H:%M')}, karta …{s.card[-4:]}"
        )
    lines.append("Toʻlovni tekshiring yoki mijozga eslating. Toʻlangan boʻlsa, kirimni Airtableʼga kiriting.")
    return "\n".join(lines)


def overdue_sends(
    sends: Iterable[CardSend],
    incomes: List[Dict[str, Any]],
    state: Dict[str, Dict[str, Any]],
    now: datetime,
    grace_days: int,
) -> List[CardSend]:
    """Unpaid sends older than ``grace_days`` that were not reminded yet."""
    due: List[CardSend] = []
    cutoff = now - timedelta(days=grace_days)
    for s in sends:
        entry = state.setdefault(s.uid, {"sent_at": s.sent_at.isoformat()})
        entry.update(manager=s.manager_key, client=s.client_name or s.chat_title,
                     amount=s.amount, card=s.card[-4:])
        if entry.get("paid") or entry.get("reminded_at"):
            continue
        if is_paid(s, incomes):
            entry["paid"] = True
            continue
        if s.sent_at <= cutoff:
            due.append(s)
    return due


Sender = Callable[[str, Optional[int]], Awaitable[bool]]


async def run_cycle(
    sends: List[CardSend],
    incomes_raw: List[Dict[str, Any]],
    send_message: Sender,
    now: Optional[datetime] = None,
    state_path: str = STATE_FILE,
) -> Dict[str, int]:
    """Match + remind. ``send_message(text, topic_id)`` posts to sales group/owner."""
    now = now or datetime.now(timezone.utc)
    grace = config.grace_days()
    state = load_state(state_path)
    unique: Dict[str, CardSend] = {}
    for s in sends:  # prefer a real manager over the "owner" fallback attribution
        if s.uid not in unique or unique[s.uid].manager_key == OWNER_KEY:
            unique[s.uid] = s
    due = overdue_sends(unique.values(), income_rows(incomes_raw), state, now, grace)
    managers = {m.key: m for m in config.load_managers()}
    by_manager: Dict[str, List[CardSend]] = {}
    for s in due:
        by_manager.setdefault(s.manager_key, []).append(s)
    reminded = 0
    for key, items in by_manager.items():
        mgr = managers.get(key)
        name = mgr.name if mgr else "Baxtiyorjon"
        topic = mgr.topic_id if mgr else config.OWNER_TOPIC_ID
        if await send_message(format_reminder(name, items, grace), topic):
            for s in items:
                state[s.uid]["reminded_at"] = now.isoformat()
            reminded += len(items)
    save_state(state, state_path)
    return {"sends": len(unique), "due": len(due), "reminded": reminded}


def manager_entries(state: Dict[str, Dict[str, Any]], manager_key: str) -> List[Dict[str, Any]]:
    return [e for k, e in state.items() if not k.startswith("_") and e.get("manager") == manager_key]


def format_report(manager_name: str, entries: List[Dict[str, Any]]) -> str:
    """Per-manager summary: sent / paid / waiting (reminded ones marked)."""
    paid = [e for e in entries if e.get("paid")]
    waiting = [e for e in entries if not e.get("paid")]
    lines = [
        f"📊 <b>{html.escape(manager_name)}</b> — karta kuzatuvi",
        f"Karta yuborilgan: {len(entries)} | Toʻlagan: {len(paid)} | Kutilmoqda: {len(waiting)}",
    ]
    for e in sorted(waiting, key=lambda x: x.get("sent_at", "")):
        mark = " ⏰" if e.get("reminded_at") else ""
        client = html.escape(str(e.get("client") or "?"))
        lines.append(f"• {client} — {_fmt_amount(e.get('amount'))}, {str(e.get('sent_at', ''))[:10]}{mark}")
    return "\n".join(lines)


async def send_daily_reports(send_message: Sender, today: str, state_path: str = STATE_FILE) -> int:
    """Once per day each manager gets own report in own topic (owner -> 118)."""
    state = load_state(state_path)
    meta = state.setdefault("_meta", {})
    if meta.get("report_date") == today:
        return 0
    targets = [(m.key, m.name, m.topic_id) for m in config.load_managers()]
    targets.append((OWNER_KEY, "Baxtiyorjon", config.OWNER_TOPIC_ID))
    sent = 0
    for key, name, topic in targets:
        entries = manager_entries(state, key)
        if entries and await send_message(format_report(name, entries), topic):
            sent += 1
    meta["report_date"] = today
    save_state(state, state_path)
    return sent
