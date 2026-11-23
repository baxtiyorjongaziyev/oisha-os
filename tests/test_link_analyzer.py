"""
Tests for LinkAnalyzer service.
"""
from unittest.mock import AsyncMock, patch
import pytest

from src.services.ai.link_analyzer import LinkAnalyzer, AnalyzedLink


def test_extract_urls():
    analyzer = LinkAnalyzer()
    text = "Salom, bizning saytimiz https://mybrand.uz va instagram: instagram.com/mybrand_uz."
    urls = analyzer.extract_urls(text)
    assert urls == ["https://mybrand.uz", "https://instagram.com/mybrand_uz"]


def test_categorize_url():
    analyzer = LinkAnalyzer()
    assert analyzer.categorize_url("https://instagram.com/p/12345") == "instagram"
    assert analyzer.categorize_url("https://t.me/brand_uz") == "telegram"
    assert analyzer.categorize_url("https://www.behance.net/gallery/123") == "design_ref"
    assert analyzer.categorize_url("https://drive.google.com/drive/folders/xyz") == "drive"
    assert analyzer.categorize_url("https://samarkand-dryfruits.uz") == "website"


@pytest.mark.asyncio
async def test_analyze_url():
    analyzer = LinkAnalyzer()
    with patch.object(analyzer, "fetch_meta_preview", AsyncMock(return_value=("Qandolat Fabrikasi", "Eng shirin mahsulotlar"))):
        res = await analyzer.analyze_url("https://qandolat.uz")
        assert isinstance(res, AnalyzedLink)
        assert res.category == "website"
        assert res.title == "Qandolat Fabrikasi"
        assert "Qandolat Fabrikasi" in res.sales_insight


def test_format_links_summary():
    analyzer = LinkAnalyzer()
    link = AnalyzedLink(
        url="https://behance.net/gallery/abc",
        category="design_ref",
        domain="behance.net",
        title="Minimal Packaging",
        description="",
        sales_insight="Mijoz dizayn yoʻnalishi boʻyicha aniq didga ega.",
    )
    summary = analyzer.format_links_summary([link])
    assert "MIJOZ YUBORGAN HAVOLALAR TAHLILI" in summary
    assert "DESIGN_REF" in summary
    assert "Minimal Packaging" in summary
