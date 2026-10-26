"""Davomatni to'liq Telegram ichida yuritish: ulanish so'rovi, owner tasdig'i, hisobotlar.

Sayt va Telegram Login widget kerak emas: xodim botga ``/ulanish Ism Familiya`` yozadi,
owner'ga tugmali xabar keladi. Hisobotlar faqat vaqt va holatni ko'rsatadi.
"""
from __future__ import annotations

import html
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.services.core.attendance import bootstrap, linking, reports, rules
from src.services.core.attendance.schema import init_attendance_tables
from src.services.core.attendance.service import AttendanceError

_TZ = ZoneInfo("Asia/Tashkent")
CB_APPROVE, CB_REJECT = "att_link:ok:", "att_link:no:"

LIVE_HOWTO = (
    "📍 Endi botga <b>jonli lokatsiya</b> yuboring: 📎 → Lokatsiya → «Jonli lokatsiyani ulashish» "
    "→ «To'xtatmaguncha». Ofisga kirsangiz «keldi», 17:00 dan keyin chiqib ketsangiz «ketdi» o'zi belgilanadi."
)

_ERRORS = {
    "already_linked": "Siz allaqachon ulangansiz. " + LIVE_HOWTO,
    "name_required": "Ism-familiyani yozing: /ulanish Ism Familiya",
    "request_not_found": "So'rov topilmadi yoki allaqachon ko'rib chiqilgan.",
    "employee_not_linkable": "Bu xodimni ulab bo'lmaydi.",
}


def error_text(exc: AttendanceError) -> str:
    return _ERRORS.get(exc.code, f"Xatolik: {exc.code}")


async def request_link(db, telegram_id: int, full_name: str) -> dict:
    await init_attendance_tables(db)
    return await linking.request(db, telegram_id=telegram_id, full_name=full_name)


def owner_request_text(name: str, username: str | None) -> str:
    who = html.escape(name) + (f" (@{html.escape(username)})" if username else "")
    return f"🆕 <b>Davomatga ulanish so'rovi</b>\n👤 {who}\nTasdiqlaysizmi?"


def owner_buttons(request_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Tasdiqlash", "callback_data": f"{CB_APPROVE}{request_id}"},
        {"text": "❌ Rad etish", "callback_data": f"{CB_REJECT}{request_id}"},
    ]]}


async def decide(db, *, actor: str, data: str) -> tuple[str, int | None]:
    """Owner tugmasi. (owner'ga matn, xodimning telegram_id si yoki None)."""
    approve = data.startswith(CB_APPROVE)
    request_id = int(data.split(":")[-1])
    rows = await db.execute("SELECT telegram_id, full_name FROM attendance_link_requests WHERE id = ?",
                            [request_id])
    if not rows:
        raise AttendanceError("request_not_found", 404)
    tg, name = int(rows[0]["telegram_id"]), str(rows[0]["full_name"])
    if approve:
        await linking.approve(db, actor=actor, request_id=request_id)
        await bootstrap.run(db)  # ism team_schedules'ga mos bo'lsa grafik qo'yiladi
        return f"✅ {html.escape(name)} davomatga ulandi.", tg
    await linking.reject(db, actor=actor, request_id=request_id)
    return f"❌ {html.escape(name)} so'rovi rad etildi.", tg


def _local(ts: str) -> str:
    return datetime.fromisoformat(ts).astimezone(_TZ).strftime("%H:%M")


async def today_text(db, day: date | None = None) -> str:
    await init_attendance_tables(db)
    day = day or datetime.now(_TZ).date()
    board = await reports.dashboard(db, day, rules.Calendar())
    by_emp: dict[str, dict] = {}
    for e in board["events"]:
        by_emp.setdefault(e["employee_name"], {})[e["kind"]] = e
    names = [str(r["name"]) for r in await db.execute(
        "SELECT name FROM employees WHERE is_active = 1 ORDER BY name", [])]
    lines = [f"📋 <b>Davomat — {day.isoformat()}</b>"]
    for name in names:
        ev = by_emp.get(name, {})
        cin, cout = ev.get("check_in"), ev.get("check_out")
        if cin is None:
            lines.append(f"▫️ {html.escape(name)} — kelmagan")
            continue
        late = f", {cin['minutes_late']} daq kech" if cin["minutes_late"] else ""
        out = f", ketdi {cout['local_time']}" if cout else ", hali ishda"
        lines.append(f"{'⏰' if cin['minutes_late'] else '✅'} {html.escape(name)} — keldi {cin['local_time']}{late}{out}")
    if not names:
        lines.append("Hali hech kim ulanmagan. Xodimlar botga /ulanish Ism Familiya yozsin.")
    return "\n".join(lines)


async def month_text(db, today: date | None = None) -> str:
    from src.services.core.attendance import summary

    await init_attendance_tables(db)
    today = today or datetime.now(_TZ).date()
    start = today.replace(day=1)
    rows = await summary.period_summary(db, start, today, today=today)
    lines = [f"📊 <b>Davomat — {start.isoformat()} … {today.isoformat()}</b>"]
    for r in rows:
        lines.append(f"• {html.escape(str(r['name']))}: {r['present_days']}/{r['scheduled_days']} kun, "
                     f"kech {r['late_days']} marta ({r['late_minutes']} daq), kelmagan {r['absent_days']}")
    if not rows:
        lines.append("Hali ma'lumot yo'q.")
    return "\n".join(lines)
