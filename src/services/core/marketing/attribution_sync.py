"""AmoCRM bitim narxi/yakunini `lead_attribution` jadvaliga sinxronlaydi.

`metasell_revenue.py`ning marketing versiyasi: farqi — u faqat qo'ng'iroq
bo'lgan leadlarni qamraydi (`call_analyses`), bu esa Meta Lead Ads orqali
kelgan HAR BIR leadni (qo'ng'iroq bo'ladimi yo'qmi) qamraydi — chunki
kampaniya ROI'si uchun barcha lead kerak, faqat qo'ng'iroq qilinganlari emas.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from src.services.core.marketing.attribution_store import (
    pending_revenue_sync,
    update_revenue,
)
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

STATUS_WON = 142
STATUS_LOST = 143
_REQUEST_DELAY_SECONDS = 0.2


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class AttributionSyncResult:
    checked: int = 0
    updated: int = 0
    won: int = 0
    lost: int = 0
    still_open: int = 0
    failed: int = 0

    def to_dict(self) -> dict:
        return {
            "checked": self.checked,
            "updated": self.updated,
            "won": self.won,
            "lost": self.lost,
            "still_open": self.still_open,
            "failed": self.failed,
        }


async def sync_attribution_revenue(
    amocrm: Any, days: int = 90, limit: int = 200
) -> AttributionSyncResult:
    """Ochiq (lead_won IS NULL) yozuvlarni AmoCRM'dan yangilaydi."""
    result = AttributionSyncResult()
    if amocrm is None:
        return result

    pending = await asyncio.to_thread(pending_revenue_sync, days, limit)
    if not pending:
        return result

    for row in pending:
        result.checked += 1
        leadgen_id = row["leadgen_id"]
        lead_id = row["lead_id"]
        try:
            lead = await amocrm.get_lead(int(lead_id))
        except Exception as exc:
            logger.warning("[ADS ATTRIBUTION] Bitim %s olinmadi: %s", lead_id, exc)
            result.failed += 1
            continue
        if not lead:
            result.failed += 1
            continue

        price = _to_float(lead.get("price"))
        status_id = lead.get("status_id")
        if status_id == STATUS_WON:
            won: int | None = 1
            result.won += 1
        elif status_id == STATUS_LOST:
            won = 0
            result.lost += 1
        else:
            won = None
            result.still_open += 1

        try:
            await asyncio.to_thread(
                update_revenue, leadgen_id, price, won, get_local_now().isoformat()
            )
            result.updated += 1
        except Exception as exc:
            logger.warning("[ADS ATTRIBUTION] Yozib bo'lmadi (%s): %s", leadgen_id, exc)

        await asyncio.sleep(_REQUEST_DELAY_SECONDS)

    logger.info("[ADS ATTRIBUTION] Sinxronizatsiya: %s", result.to_dict())
    return result
