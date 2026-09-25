"""Read-only Meta Ads Insights client.

`InstagramGraphClient` faqat organik (profil/media) ma'lumotni oladi — reklama
xarajati (spend) uchun alohida endpoint kerak: `act_<AD_ACCOUNT_ID>/insights`.
Bu klass shu endpointdan kampaniya kesimida kunlik `spend`, `impressions`,
`clicks` va "lead" harakatlarini o'qiydi. Yozish huquqi yo'q — faqat o'qish.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
import structlog

from src.settings import settings

logger = structlog.get_logger("MetaAdsClient")

# Bitta so'rovda so'raladigan ustunlar. `actions` ichidan "lead" turini
# ajratib olamiz — bu Meta tomonidan hisoblangan lead soni (bizniki bilan
# solishtirish uchun foydali, lekin CRM lead soni ustuvor hisoblanadi).
_INSIGHTS_FIELDS = "campaign_id,campaign_name,spend,impressions,clicks,actions"


def _secret_text(value: Any) -> str:
    getter = getattr(value, "get_secret_value", None)
    return str(getter() if callable(getter) else value or "").strip()


class MetaAdsClient:
    """Read-only wrapper around the Meta Marketing API Insights endpoint."""

    def __init__(self, settings_obj: Any = None):
        self.settings = settings_obj or settings
        self.ad_account_id = (
            os.environ.get("META_AD_ACCOUNT_ID", "").strip()
            or getattr(self.settings, "META_AD_ACCOUNT_ID", None)
            or ""
        )
        self.api_version = os.environ.get("META_GRAPH_API_VERSION", "").strip() or "v19.0"

    @property
    def access_token(self) -> str:
        env_token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
        if env_token:
            return env_token
        return _secret_text(getattr(self.settings, "META_PAGE_ACCESS_TOKEN", None))

    @property
    def configured(self) -> bool:
        return bool(self.ad_account_id and self.access_token)

    def _account_path(self) -> str:
        account = self.ad_account_id
        return account if account.startswith("act_") else f"act_{account}"

    def get_daily_campaign_insights(
        self, since: str, until: str
    ) -> List[Dict[str, Any]]:
        """Kunlik, kampaniya kesimidagi spend/impressions/clicks/leads.

        `since`/`until` — "YYYY-MM-DD". Har bir qator bitta kun + bitta
        kampaniyaga tegishli (`time_increment=1`), shuning uchun keyinchalik
        `meta_ad_spend` jadvaliga to'g'ridan-to'g'ri upsert qilinadi.
        """
        if not self.configured:
            logger.warning(
                "[META ADS] Sozlanmagan",
                missing=[
                    n
                    for n, ok in (
                        ("META_AD_ACCOUNT_ID", bool(self.ad_account_id)),
                        ("META_PAGE_ACCESS_TOKEN", bool(self.access_token)),
                    )
                    if not ok
                ],
            )
            return []

        url = f"https://graph.facebook.com/{self.api_version}/{self._account_path()}/insights"
        params = {
            "access_token": self.access_token,
            "level": "campaign",
            "fields": _INSIGHTS_FIELDS,
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "time_increment": 1,
            "limit": 500,
        }

        rows: List[Dict[str, Any]] = []
        next_url: Optional[str] = url
        next_params: Optional[Dict[str, Any]] = params
        pages_fetched = 0
        while next_url and pages_fetched < 20:
            try:
                response = requests.get(next_url, params=next_params, timeout=30)
                payload = response.json()
            except requests.RequestException as exc:
                logger.warning("[META ADS] So'rov muvaffaqiyatsiz", error=type(exc).__name__)
                break
            except ValueError:
                logger.warning("[META ADS] JSON parse xatosi", status=response.status_code)
                break

            if response.status_code >= 400 or payload.get("error"):
                error = payload.get("error") or {}
                logger.warning(
                    "[META ADS] Graph xatosi",
                    message=error.get("message"),
                    code=error.get("code"),
                )
                break

            rows.extend(payload.get("data") or [])
            paging = payload.get("paging") or {}
            next_url = paging.get("next")
            next_params = None  # `next` allaqachon to'liq query bilan keladi
            pages_fetched += 1

        return rows

    def get_ad_name(self, ad_id: str) -> Optional[str]:
        """Bitta reklama (ad_id)ning nomini oladi — "qaysi video/aksiya" savoliga javob.

        `META_AD_ACCOUNT_ID` shart emas — faqat `ads_read` huquqli token
        bilan bitta ad obyektini o'qiydi. Kreativ nomi (creative.name)
        odatda dizayner/marketolog qo'ygan tushunarli nom bo'ladi
        (masalan "Video 3 - Brend strategiya - Sentabr").
        """
        if not ad_id or not self.access_token:
            return None

        url = f"https://graph.facebook.com/{self.api_version}/{ad_id}"
        params = {
            "access_token": self.access_token,
            "fields": "name,creative{name,title,video_id}",
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            payload = response.json()
        except requests.RequestException as exc:
            logger.warning("[META ADS] Ad nomi olinmadi", error=type(exc).__name__)
            return None
        except ValueError:
            return None

        if response.status_code >= 400 or payload.get("error"):
            error = payload.get("error") or {}
            logger.warning(
                "[META ADS] Ad nomi Graph xatosi",
                message=error.get("message"),
                code=error.get("code"),
            )
            return None

        creative = payload.get("creative") or {}
        name = (
            payload.get("name")
            or creative.get("name")
            or creative.get("title")
        )
        return str(name).strip() if name else None

    def get_ad_creative_url(self, ad_id: str) -> Optional[str]:
        """Reklama kreativining Instagram havolasini oladi."""
        if not ad_id:
            return None
        if ad_id in KNOWN_CREATIVE_URLS:
            return KNOWN_CREATIVE_URLS[ad_id]
        if not self.access_token:
            return None

        url = f"https://graph.facebook.com/{self.api_version}/{ad_id}"
        params = {
            "access_token": self.access_token,
            "fields": "name,creative{id,instagram_permalink_url,video_id}",
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            payload = response.json()
            creative = payload.get("creative") or {}
            permalink = creative.get("instagram_permalink_url")
            if permalink:
                return str(permalink).strip()
            video_id = creative.get("video_id")
            if video_id:
                return f"https://www.instagram.com/reel/{video_id}/"
        except Exception as exc:
            logger.warning("[META ADS] Creative URL olinmadi", error=str(exc))
        return None

    @staticmethod
    def extract_lead_actions(row: Dict[str, Any]) -> int:
        """`actions[]` ichidan Meta hisoblagan "lead" harakatlar sonini oladi."""
        total = 0
        for action in row.get("actions") or []:
            if str(action.get("action_type", "")) in ("lead", "onsite_conversion.lead_grouped"):
                try:
                    total += int(float(action.get("value", 0)))
                except (TypeError, ValueError):
                    continue
        return total


KNOWN_CREATIVE_URLS: Dict[str, str] = {
    "120249419742870032": "https://www.instagram.com/p/DdMgcrcgnuH/",
    "120249477279140032": "https://www.instagram.com/p/DdVkUMngJiW/",
    "v2": "https://www.instagram.com/p/DdMgcrcgnuH/",
    "v6": "https://www.instagram.com/p/DdVkUMngJiW/",
}


def get_creative_url(ad_id_or_name: str) -> Optional[str]:
    """Reklama yoki video nomiga ko'ra Instagram havolasini qaytaradi."""
    clean = str(ad_id_or_name or "").strip()
    if not clean:
        return None
    if clean in KNOWN_CREATIVE_URLS:
        return KNOWN_CREATIVE_URLS[clean]
    if clean.lower() in KNOWN_CREATIVE_URLS:
        return KNOWN_CREATIVE_URLS[clean.lower()]
    return None

