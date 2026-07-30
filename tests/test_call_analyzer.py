from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest

from src.services.core.call_analyzer import (
    CallAnalyzer,
    GeminiQuotaCooldownError,
    _rubric_applies,
    _speaker_split,
    _talk_ratio_verdict,
)
from src.services.utils.gemini_fallback import model_candidates


@pytest.fixture(autouse=True)
def reset_call_analyzer_cooldown():
    CallAnalyzer._gemini_blocked_until = 0.0
    yield
    CallAnalyzer._gemini_blocked_until = 0.0


def _mock_db_with_processed_row(row):
    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = row

    execute_result = MagicMock()
    execute_result.__aenter__ = AsyncMock(return_value=mock_cursor)
    execute_result.__aexit__ = AsyncMock(return_value=None)

    mock_conn = MagicMock()
    mock_conn.execute = MagicMock(return_value=execute_result)

    db_mock = MagicMock()
    db_mock.get_connection = AsyncMock(return_value=mock_conn)
    return db_mock


@pytest.mark.asyncio
async def test_is_call_processed_true():
    analyzer = CallAnalyzer(
        amocrm=MagicMock(),
        voice_processor=MagicMock(),
        db=_mock_db_with_processed_row((1,)),
    )

    processed = await analyzer._is_call_processed("call-123")

    assert processed is True


@pytest.mark.asyncio
async def test_is_call_processed_false():
    analyzer = CallAnalyzer(
        amocrm=MagicMock(),
        voice_processor=MagicMock(),
        db=_mock_db_with_processed_row(None),
    )

    processed = await analyzer._is_call_processed("call-456")

    assert processed is False


@pytest.mark.asyncio
async def test_analyze_transcript_success():
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                text=(
                    '{"summary": "Mijoz brending narxlari bilan qiziqdi.", '
                    '"category": "Mijoz", "client_mood": "Positive", '
                    '"next_steps": "Tijorat taklifini yuborish"}'
                )
            )

    fake_client = SimpleNamespace(models=FakeModels())
    analyzer = CallAnalyzer(
        amocrm=MagicMock(),
        db=MagicMock(),
        voice_processor=MagicMock(),
        gemini_client=fake_client,
    )

    result = await analyzer.analyze_transcript("Salom, brending narxi qancha?")

    assert result["category"] == "Mijoz"
    assert result["summary"] == "Mijoz brending narxlari bilan qiziqdi."
    assert result["client_mood"] == "Ijobiy"


@pytest.mark.asyncio
async def test_gemini_generate_content_pauses_after_quota_error():
    models = MagicMock()
    models.generate_content = AsyncMock(
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")
    )
    analyzer = CallAnalyzer(
        amocrm=MagicMock(),
        db=MagicMock(),
        gemini_client=SimpleNamespace(aio=SimpleNamespace(models=models)),
    )

    # Mock non-Gemini fallback to also fail (return None)
    with patch("src.services.utils.gemini_fallback._non_gemini_fallback", new_callable=AsyncMock, return_value=None):
        with pytest.raises(GeminiQuotaCooldownError):
            await analyzer._gemini_generate_content(contents="first")
        with pytest.raises(GeminiQuotaCooldownError):
            await analyzer._gemini_generate_content(contents="second")

    assert models.generate_content.await_count == len(
        model_candidates(analyzer.model_name)
    )
    assert analyzer._gemini_cooling_down()


@pytest.mark.asyncio
async def test_recent_calls_deferred_during_quota_cooldown_without_openai():
    amocrm_mock = MagicMock()
    amocrm_mock.get_leads_detailed = AsyncMock(return_value=[])
    analyzer = CallAnalyzer(
        amocrm=amocrm_mock,
        db=MagicMock(),
        gemini_client=MagicMock(),
    )
    analyzer.openai_client = None
    analyzer._pause_gemini_for_quota()

    result = await analyzer.analyze_recent_calls()

    assert result["calls_processed"] == 0
    assert result["contact_calls_processed"] == 0
    amocrm_mock.get_leads_detailed.assert_not_awaited()


