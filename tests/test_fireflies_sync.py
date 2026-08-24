"""Unit tests for FirefliesSync and call intelligence bridge."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.core.integrations.fireflies_sync import FirefliesSync


@pytest.mark.asyncio
async def test_fireflies_normalize_dialogue():
    sync = FirefliesSync(api_key="test-key")
    sync.manager_name = "baxtiyorjon"

    data = {
        "sentences": [
            {"speaker_name": "Baxtiyorjon Gaziyev", "text": "Assalomu alaykum! Jon Branding xizmatlari bo'yicha qanday yordam bera olaman?"},
            {"speaker_name": "Alisher Navoiy", "text": "Bizga yangi brending va vizual identika kerak."},
        ]
    }

    dialogue = sync.normalize_dialogue(data)
    assert "Menejer (Baxtiyorjon Gaziyev):" in dialogue
    assert "Mijoz (Alisher Navoiy):" in dialogue
    assert "brending va vizual identika" in dialogue


@pytest.mark.asyncio
async def test_fireflies_process_transcript_success():
    sync = FirefliesSync(api_key="test-key")
    sync.manager_name = "baxtiyorjon"

    fake_transcript = {
        "id": "trans-123",
        "title": "Jon Branding Strategy Session (+998901234567)",
        "duration": 185,
        "organizer_email": "baxtiyorjon@jonbranding.uz",
        "participants": ["Alisher", "Baxtiyorjon"],
        "sentences": [
            {"speaker_name": "Baxtiyorjon", "text": "Xush kelibsiz! Loyihangiz maqsadi nima?"},
            {"speaker_name": "Alisher", "text": "Bizga rebranding kerak, byudjetimiz $5,000."},
            {"speaker_name": "Baxtiyorjon", "text": "Kelishdik, dushanba 15:00 da taqdimot qilamiz."},
        ],
    }

    sync.fetch_transcript = AsyncMock(return_value=fake_transcript)
    sync.amocrm.search_leads = MagicMock(return_value=[{"id": 45678, "name": "Alisher Navoiy"}])
    sync.amocrm.add_lead_note = MagicMock(return_value=True)
    sync.amocrm.add_lead_tag = MagicMock(return_value=True)
    sync._notify_telegram = AsyncMock(return_value=None)

    with patch("src.services.core.call_analyzer.CallAnalyzer.analyze_transcript", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = {
            "category": "Mijoz",
            "client_mood": "Ijobiy",
            "summary": "Rebranding bo'yicha uchrashuv",
            "next_steps": "Dushanba 15:00 taqdimot",
            "kelishilgan_vaqt": "2026-08-31T15:00:00",
            "natija": "Kelishuv",
        }

        result = await sync.process_transcript("trans-123")
        assert result["status"] == "success"
        assert result["lead_id"] == 45678
        assert "Rebranding" in result["summary"]
        sync.amocrm.add_lead_note.assert_called_once()
        sync._notify_telegram.assert_called_once()
