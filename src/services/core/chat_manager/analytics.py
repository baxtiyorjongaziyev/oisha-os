"""Analitika — docs/reveo-clone-spec.md 3.3, `chat_manager` bazasidan hisoblanadi.

Davr: oxirgi N kun (Toshkent vaqti, UTC+5, yozgi vaqt yo'q). Hamma raqam
shu davrda faol bo'lgan dialoglar bo'yicha: davrda kamida bitta xabari bor.
"""
from __future__ import annotations

import datetime as dt
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from src.services.core.chat_manager import store

TASHKENT = dt.timezone(dt.timedelta(hours=5))
PERIODS = (7, 14, 30)
WORK_START, WORK_END = 9, 19
WEEKDAYS = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")


def _local(ts: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts, TASHKENT)


def is_after_hours(ts: float) -> bool:
    """19:00–9:00 va dam olish kunlari (shanba, yakshanba)."""
    moment = _local(ts)
    return moment.weekday() >= 5 or not WORK_START <= moment.hour < WORK_END


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _rows(sql: str, params: tuple) -> List[Dict[str, Any]]:
    with store._conn() as c:  # noqa: SLF001 - same package, read-only aggregate
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def build(days: int = 7, channel: str = "", now: Optional[float] = None) -> Dict[str, Any]:
    if days not in PERIODS:
        raise ValueError(f"days must be one of {PERIODS}")
    if channel and channel not in store.CHANNELS:
        raise ValueError(f"unknown channel: {channel}")
    end = now if now is not None else time.time()
    start = end - days * 86400
    channel_sql = " AND d.channel = ?" if channel else ""
    base = (start, end, channel) if channel else (start, end)

    messages = _rows(
        "SELECT m.dialog_id, m.direction, m.author, m.created_at, d.channel "
        "FROM dialog_messages m JOIN dialogs d ON d.id = m.dialog_id "
        f"WHERE m.created_at >= ? AND m.created_at <= ?{channel_sql} "  # nosec B608
        "ORDER BY m.dialog_id, m.created_at, m.id",
        base,
    )
    requests = _rows(
        "SELECT r.dialog_id, r.category, r.status, r.amocrm_lead_id, r.created_at, d.channel "
        "FROM chat_requests r JOIN dialogs d ON d.id = r.dialog_id "
        f"WHERE r.created_at >= ? AND r.created_at <= ?{channel_sql}",  # nosec B608
        base,
    )

    dialog_ids = {m["dialog_id"] for m in messages}
    incoming = [m for m in messages if m["direction"] == "in"]
    by_dialog: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for m in messages:
        by_dialog[m["dialog_id"]].append(m)

    # Javob tezligi: mijoz xabaridan keyingi birinchi operator javobigacha.
    reply_delays: List[float] = []
    operator_dialogs = set()
    drafted_dialogs = set()
    for dialog_id, items in by_dialog.items():
        waiting_since: Optional[float] = None
        for m in items:
            if m["direction"] == "in":
                waiting_since = waiting_since or m["created_at"]
            elif m["author"] == "operator":
                operator_dialogs.add(dialog_id)
                if waiting_since is not None:
                    reply_delays.append(m["created_at"] - waiting_since)
                waiting_since = None
            elif m["author"] == "ai_draft":
                drafted_dialogs.add(dialog_id)
    # AI qoralamasi mijozga ketmaydi — undan keyin ham dialog javob kutmoqda.
    unanswered = set()
    for dialog_id, items in by_dialog.items():
        sent = [m for m in items if m["author"] != "ai_draft"]
        if sent and sent[-1]["direction"] == "in":
            unanswered.add(dialog_id)

    by_category: Dict[str, set] = defaultdict(set)
    for r in requests:
        by_category[r["category"]].add(r["dialog_id"])
    leads = [r for r in requests if r["category"] == "lead"]
    interested_dialogs = by_category["interested"] | by_category["lead"]
    lead_dialogs = by_category["lead"]
    closed_dialogs = {r["dialog_id"] for r in leads if r["status"] == "done"}

    funnel = [
        {"key": "wrote", "title": "Yozdi", "count": len(dialog_ids)},
        {"key": "interested", "title": "Xaridga qiziqdi", "count": len(interested_dialogs)},
        {"key": "lead", "title": "Kontakt qoldirdi — zayavka", "count": len(lead_dialogs)},
        {"key": "closed", "title": "Menejer yopdi", "count": len(closed_dialogs)},
    ]
    for prev, step in zip(funnel, funnel[1:]):
        step["of_previous"] = _pct(step["count"], prev["count"])
        step["lost"] = max(prev["count"] - step["count"], 0)
    funnel[0]["of_previous"] = 100.0 if dialog_ids else 0.0
    funnel[0]["lost"] = 0

    heatmap = [[0] * 24 for _ in range(7)]
    for m in incoming:
        moment = _local(m["created_at"])
        heatmap[moment.weekday()][moment.hour] += 1
    peak = max(
        ((day, hour) for day in range(7) for hour in range(24)),
        key=lambda cell: heatmap[cell[0]][cell[1]],
    )
    after_hours = sum(1 for m in incoming if is_after_hours(m["created_at"]))

    daily: Dict[str, Dict[str, int]] = {}
    for offset in range(days - 1, -1, -1):
        key = _local(end - offset * 86400).strftime("%Y-%m-%d")
        daily[key] = {"dialogs": 0, "requests": 0}
    seen_day = set()
    for m in messages:
        key = _local(m["created_at"]).strftime("%Y-%m-%d")
        if key in daily and (m["dialog_id"], key) not in seen_day:
            seen_day.add((m["dialog_id"], key))
            daily[key]["dialogs"] += 1
    for r in requests:
        key = _local(r["created_at"]).strftime("%Y-%m-%d")
        if key in daily:
            daily[key]["requests"] += 1

    channels = []
    for name in store.CHANNELS:
        ids = {m["dialog_id"] for m in messages if m["channel"] == name}
        if not ids:
            continue
        ch_leads = {r["dialog_id"] for r in leads if r["channel"] == name}
        channels.append({
            "channel": name,
            "dialogs": len(ids),
            "share": _pct(len(ids), len(dialog_ids)),
            "leads": len(ch_leads),
            "conversion": _pct(len(ch_leads), len(ids)),
        })

    category_counts = Counter(r["category"] for r in requests)
    open_counts = Counter(r["category"] for r in requests if r["status"] == "open")
    return {
        "days": days,
        "channel": channel,
        "kpi": {
            "dialogs": len(dialog_ids),
            "interested": len(interested_dialogs),
            "interested_pct": _pct(len(interested_dialogs), len(dialog_ids)),
            "leads": len(leads),
            "leads_open": sum(1 for r in leads if r["status"] == "open"),
            "conversion": _pct(len(lead_dialogs), len(interested_dialogs)),
            "ai_drafted_pct": _pct(len(drafted_dialogs), len(dialog_ids)),
            "after_hours_pct": _pct(after_hours, len(incoming)),
        },
        "funnel": funnel,
        "outcomes": {
            "operator": len(operator_dialogs),
            "unanswered": len(unanswered),
            "avg_reply_min": round(sum(reply_delays) / len(reply_delays) / 60, 1)
            if reply_delays else None,
            "complaints": category_counts.get("complaint", 0),
        },
        "categories": [
            {"key": key, "title": title, "count": category_counts.get(key, 0),
             "open": open_counts.get(key, 0)}
            for key, title in store.REQUEST_CATEGORIES.items()
        ],
        "daily": [{"date": k, **v} for k, v in daily.items()],
        "channels": channels,
        "heatmap": {
            "weekdays": list(WEEKDAYS),
            "cells": heatmap,
            "peak": {"weekday": WEEKDAYS[peak[0]], "hour": peak[1]}
            if incoming else None,
            "after_hours_pct": _pct(after_hours, len(incoming)),
        },
    }
