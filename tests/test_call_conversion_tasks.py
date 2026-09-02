"""Unit tests for Call Intelligence conversion recommendations and task generation."""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.time_utils import get_local_now

from src.services.call_analytics.crm_notes import CallCrmNotesMixin
from src.services.call_analytics.crm_tasks import CallCrmTasksMixin
from src.services.call_analytics.helpers import _looks_like_stt_hallucination
from src.services.call_analytics.normalizer import CallNormalizerMixin
from src.services.call_analytics.note_extractor import NoteExtractorMixin
from src.services.call_analytics.transcriber import CallTranscriberMixin
from src.services.core.calls.call_notifier import build_call_alert_message
from src.schedulers.call_analysis_scheduler import (
    CallScanResult,
    _is_eligible_for_scan,
    run_call_analysis_scan,
)


class DummyAnalyzer(
    CallCrmNotesMixin,
    CallCrmTasksMixin,
    CallNormalizerMixin,
    CallTranscriberMixin,
    NoteExtractorMixin,
):
    def __init__(self, amocrm=None, db=None):
        self.amocrm = amocrm or MagicMock()
        self.db = db or MagicMock()
        self.gemini_client = MagicMock()
        self.openai_client = MagicMock()
        self.stt_service = MagicMock()
        self.max_transcript_note_chars = 3000


