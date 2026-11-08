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


@pytest.mark.asyncio
async def test_transcribe_video_note_and_media():
    mock_stt = MagicMock()
    mock_res = MagicMock()
    mock_res.transcript = "Assalomu alaykum, yangi dizayn boʻyicha video yubordim"
    mock_stt.transcribe = AsyncMock(return_value=mock_res)

    crawler = TelegramHistoryCrawler(repo=MagicMock(), stt=mock_stt)

    # 1. Aylana video xabar (video_note)
    mock_client = MagicMock()
    mock_client.download_media = AsyncMock(return_value=b"fake_mp4_bytes")

    msg_video_note = MagicMock()
    msg_video_note.video_note = MagicMock()
    msg_video_note.video_note.duration = 15
    msg_video_note.voice = None
    msg_video_note.audio = None
    msg_video_note.photo = None
    msg_video_note.video = None

    text = await crawler._transcribe_if_voice(mock_client, msg_video_note)
    assert "Aylana video xabar" in text
    assert "yangi dizayn boʻyicha video yubordim" in text

    # 2. Rasm izohi bilan
    msg_photo = MagicMock()
    msg_photo.video_note = None
    msg_photo.voice = None
    msg_photo.audio = None
    msg_photo.photo = MagicMock()
    msg_photo.video = None
    msg_photo.message = "Mana bu bizning hozirgi qadoq"

    photo_text = await crawler._transcribe_if_voice(mock_client, msg_photo)
    assert "[Rasm: \"Mana bu bizning hozirgi qadoq\"]" == photo_text
