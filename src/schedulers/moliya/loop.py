"""Moliya hisobotlari rejalashtiruvchisi — har bir hisobotni o'z vaqtida yuboradi.

``boot.py`` da bir marta ``asyncio.create_task(...)`` bilan ishga tushiriladi.
Har 60 soniyada tekshiradi; oyna 5 daqiqa — sikl siljisa ham o'tkazib
yubormaydi. Kunlik takrorlanish DB orqali to'siladi.
"""

from __future__ import annotations

import asyncio
import logging

from src.schedulers.moliya.balans import run_balans_eslatmasi, run_balans_report
from src.schedulers.moliya.cashflow import run_cashflow_report
from src.schedulers.moliya.helpers import run_once_per_day
from src.schedulers.moliya.pnl import run_pnl_report
from src.schedulers.moliya.qarzdorlik import run_qarzdorlik_report

logger = logging.getLogger(__name__)


async def moliya_hisobotlari_loop() -> None:
    from src.time_utils import get_local_now

    await asyncio.sleep(120)  # bot to'liq ko'tarilishini kutamiz

    logger.info("[MOLIYA] Hisobot sikli boshlandi")

    while True:
        try:
            now = get_local_now()
            day = now.strftime("%Y-%m-%d")

            # Qarzdorlik — dushanba 09:00
            if now.weekday() == 0 and now.hour == 9 and now.minute < 5:
                await run_once_per_day("moliya_qarzdorlik", day, run_qarzdorlik_report)

            # Balans — har kuni 09:00
            if now.hour == 9 and now.minute < 5:
                await run_once_per_day("moliya_balans", day, run_balans_report)

            # P&L — har oyning 1-sanasi 09:00, o'tgan oy hisoboti
            if now.day == 1 and now.hour == 9 and now.minute < 5:
                await run_once_per_day("moliya_pnl", day, lambda: run_pnl_report(now))

            # Cashflow — har kuni 19:00
            if now.hour == 19 and now.minute < 5:
                await run_once_per_day("moliya_cashflow", day, lambda: run_cashflow_report(now))

            # Kunlik balans eslatmasi — har kuni 20:00
            if now.hour == 20 and now.minute < 5:
                await run_once_per_day("moliya_balans_eslatma", day, run_balans_eslatmasi)

        except Exception:
            logger.error("[MOLIYA] Sikl xatosi", exc_info=True)

        await asyncio.sleep(60)
