"""Tests for Twenty CRM client, MoiZvonki webhook bridge, and Resilient Migration Store."""
from __future__ import annotations

import os
import tempfile
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.routes.twenty_moizvonki import (
    normalize_phone_number,
    build_call_note_body,
    _verify_webhook_auth,
    _is_call_processed,
    _record_call_processed,
    process_moizvonki_call,
    MoizvonkiCallPayload,
    router,
)
from src.services.core.crm.twenty_client import (
    TwentyClient,
    TwentyAuthError,
    DEFAULT_AMO_STAGE_MAP,
)
from scripts.migrate_amocrm_to_twenty import (
    SyncMappingStore,
    resolve_twenty_seller_id,
    AMOCRM_SELLER_INFO,
)


def test_normalize_phone_number():
    assert normalize_phone_number("+998901234567") == "+998901234567"
    assert normalize_phone_number("998901234567") == "+998901234567"
    assert normalize_phone_number("901234567") == "+998901234567"
    assert normalize_phone_number("89012345678") == "+79012345678"
    assert normalize_phone_number("") == ""
    assert normalize_phone_number(None) == ""


def test_build_call_note_body():
    body = build_call_note_body(
        phone="+998901234567",
        manager="Shahnoza",
        direction_str="Kiruvchi",
        duration=75,
        status_str="Javob berildi",
        audio_url="https://audio.example.com/rec123.mp3",
        start_time="2026-10-19 14:00:00",
    )
    assert "**📞 Qo'ng'iroq tafsilotlari (Kiruvchi)**" in body
    assert "+998901234567" in body
    assert "Shahnoza" in body
    assert "75 soniya" in body
    assert "Javob berildi" in body
    assert "https://audio.example.com/rec123.mp3" in body
    assert "2026-10-19 14:00:00" in body


def test_verify_webhook_auth(monkeypatch):
    monkeypatch.setenv("SKIP_LIVE", "1")
    monkeypatch.delenv("MOIZVONKI_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("TELEPHONY_WEBHOOK_SECRET", raising=False)
    # Allows in test mode
    _verify_webhook_auth(None, None, None)

    # In production without test flags, raises 500
    monkeypatch.delenv("SKIP_LIVE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    with pytest.raises(HTTPException) as exc_500:
        _verify_webhook_auth(None, None, None)
    assert exc_500.value.status_code == 500

    # Secret configured -> verify matching
    monkeypatch.setenv("MOIZVONKI_WEBHOOK_SECRET", "super-secret-token")
    _verify_webhook_auth("super-secret-token", None, None)
    _verify_webhook_auth(None, "Bearer super-secret-token", None)
    _verify_webhook_auth(None, None, "super-secret-token")

    # Invalid secret -> raises 401
    with pytest.raises(HTTPException) as exc_401:
        _verify_webhook_auth("wrong-secret", None, None)
    assert exc_401.value.status_code == 401


def test_call_id_deduplication():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_calls.db")
        call_id = "test-call-uuid-999"

        assert not _is_call_processed(call_id, db_path=db_path)
        _record_call_processed(call_id, db_path=db_path)
        assert _is_call_processed(call_id, db_path=db_path)


@pytest.mark.asyncio
async def test_process_moizvonki_call_success_and_duplicate():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_calls.db")
        client = MagicMock(spec=TwentyClient)
        client.find_person_by_phone = AsyncMock(return_value={"id": "person-123", "name": "Test"})
        client.add_timeline_note = AsyncMock(return_value={"id": "note-456"})

        payload = MoizvonkiCallPayload(
            phone="+998901234567",
            direction="in",
            status="answered",
            duration=40,
            recording_url="https://rec.mp3",
            call_id="call-abc-1",
        )

        # 1. First execution -> success
        result = await process_moizvonki_call(payload, client, db_path=db_path)
        assert result["status"] == "success"
        assert result["person_id"] == "person-123"
        assert result["note_id"] == "note-456"

        # 2. Duplicate execution with same call_id -> duplicate without calling add_timeline_note again
        client.add_timeline_note.reset_mock()
        dup_result = await process_moizvonki_call(payload, client, db_path=db_path)
        assert dup_result["status"] == "duplicate"
        assert dup_result["call_id"] == "call-abc-1"
        client.add_timeline_note.assert_not_called()


@pytest.mark.asyncio
async def test_process_moizvonki_call_note_failure_raises_502():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_calls.db")
        client = MagicMock(spec=TwentyClient)
        client.find_person_by_phone = AsyncMock(return_value={"id": "person-123"})
        # Note creation fails -> returns None
        client.add_timeline_note = AsyncMock(return_value=None)

        payload = MoizvonkiCallPayload(
            phone="+998901234567",
            call_id="call-fail-1",
        )

        with pytest.raises(HTTPException) as exc_info:
            await process_moizvonki_call(payload, client, db_path=db_path)
        assert exc_info.value.status_code == 502


def test_twenty_client_stage_mapping_and_auth():
    # Valid Twenty enum stage values
    assert DEFAULT_AMO_STAGE_MAP[142] == "CUSTOMER"
    assert DEFAULT_AMO_STAGE_MAP[89067962] == "NEW"
    assert DEFAULT_AMO_STAGE_MAP[87609526] == "MEETING"
    assert DEFAULT_AMO_STAGE_MAP[88871066] == "PROPOSAL"

    # Missing auth key raises TwentyAuthError when required
    client_no_key = TwentyClient(base_url="https://crm.test", api_key="")
    with pytest.raises(TwentyAuthError):
        client_no_key._headers(require_auth=True)

    # When key is present
    client_with_key = TwentyClient(base_url="https://crm.test", api_key="valid-key")
    headers = client_with_key._headers(require_auth=True)
    assert headers["Authorization"] == "Bearer valid-key"


def test_sync_mapping_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_sync.db")
        store = SyncMappingStore(db_path=db_path)

        # Entity mapping persistence
        assert store.get_mapping("lead", 12345) is None
        store.save_mapping("lead", 12345, "twenty-opp-uuid-1")
        assert store.get_mapping("lead", 12345) == "twenty-opp-uuid-1"

        # Note mapping persistence
        store.save_mapping("note", 999, "twenty-note-uuid-2")
        assert store.get_mapping("note", 999) == "twenty-note-uuid-2"

        # Checkpoints
        assert store.get_checkpoint(11162698) is None
        store.save_checkpoint(11162698, last_lead_id=555, count=25)
        cp = store.get_checkpoint(11162698)
        assert cp == (555, 25)


def test_seller_resolution():
    members_by_email = {
        "baxtiyorjongaziyev@gmail.com": "uuid-baxtiyor",
        "shahnoza@jonbranding.uz": "uuid-shahnoza",
        "oydin@jonbranding.uz": "uuid-oydin",
    }
    assert resolve_twenty_seller_id(8128012, members_by_email) == "uuid-baxtiyor"
    assert resolve_twenty_seller_id(13021974, members_by_email) == "uuid-shahnoza"
    assert resolve_twenty_seller_id(13838466, members_by_email) == "uuid-oydin"
    assert resolve_twenty_seller_id(99999999, members_by_email) is None
