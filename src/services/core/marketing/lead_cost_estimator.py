"""Bitta kelgan lead uchun "taxminiy lid narxi" (Telegram bildirishnoma uchun).

MUHIM CHEKLOV: Meta har bir leadga aniq pul miqdorini biriktirmaydi — spend
kunlik/kampaniya darajasida keladi, lead esa alohida hodisa sifatida. Shuning
uchun bu "taxminiy" qiymat: shu kampaniyaning oxirgi N kunlik
(spend / lead soni) o'rtachasi. Real vaqtda emas — ad_spend_sync necha soatda
bir yangilanadi, shuning uchun yangi kampaniya uchun bir necha soat "N/A"
bo'lishi mumkin.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from src.services.core.marketing.ad_spend_store import aggregate_spend
from src.services.core.marketing.attribution_store import count_recent_leads_for_campaign
from src.time_utils import get_local_now

_WINDOW_DAYS = 30


def estimate_cost_per_lead(campaign_id: str) -> Optional[float]:
    """Kampaniyaning oxirgi 30 kunlik o'rtacha lid narxi (so'nggi keshdan)."""
    if not campaign_id:
        return None

    now = get_local_now()
    start = (now - timedelta(days=_WINDOW_DAYS)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    spend_by_campaign = aggregate_spend(start, end)
    row = spend_by_campaign.get(campaign_id)
    if not row or not row.get("spend"):
        return None

    leads = count_recent_leads_for_campaign(campaign_id, days=_WINDOW_DAYS)
    if not leads:
        return None

    return row["spend"] / leads
