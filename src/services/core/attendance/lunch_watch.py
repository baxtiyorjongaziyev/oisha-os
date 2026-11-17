"""Obeddan qaytmaganlarni aniqlash.

Owner qarori (2026-11-17): obed 13:00–14:00 (Toshkent). 14:00 + grace dan keyin ham
ofisga qaytmagan xodim ownerʼga (yoki ATTENDANCE_NOTIFY_CHAT_ID) bildiriladi.

Manba — ``attendance_auto_state`` (Telegram jonli lokatsiyasi): bugun "keldi" qoʼygan,
hali "ketdi" qoʼymagan, hozir aniq tashqarida va obed tugashidan oldin chiqib ketgan xodim.
Jonli lokatsiya yubormaydigan xodim holati nomaʼlum — u roʼyxatga tushmaydi.
"""
from __future__ import annotations

import html
import os
from dataclasses import dataclass
from datetime import datetime, time
from typing import Iterable, Optional

LUNCH_START, LUNCH_END = time(13, 0), time(14, 0)
DEFAULT_GRACE_MIN = 10
# Lokatsiya shuncha vaqt yangilanmasa, xabarda "lokatsiya eski" deb belgilanadi.
STALE_AFTER_MIN = 30


@dataclass(frozen=True)
class LateReturner:
    employee_id: int
    name: str
    minutes_over: int
    stale: bool


def grace_minutes() -> int:
    try:
        return max(0, int(os.getenv("LUNCH_RETURN_GRACE_MIN", str(DEFAULT_GRACE_MIN))))
    except ValueError:
        return DEFAULT_GRACE_MIN


def lunch_end_ts(now_local: datetime) -> int:
    return int(datetime.combine(now_local.date(), LUNCH_END, now_local.tzinfo).timestamp())


def late_returners(rows: Iterable[dict], now_ts: int, end_ts: int, grace_min: int) -> list[LateReturner]:
    """``rows``: employee_id, name, inside, outside_since, last_seen (epoch soniya).

    Faqat bugun kelgan va ketmagan xodimlar qatorlari berilishi kerak."""
    if now_ts < end_ts + grace_min * 60:
        return []
    out = []
    for r in rows:
        since = r.get("outside_since")
        if int(r.get("inside") or 0) or not since:
            continue
        if int(since) > end_ts:
            continue  # obeddan keyin chiqqan — bu obed kechikishi emas
        if int(since) < end_ts - 14 * 3600:
            continue  # kechagi holat (bugun lokatsiya kelmagan)
        stale = now_ts - int(r.get("last_seen") or 0) > STALE_AFTER_MIN * 60
        out.append(LateReturner(int(r["employee_id"]), str(r["name"]), (now_ts - end_ts) // 60, stale))
    return sorted(out, key=lambda x: x.name)


def format_alert(items: list[LateReturner]) -> str:
    lines = ["🍽️ Obed 14:00 da tugagan, hali ofisga qaytmaganlar:"]
    for it in items:
        tail = " (lokatsiya eski)" if it.stale else ""
        lines.append(f"• {html.escape(it.name)} — {it.minutes_over} daq kechikish{tail}")
    return "\n".join(lines)


async def find_late_returners(db, now_local: datetime, *, grace_min: Optional[int] = None) -> list[LateReturner]:
    from src.services.core.attendance import auto_presence

    await auto_presence.init_tables(db)
    day = now_local.date().isoformat()
    rows = await db.execute(
        """SELECT e.id AS employee_id, e.name, s.inside, s.outside_since, s.last_seen
        FROM attendance_auto_state s JOIN employees e ON e.id = s.employee_id
        WHERE e.is_active = 1
          AND EXISTS (SELECT 1 FROM attendance_sessions a WHERE a.employee_id = e.id
                      AND a.work_date = ? AND a.kind = 'check_in' AND a.state = 'confirmed')
          AND NOT EXISTS (SELECT 1 FROM attendance_sessions a WHERE a.employee_id = e.id
                          AND a.work_date = ? AND a.kind = 'check_out' AND a.state = 'confirmed')""",
        [day, day],
    )
    dict_rows = [{k: r[k] for k in ("employee_id", "name", "inside", "outside_since", "last_seen")} for r in rows]
    g = grace_minutes() if grace_min is None else grace_min
    return late_returners(dict_rows, int(now_local.timestamp()), lunch_end_ts(now_local), g)
