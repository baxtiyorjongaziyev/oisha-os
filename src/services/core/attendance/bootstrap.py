"""Birinchi ishga tushishda avtomatik sozlash (server .env/skriptsiz).

Faqat bo'sh joyni to'ldiradi: geofence yo'q bo'lsa — owner bergan ofis; xodimning grafigi
yo'q bo'lsa va ismi aniq bitta xodimga mos kelsa — ``team_schedules``. Mavjud sozlama
hech qachon ustidan yozilmaydi.
"""
from __future__ import annotations

import logging
from datetime import date

from src.services.core.attendance import admin, repo
from src.services.core.attendance.team_schedules import OFFICE, TEAM_SCHEDULES

logger = logging.getLogger(__name__)
ACTOR = "auto-bootstrap"


async def run(db, today: date | None = None) -> dict:
    report = {"office": "exists", "schedules": [], "skipped": []}
    if await repo.active_geofence(db) is None:
        await admin.configure_office(db, actor=ACTOR, **OFFICE)
        report["office"] = "created"
    day = (today or date.today()).isoformat()
    for item in TEAM_SCHEDULES:
        rows = await db.execute("SELECT id FROM employees WHERE is_active = 1 AND lower(name) LIKE lower(?)",
                                [f"%{item['name']}%"])
        if len(rows) != 1:
            report["skipped"].append(f"{item['name']}: {len(rows)} ta mos")
            continue
        emp_id = int(rows[0][0])
        if await repo.one(db, "SELECT 1 FROM shift_assignments WHERE employee_id = ?", [emp_id]):
            continue
        await admin.set_schedule(db, actor=ACTOR, employee_id=emp_id, weekdays=item["weekdays"],
                                 optional_weekdays=item.get("optional_weekdays"), valid_from=day)
        report["schedules"].append(item["name"])
    logger.info("[ATTENDANCE] bootstrap: %s", report)
    return report
