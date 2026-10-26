import asyncio
import datetime as dt

import pytest

import src.schedulers.speed_to_lead as stl
from src.services.core.marketing.seller_metrics import TZ

# Seshanba 2026-10-27 10:00 Toshkent — ish vaqti
NOW = dt.datetime(2026, 10, 27, 10, 0, tzinfo=TZ).timestamp()


def _ago(minutes):
    return int(NOW - minutes * 60)


def test_decide_ladder():
    assert stl.decide(stl.STAGE_NONE, _ago(10), None, NOW) is None
    assert stl.decide(stl.STAGE_NONE, _ago(20), None, NOW) == "remind"
    assert stl.decide(stl.STAGE_REMINDED, _ago(20), None, NOW) is None
    assert stl.decide(stl.STAGE_REMINDED, _ago(50), None, NOW) == "escalate"
    assert stl.decide(stl.STAGE_NONE, _ago(50), None, NOW) == "escalate"
    assert stl.decide(stl.STAGE_ESCALATED, _ago(90), None, NOW) is None
    assert stl.decide(stl.STAGE_REMINDED, _ago(20), _ago(1), NOW) == "answered"
    assert stl.decide(stl.STAGE_DONE, _ago(90), None, NOW) is None


def test_night_lead_waits_until_morning():
    # Dushanba 22:00 da kelgan lid — Seshanba 09:10 da faqat 10 ish daqiqasi
    created = int(dt.datetime(2026, 10, 26, 22, 0, tzinfo=TZ).timestamp())
    now = dt.datetime(2026, 10, 27, 9, 10, tzinfo=TZ).timestamp()
    assert stl.decide(stl.STAGE_NONE, created, None, now) is None
    assert not stl.is_work_time(dt.datetime(2026, 10, 26, 22, 0, tzinfo=TZ).timestamp())
    assert stl.is_work_time(now)


def test_seller_map_and_mention():
    m = stl.parse_seller_map("111:222, bad, 333:x ,444:555")
    assert m == {111: 222, 444: 555}
    assert 'tg://user?id=222' in stl.seller_mention(111, "Ali <x>", m)
    assert "&lt;x&gt;" in stl.seller_mention(111, "Ali <x>", m)
    assert stl.seller_mention(999, "Vali", m) == "<b>Vali</b>"
    assert "belgilanmagan" in stl.seller_mention(stl.BOT_RESPONSIBLE_USER_ID, "bot", m)


def test_candidate_leads_filters_backlog_closed_done():
    state = {"since": _ago(60), "leads": {"5": {"stage": stl.STAGE_DONE}}}
    leads = [
        {"id": 1, "created_at": _ago(30), "status_id": 1},
        {"id": 2, "created_at": _ago(120), "status_id": 1},   # since dan oldin
        {"id": 3, "created_at": _ago(30), "status_id": 142},  # yopilgan
        {"id": 5, "created_at": _ago(30), "status_id": 1},    # tugagan
    ]
    assert [l["id"] for l in stl.candidate_leads(leads, state, NOW)] == [1]


class _FakeAmo:
    def __init__(self, leads, events):
        self.leads, self.events = leads, events

    async def get_leads(self, **_):
        return self.leads

    def get_user_name(self, uid):
        return "Shahnoza"


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(stl, "_STATE_FILE", tmp_path / "state.json")
    sent = []

    async def fake_send(action, text, lead_id):
        sent.append((action, lead_id))
        return True

    monkeypatch.setattr(stl, "_send", fake_send)
    return sent


def _run(amo, events, monkeypatch, now=NOW):
    async def fake_events(_amo, lead_id):
        return events.get(lead_id, [])

    import src.services.core.marketing.attribution_sync as sync
    monkeypatch.setattr(sync, "_fetch_lead_events", fake_events)
    return asyncio.run(stl.check_once(amo, now=now))


def test_first_run_sets_baseline_without_alerts(harness, monkeypatch):
    amo = _FakeAmo([{"id": 1, "created_at": _ago(30), "status_id": 1, "responsible_user_id": 7}], {})
    assert _run(amo, {}, monkeypatch) == 0
    assert harness == []
    assert stl.load_state()["since"] == NOW


def test_full_ladder_then_answered(harness, monkeypatch):
    stl.save_state({"since": _ago(600), "leads": {}}, NOW)
    lead = {"id": 1, "created_at": _ago(20), "status_id": 1, "responsible_user_id": 7}
    amo = _FakeAmo([lead], {})
    _run(amo, {}, monkeypatch)
    assert harness == [("remind", 1)]
    _run(amo, {}, monkeypatch)  # takror yo'q
    assert harness == [("remind", 1)]
    _run(amo, {}, monkeypatch, now=NOW + 30 * 60)
    assert harness[-1] == ("escalate", 1)
    touch = [{"type": "outgoing_call", "created_by": 7, "created_at": int(NOW + 35 * 60)}]
    _run(amo, {1: touch}, monkeypatch, now=NOW + 40 * 60)
    assert harness[-1] == ("answered", 1)
    assert stl.load_state()["leads"]["1"]["stage"] == stl.STAGE_DONE


def test_answered_on_time_is_silent(harness, monkeypatch):
    stl.save_state({"since": _ago(600), "leads": {}}, NOW)
    touch = [{"type": "outgoing_call", "created_by": 7, "created_at": _ago(25)}]
    amo = _FakeAmo([{"id": 1, "created_at": _ago(30), "status_id": 1, "responsible_user_id": 7}], {})
    _run(amo, {1: touch}, monkeypatch)
    assert harness == []
    assert stl.load_state()["leads"]["1"]["stage"] == stl.STAGE_DONE
