"""Tests for the amoCRM notes connector, report text and /vadalar command."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.services.evidence import build_promise_report
from src.services.evidence.amocrm_notes import SOURCE, fetch_recent_notes
from src.services.evidence.report_text import format_promise_report

NOW = datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc)  # 11:00 Tashkent
CREATED = int(datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc).timestamp())


class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def json(self):
        return self._body


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


class _Amo:
    base_url = "https://example.amocrm.ru"

    def _get_headers(self):
        return {"Authorization": "Bearer test"}


def _note(nid, text, lead=777):
    return {"id": nid, "entity_id": lead, "created_by": 5, "created_at": CREATED, "params": {"text": text}}


@pytest.mark.asyncio
async def test_fetch_notes_pages_and_reports_ok():
    session = _Session([
        _Resp(200, {"_embedded": {"notes": [_note(1, "Mijoz ertaga 3 million to'laydi")]},
                    "_links": {"next": {"href": "https://example.amocrm.ru/next"}}}),
        _Resp(200, {"_embedded": {"notes": [_note(2, "Qo'ng'iroq qilindi"), _note(3, "")]}}),
    ])
    msgs, status = await fetch_recent_notes(_Amo(), days=14, now=NOW, session=session)
    assert status == "ok"
    assert [m.source_id for m in msgs] == ["1", "2"]
    assert msgs[0].lead_id == "777"
    assert session.calls[0][1]["filter[note_type][0]"] == "common"
    assert session.calls[1] == ("https://example.amocrm.ru/next", None)


@pytest.mark.asyncio
async def test_fetch_notes_http_error_is_reported_not_hidden():
    msgs, status = await fetch_recent_notes(_Amo(), now=NOW, session=_Session([_Resp(401)]))
    assert msgs == []
    assert status == "amoCRM HTTP 401"


@pytest.mark.asyncio
async def test_fetch_notes_204_means_ok_and_empty():
    msgs, status = await fetch_recent_notes(_Amo(), now=NOW, session=_Session([_Resp(204)]))
    assert (msgs, status) == ([], "ok")


@pytest.mark.asyncio
async def test_fetch_notes_without_amocrm():
    assert await fetch_recent_notes(None) == ([], "amocrm sozlanmagan")


@pytest.mark.asyncio
async def test_report_text_shows_evidence_and_incomplete_warning():
    msgs, _ = await fetch_recent_notes(
        _Amo(), now=NOW,
        session=_Session([_Resp(200, {"_embedded": {"notes": [_note(9, "Mijoz ertaga 3 million to'laydi")]}})]),
    )
    report = build_promise_report(msgs, source_status={SOURCE: "ok", "telegram": "ulanmagan"})
    text = format_promise_report(report, 14)
    assert "29.10.2026 — 3 000 000 so'm (lid 777)" in text
    assert "Menejer yozgan (1)" in text
    assert "amocrm_note #9" in text
    assert "To'liq emas" in text and "telegram: ulanmagan" in text


@pytest.mark.asyncio
async def test_vadalar_command_for_owner(monkeypatch):
    from src import config
    from src.handlers.msg_pipeline import admin_commands
    import src.services.evidence.amocrm_notes as notes_mod

    async def fake_fetch(amocrm, days=14, **_):
        return [], "amoCRM HTTP 401"

    monkeypatch.setattr(notes_mod, "fetch_recent_notes", fake_fetch)
    monkeypatch.setattr(config, "OWNER_ID", 42, raising=False)

    sent = []

    async def respond(text, **_):
        sent.append(text)

    event = SimpleNamespace(
        is_private=True, sender_id=42,
        message=SimpleNamespace(text="/vadalar 7"), respond=respond,
    )
    handled = await admin_commands.process_admin_commands(
        event, client=None, bot_client=None,
        msg_controller=SimpleNamespace(crm=SimpleNamespace(amocrm=_Amo())),
        settings=None, meeting_scheduler=None, get_surgical_integration=None,
        _negotiation_int=None, lead_scraper=None, audit_agent=None,
        auto_lead_agent=None, admin_bot=None, TN5_GROUP_ID=None, TN5_TOPIC_ID=None,
    )
    assert handled is True
    assert "oxirgi 7 kun" in sent[-1]
    assert "amoCRM HTTP 401" in sent[-1]


@pytest.mark.asyncio
async def test_vadalar_ignored_for_strangers(monkeypatch):
    from src import config
    from src.handlers.msg_pipeline import admin_commands

    monkeypatch.setattr(config, "OWNER_ID", 42, raising=False)
    monkeypatch.setattr(config, "WHITELIST_IDS", [], raising=False)
    event = SimpleNamespace(
        is_private=True, sender_id=999,
        message=SimpleNamespace(text="/vadalar"), respond=None,
    )
    handled = await admin_commands.process_admin_commands(
        event, client=None, bot_client=None, msg_controller=None, settings=None,
        meeting_scheduler=None, get_surgical_integration=None, _negotiation_int=None,
        lead_scraper=None, audit_agent=None, auto_lead_agent=None, admin_bot=None,
        TN5_GROUP_ID=None, TN5_TOPIC_ID=None,
    )
    assert handled is False


class _BadJsonResp(_Resp):
    def json(self):
        raise ValueError("not json")


class _BoomSession:
    def get(self, *a, **k):
        raise ConnectionError("down")


@pytest.mark.asyncio
async def test_fetch_notes_invalid_json_is_reported():
    msgs, status = await fetch_recent_notes(_Amo(), now=NOW, session=_Session([_BadJsonResp(200)]))
    assert msgs == []
    assert "JSON" in status


@pytest.mark.asyncio
async def test_fetch_notes_unexpected_shapes_do_not_crash():
    session = _Session([_Resp(200, {"_embedded": None, "_links": None})])
    assert await fetch_recent_notes(_Amo(), now=NOW, session=session) == ([], "ok")
    session = _Session([_Resp(200, [1, 2])])
    msgs, status = await fetch_recent_notes(_Amo(), now=NOW, session=session)
    assert msgs == [] and "format" in status


@pytest.mark.asyncio
async def test_fetch_notes_request_exception_is_reported():
    msgs, status = await fetch_recent_notes(_Amo(), now=NOW, session=_BoomSession())
    assert msgs == []
    assert status == "amoCRM so'rovi xato: ConnectionError"


@pytest.mark.asyncio
async def test_fetch_notes_page_limit_marks_partial():
    import src.services.evidence.amocrm_notes as notes_mod

    page = {"_embedded": {"notes": [_note(1, "x")]}, "_links": {"next": {"href": "https://e/next"}}}
    session = _Session([_Resp(200, page) for _ in range(notes_mod._MAX_PAGES)])
    msgs, status = await fetch_recent_notes(_Amo(), now=NOW, session=session)
    assert len(msgs) == notes_mod._MAX_PAGES
    assert status == f"faqat {notes_mod._MAX_PAGES} sahifa o'qildi"


@pytest.mark.parametrize("cmd,days", [("/vadalar", 14), ("/vadalar 30", 30), ("/vadalar 0", 14), ("/vadalar 999", 14), ("/vadalar abc", 14)])
@pytest.mark.asyncio
async def test_vadalar_period_and_fallback(monkeypatch, cmd, days):
    from src import config
    from src.handlers.msg_pipeline import admin_commands
    import src.services.evidence.amocrm_notes as notes_mod

    seen = {}

    async def fake_fetch(amocrm, days=14, **_):
        seen["days"] = days
        return [], "ok"

    monkeypatch.setattr(notes_mod, "fetch_recent_notes", fake_fetch)
    monkeypatch.setattr(config, "OWNER_ID", 42, raising=False)

    async def respond(text, **_):
        pass

    event = SimpleNamespace(is_private=True, sender_id=42, message=SimpleNamespace(text=cmd), respond=respond)
    await admin_commands.process_admin_commands(
        event, client=None, bot_client=None,
        msg_controller=SimpleNamespace(crm=SimpleNamespace(amocrm=_Amo())),
        settings=None, meeting_scheduler=None, get_surgical_integration=None,
        _negotiation_int=None, lead_scraper=None, audit_agent=None,
        auto_lead_agent=None, admin_bot=None, TN5_GROUP_ID=None, TN5_TOPIC_ID=None,
    )
    assert seen["days"] == days
