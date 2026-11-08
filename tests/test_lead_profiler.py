"""
Tests for TelegramLeadProfiler service.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.ai.lead_profiler import (
    TelegramLeadProfiler,
    TelegramLeadProfile,
    TelegramRawSignals,
)


@pytest.mark.asyncio
async def test_fallback_profile():
    profiler = TelegramLeadProfiler(gemini_client=None)
    signals = TelegramRawSignals(
        user_id=123456,
        first_name="Alisher",
        last_name="Usmonov",
        username="alisher_u",
        phone="998901234567",
        about="Tadbirkor, investor",
        is_premium=True,
    )
    profile = await profiler.analyze_lead(signals, "Salom, brending narxi qancha?")
    assert isinstance(profile, TelegramLeadProfile)
    assert profile.user_id == 123456
    assert profile.full_name == "Alisher Usmonov"
    assert profile.is_premium is True
    assert "Yuqori" in profile.solvency_level
    dossier = profile.format_dossier()
    assert "TELEGRAM 360° MIJOZ DOSYESI" in dossier
    assert "⭐️ Premium Akkaunt" in dossier
    assert "Muz yorar mavzu" in dossier


def test_parse_profile_json():
    profiler = TelegramLeadProfiler(gemini_client=None)
    signals = TelegramRawSignals(
        user_id=98765,
        first_name="Bobur",
        last_name="",
        username="bobur_dev",
        phone="",
        about="IT va FinTech",
        is_premium=False,
    )
    raw_json = """
    ```json
    {
        "business_domain": "FinTech dasturlash",
        "estimated_role": "LPR (Startap asoschisi)",
        "psychological_type": "Analitik (texnik tafsilotlarga qiziquvchi)",
        "solvency_level": "Oʻrtacha (Business)",
        "communication_tip": "Texnik afzalliklar va arxitektura bilan tushuntiring.",
        "recommended_package": "FinTech ilova rebrendingi",
        "key_icebreaker": "FinTech ilovalardagi UX/UI yechimlarimiz boʻyicha fikr almashsak."
    }
    ```
    """
    profile = profiler._parse_profile_json(raw_json, signals, "Bobur")
    assert profile.user_id == 98765
    assert profile.business_domain == "FinTech dasturlash"
    assert profile.estimated_role == "LPR (Startap asoschisi)"
    assert profile.solvency_level == "Oʻrtacha (Business)"
    assert "UX/UI" in profile.key_icebreaker


@pytest.mark.asyncio
async def test_extract_raw_signals():
    mock_client = MagicMock()
    mock_user_entity = MagicMock()
    mock_user_entity.id = 555666
    mock_user_entity.first_name = "Jamshid"
    mock_user_entity.last_name = "Karimov"
    mock_user_entity.username = "jamshid_k"
    mock_user_entity.phone = "998991112233"
    mock_user_entity.premium = True
    mock_user_entity.verified = False
    mock_user_entity.lang_code = "uz"

    # Mock GetFullUserRequest call
    mock_full = MagicMock()
    mock_full.full_user.about = "CEO at Jon Group"
    mock_full.full_user.business_work_hours = None
    mock_full.full_user.business_intro = None

    # Mock GetCommonChatsRequest
    mock_common = MagicMock()
    mock_chat = MagicMock()
    mock_chat.title = "Marketing Uz Club"
    mock_common.chats = [mock_chat]

    async def client_call(req):
        from telethon.tl.functions.messages import GetCommonChatsRequest
        from telethon.tl.functions.users import GetFullUserRequest
        if isinstance(req, GetFullUserRequest):
            return mock_full
        if isinstance(req, GetCommonChatsRequest):
            return mock_common
        return MagicMock()

    mock_client.side_effect = client_call
    mock_client.get_profile_photos = AsyncMock(return_value=[MagicMock(), MagicMock()])

    profiler = TelegramLeadProfiler(gemini_client=None)
    signals = await profiler.extract_raw_signals(mock_client, mock_user_entity)

    assert signals.user_id == 555666
    assert signals.about == "CEO at Jon Group"
    assert signals.is_premium is True
    assert signals.photo_count == 2
    assert "Marketing Uz Club" in signals.common_chats
