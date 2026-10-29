"""
Kunlik lead generatsiyasi va sovuq bazani reaktivatsiya qilishni qo'lda ishga tushirish skripti.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, ".")
os.environ["AMOCRM_TOKEN_DB_PERSIST"] = "0"
sys.stdout.reconfigure(encoding="utf-8")

from src.schedulers.daily_lead_engine_scheduler import execute_daily_lead_cycle


async def main():
    print("==================================================")
    print("OISHA-OS: KUNLIK LEAD GENERATSIYA VA REAKTIVATSIYA")
    print("==================================================")
    report = await execute_daily_lead_cycle(cold_batch_size=5, tg_batch_size=5)
    print("\n✅ Sikl yakunlandi:")
    print(f"Sana: {report['date']}")
    print(f"Sovuq bazadan tushirilgan yangi leadlar soni: {report['cold_leads_created']}")
    for l in report.get("cold_leads", []):
        print(f"  • Asl #{l['original_id']} -> Yangi #{l['new_id']}: {l['name']}")
    print(f"Telegramdan tushirilgan potensial leadlar soni: {report['tg_leads_imported']}")
    for l in report.get("tg_leads", []):
        print(f"  • Yangi #{l['new_lead_id']}: {l['service']}")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
