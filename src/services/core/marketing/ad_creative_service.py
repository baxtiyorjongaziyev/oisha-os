"""Ad Creative resolution and persistent caching service for Meta Ads.

Resolves creative details (video reel, photo post, banner, carousel) for incoming
Meta Lead Ads, storing known creatives in SQLite and providing salespeople with
1-click visual links in amoCRM, Telegram, and Jon CRM.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional
import requests
import structlog

from src.time_utils import get_local_now

logger = structlog.get_logger("AdCreativeService")

_DB_PATH = Path(__file__).resolve().parents[4] / "data" / "meta_ad_creatives.db"

KNOWN_CREATIVE_URLS: Dict[str, str] = {
    "120249419742870032": "https://www.instagram.com/p/DdMgcrcgnuH/",
    "120249477279140032": "https://www.instagram.com/reel/DdVkUMngJiW/",
    "120249953969790032": "https://www.instagram.com/reel/DdVkUMngJiW/",
    "120249953969770032": "https://www.instagram.com/p/DdMgcrcgnuH/",
    "v2": "https://www.instagram.com/p/DdMgcrcgnuH/",
    "v6": "https://www.instagram.com/reel/DdVkUMngJiW/",
    "v1": "https://www.instagram.com/jonbranding/",
}

KNOWN_CREATIVE_NAMES: Dict[str, str] = {
    "120249419742870032": "V2 - Brending video",
    "120249477279140032": "V6 - Brending video",
    "120249953969790032": "V6 - Brending video",
    "120249953969770032": "V2 - Brending video",
    "v2": "V2 - Brending video",
    "v6": "V6 - Brending video",
    "v1": "V1 - Brending video",
}


@dataclass(frozen=True)
class AdCreativeDetails:
    ad_id: str
    ad_name: str
    creative_type: str  # "video", "photo", "carousel"
    type_icon: str  # "🎬", "🖼", "📑"
    creative_url: str  # Direct 1-click link
    thumbnail_url: Optional[str] = None
    campaign_name: Optional[str] = None
    source: str = "fallback"


def _init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ad_creatives (
                ad_id TEXT PRIMARY KEY,
                ad_name TEXT,
                creative_type TEXT,
                type_icon TEXT,
                creative_url TEXT,
                thumbnail_url TEXT,
                campaign_name TEXT,
                updated_at TEXT
            )
            """
        )


def infer_creative_type(name: str) -> tuple[str, str]:
    """Infer (creative_type, type_icon) from ad or creative name."""
    n = (name or "").lower().strip()
    if "carousel" in n or "karusel" in n:
        return "carousel", "📑"
    if n.startswith("v") or any(w in n for w in ("video", "reel", "clip", "rolik")):
        return "video", "🎬"
    if n.startswith("p") or any(w in n for w in ("photo", "rasm", "poster", "banner", "surat")):
        return "photo", "🖼"
    return "creative", "🎬"


def get_stored_creative(ad_id: str) -> Optional[AdCreativeDetails]:
    """Fetch creative details from local SQLite registry."""
    if not ad_id:
        return None
    _init_db()
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM ad_creatives WHERE ad_id = ?", (str(ad_id),)).fetchone()
        if row:
            return AdCreativeDetails(
                ad_id=row["ad_id"],
                ad_name=row["ad_name"] or f"Ad {ad_id}",
                creative_type=row["creative_type"] or "video",
                type_icon=row["type_icon"] or "🎬",
                creative_url=row["creative_url"] or "",
                thumbnail_url=row["thumbnail_url"],
                campaign_name=row["campaign_name"],
                source="sqlite_cache",
            )
    return None


def save_creative(
    ad_id: str,
    ad_name: str,
    creative_url: str,
    creative_type: Optional[str] = None,
    type_icon: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    campaign_name: Optional[str] = None,
) -> None:
    """Save or update ad creative in local SQLite registry."""
    if not ad_id:
        return
    _init_db()
    c_type, icon = infer_creative_type(ad_name)
    c_type = creative_type or c_type
    icon = type_icon or icon
    now_iso = get_local_now().isoformat()
    with sqlite3.connect(_DB_PATH, timeout=10) as conn:
        conn.execute(
            """
            INSERT INTO ad_creatives (ad_id, ad_name, creative_type, type_icon, creative_url, thumbnail_url, campaign_name, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ad_id) DO UPDATE SET
                ad_name=excluded.ad_name,
                creative_type=excluded.creative_type,
                type_icon=excluded.type_icon,
                creative_url=excluded.creative_url,
                thumbnail_url=excluded.thumbnail_url,
                campaign_name=COALESCE(excluded.campaign_name, ad_creatives.campaign_name),
                updated_at=excluded.updated_at
            """,
            (str(ad_id), ad_name, c_type, icon, creative_url, thumbnail_url, campaign_name, now_iso),
        )


