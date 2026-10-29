"""24/7 background scheduler: Meta Lead Ads avtomatik optimizatsiyasi.

Har `META_LEAD_OPTIMIZER_INTERVAL_SEC` da barcha faol Ad Set'larni skaner qiladi
va oddiy forma rejimida turganlarini `QUALITY_LEAD` (Conversion Leads) ga o'tkazadi.
Inson aralashuvisiz, fon rejimida to'liq avtonom ishlaydi.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from src.services.core.marketing.meta_lead_optimizer import (
    notify_optimization_success,
    run_lead_optimization_sweep,
)

logger = logging.getLogger("MetaLeadOptimizerScheduler")

# Standart interval: 6 soat (21600 soniya)
_DEFAULT_INTERVAL_SEC = 21600


def _is_enabled() -> bool:
    val = os.getenv("META_LEAD_OPTIMIZER_ENABLED", "1").strip().lower()
    return val not in {"0", "false", "no", "off"}


def _get_interval() -> int:
    try:
        return int(os.getenv("META_LEAD_OPTIMIZER_INTERVAL_SEC", str(_DEFAULT_INTERVAL_SEC)))
    except ValueError:
        return _DEFAULT_INTERVAL_SEC


async def meta_lead_optimizer_loop(bot_runtime: Any = None) -> None:
    """Doimiy fonda aylanuvchi optimizatsiya sikli."""
    interval = _get_interval()
    logger.info("[META OPTIMIZER LOOP] Ishga tushdi (interval=%ds)", interval)

    # Server qayta yoqilganda asosiy xizmatlar ko'tarilib olishi uchun 90 soniya kutadi
    try:
        await asyncio.sleep(90)
    except asyncio.CancelledError:
        logger.info("[META OPTIMIZER LOOP] Startup bekor qilindi")
        return

    while True:
        try:
            if not _is_enabled():
                logger.debug("[META OPTIMIZER LOOP] META_LEAD_OPTIMIZER_ENABLED=0 — o'chiq")
            else:
                res = await asyncio.to_thread(run_lead_optimization_sweep)
                converted_list = res.get("converted") or []
                if converted_list:
                    for name in converted_list:
                        await notify_optimization_success(name, "", bot_runtime)
                logger.info(
                    "[META OPTIMIZER LOOP] Skan yakunlandi: %d ta guruh ko'rildi, %d ta o'tkazildi, %d ta kutishda",
                    res.get("scanned", 0),
                    len(converted_list),
                    len(res.get("pending", [])),
                )
        except asyncio.CancelledError:
            logger.info("[META OPTIMIZER LOOP] To'xtatildi")
            break
        except Exception as exc:
            logger.error("[META OPTIMIZER LOOP] Sikl xatosi: %s", exc, exc_info=True)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[META OPTIMIZER LOOP] Cancelled")
            break
