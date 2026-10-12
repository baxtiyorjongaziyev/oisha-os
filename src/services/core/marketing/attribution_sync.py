"""AmoCRM bitim narxi/yakunini `lead_attribution` jadvaliga sinxronlaydi.

`metasell_revenue.py`ning marketing versiyasi: farqi — u faqat qo'ng'iroq
bo'lgan leadlarni qamraydi (`call_analyses`), bu esa Meta Lead Ads orqali
kelgan HAR BIR leadni (qo'ng'iroq bo'ladimi yo'qmi) qamraydi — chunki
kampaniya ROI'si uchun barcha lead kerak, faqat qo'ng'iroq qilinganlari emas.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.services.core.marketing.attribution_store import (
    has_first_touch,
    pending_revenue_sync,
    update_revenue,
    update_seller_info,
)
from src.services.core.marketing.seller_metrics import FIRST_TOUCH_EVENT_TYPES, first_touch_ts
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


async def _notify_capi(lead_id: Any, status_id: Any, price: float, leadgen_id: str) -> bool:
    """Meta CAPI (Conversion Leads) — status o'zgarishini Meta'ga qaytarish.

    False — event yuborilmadi va qayta urinish kerak (yozuvni yakunlamaslik uchun).
    """
    try:
        from src.services.core.marketing.meta_capi_triggers import on_amo_status
        result = await on_amo_status(int(lead_id), status_id, price=price, leadgen_id=leadgen_id)
    except Exception as exc:
        logger.warning("[ADS ATTRIBUTION] CAPI yuborilmadi (%s): %s", leadgen_id, type(exc).__name__)
        return False
    return result is None or result.status != "failed"


def _to_int(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


_FIRST_TOUCH_LOOKBACK_SEC = 14 * 86400


async def _fetch_lead_events(amocrm: Any, lead_id: int) -> list:
    import requests

    params = {"filter[entity]": "lead", "filter[entity_id][0]": lead_id, "limit": 100}
    for i, t in enumerate(FIRST_TOUCH_EVENT_TYPES):
        params[f"filter[type][{i}]"] = t
    resp = await amocrm._request_with_auth(
        requests.get, f"{amocrm.base_url}/api/v4/events", params=params, timeout=30,
    )
    if resp.status_code != 200:
        return []
    return (resp.json() or {}).get("_embedded", {}).get("events", [])


async def _sync_seller_info(amocrm: Any, leadgen_id: str, lead_id: int, lead: dict, names: dict) -> None:
    """Mas'ul sotuvchi va birinchi javob vaqtini yozadi (javob topilguncha, 14 kun ichida)."""
    uid = _to_int(lead.get("responsible_user_id"))
    created_ts = _to_int(lead.get("created_at"))
    if uid and uid not in names:
        names[uid] = await asyncio.to_thread(amocrm.get_user_name, uid)
    touch = None
    if created_ts and not await asyncio.to_thread(has_first_touch, leadgen_id)             and time.time() - created_ts < _FIRST_TOUCH_LOOKBACK_SEC:
        touch = first_touch_ts(created_ts, await _fetch_lead_events(amocrm, lead_id))
    await asyncio.to_thread(
        update_seller_info, leadgen_id, uid, names.get(uid, "") if uid else "", created_ts, touch,
    )


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

    names: dict = {}
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

        if not await _notify_capi(lead_id, status_id, price, leadgen_id) and won is not None:
            # Yakuniy statusni yozmaymiz — keyingi siklda CAPI qayta uriniladi.
            result.failed += 1
            continue

        try:
            await asyncio.to_thread(
                update_revenue, leadgen_id, price, won, get_local_now().isoformat(),
                _to_int(status_id), _to_int(lead.get("loss_reason_id")),
            )
            result.updated += 1
        except Exception as exc:
            logger.warning("[ADS ATTRIBUTION] Yozib bo'lmadi (%s): %s", leadgen_id, exc)

        try:
            await _sync_seller_info(amocrm, leadgen_id, int(lead_id), lead, names)
        except Exception as exc:
            logger.warning("[ADS ATTRIBUTION] Sotuvchi ma'lumoti (%s): %s", leadgen_id, exc)

        await asyncio.sleep(_REQUEST_DELAY_SECONDS)

    logger.info("[ADS ATTRIBUTION] Sinxronizatsiya: %s", result.to_dict())
    return result
