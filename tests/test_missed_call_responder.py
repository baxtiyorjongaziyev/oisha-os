"""Javobsiz qo'ng'iroq responder testlari."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.call_analytics import missed_call_responder as mcr
from src.time_utils import get_local_timezone

TZ = get_local_timezone()
DAY = datetime(2026, 10, 6, 14, 30, tzinfo=TZ)
NIGHT = datetime(2026, 10, 6, 23, 40, tzinfo=TZ)


def _note(**overrides):
    note = {
        "id": "555",
        "note_type": "10",
        "element_id": "777",
        "element_type": "2",
        "DURATION": "0",
        "PHONE": "+998901234567",
        "UNIQ": "call-abc",
        "responsible_user_id": "42",
    }
    note.update(overrides)
    return note


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    mcr.reset_dedup()
    monkeypatch.delenv(mcr.SLA_ENV, raising=False)
    yield
    mcr.reset_dedup()


def _amocrm():
    amo = MagicMock()
    amo.create_task = AsyncMock(return_value={"ok": True})
    return amo


# --- aniqlash ---

def test_missed_inbound_detected_from_flat_webhook_fields():
    assert mcr.is_missed_inbound(_note())


def test_v4_named_type_and_nested_params():
    note = {"note_type": "call_in", "element_id": "1", "params": {"duration": 0, "phone": "1"}}
    assert mcr.is_missed_inbound(note)


def test_duration_in_json_text():
    note = {"note_type": "10", "element_id": "1", "text": '{"DURATION": 0, "PHONE": "998"}'}
    assert mcr.is_missed_inbound(note)


@pytest.mark.parametrize("override", [
    {"DURATION": "35"},          # gaplashilgan
    {"note_type": "11"},         # chiquvchi
    {"call_status": "4"},        # muvaffaqiyatli
    {"DURATION": None},          # davomiylik noma'lum → alert yo'q
])
def test_not_missed(override):
    note = _note(**override)
    if override.get("DURATION", "x") is None:
        note.pop("DURATION")
    assert not mcr.is_missed_inbound(note)


# --- rejimlar ---

@pytest.mark.asyncio
async def test_mode_off_does_nothing(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "off")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock()) as alert:
        res = await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
    assert res["handled"] is False
    alert.assert_not_called()
    amo.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_mode_falls_back_to_off(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "yes-please")
    assert mcr.get_mode() == "off"


@pytest.mark.asyncio
async def test_alert_mode_sends_telegram_only(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "alert")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)) as alert:
        res = await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
    assert res == {"handled": True, "alert": True, "task": False}
    assert "+998901234567" in alert.call_args.args[0]
    amo.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_live_mode_creates_task_with_sla(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "live")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)):
        res = await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
    assert res["task"] is True
    kwargs = amo.create_task.call_args.kwargs
    assert kwargs["element_id"] == 777
    assert kwargs["responsible_user_id"] == 42
    assert kwargs["complete_till"] == int(DAY.timestamp()) + 15 * 60


@pytest.mark.asyncio
async def test_custom_sla(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "live")
    monkeypatch.setenv(mcr.SLA_ENV, "5")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)):
        await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
    assert amo.create_task.call_args.kwargs["complete_till"] == int(DAY.timestamp()) + 5 * 60


@pytest.mark.asyncio
async def test_duplicate_webhook_handled_once(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "live")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)) as alert:
        await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
        res = await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
    assert res["reason"] == "duplicate"
    assert alert.call_count == 1
    assert amo.create_task.call_count == 1


@pytest.mark.asyncio
async def test_contact_note_alerts_without_task(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "live")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)):
        res = await mcr.handle_missed_call_note(_note(element_type="1"), amocrm=amo, now=DAY)
    assert res["alert"] is True and res["task"] is False
    amo.create_task.assert_not_called()


# --- quiet hours ---

@pytest.mark.asyncio
async def test_quiet_hours_no_telegram_task_next_morning(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "live")
    amo = _amocrm()
    with patch.object(mcr, "_send_alert", AsyncMock()) as alert:
        res = await mcr.handle_missed_call_note(_note(), amocrm=amo, now=NIGHT)
    alert.assert_not_called()
    assert res["reason"] == "quiet_hours"
    expected = datetime(2026, 10, 7, 9, 0, tzinfo=TZ)
    assert amo.create_task.call_args.kwargs["complete_till"] == int(expected.timestamp())


def test_deadline_after_midnight_is_same_morning():
    early = datetime(2026, 10, 7, 2, 15, tzinfo=TZ)
    assert mcr.callback_deadline(early, 15) == datetime(2026, 10, 7, 9, 0, tzinfo=TZ)


# --- xavfsizlik ---

@pytest.mark.asyncio
async def test_failures_never_raise(monkeypatch):
    monkeypatch.setenv(mcr.MODE_ENV, "live")
    amo = _amocrm()
    amo.create_task = AsyncMock(side_effect=RuntimeError("amocrm down"))
    with patch.object(mcr, "_send_alert", AsyncMock(return_value=True)):
        res = await mcr.handle_missed_call_note(_note(), amocrm=amo, now=DAY)
    assert res["handled"] is True and res["task"] is False


def test_alert_escapes_html():
    text = mcr.build_alert("<b>x</b>", None, 15, DAY)
    assert "<b>x</b>" not in text and "&lt;b&gt;" in text


# --- webhook integratsiyasi ---

def test_amocrm_notes_webhook_triggers_responder(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.services.api_server import webhooks

    monkeypatch.setenv(mcr.MODE_ENV, "alert")
    app = FastAPI()
    app.state.limiter = webhooks.limiter
    app.include_router(webhooks.router)
    handler = AsyncMock(return_value={"handled": True})
    form = {
        "notes[add][0][id]": "901",
        "notes[add][0][note_type]": "10",
        "notes[add][0][element_id]": "777",
        "notes[add][0][element_type]": "2",
        "notes[add][0][params][DURATION]": "0",
        "notes[add][0][params][PHONE]": "+998901234567",
    }
    with patch.object(mcr, "handle_missed_call_note", handler), \
         patch.object(webhooks, "_get_amocrm_instance", return_value=None), \
         patch("src.services.core.call_analyzer.CallAnalyzer"), \
         patch.object(webhooks, "_get_db_instance", AsyncMock(return_value=None)):
        resp = TestClient(app).post("/webhook/amocrm_notes", data=form)
    assert resp.json() == {"status": "ok"}
    handler.assert_called_once()
    assert handler.call_args.args[0]["DURATION"] == "0"
