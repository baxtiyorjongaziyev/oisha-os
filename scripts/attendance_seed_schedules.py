"""src/services/core/attendance/team_schedules.json dagi grafiklarni xodim ismi bo'yicha bazaga yozadi.

Ishlatish (serverda, ofis geofence sozlangandan keyin):
    python scripts/attendance_seed_schedules.py            # faqat ko'rsatadi (dry-run)
    python scripts/attendance_seed_schedules.py --apply    # yozadi

Ism ``employees.name`` da aniq bitta faol xodimga mos kelmasa — o'tkazib yuboriladi va
ekranga chiqariladi; taxmin bilan yozilmaydi.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main(apply: bool) -> int:
    from src.database_pool import db_pool
    from src.services.core.attendance import admin
    from src.services.core.attendance.schema import init_attendance_tables

    cfg = json.loads((ROOT / "src" / "services" / "core" / "attendance" / "team_schedules.json").read_text(encoding="utf-8"))
    await init_attendance_tables(db_pool)
    problems = 0
    for item in cfg["employees"]:
        rows = await db_pool.execute(
            "SELECT id, name FROM employees WHERE is_active = 1 AND lower(name) LIKE lower(?)",
            [f"%{item['name']}%"])
        if len(rows) != 1:
            problems += 1
            print(f"SKIP {item['name']}: {len(rows)} ta mos xodim topildi {[r['name'] for r in rows]}")
            continue
        emp_id = int(rows[0]["id"])
        print(f"{'APPLY' if apply else 'DRY  '} {item['name']} (id={emp_id}): {item['weekdays']}"
              f" optional={item.get('optional_weekdays', [])}")
        if apply:
            await admin.set_schedule(db_pool, actor="seed-script", employee_id=emp_id,
                                     weekdays=item["weekdays"], optional_weekdays=item.get("optional_weekdays"),
                                     valid_from=date.today().isoformat())
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    sys.exit(asyncio.run(main(parser.parse_args().apply)))
