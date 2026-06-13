from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.core.agent_verifier import CRMStateVerifier
from src.services.erp.verifiers import (
    AirtableRecordLiveVerifier,
    AmoCRMTaskLiveVerifier,
    MeetingLiveVerifier,
    TelegramMessageLiveVerifier,
)


@pytest.mark.asyncio
async def test_legacy_crm_state_verifier_fails_closed_without_live_client():
    result = await CRMStateVerifier().verify("101", "202", amocrm=None)

    assert result["success"] is False
    assert result["reason"] == "crm_live_readback_unavailable"


@pytest.mark.asyncio
async def test_legacy_crm_state_verifier_fails_when_live_record_has_no_status():
    amocrm = MagicMock()
    amocrm.get_lead = AsyncMock(return_value={})

    result = await CRMStateVerifier().verify("101", "202", amocrm=amocrm)

    assert result["success"] is False
    assert "crm_state_missing_from_live_readback" in result["reason"]


@pytest.mark.asyncio
async def test_amocrm_api_success_is_failure_when_task_is_not_in_lead():
    amocrm = MagicMock()
    amocrm.get_lead_open_tasks = AsyncMock(return_value=[])
    verifier = AmoCRMTaskLiveVerifier(amocrm)
    action = {
        "action_type": "amocrm.create_task",
        "payload": {"lead_id": 101},
        "expected_result": {"lead_id": 101, "task_exists": True},
    }

    result = await verifier.verify(action, {"success": True, "task_id": 202})

    assert result.success is False
    assert result.reason == "amocrm_task_missing_after_write"
    assert result.actual["task_exists"] is False


@pytest.mark.asyncio
async def test_airtable_api_success_is_failure_when_field_did_not_change():
    airtable = MagicMock()
    airtable.get_projects.return_value = [
        {"id": "rec-1", "fields": {"Loyiha bosqichi": "Brief"}}
    ]
    verifier = AirtableRecordLiveVerifier(airtable)
    action = {
        "action_type": "airtable.update_fields",
        "payload": {
            "record_id": "rec-1",
            "fields": {"Loyiha bosqichi": "Dizayn"},
        },
        "expected_result": {"record_id": "rec-1"},
    }

    result = await verifier.verify(action, {"success": True})

    assert result.success is False
    assert result.reason == "airtable_fields_mismatch"
    assert result.actual["fields"]["Loyiha bosqichi"] == "Brief"


@pytest.mark.asyncio
async def test_telegram_send_success_without_message_id_is_failure():
    telegram = MagicMock()
    verifier = TelegramMessageLiveVerifier(telegram)
    action = {
        "action_type": "telegram.send_message",
        "payload": {"chat_id": 777, "text": "Salom"},
        "expected_result": {"chat_id": 777, "message_exists": True},
    }

    result = await verifier.verify(action, {"success": True})

    assert result.success is False
    assert result.reason == "telegram_message_id_missing"


@pytest.mark.asyncio
async def test_telegram_message_is_confirmed_by_live_readback():
    telegram = MagicMock()
    telegram.get_messages = AsyncMock(return_value=MagicMock(id=55, message="Salom"))
    verifier = TelegramMessageLiveVerifier(telegram)
    action = {
        "action_type": "telegram.send_message",
        "payload": {"chat_id": 777, "text": "Salom"},
        "expected_result": {"chat_id": 777, "message_exists": True},
    }

    result = await verifier.verify(action, {"success": True, "message_id": 55})

    assert result.success is True
    assert result.actual["message_id"] == 55


@pytest.mark.asyncio
async def test_calendar_exists_but_amocrm_meeting_task_missing_is_partial_failure():
    calendar = MagicMock()
    calendar.get_upcoming_events.return_value = [
        {
            "id": "event-1",
            "summary": "Suhbat: Farrux",
            "start": {"dateTime": "2026-06-14T13:00:00+05:00"},
        }
    ]
    amocrm = MagicMock()
    amocrm.get_lead_open_tasks = AsyncMock(return_value=[])
    verifier = MeetingLiveVerifier(calendar, amocrm)
    action = {
        "action_type": "calendar.create_meeting",
        "payload": {
            "lead_id": 101,
            "summary": "Suhbat: Farrux",
            "start_time": "2026-06-14T13:00:00+05:00",
        },
        "expected_result": {
            "calendar_event_exists": True,
            "amocrm_task_exists": True,
        },
    }

    result = await verifier.verify(action, {"success": True, "event_id": "event-1"})

    assert result.success is False
    assert result.reason == "calendar_created_amocrm_task_missing"
    assert result.actual["calendar_event_exists"] is True
    assert result.actual["amocrm_task_exists"] is False