def _fetch_creative_from_meta(ad_id: str, access_token: str, version: str) -> Optional[AdCreativeDetails]:
    """Fetch rich creative object from Meta Graph API."""
    if not ad_id or not access_token:
        return None
    url = f"https://graph.facebook.com/{version}/{ad_id}"
    fields = (
        "id,name,creative{id,name,title,body,image_url,thumbnail_url,"
        "instagram_permalink_url,effective_object_story_id,video_id}"
    )
    try:
        res = requests.get(url, params={"access_token": access_token, "fields": fields}, timeout=12)
        if res.status_code != 200:
            return None
        payload = res.json()
        ad_name = payload.get("name") or f"Ad {ad_id}"
        creative = payload.get("creative") or {}
        cr_name = creative.get("name") or creative.get("title") or ad_name

        c_url = ""
        permalink = creative.get("instagram_permalink_url")
        if permalink:
            c_url = str(permalink).strip()
        elif creative.get("video_id"):
            c_url = f"https://www.instagram.com/reel/{creative['video_id']}/"
        elif creative.get("effective_object_story_id"):
            story_id = str(creative["effective_object_story_id"]).strip()
            c_url = f"https://www.facebook.com/{story_id}"
        elif creative.get("image_url"):
            c_url = str(creative["image_url"]).strip()
        elif creative.get("thumbnail_url"):
            c_url = str(creative["thumbnail_url"]).strip()

        c_type, icon = infer_creative_type(cr_name)
        thumb = creative.get("thumbnail_url") or creative.get("image_url")
        return AdCreativeDetails(
            ad_id=str(ad_id),
            ad_name=cr_name,
            creative_type=c_type,
            type_icon=icon,
            creative_url=c_url,
            thumbnail_url=thumb,
            source="meta_graph",
        )
    except Exception as exc:
        logger.warning("[AD CREATIVE] Meta fetch exception: %s", exc)
        return None


def resolve_ad_creative(
    ad_id: str,
    ad_name: Optional[str] = None,
    campaign_name: Optional[str] = None,
    access_token: Optional[str] = None,
) -> AdCreativeDetails:
    """Resolve full creative details with 0-exception fallback."""
    clean_id = str(ad_id or "").strip()
    clean_name = str(ad_name or "").strip()

    # 1. Check local SQLite registry
    cached = get_stored_creative(clean_id)
    if cached and cached.creative_url:
        return cached

    # 2. Check KNOWN_CREATIVE_URLS
    if clean_id in KNOWN_CREATIVE_URLS:
        name = clean_name or KNOWN_CREATIVE_NAMES.get(clean_id) or f"Creative {clean_id}"
        c_type, icon = infer_creative_type(name)
        details = AdCreativeDetails(
            ad_id=clean_id,
            ad_name=name,
            creative_type=c_type,
            type_icon=icon,
            creative_url=KNOWN_CREATIVE_URLS[clean_id],
            campaign_name=campaign_name,
            source="known_registry",
        )
        save_creative(clean_id, name, details.creative_url, c_type, icon, campaign_name=campaign_name)
        return details

    # 3. Check by lower name in KNOWN_CREATIVE_URLS
    if clean_name and clean_name.lower() in KNOWN_CREATIVE_URLS:
        k = clean_name.lower()
        c_type, icon = infer_creative_type(clean_name)
        details = AdCreativeDetails(
            ad_id=clean_id or k,
            ad_name=KNOWN_CREATIVE_NAMES.get(k) or clean_name,
            creative_type=c_type,
            type_icon=icon,
            creative_url=KNOWN_CREATIVE_URLS[k],
            campaign_name=campaign_name,
            source="known_name",
        )
        if clean_id:
            save_creative(clean_id, clean_name, details.creative_url, c_type, icon, campaign_name=campaign_name)
        return details

    # 4. Try Meta Graph API if token is provided or available
    token = access_token
    if not token:
        from src.services.core.marketing.meta_ads_client import MetaAdsClient
        token = MetaAdsClient().access_token

    if token and clean_id:
        from src.services.core.instagram.graph_version import graph_api_version
        api_ver = graph_api_version()
        meta_det = _fetch_creative_from_meta(clean_id, token, api_ver)
        if meta_det and meta_det.creative_url:
            save_creative(
                clean_id,
                meta_det.ad_name,
                meta_det.creative_url,
                meta_det.creative_type,
                meta_det.type_icon,
                meta_det.thumbnail_url,
                campaign_name,
            )
            return meta_det

    # 5. Fallback heuristic
    effective_name = clean_name or (cached.ad_name if cached else "") or f"Ad {clean_id or 'Meta'}"
    c_type, icon = infer_creative_type(effective_name)

    # Fallback URL: Instagram page or Ads Manager link if id exists
    if clean_id:
        fallback_url = f"https://www.facebook.com/ads/manage/preview/?ad_id={clean_id}"
    else:
        fallback_url = "https://www.instagram.com/jonbranding/"

    details = AdCreativeDetails(
        ad_id=clean_id,
        ad_name=effective_name,
        creative_type=c_type,
        type_icon=icon,
        creative_url=fallback_url,
        campaign_name=campaign_name,
        source="fallback",
    )
    if clean_id:
        save_creative(clean_id, effective_name, fallback_url, c_type, icon, campaign_name=campaign_name)
    return details