class TestCallConversionAndTasks:
    """Test suite verifying end-to-end conversion recommendations and task scheduling."""

    def test_stt_hallucination_filter_accepts_short_uzbek_audio(self):
        """Short legitimate Uzbek customer inquiries must not be rejected."""
        valid_uzbek_notes = [
            "Assalomu alaykum, brending xizmati narxini bilsam bo'ladimi?",
            "Salom, ertaga soat 14:00 da qayta telefon qiling",
            "Assalomu alaykum, taklifingizni ko'rib chiqdik, shartnoma yuboring",
            "Rahmat, tushundim",
        ]
        for note in valid_uzbek_notes:
            assert _looks_like_stt_hallucination(note) is False, f"Erroneously filtered: {note}"

    def test_stt_hallucination_filter_rejects_subtitles_and_loops(self):
        """Subtitles artifacts and single-word repetitive loops must be rejected."""
        hallucinations = [
            "Subtitles by the Amara.org community",
            "Transkripsiya Uzbek Subtitles jamoasi tomonidan tayyorlandi",
            "rahmat rahmat rahmat rahmat rahmat rahmat rahmat rahmat rahmat rahmat rahmat",
        ]
        for h in hallucinations:
            assert _looks_like_stt_hallucination(h) is True, f"Failed to detect hallucination: {h}"

    def test_note_extractor_detects_chat_voice_and_attachments(self):
        """Voice notes inside service_message, common, and attachments must be detected."""
        extractor = DummyAnalyzer()

        # Chat audio attachment
        note1 = {
            "note_type": "service_message",
            "params": {"link": "https://amocrm.ru/storage/audio.mp3"},
        }
        assert extractor._looks_like_call_note(note1) is True

        # Custom text with audio link
        note2 = {
            "note_type": "common",
            "text": "Mijoz ovozli xabar qoldirdi: https://files.jonbranding.uz/rec_123.ogg",
        }
        assert extractor._looks_like_call_note(note2) is True

        # PBX Call record
        note3 = {
            "note_type": "call_in",
            "params": {"record_url": "https://pbx.tel/rec/998901234567.wav"},
        }
        assert extractor._looks_like_call_note(note3) is True

    def test_find_audio_url_in_nested_dict(self):
        """Audio URLs in nested dict structures must be found."""
        extractor = DummyAnalyzer()
        payload = {
            "data": {
                "attachment": {
                    "download_url": "https://cdn.amocrm.ru/files/voice_msg.m4a"
                }
            }
        }
        found = extractor._find_audio_url(payload)
        assert found == "https://cdn.amocrm.ru/files/voice_msg.m4a"

    def test_normalizer_extracts_conversion_advice_and_agreed_time(self):
        """Normalizer should parse konversiya_tavsiyalari and parse agreed time."""
        analyzer = DummyAnalyzer()
        raw_analysis = {
            "category": "Mijoz",
            "summary": "Mijoz logotip va qadoq dizayni so'radi.",
            "client_mood": "ijobiy",
            "next_steps": "Ertaga soat 15:00 da portfolio yuborish va narxlarni tushuntirish",
            "konversiya_tavsiyalari": [
                "Oldingi keyslar va vizual taqdimotni yuboring",
                "To'lovni 2 qismga bo'lib to'lash imkoniyatini eslating",
            ],
            "kelishilgan_vaqt": (get_local_now() + timedelta(days=3)).strftime("%Y-%m-%dT15:00:00"),
            "sifat_bahosi": 88,
        }
        normalized = analyzer._normalise_analysis(raw_analysis, "Qisqa audio")
        assert normalized["category"] == "Mijoz"
        assert len(normalized["konversiya_tavsiyalari"]) == 2
        assert "Oldingi keyslar" in normalized["konversiya_tavsiyalari"][0]
        assert normalized["kelishilgan_vaqt"] is not None
        assert normalized["kelishilgan_vaqt"].hour == 15

    def test_build_amocrm_note_includes_conversion_section(self):
        """Built AmoCRM note must contain the conversion advice section."""
        analyzer = DummyAnalyzer()
        analysis = {
            "category": "iliq",
            "summary": "Brending xizmatiga qiziqish bor",
            "client_mood": "Ijobiy",
            "next_steps": "Tijoriy taklif jo'natish",
            "konversiya_tavsiyalari": [
                "Kompaniya taqdimotini Telegram orqali yuboring",
                "Mijozning byudjeti haqida ochiq savol bering",
            ],
            "kelishilgan_vaqt": datetime(2026, 9, 3, 11, 30, tzinfo=timezone.utc),
        }
        note_text = analyzer._build_amocrm_note(
            analysis=analysis,
            transcript_snippet="Mijoz bilan suhbat",
            caller_phone="+998901234567",
        )
        assert "──── MURABBIY IZOHI VA KONVERSIYA ────" in note_text
        assert "💡 Tavsiya:" in note_text
        assert "Kompaniya taqdimotini Telegram" in note_text
        assert "⏰ Kelishilgan vaqt: 03.09.2026 11:30" in note_text

    def test_build_task_text_includes_conversion_advice_and_schedule(self):
        """AmoCRM task text must be structured with action, advice, and agreed time."""
        analyzer = DummyAnalyzer()
        task_text = analyzer._build_task_text(
            category="issiq",
            summary="Mijoz shartnoma kutmoqda",
            client_mood="ijobiy",
            next_steps="Shartnomani imzolashga yuborish",
            agreed_datetime=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            conversion_advice=["Prepayment 50% ekanligini qayd eting"],
        )
        assert "🎯 VAZIFA: Shartnomani imzolashga yuborish" in task_text
        assert "⏰ Kelishilgan vaqt: 01.09.2026 10:00" in task_text
        assert "💡 Konversiya tavsiyasi:" in task_text
        assert "Prepayment 50%" in task_text
        assert "📝 Suhbat xulosasi: Mijoz shartnoma kutmoqda" in task_text

    def test_telegram_alert_message_formatting(self):
        """Telegram HTML alert card must include score, agreed time, and conversion advice."""
        analysis = {
            "sifat_bahosi": 92,
            "natija": "Shartnoma bosqichiga o'tdi",
            "konversiya_tavsiyalari": ["Ertalab soat 10:00 da shartnomani tekshirish"],
            "kelishilgan_vaqt": datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
        }
        msg = build_call_alert_message(
            lead_id=778899,
            call_id="call_999",
            category="issiq",
            summary="Mijoz brendbuk uchun rozi bo'ldi",
            client_mood="a'lo",
            next_steps="Shartnoma jo'natish",
            duration_seconds=145,
            manager_name="Ali Valiyev",
            caller_phone="+998901112233",
            analysis=analysis,
            task_id="task_555",
        )
        assert "🎙 <b>AI Qo'ng'iroq Tahlili (Call Intelligence)</b>" in msg
        assert "Ali Valiyev" in msg
        assert "2m 25s" in msg
        assert "⭐️ <b>Sifat Bahosi:</b> 92/100" in msg
        assert "⏰ <b>Kelishilgan vaqt:</b> 02.09.2026 10:00" in msg
        assert "💡 <b>Konversiya Tavsiyalari:</b>" in msg
        assert "Task #task_555" in msg

    @pytest.mark.asyncio
    async def test_scheduler_scan_execution(self):
        """Scheduler scan should discover leads and invoke CallAnalyzer."""
        mock_amocrm = MagicMock()
        mock_amocrm.get_leads = MagicMock(return_value=[
            {"id": 101, "status_id": 142, "responsible_user_id": 55},
            {"id": 102, "status_id": 143},  # Closed lost -> filtered out
        ])
        mock_amocrm.get_lead_phone = MagicMock(return_value="+998901234567")

        mock_db = MagicMock()

        with patch("src.services.core.call_analyzer.CallAnalyzer") as MockAnalyzerCls:
            mock_inst = MagicMock()
            mock_inst.process_call_recordings_for_lead = AsyncMock(return_value=["call_1"])
            MockAnalyzerCls.return_value = mock_inst

            scan_res = await run_call_analysis_scan(amocrm=mock_amocrm, db=mock_db, limit=10)
            assert scan_res.scanned_leads == 1
            assert scan_res.processed_calls == 1
            assert scan_res.errors == 0