@pytest.mark.asyncio
async def test_persisted_call_cooldown_defers_scan_after_restart():
    amocrm_mock = MagicMock()
    amocrm_mock.get_leads_detailed = AsyncMock(return_value=[])
    db_mock = MagicMock()
    db_mock.get_state = AsyncMock(return_value=str(time.time() + 600))
    analyzer = CallAnalyzer(
        amocrm=amocrm_mock,
        db=db_mock,
        gemini_client=MagicMock(),
    )
    analyzer.openai_client = None

    result = await analyzer.analyze_recent_calls()

    assert result["calls_processed"] == 0
    assert analyzer._gemini_cooldown_remaining() >= 598
    amocrm_mock.get_leads_detailed.assert_not_awaited()


def test_find_audio_url_from_nested_params():
    analyzer = CallAnalyzer(amocrm=MagicMock(), db=MagicMock())
    note = {
        "note_type": "common",
        "params": {
            "attachments": [
                {
                    "type": "recording",
                    "payload": {"record_url": "https://cdn.example.com/call-1.mp3?token=abc"},
                }
            ]
        },
    }

    assert analyzer._find_audio_url(note) == "https://cdn.example.com/call-1.mp3?token=abc"
    assert analyzer._looks_like_call_note(note) is True


def test_analysis_marker_helpers_and_duration():
    analyzer = CallAnalyzer(amocrm=MagicMock(), db=MagicMock())
    notes = [
        {
            "params": {
                "text": "[AI_CALL_ANALYSIS] Oisha-OS: Qo'ng'iroq tahlili\nCall ID: call-777"
            }
        }
    ]

    assert analyzer._lead_has_analysis(notes) is True
    assert analyzer._note_has_analysis_for_call(notes, "call-777") is True
    assert analyzer._note_has_analysis_for_call(notes, "call-888") is False
    assert analyzer._extract_call_duration_seconds({"params": {"duration": "42"}}) == 42


def test_common_note_self_link_is_not_call_recording():
    analyzer = CallAnalyzer(amocrm=MagicMock(), db=MagicMock())
    note = {
        "id": 123,
        "note_type": "common",
        "params": {"text": "Oddiy primicheniya"},
        "_links": {
            "self": {
                "href": "https://example.amocrm.ru/api/v4/leads/1/notes/123"
            }
        },
    }

    assert analyzer._find_audio_url(note.get("params") or {}) is None
    assert analyzer._looks_like_call_note(note) is False


@pytest.mark.asyncio
async def test_process_call_recordings_for_lead_success():
    call_note = {
        "id": 112233,
        "note_type": "call_in",
        "params": {
            "uniq": "call-uniq-777",
            "link": "https://amocrm.com/calls/recording.mp3",
            "phone": "+998901234567",
        },
    }

    amocrm_mock = MagicMock()
    amocrm_mock.get_lead_notes = AsyncMock(return_value=[call_note])
    amocrm_mock.add_lead_note = MagicMock(return_value=True)
    amocrm_mock.add_lead_tag = AsyncMock(return_value=True)
    amocrm_mock.create_task = AsyncMock(return_value={"id": 555})

    db_mock = _mock_db_with_processed_row(None)
    db_conn = await db_mock.get_connection()
    db_conn.commit = AsyncMock()

    analyzer = CallAnalyzer(
        amocrm=amocrm_mock,
        voice_processor=MagicMock(),
        db=db_mock,
        gemini_client=None,
    )

    analysis_result = {
        "category": "Mijoz",
        "summary": "Mijoz qiziqdi",
        "client_mood": "Ijobiy",
        "next_steps": "Qayta qo'ng'iroq",
    }

    with patch.object(
        analyzer, "_fetch_audio_bytes", return_value=(b"AUDIO_DATA", "audio/mpeg")
    ), patch.object(
        analyzer, "_transcribe_inline", return_value="A: Salom\nB: Brending narxi qancha?"
    ), patch.object(
        analyzer, "analyze_transcript", return_value=analysis_result
    ):
        processed = await analyzer.process_call_recordings_for_lead(
            999,
            responsible_user_id=777,
        )

    assert processed == 1
    amocrm_mock.add_lead_tag.assert_called_once_with(999, "Mijoz")
    amocrm_mock.create_task.assert_called_once()
    task_args = amocrm_mock.create_task.call_args.args
    task_kwargs = amocrm_mock.create_task.call_args.kwargs
    assert task_args[0] == 999
    assert "Qayta qo'ng'iroq" in task_args[1]
    assert task_kwargs["responsible_user_id"] == 777
    # Note 1 (tahlil): has transcription + analysis summary; no call ID here
    note1_text = amocrm_mock.add_lead_note.call_args_list[0].args[1]
    assert "Transkripsiya (O'zbek)" in note1_text
    assert "AI_CALL_ANALYSIS" in note1_text
    assert "Mijoz qiziqdi" in note1_text
    # Note 2 (mijoz profili): has call ID in "ID: <call_id>" format
    note2_text = amocrm_mock.add_lead_note.call_args_list[1].args[1]
    assert "AI_CALL_ANALYSIS" in note2_text
    assert "ID: call-uniq-777" in note2_text
    insert_args = db_conn.execute.call_args_list[-1].args
    assert "INSERT OR IGNORE INTO call_analyses" in insert_args[0]
    assert "555" in insert_args[1]


