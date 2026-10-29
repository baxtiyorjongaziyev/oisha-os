"""
Kunlik Lead Generatsiyasi va Qayta Uyg'otish Servisi (Daily Lead Engine Scheduler).

Har kuni ertalab (Toshkent vaqti bilan 09:00 da):
1. amoCRM sovuq bazasidan 5 ta dolzarb mijozni tahlil qilib, 'Mijoz tarixi' va
   'Munosabat o'rnatish strategiyasi' bilan 'Yangi LEads' bosqichiga tushiradi.
2. Telegram prospect kashfiyoti navbatidan yangi potensial mijozlarni amoCRMga uzatadi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.services.core.leads.cold_reactivator import ColdLeadReactivator
from src.services.core.leads.telegram_prospect_importer import TelegramProspectImporter
from src.time_utils import get_local_now

logger = logging.getLogger("daily_lead_engine")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STATE_FILE = _PROJECT_ROOT / "data" / "daily_lead_engine_state.json"


def _get_last_run_date() -> str:
    if not _STATE_FILE.exists():
        return ""
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("last_run_date", "")
    except Exception:
        return ""


def _set_last_run_date(date_str: str, report: Dict[str, Any]) -> None:
    os.makedirs(_STATE_FILE.parent, exist_ok=True)
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_run_date": date_str,
                "last_report": report,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    except Exception as e:
        logger.warning(f"[DAILY_LEAD_ENGINE] Holatni saqlashda xato: {e}")


async def execute_daily_lead_cycle(cold_batch_size: int = 5, tg_batch_size: int = 5) -> Dict[str, Any]:
    """Bir kunlik leadlarni tushirish siklini bajaradi."""
    logger.info("[DAILY_LEAD_ENGINE] Kunlik lead generatsiya sikli boshlandi...")
    loop = asyncio.get_event_loop()

    # 1. Sovuq baza reaktivatsiyasi (blocking HTTP so'rovlar alohida thread'da)
    reactivator = ColdLeadReactivator()
    cold_res = await loop.run_in_executor(None, lambda: reactivator.run_batch(count=cold_batch_size))
    logger.info(f"[DAILY_LEAD_ENGINE] Sovuq bazadan {cold_res['created_count']} ta yangi lead tushirildi.")

    # 2. Telegram potensial mijozlar importi
    importer = TelegramProspectImporter()
    tg_res = await importer.import_pending_prospects(limit=tg_batch_size)
    logger.info(f"[DAILY_LEAD_ENGINE] Telegramdan {tg_res['imported_count']} ta yangi lead tushirildi.")

    report = {
        "date": get_local_now().strftime("%Y-%m-%d"),
        "cold_leads_created": cold_res["created_count"],
        "cold_leads": cold_res.get("leads", []),
        "tg_leads_imported": tg_res["imported_count"],
        "tg_leads": tg_res.get("leads", []),
    }
    return report


async def daily_lead_engine_loop():
    """Doimiy fonda har kuni soat 09:00 da tekshiruvchi loop."""
    logger.info("[DAILY_LEAD_ENGINE] Scheduler loop ishga tushdi.")
    await asyncio.sleep(30)

    while True:
        try:
            now = get_local_now()
            today_str = now.strftime("%Y-%m-%d")
            last_run = _get_last_run_date()

            # Ertalabki vaqtda (soat 09:00 dan 21:00 gacha) bugun hali ishga tushmagan bo'lsa
            if 9 <= now.hour < 21 and last_run != today_str:
                report = await execute_daily_lead_cycle(cold_batch_size=5, tg_batch_size=5)
                _set_last_run_date(today_str, report)
                logger.info(f"[DAILY_LEAD_ENGINE] {today_str} uchun sikl muvaffaqiyatli yakunlandi: {report}")
        except Exception as e:
            logger.error(f"[DAILY_LEAD_ENGINE] Siklda kutilmagan xatolik: {e}")

        await asyncio.sleep(1800)  # Har 30 daqiqada tekshiradi
