import asyncio
from urllib.parse import parse_qs, urlparse

import pytest

from src.services.core.marketing.ad_library_links import (
    USAGE_TEXT,
    build_ad_library_url,
    extract_page_query,
    find_social_page_queries,
    format_ad_library_reply,
)


def _params(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_build_url_targets_active_uz_ads():
    url = build_ad_library_url("brand uz")
    assert url.startswith("https://www.facebook.com/ads/library/?")
    params = _params(url)
    assert params["q"] == "brand uz"
    assert params["country"] == "UZ"
    assert params["active_status"] == "active"
    assert params["ad_type"] == "all"


def test_build_url_rejects_empty_query():
    with pytest.raises(ValueError):
        build_ad_library_url("   ")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.instagram.com/brand_uz/", "brand_uz"),
        ("instagram.com/brand_uz?igsh=abc", "brand_uz"),
        ("https://m.facebook.com/BrandPage", "BrandPage"),
        ("@brand_uz", "brand_uz"),
        ("Brand Mebel", "Brand Mebel"),
        ("https://www.instagram.com/p/C1abc/", None),
        ("https://www.instagram.com/reel/C1abc/", None),
        ("https://example.com/brand", None),
        ("https://notinstagram.com/brand", None),
        ("", None),
    ],
)
def test_extract_page_query(raw, expected):
    assert extract_page_query(raw) == expected


def test_find_social_page_queries_dedupes_and_skips_posts():
    text = (
        "Saytimiz: https://example.com, Insta: https://instagram.com/brand_uz. "
        "Yana https://www.instagram.com/Brand_UZ/ va post https://instagram.com/p/xyz "
        "hamda facebook.com/brandpage"
    )
    assert find_social_page_queries(text) == ["brand_uz", "brandpage"]


def test_find_social_page_queries_respects_limit():
    text = " ".join(f"https://instagram.com/page{i}" for i in range(5))
    assert find_social_page_queries(text, limit=2) == ["page0", "page1"]


def test_reply_contains_link_and_usage_fallback():
    reply = format_ad_library_reply(" https://instagram.com/brand_uz ")
    assert "brand_uz" in reply
    assert "facebook.com/ads/library/" in reply
    assert format_ad_library_reply("") == USAGE_TEXT
    assert format_ad_library_reply("https://example.com") == USAGE_TEXT


class _Event:
    def __init__(self):
        self.sent = []

    async def respond(self, text, **kwargs):
        self.sent.append((text, kwargs))


def test_admin_handler_only_matches_adlib():
    from src.handlers.msg_pipeline.admin_commands import _handle_ad_library

    event = _Event()
    assert asyncio.run(_handle_ad_library(event, "/adlibrary")) is False
    assert asyncio.run(_handle_ad_library(event, "/adlib @brand_uz")) is True
    text, kwargs = event.sent[0]
    assert "q=brand_uz" in text
    assert kwargs == {"link_preview": False}


def test_dossier_lists_ad_library_links():
    from src.services.ai.lead_profiler import TelegramLeadProfile

    profile = TelegramLeadProfile(
        user_id=1, full_name="Test", username="", phone="", is_premium=False,
        business_domain="d", estimated_role="r", psychological_type="p",
        solvency_level="s", communication_tip="c", recommended_package="k",
        key_icebreaker="i", ad_library_queries=["brand_uz"],
    )
    dossier = profile.format_dossier()
    assert "Meta reklamalari" in dossier
    assert "q=brand_uz" in dossier

    profile.ad_library_queries = []
    assert "Meta reklamalari" not in profile.format_dossier()