@pytest.mark.asyncio
async def test_follow_up_task_skipped_for_na_next_steps():
    amocrm_mock = MagicMock()
    amocrm_mock.create_task = AsyncMock(return_value={"id": 555})
    analyzer = CallAnalyzer(amocrm=amocrm_mock, db=MagicMock(), gemini_client=None)

    created = await analyzer._create_follow_up_task(
        lead_id=999,
        category="Boshqa",
        summary="Xulosa",
        client_mood="Noaniq",
        next_steps="N/A",
    )

    assert created == ""
    amocrm_mock.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_process_call_recordings_dry_run_does_not_write():
    call_note = {
        "id": 112233,
        "note_type": "call_in",
        "params": {
            "uniq": "call-uniq-888",
            "link": "https://amocrm.com/calls/recording.mp3",
            "duration": 30,
        },
    }

    amocrm_mock = MagicMock()
    amocrm_mock.get_lead_notes = AsyncMock(return_value=[call_note])
    amocrm_mock.add_lead_note = MagicMock(return_value=True)
    amocrm_mock.add_lead_tag = AsyncMock(return_value=True)
    amocrm_mock.create_task = AsyncMock(return_value={"id": 555})

    analyzer = CallAnalyzer(amocrm=amocrm_mock, db=_mock_db_with_processed_row(None), gemini_client=None)

    with patch.object(
        analyzer, "_fetch_audio_bytes", return_value=(b"AUDIO_DATA", "audio/mpeg")
    ), patch.object(
        analyzer, "_transcribe_inline", return_value="A: Salom\nB: Brending narxi qancha?"
    ), patch.object(
        analyzer,
        "analyze_transcript",
        return_value={
            "category": "Mijoz",
            "summary": "Mijoz qiziqdi",
            "client_mood": "Ijobiy",
            "next_steps": "Qayta qo'ng'iroq",
        },
    ):
        processed = await analyzer.process_call_recordings_for_lead(999, write=False)

    assert processed == 1
    amocrm_mock.add_lead_note.assert_not_called()
    amocrm_mock.add_lead_tag.assert_not_called()
    amocrm_mock.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_contact_level_calls_route_only_to_single_linked_lead():
    notes = [
        {"entity_id": 10, "params": {"link": "https://cdn.example.com/one.mp3"}},
        {"entity_id": 20, "params": {"link": "https://cdn.example.com/none.mp3"}},
        {"entity_id": 30, "params": {"link": "https://cdn.example.com/many.mp3"}},
    ]
    amocrm_mock = MagicMock()
    amocrm_mock.get_recent_contact_call_notes = AsyncMock(return_value=notes)
    amocrm_mock.get_contact_linked_leads = AsyncMock(
        side_effect=[
            [{"id": 999, "responsible_user_id": 777}],
            [],
            [{"id": 111}, {"id": 222}],
        ]
    )
    analyzer = CallAnalyzer(amocrm=amocrm_mock, db=MagicMock())
    analyzer.process_call_recordings_for_lead = AsyncMock(return_value=1)

    stats = await analyzer.analyze_recent_contact_calls(limit=3)

    assert stats == {
        "contact_calls_discovered": 3,
        "contact_calls_resolved": 1,
        "contact_calls_unlinked": 1,
        "contact_calls_ambiguous": 1,
        "contact_calls_processed": 1,
    }
    analyzer.process_call_recordings_for_lead.assert_awaited_once()
    kwargs = analyzer.process_call_recordings_for_lead.await_args.kwargs
    assert kwargs["responsible_user_id"] == 777
    assert kwargs["call_notes_override"] == [notes[0]]


