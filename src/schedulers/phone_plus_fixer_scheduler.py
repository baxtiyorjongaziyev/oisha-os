"""Har soatda amoCRM kontaktlaridagi "+" siz raqamlarni tuzatadi.

``PHONE_PLUS_FIXER_ENABLED=0`` bilan oʻchadi; ``PHONE_PLUS_FIXER_INTERVAL_MIN``
oraliqni belgilaydi (default 60).
"""
from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def phone_plus_fixer_loop() -> None:
    if os.getenv("PHONE_PLUS_FIXER_ENABLED", "1") != "1":
        logger.info("[PHONE-PLUS] Oʻchirilgan")
        return
    try:
        interval = max(10, int(os.getenv("PHONE_PLUS_FIXER_INTERVAL_MIN", "60")))
    except ValueError:
        interval = 60
    await asyncio.sleep(300)
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    from src.services.core.crm.phone_plus_fixer import fix_contact_phones

    crm = AmoCRMSync()
    first_run = True
    while True:
        try:
            # Birinchi oʻtishda hamma kontakt, keyin faqat oxirgi yangilangan 1000 tasi.
            await fix_contact_phones(crm, max_pages=400 if first_run else 4)
            first_run = False
        except Exception as exc:
            logger.error("[PHONE-PLUS] Loop error: %s", exc)
        await asyncio.sleep(interval * 60)
