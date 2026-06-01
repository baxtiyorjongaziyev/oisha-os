from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest

from src.services.core.call_analyzer import CallAnalyzer, GeminiQuotaCooldownError
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
    note_text = amocrm_mock.add_lead_note.call_args.args[1]
    assert "Transkripsiya (O'zbek)" in note_text
    assert "AI_CALL_ANALYSIS" in note_text
    assert "Call ID: call-uniq-777" in note_text
    assert "Mijoz qiziqdi" in note_text
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