@pytest.mark.asyncio
async def test_short_call_skipped_with_min_duration_guard():
    """Ovoz pochtasi/band ohang kabi juda qisqa yozuvlar hech qanday AI
    tahliliga yuborilmasligi va CRM'ga yozilmasligi kerak — real suhbat
    bo'lmagan qo'ng'iroqni AI "tahlil qilib" to'qib yozishining oldini oladi."""
    call_note = {
        "id": 1,
        "note_type": "call_in",
        "params": {
            "uniq": "call-short-1",
            "link": "https://amocrm.com/calls/recording.mp3",
            "duration": 2,  # 2 soniya — haqiqiy suhbat bo'lishi mumkin emas
        },
    }
    amocrm_mock = MagicMock()
    amocrm_mock.get_lead_notes = AsyncMock(return_value=[call_note])
    amocrm_mock.add_lead_note = MagicMock(return_value=True)

    analyzer = CallAnalyzer(amocrm=amocrm_mock, voice_processor=MagicMock(), db=_mock_db_with_processed_row(None))

    with patch.object(analyzer, "_fetch_audio_bytes") as fetch_mock, patch.object(
        analyzer, "_transcribe_inline"
    ) as transcribe_mock:
        processed = await analyzer.process_call_recordings_for_lead(
            999, min_call_duration_seconds=10,
        )

    assert processed == 0
    fetch_mock.assert_not_called()
    transcribe_mock.assert_not_called()
    amocrm_mock.add_lead_note.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_inline_returns_none_when_gemini_reports_no_speech():
    """Gemini audio'da tushunarli nutq yo'qligini bildirsa (sentinel),
    to'qilgan (hallucinated) transkripsiya sifatida qabul qilinmasligi kerak."""
    from src.services.core.call_analyzer import NO_SPEECH_SENTINEL

    analyzer = CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=MagicMock())
    analyzer.free_ai_router = MagicMock()
    analyzer.free_ai_router.transcribe_audio = AsyncMock(side_effect=RuntimeError("no free provider"))

    fake_response = SimpleNamespace(text=NO_SPEECH_SENTINEL)
    with patch.object(analyzer, "_gemini_generate_content", return_value=fake_response):
        transcript = await analyzer._transcribe_inline(b"AUDIO", "audio/mpeg")

    assert transcript is None


@pytest.mark.asyncio
async def test_free_stt_hallucination_falls_through_to_gemini():
    """Free STT provayder natijasi hallucination deb rad etilsa, butun
    transkripsiya bekor bo'lmasligi kerak — Gemini (sentinel prompt bilan)
    yo'liga o'tib, uning haqiqiy natijasi qabul qilinadi (Codex P2 review)."""
    analyzer = CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=MagicMock())
    analyzer.free_ai_router = MagicMock()
    analyzer.free_ai_router.transcribe_audio = AsyncMock(
        return_value=SimpleNamespace(provider="groq", model="whisper", text="Thank you for watching")
    )

    real_transcript = "A: Salom, brending xizmati kerak edi\nB: Albatta, qaysi yo'nalishda?"
    fake_response = SimpleNamespace(text=real_transcript)
    with patch.object(analyzer, "_gemini_generate_content", return_value=fake_response):
        transcript = await analyzer._transcribe_inline(b"AUDIO", "audio/mpeg")

    assert transcript == real_transcript


