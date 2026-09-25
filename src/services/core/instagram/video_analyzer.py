"""Analyzes the actual Instagram video/reel content (not just the caption)
so comment replies can be grounded in what the video really shows/says.

Result is cached per media_id (in-process) so the same video isn't
re-downloaded/re-analyzed for every comment it receives.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - optional dependency
    genai = None
    types = None

from src.settings import settings

logger = logging.getLogger("InstagramVideoAnalyzer")

# Gemini inline-bytes requests are capped well under its ~20MB request-body
# limit once base64-encoded; skip analysis instead of sending an oversized
# request for longer Reels.
_MAX_VIDEO_BYTES = 15 * 1024 * 1024

_video_analysis_cache: Dict[str, str] = {}

_ANALYSIS_PROMPT = (
    "Ushbu Instagram video/reels'ni tomosha qiling. O'zbek tilida, 3-5 gapda, "
    "video aslida NIMA haqida ekanini yozing: qanday xizmat/mahsulot ko'rsatilgan, "
    "video ichida gapirilgan asosiy fikrlar, ko'rsatilgan narsalar. Bu matn keyinchalik "
    "shu videoga yozilgan izohlarga javob berish uchun kontekst sifatida ishlatiladi — "
    "shuning uchun aniq va faktik bo'lsin, badiiy tasvirlashga hojat yo'q."
)


def _get_client() -> Optional[Any]:
    if genai is None:
        return None
    api_key = settings.GEMINI_API_KEY.get_secret_value().strip() if settings.GEMINI_API_KEY else ""
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _fetch_media_details(media_id: str, access_token: str) -> Dict[str, Any]:
    url = f"https://graph.facebook.com/v19.0/{media_id}"
    params = {"fields": "caption,media_type,media_url", "access_token": access_token}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json() or {}
        logger.warning("[VIDEO_ANALYZER] Failed to fetch media details", status_code=resp.status_code)
    except Exception as exc:
        logger.error("[VIDEO_ANALYZER] Exception fetching media details", error=str(exc))
    return {}


def _download_video(media_url: str) -> Optional[bytes]:
    try:
        resp = requests.get(media_url, timeout=30, stream=True)
        if resp.status_code != 200:
            return None
        content_length = int(resp.headers.get("content-length") or 0)
        if content_length and content_length > _MAX_VIDEO_BYTES:
            logger.info("[VIDEO_ANALYZER] Video too large, skipping", size=content_length)
            return None
        data = resp.content
        if len(data) > _MAX_VIDEO_BYTES:
            logger.info("[VIDEO_ANALYZER] Video too large after download, skipping", size=len(data))
            return None
        return data
    except Exception as exc:
        logger.error("[VIDEO_ANALYZER] Exception downloading video", error=str(exc))
        return None


async def analyze_media_content(media_id: str, access_token: str, caption: str = "") -> str:
    """Returns a short factual description of what the video/reel actually
    shows and says, grounded in real content rather than just the caption.
    Falls back to the caption (or empty string) if video analysis isn't
    possible (no video, download/analysis failure, Gemini unavailable)."""
    if not media_id:
        return caption

    cached = _video_analysis_cache.get(media_id)
    if cached is not None:
        return cached

    details = _fetch_media_details(media_id, access_token)
    media_type = str(details.get("media_type") or "").upper()
    media_url = details.get("media_url") or ""
    result_caption = details.get("caption") or caption

    if media_type not in {"VIDEO", "REELS"} or not media_url:
        # Image posts or missing URL — caption is the best context available.
        _video_analysis_cache[media_id] = result_caption
        return result_caption

    client = _get_client()
    if client is None:
        _video_analysis_cache[media_id] = result_caption
        return result_caption

    video_bytes = _download_video(media_url)
    if not video_bytes:
        _video_analysis_cache[media_id] = result_caption
        return result_caption

    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_VISION_MODEL,
            contents=[
                types.Part.from_bytes(data=video_bytes, mime_type="video/mp4"),
                _ANALYSIS_PROMPT,
            ],
        )
        summary = (getattr(response, "text", None) or "").strip()
        if summary:
            combined = f"{result_caption}\n\nVideo tahlili: {summary}" if result_caption else summary
            _video_analysis_cache[media_id] = combined
            logger.info("[VIDEO_ANALYZER] Video analyzed", media_id=media_id)
            return combined
    except Exception as exc:
        logger.error("[VIDEO_ANALYZER] Gemini video analysis failed", error=str(exc))

    _video_analysis_cache[media_id] = result_caption
    return result_caption
