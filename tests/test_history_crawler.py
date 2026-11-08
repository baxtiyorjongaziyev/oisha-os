"""
Tests for TelegramHistoryCrawler service.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.services.ai.history_crawler import (
    TelegramHistoryCrawler,
    CrawledLeadRecord,
)


def test_is_personal_or_junk_filtering():
    crawler = TelegramHistoryCrawler(repo=MagicMock())

    # Family members should be filtered out
    mock_mom = MagicMock()
    mock_mom.first_name = "Onajonim"
    mock_mom.last_name = ""
    mock_mom.is_self = False
    mock_mom.bot = False
    mock_mom.id = 111
    assert crawler.is_personal_or_junk(mock_mom) is True

    mock_sister = MagicMock()
    mock_sister.first_name = "Firuzxon"
    mock_sister.last_name = "Opam"
    mock_sister.is_self = False
    mock_sister.bot = False
    mock_sister.id = 222
    assert crawler.is_personal_or_junk(mock_sister) is True

    mock_son = MagicMock()
    mock_son.first_name = "Abdulloh"
    mock_son.last_name = "Oʻgʻlim"
    mock_son.is_self = False
    mock_son.bot = False
    mock_son.id = 333
    assert crawler.is_personal_or_junk(mock_son) is True

    mock_neighbor = MagicMock()
    mock_neighbor.first_name = "Muhammadamin"
    mock_neighbor.last_name = "Aka Qoshni"
    mock_neighbor.is_self = False
    mock_neighbor.bot = False
    mock_neighbor.id = 444
    assert crawler.is_personal_or_junk(mock_neighbor) is True

    # Real business client should NOT be filtered out
    mock_client = MagicMock()
    mock_client.first_name = "Ruslon"
    mock_client.last_name = "TN6 Gr"
    mock_client.is_self = False
    mock_client.bot = False
    mock_client.id = 555
    assert crawler.is_personal_or_junk(mock_client) is False

    mock_client2 = MagicMock()
    mock_client2.first_name = "SHUKURULLOH"
    mock_client2.last_name = ""
    mock_client2.is_self = False
    mock_client2.bot = False
    mock_client2.id = 666
    assert crawler.is_personal_or_junk(mock_client2) is False


def test_generate_digest_markdown():
    crawler = TelegramHistoryCrawler(repo=MagicMock())
    lead = CrawledLeadRecord(
        peer_id=777,
        full_name="Jamshid Karimov",
        username="jamshid_k",
        phone="998901234567",
        is_premium=True,
        business_domain="Qurilish mollari",
        estimated_role="LPR (Rahbar)",
        solvency_level="Yuqori",
        lead_score=85,
        key_icebreaker="Qurilish boʻyicha yangi tendensiyalar...",
        ready_to_send_script="Jamshid aka, sizga oʻxshash keysimizni koʻrib chiqdik...",
        last_chat_snippet="Narx qancha boʻladi?",
    )
    md = crawler.generate_digest_markdown([lead])
    assert "TELEGRAM 3 YILLIK ARXIVI" in md
    assert "Jamshid Karimov" in md
    assert "⭐️ Premium" in md
    assert "Qurilish mollari" in md
    assert "Jamshid aka" in md
