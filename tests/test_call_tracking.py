"""Statik call tracking testlari."""
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import callback_widget
from src.api.security import is_protected_path
from src.services.call_analytics import missed_call_responder as mcr
from src.services.core.leads import call_tracking as ct
from src.time_utils import get_local_timezone

NUMBERS = {"instagram": "+998 71 200 00 01", "google": "712000002", "default": "+998712000000"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv(ct.NUMBERS_ENV, json.dumps(NUMBERS))
    ct.reset_dedup()
    mcr.reset_dedup()
    yield
    ct.reset_dedup()
    mcr.reset_dedup()


def _note(**overrides):
    note = {
        "id": "901", "note_type": "10", "element_id": "777", "element_type": "2",
        "DURATION": "42", "PHONE": "+998901234567", "TO": "998712000001", "UNIQ": "call-1",
    }
    note.update(overrides)
    return note


# --- sozlama ---

def test_numbers_normalized():
    assert ct.load_numbers() == {
        "instagram": "+998712000001", "google": "+998712000002", "default": "+998712000000",
    }


def test_disabled_when_env_missing_or_broken(monkeypatch):
    monkeypatch.delenv(ct.NUMBERS_ENV)
    assert not ct.is_enabled()
    monkeypatch.setenv(ct.NUMBERS_ENV, "{not json")
    assert ct.load_numbers() == {}
    monkeypatch.setenv(ct.NUMBERS_ENV, '["+998712000001"]')
    assert ct.load_numbers() == {}


def test_bad_entries_skipped(monkeypatch):
    monkeypatch.setenv(ct.NUMBERS_ENV, json.dumps({"ok": "+998712000001", "bad": "123", "Bad Key!": "+998712000003"}))
    assert ct.load_numbers() == {"ok": "+998712000001"}


# --- moslash ---

@pytest.mark.parametrize("number,source", [
    ("+998712000001", "instagram"),
    ("71 200 00 02", "google"),
    ("998712000000", "default"),
    ("+998712009999", None),
    ("12", None),
])
def test_source_for_number(number, source):
    assert ct.source_for_number(number) == source


def test_source_found_in_any_field_but_client_phone():
    assert ct.source_for_note(_note())["source"] == "instagram"
    assert ct.source_for_note(_note(TO=None, text="Kiruvchi: liniya +998 71 200 00 02"))["source"] == "google"


def test_client_phone_is_never_used_as_tracking_number():
    note = _note(TO=None, PHONE="+998712000001")
    assert ct.source_for_note(note) is None


# --- AmoCRM izoh ---

@pytest.mark.asyncio
async def test_inbound_call_gets_source_note():
    amo = MagicMock()
    assert await ct.attribute_inbound_call(_note(), amo) == "instagram"
    lead_id, text = amo.add_lead_note.call_args.args
    assert lead_id == 777
    assert "Qo'ng'iroq manbasi: instagram" in text and "+998712000001" in text


@pytest.mark.asyncio
async def test_duplicate_webhook_writes_once():
    amo = MagicMock()
    await ct.attribute_inbound_call(_note(), amo)
    assert await ct.attribute_inbound_call(_note(), amo) is None
    assert amo.add_lead_note.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [{"note_type": "11"}, {"element_type": "1"}, {"TO": "+998712009999"}])
async def test_not_attributed(override):
    amo = MagicMock()
    assert await ct.attribute_inbound_call(_note(**override), amo) is None
    amo.add_lead_note.assert_not_called()


@pytest.mark.asyncio
async def test_amocrm_failure_never_raises():
    amo = MagicMock()
    amo.add_lead_note.side_effect = RuntimeError("down")
    assert await ct.attribute_inbound_call(_note(), amo) is None


# --- javobsiz qo'ng'iroq alertida manba ---

@pytest.mark.asyncio
async def test_missed_call_alert_includes_source(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "alert")
    day = datetime(2026, 10, 6, 14, 30, tzinfo=get_local_timezone())
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)) as alert:
        await mcr.handle_missed_call_note(_note(DURATION="0"), amocrm=None, now=day)
    assert "Manba: instagram" in alert.call_args.args[0]


# --- endpoint ---

def _client():
    app = FastAPI()
    app.state.limiter = callback_widget.limiter
    app.include_router(callback_widget.router)
    return TestClient(app)


def test_config_endpoint_public_and_returns_numbers():
    assert is_protected_path("/api/call-tracking/config") is False
    resp = _client().get("/api/call-tracking/config")
    assert resp.status_code == 200
    assert resp.json()["numbers"]["instagram"] == "+998712000001"


def test_config_endpoint_empty_when_disabled(monkeypatch):
    monkeypatch.delenv(ct.NUMBERS_ENV)
    assert _client().get("/api/call-tracking/config").json() == {"numbers": {}}


# --- webhook ---

def test_amocrm_notes_webhook_triggers_attribution():
    from src.services.api_server import webhooks

    app = FastAPI()
    app.state.limiter = webhooks.limiter
    app.include_router(webhooks.router)
    handler = AsyncMock(return_value="instagram")
    form = {
        "notes[add][0][id]": "902",
        "notes[add][0][note_type]": "10",
        "notes[add][0][element_id]": "777",
        "notes[add][0][params][DURATION]": "42",
        "notes[add][0][params][PHONE]": "+998901234567",
        "notes[add][0][params][TO]": "998712000001",
    }
    with patch.object(ct, "attribute_inbound_call", handler), \
         patch.object(webhooks, "_get_amocrm_instance", return_value=None), \
         patch("src.services.core.call_analyzer.CallAnalyzer"), \
         patch.object(webhooks, "_get_db_instance", AsyncMock(return_value=None)):
        TestClient(app).post("/webhook/amocrm_notes", data=form)
    handler.assert_called_once()
    assert handler.call_args.args[0]["TO"] == "998712000001"