def test_transcript_impossible_for_duration():
    """47s qo'ng'iroqqa ~250 so'zlik 'suhbat' jismonan sig'maydi — rad
    etilishi kerak; real hajmdagi transkripsiya esa o'tishi kerak."""
    from src.services.core.call_analyzer import _transcript_impossible_for_duration

    fabricated = " ".join(["so'z"] * 250)  # foydalanuvchi ko'rsatgan real hodisa
    assert _transcript_impossible_for_duration(fabricated, 47) is True

    realistic = " ".join(["so'z"] * 100)  # 47s uchun ~2.1 so'z/s — normal
    assert _transcript_impossible_for_duration(realistic, 47) is False

    # Davomiylik noma'lum bo'lsa tekshiruv o'tkazib yuboriladi
    assert _transcript_impossible_for_duration(fabricated, 0) is False
    # Qisqa matnlar shovqinli nisbat bergani uchun tekshirilmaydi
    assert _transcript_impossible_for_duration("salom alaykum rahmat", 1) is False


@pytest.mark.asyncio
async def test_impossible_transcript_skipped_before_analysis():
    """Davomiylikka sig'maydigan transkripsiya AmoCRM'ga yozilmasligi va
    tahlilga umuman yuborilmasligi kerak."""
    call_note = {
        "id": 5054,
        "note_type": "call_in",
        "params": {
            "uniq": "call-impossible-47s",
            "link": "https://amocrm.com/calls/recording.mp3",
            "duration": 47,
        },
    }
    amocrm_mock = MagicMock()
    amocrm_mock.get_lead_notes = AsyncMock(return_value=[call_note])
    amocrm_mock.add_lead_note = MagicMock(return_value=True)

    analyzer = CallAnalyzer(amocrm=amocrm_mock, voice_processor=MagicMock(), db=_mock_db_with_processed_row(None))

    fabricated = " ".join(["so'z"] * 250)
    with patch.object(
        analyzer, "_fetch_audio_bytes", return_value=(b"AUDIO", "audio/mpeg")
    ), patch.object(
        analyzer, "_transcribe_inline", return_value=fabricated
    ), patch.object(analyzer, "analyze_transcript") as analyze_mock:
        processed = await analyzer.process_call_recordings_for_lead(999)

    assert processed == 0
    analyze_mock.assert_not_called()
    amocrm_mock.add_lead_note.assert_not_called()


# --- Gapirish nisbati va rubrik amal qilishi ---


def test_speaker_split_generic_labels_not_attributed():
    """Diarizatsiya 'A:'/'B:' bersa — nisbat hisoblanadi, lekin rol biriktirilmaydi."""
    transcript = (
        "A: Allo.\n"
        "B: Allo, assalomu alaykum.\n"
        "A: Va alaykum assalom. Qaysi tomondansiz?\n"
        "B: Men mana eshik tomondanman, aka.\n"
    )
    first, second, attributed = _speaker_split(transcript)

    assert attributed is False
    assert first + second == 100
    # Rol noma'lum ekan — sotuvchini ayblaydigan hukm chiqmasligi shart.
    assert "aniqlanmadi" in _talk_ratio_verdict(first, attributed)


def test_speaker_split_role_labels_attributed():
    transcript = "Mijoz: " + "salom " * 40 + "\nSotuvchi: qisqa javob"
    client_pct, agent_pct, attributed = _speaker_split(transcript)

    assert attributed is True
    assert client_pct > 55
    assert "Yaxshi" in _talk_ratio_verdict(client_pct, attributed)


def test_talk_ratio_verdict_no_data_is_not_an_accusation():
    assert "aniqlanmadi" in _talk_ratio_verdict(0, True)


def test_rubric_skipped_for_non_sales_or_short_calls():
    long_sales = "Mijoz: " + "brending narxi " * 30
    assert _rubric_applies("Mijoz", long_sales) is True
    assert _rubric_applies("Oila", long_sales) is False
    assert _rubric_applies("Mijoz", "A: Allo.\nB: Boldi, hozir otyapman.") is False


def test_analysis_note_omits_rubric_when_not_applicable():
    analyzer = CallAnalyzer(amocrm=MagicMock(), voice_processor=MagicMock(), db=MagicMock())
    note = analyzer._build_amocrm_note(
        {
            "summary": "Kuryer eshik oldida.",
            "category": "Boshqa",
            "rubrik_amal_qiladi": False,
            "talk_ratio_attributed": False,
            "client_talk_pct": 0,
            "agent_talk_pct": 0,
        }
    )

    assert "JON BRANDING RUBRIK" not in note
    assert "Sifat bahosi" not in note
    assert "Baholanmadi" in note
    assert "sotuvchi haddan ko'p gapirdi" not in note


