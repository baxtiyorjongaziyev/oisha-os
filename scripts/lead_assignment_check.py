"""Lid biriktirishni yoqishdan oldingi tekshiruv. FAQAT O'QISH.

Hetzner prod serverda (prod DB) ishga tushiriladi: GitHub Actions "Server read-only report"
workflow'ida `report=lead_assignment_check`.

Ko'rsatadi: sotuvchilar `employees` jadvalida bormi va faolmi, oxirgi 7 kunda
nechta kun davomat belgilagan, bugun kim ishda, guruh sozlamasi bormi.
Telefon, token yoki Telegram ID chiqarilmaydi (faqat bor/yo'q).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.core.leads.assignment import ROUTES, LeadAssigner, _matches  # noqa: E402
from src.time_utils import get_local_now  # noqa: E402

SELLER_PREFIXES = sorted({p for groups in ROUTES.values() for g in groups for p in g})


def _yes(value) -> str:
    return "bor" if value else "YO'Q"


async def main() -> int:
    from src.database_pool import db_pool
    from src.settings import settings

    problems = []
    try:
        employees = await db_pool.execute(
            "SELECT id, name, role, is_active, amo_id, telegram_id FROM employees ORDER BY name", []
        )
    except Exception as exc:
        print(f"employees jadvali o'qilmadi: {type(exc).__name__}")
        return 1
    print(f"Barcha xodimlar ({len(employees)}): " + ", ".join(
        f"{e['name']}{'' if e['is_active'] else ' (faol emas)'}" for e in employees))
    try:
        pend = await db_pool.execute(
            "SELECT full_name, state FROM attendance_link_requests ORDER BY id DESC LIMIT 20", [])
        print("Ulanish so'rovlari: " + (", ".join(f"{r['full_name']} [{r['state']}]" for r in pend) or "yo'q"))
    except Exception as exc:
        print(f"attendance_link_requests o'qilmadi: {type(exc).__name__}")
    print("\nSotuvchilar (employees):")
    sellers = [e for e in employees if _matches(e["name"], SELLER_PREFIXES)]
    for prefix in ("mumtoz", "rayxon", "shahnoz"):
        if not any(_matches(e["name"], [prefix, prefix.replace("x", "h")]) for e in sellers):
            problems.append(f"'{prefix}…' ismli xodim employees'da yo'q")
    for e in sellers:
        print(f"  #{e['id']} {e['name']} — rol: {e['role']}, faol: {_yes(e['is_active'])}, "
              f"amo_id: {e['amo_id'] or 'yoq (teg bilan beriladi)'}, telegram: {_yes(e['telegram_id'])}")
        if not e["is_active"]:
            problems.append(f"{e['name']} faol emas")

    today = get_local_now().date()
    week_ago = (today - timedelta(days=6)).isoformat()
    try:
        rows = await db_pool.execute(
            """SELECT emp.name, e.work_date, e.kind, e.server_ts FROM attendance_events e
            JOIN employees emp ON emp.id = e.employee_id
            WHERE e.work_date BETWEEN ? AND ? ORDER BY e.work_date, e.server_ts""",
            [week_ago, today.isoformat()],
        )
    except Exception as exc:
        print(f"\nattendance_events o'qilmadi: {type(exc).__name__}")
        return 1
    print(f"\nDavomat, {week_ago} … {today}:")
    for e in sellers:
        days = sorted({r["work_date"] for r in rows if r["name"] == e["name"] and r["kind"] == "check_in"})
        print(f"  {e['name']}: {len(days)} kun check_in")
        if not days:
            problems.append(f"{e['name']} 7 kunda bir marta ham check_in qilmagan")
    print(f"\nBugun ({today}):")
    for r in rows:
        if r["work_date"] == today.isoformat() and _matches(r["name"], SELLER_PREFIXES):
            print(f"  {r['server_ts']} {r['name']} {r['kind']}")
    duty = await LeadAssigner(None, db_pool).on_duty()
    print("Hozir ishda: " + (", ".join(p["name"] for p in duty) or "hech kim"))

    group = getattr(settings, "TARGET_LEADS_GROUP_ID", None)
    print(f"\nTARGET_LEADS_GROUP_ID: {_yes(group)}, BOT_TOKEN: {_yes(settings.BOT_TOKEN.get_secret_value())}")
    if not group:
        problems.append("TARGET_LEADS_GROUP_ID sozlanmagan — guruhga xabar ketmaydi")

    print("\nXULOSA: " + ("tayyor" if not problems else "TAYYOR EMAS"))
    for p in problems:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
