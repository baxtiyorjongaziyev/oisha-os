"""Moliya hisobotlari rejalashtiruvchisi — har bir hisobotni o'z vaqtida yuboradi.

``boot.py`` da bir marta ``asyncio.create_task(...)`` bilan ishga tushiriladi.
Har 60 soniyada tekshiradi; oyna 5 daqiqa — sikl siljisa ham o'tkazib
yubormaydi. Kunlik takrorlanish DB orqali to'siladi.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from src.schedulers.moliya.balans import run_balans_eslatmasi, run_balans_report
from src.schedulers.moliya.cashflow import run_cashflow_report
from src.schedulers.moliya.helpers import run_once_per_day
from src.schedulers.moliya.kuzatuv import run_kuzatuv_report
from src.schedulers.moliya.pnl import run_pnl_report
from src.schedulers.moliya.qarzdorlik import run_qarzdorlik_report
from src.schedulers.moliya.soliq import SOLIQ_KUNLARI, run_soliq_eslatma

from src.schedulers.moliya.moliyachi_skill import run_skill_update

logger = logging.getLogger(__name__)


KUZATUV_HOUR = 9


def kuzatuv_target(now: datetime) -> Optional[datetime]:
    """09:00–09:04 da kechagi toʻliq kun uchun kuzatuv hisobotini qaytaradi."""
    if now.hour == KUZATUV_HOUR and now.minute < 5:
        return now - timedelta(days=1)
    return None


_last_reconcile_slot: list[Optional[str]] = [None]


def reconcile_slot(now: datetime) -> Optional[str]:
    """Yarim soatlik slot (5 daqiqalik oyna) — sikl siljisa ham oʻtkazib yuborilmaydi."""
    if now.minute % 30 < 5:
        return now.strftime("%Y-%m-%d %H:") + ("00" if now.minute < 30 else "30")
    return None


def hisobchi_active() -> bool:
    """HISOBCHI_ACTIVE=1 bo'lmasa guruhga hisobot/eslatma yuborilmaydi (default: to'xtatilgan)."""
    return os.getenv("HISOBCHI_ACTIVE", "").strip().lower() in {"1", "true", "yes", "on"}


async def _run_group_reports(now: datetime, day: str) -> None:
    """Faol Hisobchi rejimidagi guruh hisobotlari va eslatmalar."""
    if now.weekday() == 0 and now.hour == 9 and now.minute < 5:
        await run_once_per_day("moliya_qarzdorlik", day, run_qarzdorlik_report)
    if now.hour == 9 and now.minute < 5:
        await run_once_per_day("moliya_balans", day, run_balans_report)
    if now.day == 1 and now.hour == 9 and now.minute < 5:
        await run_once_per_day("moliya_pnl", day, lambda: run_pnl_report(now))
    if now.hour == 19 and now.minute < 5:
        await run_once_per_day("moliya_cashflow", day, lambda: run_cashflow_report(now))
    if now.hour == 20 and now.minute < 5:
        await run_once_per_day("moliya_balans_eslatma", day, run_balans_eslatmasi)


async def moliya_hisobotlari_loop() -> None:
    from src.time_utils import get_local_now

    await asyncio.sleep(120)  # bot toʻliq koʻtarilishini kutamiz

    logger.info("[MOLIYA] Hisobot sikli boshlandi")

    while True:
        try:
            now = get_local_now()
            day = now.strftime("%Y-%m-%d")

            if now.hour == 0 and 10 <= now.minute < 15:
                yesterday = now - timedelta(days=1)
                await run_once_per_day(
                    "moliyachi_skill", day,
                    lambda: run_skill_update(yesterday, send=yesterday.weekday() == 6),
                )

            # Soliq eslatmasi — egasiga; Hisobchi toʼxtatilgan boʼlsa ham ishlaydi
            if now.day in SOLIQ_KUNLARI and now.hour == 9 and now.minute < 5:
                await run_once_per_day("soliq_eslatma", day, lambda: run_soliq_eslatma(now))

            # Hisobchi kuzatuvi (moliyachi ishini oʻrganish) — egasiga, 09:00 (kechagi kun)
            target = kuzatuv_target(now)
            if target is not None:
                await run_once_per_day(
                    "moliya_kuzatuv", day, lambda t=target: run_kuzatuv_report(t)
                )

            # Airtable boʻsh maydonlarni bittama-bitta soʻrash — 10:00
            if now.hour == 10 and now.minute < 5:
                from src.services.core.finance.airtable_gap_filler import run_daily_gap_prompt

                await run_once_per_day("airtable_gap_prompt", day, run_daily_gap_prompt)

            # Kunlik qoldiq rekonsiliatsiyasi — har 30 daqiqada (quiet-hours ichida jim)
            slot = reconcile_slot(now)
            if slot is not None and slot != _last_reconcile_slot[0]:
                from src.services.core.finance.balance_reconcile import run_balance_reconcile

                _last_reconcile_slot[0] = slot
                await run_balance_reconcile(now)

            if hisobchi_active():
                await _run_group_reports(now, day)

        except Exception:
            logger.error("[MOLIYA] Sikl xatosi", exc_info=True)

        await asyncio.sleep(60)