def test_parse_agreed_datetime_accepts_valid_future_time():
    from datetime import datetime
    from src.services.core.call_analyzer import _parse_agreed_datetime
    from src.time_utils import get_local_timezone

    reference = datetime(2026, 7, 15, 10, 0, tzinfo=get_local_timezone())
    result = _parse_agreed_datetime("2026-07-16 15:00", reference_now=reference)

    assert result is not None
    assert result.year == 2026 and result.month == 7 and result.day == 16
    assert result.hour == 15


def test_parse_agreed_datetime_rejects_past_and_hallucinated_far_future():
    from datetime import datetime
    from src.services.core.call_analyzer import _parse_agreed_datetime
    from src.time_utils import get_local_timezone

    reference = datetime(2026, 7, 15, 10, 0, tzinfo=get_local_timezone())

    # O'tmish — rad etiladi
    assert _parse_agreed_datetime("2026-07-14 10:00", reference_now=reference) is None
    # Juda uzoq kelajak (60 kundan ortiq) — hallucination deb rad etiladi
    assert _parse_agreed_datetime("2027-01-01 10:00", reference_now=reference) is None
    # Bo'sh/null — rad etiladi
    assert _parse_agreed_datetime(None, reference_now=reference) is None
    assert _parse_agreed_datetime("null", reference_now=reference) is None
    assert _parse_agreed_datetime("N/A", reference_now=reference) is None


@pytest.mark.asyncio
async def test_follow_up_task_uses_agreed_datetime_when_present():
    """Suhbatda 'ertaga soat 15da' kabi aniq vaqt kelishilgan bo'lsa, vazifa
    standart 24-soatlik muddat o'rniga aynan shu vaqtga qo'yilishi kerak."""
    from datetime import datetime, timezone as tz
    from src.time_utils import get_local_timezone

    amocrm_mock = MagicMock()
    amocrm_mock.create_task = AsyncMock(return_value={"id": 777})

    analyzer = CallAnalyzer(amocrm=amocrm_mock, db=MagicMock())
    agreed = datetime(2026, 8, 1, 15, 0, tzinfo=get_local_timezone())

    task_id = await analyzer._create_follow_up_task(
        lead_id=999,
        category="Mijoz",
        summary="Mijoz brif yuborishga rozi bo'ldi",
        client_mood="Ijobiy",
        next_steps="Ertaga soat 15:00 da qayta qo'ng'iroq qilish",
        agreed_datetime=agreed,
    )

    assert task_id
    amocrm_mock.create_task.assert_awaited_once()
    call_args = amocrm_mock.create_task.await_args
    complete_till = call_args.args[2]
    assert complete_till == int(agreed.astimezone(tz.utc).timestamp())
    task_text = call_args.args[1]
    assert "01.08.2026 15:00" in task_text


@pytest.mark.asyncio
async def test_follow_up_task_falls_back_to_default_hours_without_agreed_time():
    """Suhbatda aniq vaqt kelishilmagan bo'lsa, standart 24-soatlik
    (yoki sozlangan) muddatga qaytishi kerak — eski xatti-harakat buzilmaydi."""
    amocrm_mock = MagicMock()
    amocrm_mock.create_task = AsyncMock(return_value={"id": 778})

    analyzer = CallAnalyzer(amocrm=amocrm_mock, db=MagicMock())

    before = time.time()
    await analyzer._create_follow_up_task(
        lead_id=999,
        category="Mijoz",
        summary="Mijoz o'ylab ko'rishga va'da berdi",
        client_mood="Neytral",
        next_steps="Keyinroq qayta bog'lanish",
        agreed_datetime=None,
    )
    after = time.time()

    call_args = amocrm_mock.create_task.await_args
    complete_till = call_args.args[2]
    expected_min = before + analyzer.task_due_hours * 3600 - 5
    expected_max = after + analyzer.task_due_hours * 3600 + 5
    assert expected_min <= complete_till <= expected_max
