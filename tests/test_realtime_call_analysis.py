"""
Tests for real-time call analysis triggered from AmoCRM webhooks and urgent problem alerts.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.requests import Request

from src.services.core.calls import call_notifier
from src.services.api_server.webhooks import _resolve_lead_id_for_note, amocrm_notes_webhook


def test_is_problem_call_detects_low_score():
    analysis = {"sifat_bahosi": 55, "client_mood": "Ijobiy"}
    assert call_notifier.is_problem_call(analysis) is True

    analysis_high = {"sifat_bahosi": 85, "client_mood": "Ijobiy"}
    assert call_notifier.is_problem_call(analysis_high) is False


def test_is_problem_call_detects_objections():
    analysis = {"sifat_bahosi": 75, "etirozlar": ["Narxi qimmat deb aytdi"]}
    assert call_notifier.is_problem_call(analysis) is True

    analysis_empty = {"sifat_bahosi": 75, "etirozlar": []}
    assert call_notifier.is_problem_call(analysis_empty) is False


def test_is_problem_call_detects_negative_mood():
    analysis = {"sifat_bahosi": 70, "client_mood": "Salbiy (jahl bilan gapirdi)"}
    assert call_notifier.is_problem_call(analysis) is True


def test_is_problem_call_detects_lost_deal():
    analysis = {"sifat_bahosi": 70, "natija": "Rad etildi / Yo'qotildi"}
    assert call_notifier.is_problem_call(analysis) is True


def test_build_urgent_problem_alert_content():
    analysis = {
        "sifat_bahosi": 45,
        "etirozlar": ["Byudjet yetarli emas"],
        "client_mood": "Salbiy",
        "konversiya_tavsiyalari": ["Bo'lib to'lash variantini taklif qilish"],
    }
    card = call_notifier.build_urgent_problem_alert(
        lead_id=12345,
        call_id="call-99",
        summary="Mijoz narxdan norozi bo'lib telefonni qo'ydi",
        client_mood="Salbiy",
        duration_seconds=75,
        manager_name="Sardor",
        caller_phone="+998901234567",
        analysis=analysis,
        subdomain="jonbranding",
    )
    assert "DIQQAT: Qo'ng'iroqda muammo" in card
    assert "12345" in card
    assert "+998901234567" in card
    assert "Sardor" in card
    assert "45/100" in card
    assert "Byudjet yetarli emas" in card
    assert "Bo'lib to'lash" in card


@pytest.mark.asyncio
async def test_send_call_analysis_telegram_alert_sends_both_cards_on_problem(monkeypatch):
    sent_messages = []

    async def fake_dispatch(text, chat_id, topic_id=None):
        sent_messages.append({"text": text, "chat_id": chat_id, "topic_id": topic_id})
        return True

    monkeypatch.setattr(call_notifier, "_dispatch_telegram_message", fake_dispatch)

    from src.settings import settings
    monkeypatch.setattr(settings, "CALL_ANALYSIS_GROUP_ID", -100111222, raising=False)
    monkeypatch.setattr(settings, "CALL_ANALYSIS_TOPIC_ID", 99, raising=False)

    analysis = {
        "sifat_bahosi": 40,
        "etirozlar": ["Qimmat"],
        "client_mood": "Salbiy",
    }
    await call_notifier.send_call_analysis_telegram_alert(
        lead_id=888,
        call_id="c-problem",
        category="Taklif",
        summary="Mijoz e'tiroz bildirdi",
        client_mood="Salbiy",
        next_steps="Qayta qo'ng'iroq",
        duration_seconds=60,
        manager_name="Ali",
        caller_phone="+998930001122",
        analysis=analysis,
        task_id="t1",
    )

    # 1 standard analysis card + 1 urgent problem alert = 2 messages
    assert len(sent_messages) == 2
    assert "Suhbat Tahlili" in sent_messages[0]["text"] or "Kategoriya" in sent_messages[0]["text"] or "Ali" in sent_messages[0]["text"]
    assert "DIQQAT: Qo'ng'iroqda muammo" in sent_messages[1]["text"]
    assert sent_messages[1]["chat_id"] == -100111222
    assert sent_messages[1]["topic_id"] == 99


@pytest.mark.asyncio
async def test_resolve_lead_id_for_note_direct_lead():
    note_lead = {"element_id": "777", "element_type": "2"}
    lead_id = await _resolve_lead_id_for_note(note_lead, None)
    assert lead_id == 777


@pytest.mark.asyncio
async def test_resolve_lead_id_for_note_contact_with_phone_lookup():
    mock_amocrm = MagicMock()
    mock_amocrm.find_active_lead_by_phone.return_value = {"id": 999}

    note_contact = {
        "element_id": "333",
        "element_type": "1",
        "phone": "+998901112233",
    }
    lead_id = await _resolve_lead_id_for_note(note_contact, mock_amocrm)
    assert lead_id == 999
    mock_amocrm.find_active_lead_by_phone.assert_called_once_with("+998901112233")


@pytest.mark.asyncio
async def test_webhook_notes_triggers_realtime_call_analysis():
    from starlette.requests import Request
    from starlette.datastructures import FormData

    dummy_form = FormData([
        ("notes[add][0][element_id]", "456"),
        ("notes[add][0][element_type]", "2"),
        ("notes[add][0][note_type]", "10"),
        ("notes[add][0][text]", "Audio zapis razgovora: https://storage.amocrm.ru/record.mp3"),
        ("notes[add][0][link]", "https://storage.amocrm.ru/record.mp3"),
    ])

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/webhook/amocrm_notes",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "app": None,
    }
    fake_request = Request(scope)
    fake_request._form = dummy_form

    with patch("src.services.api_server.webhooks._get_amocrm_instance", return_value=MagicMock()), \
         patch("src.services.api_server.webhooks._get_db_instance", AsyncMock(return_value=MagicMock())), \
         patch("src.services.core.call_analyzer.CallAnalyzer") as MockCallAnalyzer, \
         patch("asyncio.create_task") as mock_create_task:

        mock_instance = MockCallAnalyzer.return_value
        res = await amocrm_notes_webhook(fake_request)
        assert res == {"status": "ok"}

        assert mock_create_task.called
        # Check that process_call_recordings_for_lead was called
        mock_instance.process_call_recordings_for_lead.assert_called_once()
        args, kwargs = mock_instance.process_call_recordings_for_lead.call_args
        assert kwargs["lead_id"] == 456
        assert kwargs["call_notes_override"][0]["link"] == "https://storage.amocrm.ru/record.mp3"
