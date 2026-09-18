"""Reklama (video/aksiya) nomini avval keshdan, topilmasa Meta'dan oladi.

Sotuv menejeri Telegram xabarida "bu lead qaysi video/aksiya orqali
kelgan"ni ko'rishi uchun. Meta so'rovi muvaffaqiyatsiz bo'lsa yoki token
yo'q bo'lsa jim `None` qaytaradi — lead routing bunga bog'liq bo'lmasligi
kerak (fail-soft).
"""
from __future__ import annotations

from typing import Optional

from src.services.core.marketing.ad_name_cache import get_cached_name, save_name
from src.services.core.marketing.meta_ads_client import MetaAdsClient
from src.time_utils import get_local_now


def resolve_ad_name(ad_id: str) -> Optional[str]:
    if not ad_id:
        return None

    cached = get_cached_name(ad_id)
    if cached:
        return cached

    client = MetaAdsClient()
    name = client.get_ad_name(ad_id)
    if name:
        save_name(ad_id, name, get_local_now().isoformat())
    return name
