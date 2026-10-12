"""Meta lidlari bo'yicha sotuvchi metrikalari: birinchi javob vaqti (ish soatida) va yopish foizi.

Birinchi javob = lid yaratilgandan keyingi sotuvchining birinchi harakati (chiquvchi qo'ng'iroq,
chiquvchi xabar yoki status o'zgartirish). Vaqt faqat ish soatlarida sanaladi
(`WORK_START`–`WORK_END`, Du–Sha, Toshkent) — kechasi kelgan lid ertalabgacha "kutmaydi".
"""
from __future__ import annotations

import datetime as dt
from statistics import median
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tashkent")
WORK_START, WORK_END = 9, 19
WORK_DAYS = {0, 1, 2, 3, 4, 5}  # Du..Sha
FIRST_TOUCH_EVENT_TYPES = ("outgoing_call", "outgoing_chat_message", "lead_status_changed")


def business_minutes(start: dt.datetime, end: dt.datetime) -> float:
    """[start, end) oralig'idagi ish daqiqalari."""
    start, end = start.astimezone(TZ), end.astimezone(TZ)
    if end <= start:
        return 0.0
    total = 0.0
    day = start.date()
    while day <= end.date():
        if day.weekday() in WORK_DAYS:
            w0 = dt.datetime.combine(day, dt.time(WORK_START), TZ)
            w1 = dt.datetime.combine(day, dt.time(WORK_END), TZ)
            lo, hi = max(start, w0), min(end, w1)
            if hi > lo:
                total += (hi - lo).total_seconds() / 60
        day += dt.timedelta(days=1)
    return total


def first_touch_ts(lead_created_ts: int, events: Iterable[Dict[str, Any]]) -> Optional[int]:
    """Lid yaratilgandan keyingi, odam (created_by != 0) qilgan birinchi harakat vaqti."""
    times = [
        int(e["created_at"]) for e in events
        if e.get("type") in FIRST_TOUCH_EVENT_TYPES
        and int(e.get("created_by") or 0) != 0
        and int(e.get("created_at") or 0) >= int(lead_created_ts)
    ]
    return min(times) if times else None


def aggregate(rows: List[Dict[str, Any]], now: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
    """`rows`: responsible_user_id, lead_created_ts, first_touch_ts, lead_won.

    Javob berilmagan lidlar uchun hozirgacha o'tgan vaqt sanaladi (yashirilmaydi).
    """
    now = now or dt.datetime.now(TZ)
    users: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        uid = r.get("responsible_user_id")
        if not uid or not r.get("lead_created_ts"):
            continue
        u = users.setdefault(int(uid), {"user_id": int(uid), "leads": 0, "won": 0, "lost": 0,
                                        "untouched": 0, "_minutes": []})
        u["leads"] += 1
        if r.get("lead_won") == 1:
            u["won"] += 1
        elif r.get("lead_won") == 0:
            u["lost"] += 1
        created = dt.datetime.fromtimestamp(int(r["lead_created_ts"]), TZ)
        if r.get("first_touch_ts"):
            touched = dt.datetime.fromtimestamp(int(r["first_touch_ts"]), TZ)
        else:
            u["untouched"] += 1
            touched = now
        u["_minutes"].append(business_minutes(created, touched))
    out = []
    for u in users.values():
        mins = u.pop("_minutes")
        closed = u["won"] + u["lost"]
        u["median_response_min"] = round(median(mins), 1) if mins else None
        u["close_rate"] = round(u["won"] * 100 / closed, 1) if closed else None
        out.append(u)
    return sorted(out, key=lambda x: -x["leads"])


def _fmt_minutes(m: Optional[float]) -> str:
    if m is None:
        return "—"
    if m < 60:
        return f"{m:.0f} daq"
    return f"{m / 60:.1f} soat"


def format_lines(stats: List[Dict[str, Any]], names: Dict[int, str], days: int) -> List[str]:
    if not stats:
        return []
    lines = [f"👤 <b>Sotuvchilar — Meta lidlari ({days} kun):</b>"]
    for s in stats:
        name = names.get(s["user_id"], f"#{s['user_id']}")
        rate = f"{s['close_rate']:.0f}%" if s["close_rate"] is not None else "—"
        warn = f", ⏳ {s['untouched']} ta javobsiz" if s["untouched"] else ""
        lines.append(f"• <b>{name}</b>: {s['leads']} lid, javob {_fmt_minutes(s['median_response_min'])}, "
                     f"yopish {rate}{warn}")
    lines.append("")
    return lines
