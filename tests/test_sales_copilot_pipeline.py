"""Sales copilot: signals, stage fallback/LLM parsing, rules, reports, scheduler gate."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.services.core.sales_copilot import context, report, rules, service, signals, stage
from src.services.core.sales_copilot.transcript import (
    Msg,
    Transcript,
    classify_sender,
    collect_transcripts,
    dominant_manager,
)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
CARD = "5614681918811393"


def tr(*rows, key="shahnoza", chat_id=101, name="Ali"):
    msgs = [Msg(side=s, at=NOW - timedelta(minutes=m), text=x) for s, m, x in rows]
    return Transcript(key, chat_id, f"{name} | Jon Branding", name, msgs)


def run(coro):
    return asyncio.run(coro)


# --- signals ---------------------------------------------------------------

def test_signals_price_card_objection():
    t = tr(("client", 300, "Salom, logo kerak"), ("manager", 290, "Narxi 880 000 soʻm"),
           ("client", 200, "Biroz qimmat ekan"), ("manager", 100, f"Karta: {CARD} 880 000 soʻm"))
    s = signals.compute(t, NOW, [CARD])
    assert s.price_at is not None and s.card == CARD and s.card_amount == 880000
    assert "qimmat" in s.objections
    assert s.last_side == "us" and s.followups == 1 and s.client_messages == 2


def test_signals_unanswered_question():
    s = signals.compute(tr(("manager", 30, "Salom"), ("client", 10, "Narxi qancha?")), NOW, [CARD])
    assert s.last_side == "client" and s.unanswered_question and s.minutes_since_last == 10


def test_has_price_needs_number_and_word():
    assert signals.has_price("Narxi 2 mln")
    assert not signals.has_price("Narx haqida keyin")
    assert not signals.has_price("Telefon 901234567")


# --- stage -----------------------------------------------------------------

@pytest.mark.parametrize("rows,expected", [
    ([("client", 20, "Salom")], "greeting"),
    ([("client", 50, "Salom"), ("manager", 40, "Qanday biznes?"), ("client", 30, "Kafe"),
      ("manager", 20, "Tushunarli")], "discovery"),
    ([("client", 50, "Salom"), ("manager", 40, "Narxi 3 mln soʻm")], "offer"),
    ([("manager", 60, "Narxi 3 mln soʻm"), ("client", 50, "Qimmat, maslahatlashaman")], "objection"),
    ([("manager", 60, f"Karta {CARD}")], "card_sent"),
    ([("client", 6000, "Salom"), ("manager", 5000, "Narxi 3 mln soʻm")], "ghost"),
])
def test_fallback_stage(rows, expected):
    t = tr(*rows)
    assert stage.fallback_stage(t, signals.compute(t, NOW, [CARD]), NOW).stage == expected


def test_parse_llm_valid_and_invalid():
    base = stage.StageResult("offer", "q", 0.5)
    good = stage.parse_llm('x {"stage":"objection","quote":"qimmat","confidence":1.7,"draft":"Salom"} y', base)
    assert good.stage == "objection" and good.confidence == 1.0 and good.source == "llm"
    assert stage.parse_llm("not json", base) is None
    assert stage.parse_llm('{"stage":"won"}', base) is None
    assert stage.parse_llm('{"stage":"paid"}', base) is None  # paid only from Airtable


class FakeRouter:
    def __init__(self, text=None, exc=None):
        self.text, self.exc, self.calls = text, exc, 0

    async def generate_text(self, prompt, **kw):
        self.calls += 1
        if self.exc:
            raise self.exc
        return SimpleNamespace(text=self.text)


def test_classify_router_and_fallback():
    t = tr(("manager", 60, "Narxi 3 mln soʻm"), ("client", 50, "Oʻylab koʻraman"))
    s = signals.compute(t, NOW, [CARD])
    r = run(stage.classify(t, s, NOW, [], router=FakeRouter('{"stage":"objection","quote":"q","confidence":0.8}')))
    assert r.stage == "objection" and r.source == "llm"
    r = run(stage.classify(t, s, NOW, [], router=FakeRouter(exc=RuntimeError("down"))))
    assert r.source == "rules" and r.draft
    r = run(stage.classify(t, s, NOW, [], router=FakeRouter("garbage")))
    assert r.source == "rules"


def test_classify_card_never_regresses_and_paid_from_airtable():
    t = tr(("manager", 60, f"Karta {CARD} 880 000 soʻm"), name="Mustabro")
    s = signals.compute(t, NOW, [CARD])
    r = run(stage.classify(t, s, NOW, [], router=FakeRouter('{"stage":"offer","confidence":0.9}')))
    assert r.stage == "card_sent"
    income = [{"Sana": NOW.date().isoformat(), "Summa UZS": 880000, "Izoh": "Mustabro"}]
    r = run(stage.classify(t, s, NOW, income, router=FakeRouter(exc=RuntimeError())))
    assert r.stage == "paid" and r.source == "airtable"


def test_paid_ambiguous_common_amount_not_paid():
    t = tr(("manager", 60, f"Karta {CARD} 880 000 soʻm"), name="Doctor")
    s = signals.compute(t, NOW, [CARD])
    rows = [{"Sana": NOW.date().isoformat(), "Summa UZS": 880000, "Izoh": n} for n in ("Muhammad", "Aziz")]
    assert not stage.check_paid(t, s, rows)


# --- rules -----------------------------------------------------------------

def test_reply_alert_once():
    t = tr(("manager", 30, "Salom"), ("client", 7, "Narxi?"))
    s = signals.compute(t, NOW, [CARD])
    state: dict = {}
    assert [a.kind for a in rules.evaluate(t, s, state, NOW)] == ["reply"]
    assert rules.evaluate(t, s, state, NOW) == []
    t2 = tr(("client", 3, "Salom"))
    assert rules.evaluate(t2, signals.compute(t2, NOW, [CARD]), {}, NOW) == []


def test_price_followup_max_two():
    t = tr(("client", 600, "Salom"), ("manager", 420, "Narxi 3 mln soʻm"))
    s = signals.compute(t, NOW, [CARD])
    state: dict = {}
    assert [a.kind for a in rules.evaluate(t, s, state, NOW)] == ["price_followup"]
    assert rules.evaluate(t, s, state, NOW + timedelta(hours=1)) == []  # window
    assert len(rules.evaluate(t, s, state, NOW + timedelta(hours=7))) == 1
    assert rules.evaluate(t, s, state, NOW + timedelta(hours=14)) == []  # max 2


def test_card_reminder_after_12h_and_not_when_paid():
    t = tr(("manager", 13 * 60, f"Karta {CARD}"))
    s = signals.compute(t, NOW, [CARD])
    assert [a.kind for a in rules.evaluate(t, s, {}, NOW)] == ["card_reminder"]
    assert rules.evaluate(t, s, {}, NOW, paid=True) == []
    t2 = tr(("manager", 11 * 60, f"Karta {CARD}"))
    assert rules.evaluate(t2, signals.compute(t2, NOW, [CARD]), {}, NOW) == []


def test_owner_chats_get_no_alerts():
    t = tr(("client", 10, "Salom?"), key="owner")
    assert rules.evaluate(t, signals.compute(t, NOW, [CARD]), {}, NOW) == []


def test_reply_alert_from_last():
    st: dict = {}
    a = rules.reply_alert_from_last("u", "rayxona", "Ali", False, NOW - timedelta(minutes=6), st, NOW)
    assert a and a.kind == "reply"
    assert rules.reply_alert_from_last("u", "rayxona", "Ali", False, NOW - timedelta(minutes=6), st, NOW) is None
    assert rules.reply_alert_from_last("v", "rayxona", "Ali", True, NOW - timedelta(minutes=6), st, NOW) is None


def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    rules.save_state({"chats": {"a": {"manager": "shahnoza"}}}, str(p))
    assert rules.load_state(str(p))["chats"]["a"]["manager"] == "shahnoza"
    assert rules.load_state(str(tmp_path / "none.json")) == {}


# --- report / service ------------------------------------------------------

def _assessed(key, st, conf=0.8, name="X"):
    t = tr(("client", 10, "hi"), key=key, name=name)
    return report.Assessed(t, stage.StageResult(st, "q", conf, draft="Salom"), t.last_at)


def test_top_and_funnel_exclude_non_sales():
    items = [_assessed("shahnoza", s, name=s) for s in ("greeting", "card_sent", "paid", "offer")]
    items += [_assessed("owner", "card_sent"), _assessed("hasanboy", "offer")]
    top = report.top_for_manager(items, "shahnoza")
    assert [a.stage.stage for a in top] == ["card_sent", "offer", "greeting"]
    table = report.funnel(items, ["shahnoza", "mumtozmaxal", "rayxona"])
    assert set(table) == {"shahnoza", "mumtozmaxal", "rayxona"}
    assert table["shahnoza"]["paid"] == 1
    text = report.format_funnel(table, {"shahnoza": "Shahnoza"})
    assert "Shahnoza" in text and "Jami" in text
    assert "Qoralama" in report.format_top("Shahnoza", top)


def test_service_daily_routes_to_topics(monkeypatch):
    monkeypatch.delenv("CARD_WATCH_MANAGERS", raising=False)
    sent = []

    async def send(text, topic):
        sent.append(topic)
        return True

    items = [_assessed("shahnoza", "offer"), _assessed("owner", "offer")]
    assert run(service.send_daily(items, send)) == 4
    assert sorted(sent) == [118, 120, 122, 2976] and 17141 not in sent


def test_service_assess_caches_llm(monkeypatch):
    router = FakeRouter('{"stage":"offer","quote":"q","confidence":0.7}')
    t = tr(("client", 30, "Salom"), ("manager", 20, "Narxi 3 mln soʻm"))
    state: dict = {}
    run(service.assess([t], [], state, NOW, router=router))
    run(service.assess([t], [], state, NOW, router=router))
    assert router.calls == 1


def test_send_alerts_only_sales_managers():
    sent = []

    async def send(text, topic):
        sent.append(topic)
        return True

    alerts = [rules.Alert("reply", "a", "rayxona", "Ali", NOW - timedelta(minutes=9)),
              rules.Alert("reply", "b", "hasanboy", "Vali", NOW - timedelta(minutes=9))]
    assert run(service.send_alerts(alerts, send, NOW)) == 1 and sent == [2976]


def test_dedupe_prefers_manager():
    a = tr(("client", 5, "x"), key="owner", chat_id=-5)
    b = tr(("client", 5, "x"), key="rayxona", chat_id=-5)
    assert [t.manager_key for t in service.dedupe([a, b])] == ["rayxona"]


# --- transcript ------------------------------------------------------------

class FakeMsg:
    def __init__(self, out, text, minutes, username=""):
        self.out, self.message, self.date = out, text, NOW - timedelta(minutes=minutes)
        self._u = username

    async def get_sender(self):
        return SimpleNamespace(username=self._u)


class FakeClient:
    def __init__(self, dialogs, msgs):
        self.dialogs, self.msgs = dialogs, msgs

    async def iter_dialogs(self, limit=None):
        for d in self.dialogs:
            yield d

    async def iter_messages(self, chat_id, limit=None):
        for m in self.msgs[chat_id]:
            yield m


def test_collect_transcripts_owner_mode_attribution():
    group = SimpleNamespace(id=-7, name="Doctor | Jon Branding", is_user=False, is_group=True, date=NOW)
    other = SimpleNamespace(id=-8, name="Random chat", is_user=False, is_group=True, date=NOW)
    msgs = {-7: [FakeMsg(False, "Karta?", 1, "client1"), FakeMsg(False, "Narx 1 mln", 5, "rayxonjonbranding"),
                 FakeMsg(False, "Patent tayyor", 6, "jonbranding_pm"), FakeMsg(True, "Salom", 9)]}
    out = run(collect_transcripts(FakeClient([group, other], msgs), "owner", NOW - timedelta(days=1),
                                  owner_mode=True, username_map={"RayxonJonbranding": "rayxona"}))
    assert len(out) == 1 and out[0].manager_key == "rayxona"
    assert [m.side for m in out[0].messages] == ["staff", "staff", "manager", "client"]


def test_dominant_manager_and_private_classify():
    assert dominant_manager(["owner", "", "rayxona"], "owner") == "rayxona"
    assert dominant_manager(["owner"], "owner") == "owner"
    assert run(classify_sender(FakeMsg(True, "x", 1), False, {}, set())) == ("manager", "")


# --- context ---------------------------------------------------------------

def test_context_unique_match_only(tmp_path):
    db = tmp_path / "crm.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE dialer_leads (id INTEGER, name TEXT, contact_name TEXT, phone TEXT, price INT, notes_json TEXT)")
    notes = json.dumps([{"note_type": "call_intel", "ai_analysis": {"summary": "Byudjet bor"}},
                        {"note_type": "note", "text": "Qayta qoʻngʻiroq"}])
    conn.execute("INSERT INTO dialer_leads VALUES (1,'Mustabro logo','Mustabro','+998901234567',880000,?)", (notes,))
    conn.execute("INSERT INTO dialer_leads VALUES (2,'A','Muhammad Ali','',0,'[]')")
    conn.execute("INSERT INTO dialer_leads VALUES (3,'B','Muhammad Vali','',0,'[]')")
    conn.commit()
    conn.close()
    ctx = context.find_context("Mustabro", db_path=str(db))
    assert ctx["call_summary"] == "Byudjet bor" and ctx["notes"] == ["Qayta qoʻngʻiroq"]
    assert context.find_context("Muhammad", db_path=str(db)) is None
    assert context.find_context("x", phone="90 123 45 67", db_path=str(db))["lead_id"] == 1
    assert context.find_context("Mustabro", db_path=str(tmp_path / "no.db")) is None


# --- scheduler -------------------------------------------------------------

def test_scheduler_disabled_by_default(monkeypatch):
    from src.schedulers import sales_copilot_scheduler as sch

    monkeypatch.delenv("SALES_COPILOT_ENABLED", raising=False)
    assert sch.is_enabled() is False
    run(sch.sales_copilot_loop(None))  # returns immediately


def test_media_text_markers():
    from src.services.core.sales_copilot.transcript import media_text

    assert media_text(SimpleNamespace(message="", voice=object())) == "[ovozli xabar]"
    assert media_text(SimpleNamespace(message="", voice=None, photo=object())) == "[rasm]"
    assert media_text(SimpleNamespace(message=" hi ")) == "hi"
    assert media_text(SimpleNamespace(message="", voice=None, photo=None, media=None)) == ""


def test_quote_prefers_text_over_media():
    t = tr(("client", 30, "Logo kerak"), ("client", 10, "[rasm]"))
    assert stage._last_quote(t, "client") == "Logo kerak"
