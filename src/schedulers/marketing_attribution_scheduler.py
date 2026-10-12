"""24/7 background worker: Meta Ads spend + AmoCRM revenue attribution.

Har `_INTERVAL_SEC` da ikkita ishni bajaradi:
  1. Meta Ads Insights'dan so'nggi kunlar spend'ini `meta_ad_spend`ga tortadi.
  2. Meta Lead Ads orqali kelgan, hali yakuni noma'lum leadlarning AmoCRM
     holatini (yutdi/yutqazdi/narx) `lead_attribution`ga yozadi.
Ikkalasi ham `MarketingAttributionService.get_performance_data()` uchun manba.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os

logger = logging.getLogger("MarketingAttributionScheduler")

_INTERVAL_SEC = int(os.getenv("META_ADS_SYNC_INTERVAL_SEC", "10800"))  # 3 soat


async def marketing_attribution_loop() -> None:
    logger.info("[ADS ATTRIBUTION] Loop started (interval=%ds)", _INTERVAL_SEC)
    await asyncio.sleep(15)

    while True:
        try:
            from src.services.core.marketing.ad_spend_sync import sync_ad_spend
            await sync_ad_spend(days=7)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[ADS ATTRIBUTION] Spend sync xatosi: %s", exc, exc_info=True)

        try:
            from src.schedulers.leadgen_status_reporter import _send_tg_message
            from src.services.core.marketing.cpl_monitor import check_and_alert
            from src.settings import settings
            from src.time_utils import get_local_now

            chat_id = getattr(settings, "MARKETING_REPORT_CHAT_ID", None) or -1003608624065
            topic_id = getattr(settings, "MARKETING_REPORT_TOPIC_ID", None) or 42
            yesterday = (get_local_now().date() - datetime.timedelta(days=1)).isoformat()
            await asyncio.to_thread(
                check_and_alert, yesterday, lambda text: _send_tg_message(text, chat_id, topic_id),
            )
            from src.services.core.marketing.creative_report import send_weekly_if_due
            await asyncio.to_thread(
                send_weekly_if_due, get_local_now().date(),
                lambda text: _send_tg_message(text, chat_id, topic_id),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[ADS ATTRIBUTION] CPL monitor xatosi: %s", exc, exc_info=True)

        try:
            from src.services.core.instagram.leadgen_router import _amocrm_instance
            from src.services.core.marketing.attribution_sync import sync_attribution_revenue
            await sync_attribution_revenue(_amocrm_instance(), days=90)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[ADS ATTRIBUTION] Revenue sync xatosi: %s", exc, exc_info=True)

        try:
            await asyncio.sleep(_INTERVAL_SEC)
        except asyncio.CancelledError:
            logger.info("[ADS ATTRIBUTION] Cancelled")
            break
