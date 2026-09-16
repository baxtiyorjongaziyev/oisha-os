"""Meta Ads Insights'dan kunlik xarajatni mahalliy keshga tortib oladi."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from src.services.core.marketing.ad_spend_store import upsert_daily_spend
from src.services.core.marketing.meta_ads_client import MetaAdsClient
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)


async def sync_ad_spend(days: int = 7) -> int:
    """So'nggi `days` kunlik campaign-level spend'ni sinxronlaydi.

    Meta Insights API kechagi kunni ham hali yakunlanmagan holda qaytarishi
    mumkin — shuning uchun bugundan orqaga `days` kunni har safar qayta
    yozib qo'yamiz (upsert), faqat bugungi kunni emas.
    """
    client = MetaAdsClient()
    if not client.configured:
        logger.info("[META ADS SYNC] META_AD_ACCOUNT_ID yoki token yo'q — o'tkazib yuborildi")
        return 0

    now = get_local_now()
    until = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    raw_rows = await asyncio.to_thread(client.get_daily_campaign_insights, since, until)
    if not raw_rows:
        return 0

    parsed = []
    for row in raw_rows:
        parsed.append(
            {
                "date": row.get("date_start"),
                "campaign_id": row.get("campaign_id"),
                "campaign_name": row.get("campaign_name"),
                "spend": row.get("spend"),
                "impressions": row.get("impressions"),
                "clicks": row.get("clicks"),
                "meta_leads": client.extract_lead_actions(row),
            }
        )

    written = await asyncio.to_thread(upsert_daily_spend, parsed, now.isoformat())
    logger.info("[META ADS SYNC] %s qator yozildi (%s .. %s)", written, since, until)
    return written
