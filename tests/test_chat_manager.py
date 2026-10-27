"""AI Chat Manager: store, zayavka ajratish va /api/chat/ API — synthetic fakes."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import security
from src.api.rbac import Principal, Role
from src.api.routes import chat_manager
from src.api.routes.state import api_state
from src.services.core.chat_manager import extractor, store
from src.services.core.chat_manager.prompt import GUARDRAILS, build_instructions


@pytest.fixture(autouse=True)
def chat_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OISHA_CHAT_DB_PATH", str(tmp_path / "chat.db"))


class FakeRouter:
    def __init__(self, text):
        self.text = text
        self.calls = []

    async def generate_text(self, prompt, **kwargs):
        self.calls.append(prompt)
        return SimpleNamespace(text=self.text)


class FakeAmo:
    def __init__(self):
        self.created = []
        self.notes = []

    async def create_lead(self, **kwargs):
        self.created.append(kwargs)
        return 501

    def add_lead_note(self, lead_id, text):
        self.notes.append((lead_id, text))
        return {"ok": True}


# --- store -------------------------------------------------------------------

def test_record_message_creates_and_updates_dialog():
    a = store.record_message("telegram", "10", "Salom", name="Ali", now=100)
    b = store.record_message("telegram", "10", "Narxi qancha?", now=200)
    assert a == b
    d = store.get_dialog(a)
    assert d["name"] == "Ali" and d["unread"] == 2 and d["last_text"] == "Narxi qancha?"
    assert [m["text"] for m in store.get_messages(a)] == ["Salom", "Narxi qancha?"]


def test_ai_draft_keeps_dialog_waiting_and_unread_unchanged():
    did = store.record_message("instagram", "7", "Salom", now=1)
    store.record_message("instagram", "7", "Assalomu alaykum!", direction="out",
                         author="ai_draft", now=2)
    d = store.get_dialog(did)
    assert d["last_direction"] == "in" and d["unread"] == 1
    assert [x["id"] for x in store.list_dialogs(filter_key="waiting")] == [did]


def test_filters_search_and_counts():
    t = store.record_message("telegram", "1", "Logo kerak", name="Vali", now=1)
    i = store.record_message("instagram", "2", "Salom", name="Gulnora", now=2)
    store.record_message("instagram", "2", "Javob", direction="out", author="operator", now=3)
    store.set_mode(i, "operator")
    store.mark_read(t)
    assert [d["id"] for d in store.list_dialogs()] == [i, t]
    assert [d["id"] for d in store.list_dialogs(filter_key="waiting")] == [t]
    assert [d["id"] for d in store.list_dialogs(filter_key="operator")] == [i]
    assert [d["id"] for d in store.list_dialogs(query="logo")] == [t]
    assert store.dialog_counts() == {"all": 2, "waiting": 1, "operator": 1, "unread": 1}


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        store.record_message("whatsapp", "1", "x")
    with pytest.raises(ValueError):
        store.record_message("telegram", "1", "   ")
    with pytest.raises(ValueError):
        store.list_dialogs(filter_key="drop table")


def test_settings_defaults_validation_and_persistence():
    assert store.get_settings()["auto_reply"] is False
    updated = store.update_settings({"reply_length": 5, "tone": " Rasmiy "})
    assert updated["reply_length"] == 5 and updated["tone"] == "Rasmiy"
    assert store.get_settings()["reply_length"] == 5
    for bad in ({"reply_length": 9}, {"auto_reply": "yes"}, {"nope": 1}, {"informativeness": True}):
        with pytest.raises(ValueError):
            store.update_settings(bad)


def test_instructions_always_contain_guardrails():
    text = build_instructions(store.update_settings({"offer_rules": ""}))
    assert all(rule in text for rule in GUARDRAILS)


# --- extractor ---------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("tel: +998 90 123-45-67", "+998901234567"),
    ("901234567 ga qo'ng'iroq", "+998901234567"),
    ("buyurtma 12 dona", ""),
])
def test_find_phone(raw, expected):
    assert extractor.find_phone(raw) == expected


def test_parse_result_filters_unknown_categories():
    parsed = extractor.parse_result(
        'ok {"categories": ["lead", "spam", "lead"], "summary": "Mijoz logo so\'radi", "phone": ""}'
    )
    assert parsed == {"categories": ["lead"], "summary": "Mijoz logo so'radi", "phone": ""}
    assert extractor.parse_result("no json") is None


def test_extract_creates_request_and_one_amocrm_lead():
    did = store.record_message("telegram", "5", "Logo kerak, raqamim 901234567",
                               name="Ali", now=1)
    router = FakeRouter('{"categories": ["lead"], "summary": "Mijoz logo buyurtma qildi", "phone": ""}')
    amo = FakeAmo()
    created = asyncio.run(extractor.extract_dialog(store.get_dialog(did), router, amo))
    assert len(created) == 1
    req = store.list_requests(did)[0]
    assert req["category"] == "lead" and req["phone"] == "+998901234567"
    assert req["amocrm_lead_id"] == 501
    assert amo.created[0]["phone"] == "+998901234567" and amo.created[0]["name"] == "Ali"
    assert "Mijoz logo buyurtma qildi" in amo.notes[0][1]

    # Yangi xabar → qayta tahlil, lekin ikkinchi amoCRM lid ochilmaydi.
    store.record_message("telegram", "5", "Qachon tayyor bo'ladi?", now=time_after())
    assert asyncio.run(extractor.extract_dialog(store.get_dialog(did), router, amo)) == []
    assert len(amo.created) == 1 and len(store.list_requests(did)) == 1


def time_after():
    import time
    return time.time() + 10


def test_run_cycle_respects_idle_and_marks_extracted():
    store.record_message("instagram", "9", "Narx?", now=1)
    router = FakeRouter('{"categories": ["interested"], "summary": "Mijoz narx so\'radi"}')
    assert asyncio.run(extractor.run_cycle(router, None, min_idle_sec=0)) == 1
    assert asyncio.run(extractor.run_cycle(router, None, min_idle_sec=0)) == 0
    assert len(router.calls) == 1


def test_run_cycle_skips_fresh_dialogs():
    import time
    store.record_message("instagram", "9", "Narx?", now=time.time())
    router = FakeRouter('{"categories": []}')
    assert asyncio.run(extractor.run_cycle(router, None, min_idle_sec=300)) == 0
    assert router.calls == []


# --- API ---------------------------------------------------------------------

class FakeTelegram:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


def _client(monkeypatch, role=Role.OWNER):
    principal = None if role is None else Principal("1", role, "session")
    monkeypatch.setattr(security, "authorize_connection", lambda conn: principal)
    app = FastAPI()
    app.include_router(chat_manager.router)
    return TestClient(app)


def test_page_requires_cookie(monkeypatch):
    c = _client(monkeypatch)
    assert "/api/auth/telegram/login" in c.get("/api/chat/", follow_redirects=False).headers["location"]
    c.cookies.set("oisha_token", "x")
    assert "Dialoglar" in c.get("/api/chat/").text


def test_api_requires_auth(monkeypatch):
    assert _client(monkeypatch, None).get("/api/chat/dialogs").status_code == 401


def test_list_and_detail_marks_read(monkeypatch):
    did = store.record_message("telegram", "5", "Salom", name="Ali")
    c = _client(monkeypatch)
    body = c.get("/api/chat/dialogs").json()
    assert body["dialogs"][0]["id"] == did and body["counts"]["unread"] == 1
    detail = c.get(f"/api/chat/dialogs/{did}").json()
    assert detail["messages"][0]["text"] == "Salom"
    assert store.get_dialog(did)["unread"] == 0
    assert c.get("/api/chat/dialogs?filter=bad").status_code == 422
    assert c.get("/api/chat/dialogs/999").status_code == 404


def test_send_telegram_records_and_switches_to_operator(monkeypatch):
    did = store.record_message("telegram", "555", "Salom")
    tg = FakeTelegram()
    monkeypatch.setattr(api_state, "user_client", tg, raising=False)
    r = _client(monkeypatch).post(f"/api/chat/dialogs/{did}/send", json={"text": "Assalomu alaykum"})
    assert r.status_code == 200
    assert tg.sent == [(555, "Assalomu alaykum")]
    assert store.get_dialog(did)["mode"] == "operator"
    assert store.get_messages(did)[-1]["author"] == "operator"


def test_send_fails_honestly_without_client(monkeypatch):
    did = store.record_message("telegram", "555", "Salom")
    monkeypatch.setattr(api_state, "user_client", None, raising=False)
    r = _client(monkeypatch).post(f"/api/chat/dialogs/{did}/send", json={"text": "x"})
    assert r.status_code == 503
    assert len(store.get_messages(did)) == 1


def test_viewer_cannot_send_or_change_settings(monkeypatch):
    did = store.record_message("telegram", "555", "Salom")
    c = _client(monkeypatch, Role.VIEWER)
    assert c.post(f"/api/chat/dialogs/{did}/send", json={"text": "x"}).status_code == 403
    assert c.put("/api/chat/settings", json={"reply_length": 1}).status_code == 403


def test_mode_and_settings_endpoints(monkeypatch):
    did = store.record_message("telegram", "5", "Salom")
    c = _client(monkeypatch)
    assert c.post(f"/api/chat/dialogs/{did}/mode", json={"mode": "operator"}).json()["mode"] == "operator"
    assert c.post(f"/api/chat/dialogs/{did}/mode", json={"mode": "x"}).status_code == 422
    r = c.put("/api/chat/settings", json={"informativeness": 4})
    assert r.status_code == 200 and r.json()["settings"]["informativeness"] == 4
    assert c.put("/api/chat/settings", json={"informativeness": 0}).status_code == 422
    assert "Qat'iy cheklovlar" in c.get("/api/chat/settings").json()["instructions"]


# --- Zayavkalar (2-bosqich) --------------------------------------------------

def _seed_requests():
    a = store.record_message("telegram", "1", "Logo kerak", name="Ali", now=1)
    b = store.record_message("instagram", "2", "Yomon xizmat", name="Vali", now=2)
    r1, _ = store.upsert_request(a, "lead", "Mijoz logo so'radi", "+998901234567", now=10)
    r2, _ = store.upsert_request(b, "complaint", "Mijoz norozi", now=20)
    r3, _ = store.upsert_request(a, "interested", "Mijoz narx so'radi", now=30)
    return r1, r2, r3


def test_request_filters_and_counts():
    r1, r2, r3 = _seed_requests()
    store.set_request_status(r3, "taken")
    assert [r["id"] for r in store.list_requests()] == [r3, r2, r1]
    assert [r["id"] for r in store.list_requests(category="lead")] == [r1]
    assert [r["id"] for r in store.list_requests(status="open")] == [r2, r1]
    assert [r["id"] for r in store.list_requests(has_phone=True)] == [r1]
    assert [r["id"] for r in store.list_requests(query="Vali")] == [r2]
    counts = store.request_counts()
    assert counts["lead"] == {"total": 1, "open": 1}
    assert counts["interested"] == {"total": 1, "open": 0}
    assert counts["suggestion"] == {"total": 0, "open": 0}
    with pytest.raises(ValueError):
        store.list_requests(category="spam")
    with pytest.raises(ValueError):
        store.set_request_status(r1, "deleted")


def test_requests_page_and_api(monkeypatch):
    r1, _, _ = _seed_requests()
    c = _client(monkeypatch)
    c.cookies.set("oisha_token", "x")
    assert "Ishga olish" in c.get("/api/chat/zayavkalar").text
    body = c.get("/api/chat/requests?category=lead&contact=yes").json()
    assert [r["id"] for r in body["requests"]] == [r1]
    assert body["counts"]["complaint"]["open"] == 1
    assert c.get("/api/chat/requests?contact=maybe").status_code == 422
    assert c.get("/api/chat/requests?status=bad").status_code == 422
    r = c.post(f"/api/chat/requests/{r1}/status", json={"status": "taken"})
    assert r.status_code == 200 and store.list_requests(category="lead")[0]["status"] == "taken"
    assert c.post("/api/chat/requests/999/status", json={"status": "done"}).status_code == 404
    assert c.post(f"/api/chat/requests/{r1}/status", json={"status": "x"}).status_code == 422


def test_viewer_cannot_change_request_status(monkeypatch):
    r1, _, _ = _seed_requests()
    r = _client(monkeypatch, Role.VIEWER).post(f"/api/chat/requests/{r1}/status", json={"status": "done"})
    assert r.status_code == 403


# --- Analitika (3-bosqich) ---------------------------------------------------

def _ts(y, mo, d, h, mi=0):
    import datetime as _dt
    return _dt.datetime(y, mo, d, h, mi, tzinfo=_dt.timezone(_dt.timedelta(hours=5))).timestamp()


def test_after_hours_rule():
    from src.services.core.chat_manager import analytics
    assert not analytics.is_after_hours(_ts(2026, 10, 26, 10))   # Dushanba 10:00
    assert analytics.is_after_hours(_ts(2026, 10, 26, 20))       # Dushanba 20:00
    assert analytics.is_after_hours(_ts(2026, 10, 25, 12))       # Yakshanba


def test_analytics_build_counts_funnel_heatmap_and_reply_speed():
    from src.services.core.chat_manager import analytics
    now = _ts(2026, 10, 27, 18)
    a = store.record_message("telegram", "1", "Logo kerak", now=_ts(2026, 10, 26, 10))
    store.record_message("telegram", "1", "Albatta", direction="out", author="operator",
                         now=_ts(2026, 10, 26, 10, 30))
    b = store.record_message("instagram", "2", "Salom", now=_ts(2026, 10, 26, 21))
    store.record_message("instagram", "2", "Qoralama", direction="out", author="ai_draft",
                         now=_ts(2026, 10, 26, 21, 1))
    store.record_message("telegram", "3", "Eski", now=now - 40 * 86400)
    lead, _ = store.upsert_request(a, "lead", "Logo", "+998901234567", now=_ts(2026, 10, 26, 11))
    store.upsert_request(b, "complaint", "Norozi", now=_ts(2026, 10, 26, 22))
    store.set_request_status(lead, "done")

    d = analytics.build(7, now=now)
    assert d["kpi"]["dialogs"] == 2
    assert d["kpi"]["leads"] == 1 and d["kpi"]["leads_open"] == 0
    assert d["kpi"]["after_hours_pct"] == 50.0
    assert d["kpi"]["ai_drafted_pct"] == 50.0
    assert [s["count"] for s in d["funnel"]] == [2, 1, 1, 1]
    assert d["funnel"][1]["lost"] == 1
    assert d["outcomes"] == {"operator": 1, "unanswered": 1, "avg_reply_min": 30.0, "complaints": 1}
    assert d["heatmap"]["cells"][0][10] == 1 and d["heatmap"]["cells"][0][21] == 1
    assert len(d["daily"]) == 7 and d["daily"][-2] == {"date": "2026-10-26", "dialogs": 2, "requests": 2}
    assert {c["channel"]: c["leads"] for c in d["channels"]} == {"telegram": 1, "instagram": 0}

    tg = analytics.build(7, "telegram", now=now)
    assert tg["kpi"]["dialogs"] == 1 and tg["outcomes"]["complaints"] == 0


def test_analytics_empty_and_validation():
    from src.services.core.chat_manager import analytics
    d = analytics.build(14)
    assert d["kpi"]["dialogs"] == 0 and d["heatmap"]["peak"] is None and d["funnel"][0]["of_previous"] == 0.0
    with pytest.raises(ValueError):
        analytics.build(5)
    with pytest.raises(ValueError):
        analytics.build(7, "whatsapp")


def test_analytics_api_and_page(monkeypatch):
    c = _client(monkeypatch)
    c.cookies.set("oisha_token", "x")
    assert "Mijozlar qachon yozadi" in c.get("/api/chat/analitika").text
    assert c.get("/api/chat/analytics?days=30").json()["days"] == 30
    assert c.get("/api/chat/analytics?days=3").status_code == 422
    assert _client(monkeypatch, None).get("/api/chat/analytics").status_code == 401


# --- Sozlamalar, bilimlar bazasi, eslatmalar (4-bosqich) ---------------------

def test_knowledge_crud_and_validation():
    a = store.add_knowledge("Logo narxlari", "Logo paketi 3 mln so'mdan")
    store.add_knowledge("Ish vaqti", "Du-Ju 9:00-19:00")
    assert [e["title"] for e in store.list_knowledge()] == ["Ish vaqti", "Logo narxlari"]
    assert store.update_knowledge(a, "Logo narxlari", "4 mln") is True
    assert store.update_knowledge(999, "x", "y") is False
    assert store.delete_knowledge(a) is True and store.delete_knowledge(a) is False
    for title, body in (("", "x"), ("x", ""), ("x" * 201, "y")):
        with pytest.raises(ValueError):
            store.add_knowledge(title, body)


def test_instructions_include_knowledge_or_handoff_note():
    settings = store.get_settings()
    assert "Bilimlar bazasi bo'sh" in build_instructions(settings, [])
    text = build_instructions(settings, [{"title": "Narx", "body": "Logo 3 mln"}])
    assert "## Narx\nLogo 3 mln" in text and all(r in text for r in GUARDRAILS)


def test_draft_reply_uses_settings_knowledge_and_history():
    from src.services.core.chat_manager import responder
    store.add_knowledge("Narx", "Logo 3 mln so'm")
    store.update_settings({"reply_length": 1})
    router = FakeRouter("Logo 3 mln so'mdan boshlanadi.")
    captured = {}

    async def generate_text(prompt, **kwargs):
        captured.update(kwargs, prompt=prompt)
        return SimpleNamespace(text="  Logo 3 mln so'mdan boshlanadi. ")

    router.generate_text = generate_text
    history = [{"author": "client", "text": "Salom"}, {"author": "operator", "text": "Assalomu alaykum"}]
    reply = asyncio.run(responder.draft_reply(router, "Logo narxi?", history))
    assert reply == "Logo 3 mln so'mdan boshlanadi."
    assert "Logo 3 mln so'm" in captured["system"] and captured["max_tokens"] == 120
    assert captured["prompt"].endswith("Mijoz: Logo narxi?\nAgent:")
    assert "Agent: Assalomu alaykum" in captured["prompt"]


def test_followups_only_when_enabled_and_capped():
    import time
    from src.services.core.chat_manager import responder
    old = time.time() - 2 * 86400
    did = store.record_message("telegram", "8", "Narx?", now=old - 60)
    store.record_message("telegram", "8", "3 mln", direction="out", author="operator", now=old)
    router = FakeRouter("Kecha narx so'ragandingiz — buyurtma beramizmi?")
    assert asyncio.run(responder.run_followups(router)) == 0  # o'chiq

    store.update_settings({"follow_ups": True})
    assert asyncio.run(responder.run_followups(router)) == 1
    last = store.get_messages(did)[-1]
    assert last["author"] == "ai_draft" and last["direction"] == "out"
    # Qoralama yuborilmagan — dialog javob kutmoqda, qayta eslatma yo'q.
    assert asyncio.run(responder.run_followups(router)) == 0

    # Operator yubordi, mijoz yana jim — ikkinchi eslatma; uchinchisi yo'q.
    store.record_message("telegram", "8", "Eslatma", direction="out", author="operator", now=old + 1)
    assert asyncio.run(responder.run_followups(router)) == 1
    store.record_message("telegram", "8", "Eslatma 2", direction="out", author="operator", now=old + 2)
    assert asyncio.run(responder.run_followups(router)) == 0
    # Mijoz javob bersa hisob nolga tushadi.
    store.record_message("telegram", "8", "Rahmat", now=old + 3)
    assert store.get_dialog(did)["followups_sent"] == 0


def test_followups_skip_operator_mode():
    import time
    from src.services.core.chat_manager import responder
    old = time.time() - 2 * 86400
    did = store.record_message("telegram", "8", "Narx?", now=old - 60)
    store.record_message("telegram", "8", "3 mln", direction="out", author="operator", now=old)
    store.set_mode(did, "operator")
    store.update_settings({"follow_ups": True})
    assert asyncio.run(responder.run_followups(FakeRouter("x"))) == 0


def test_settings_page_knowledge_and_test_api(monkeypatch):
    from src.services.core.chat_manager import responder
    c = _client(monkeypatch)
    c.cookies.set("oisha_token", "x")
    assert "Bilimlar bazasi" in c.get("/api/chat/sozlamalar").text
    r = c.post("/api/chat/knowledge", json={"title": "Narx", "body": "Logo 3 mln"})
    entry_id = r.json()["id"]
    assert c.get("/api/chat/knowledge").json()["entries"][0]["title"] == "Narx"
    assert "Logo 3 mln" in c.get("/api/chat/settings").json()["instructions"]
    assert c.put(f"/api/chat/knowledge/{entry_id}", json={"title": "Narx", "body": "4 mln"}).status_code == 200
    assert c.put("/api/chat/knowledge/999", json={"title": "a", "body": "b"}).status_code == 404
    assert c.post("/api/chat/knowledge", json={"title": " ", "body": "b"}).status_code == 422
    assert c.delete(f"/api/chat/knowledge/{entry_id}").status_code == 200

    async def fake_draft(router, message):
        return "Javob: " + message

    monkeypatch.setattr(responder, "draft_reply", fake_draft)
    assert c.post("/api/chat/test", json={"message": "Salom"}).json() == {"reply": "Javob: Salom"}


def test_viewer_cannot_edit_knowledge_or_test(monkeypatch):
    c = _client(monkeypatch, Role.VIEWER)
    assert c.post("/api/chat/knowledge", json={"title": "a", "body": "b"}).status_code == 403
    assert c.post("/api/chat/test", json={"message": "x"}).status_code == 403


def test_old_database_gets_followups_column(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE dialogs (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, "
                  "external_id TEXT NOT NULL, name TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', "
                  "mode TEXT NOT NULL DEFAULT 'ai', starred INTEGER NOT NULL DEFAULT 0, "
                  "unread INTEGER NOT NULL DEFAULT 0, last_text TEXT NOT NULL DEFAULT '', "
                  "last_direction TEXT NOT NULL DEFAULT 'in', last_at REAL NOT NULL, "
                  "extracted_at REAL NOT NULL DEFAULT 0, UNIQUE(channel, external_id))")
    monkeypatch.setenv("OISHA_CHAT_DB_PATH", str(path))
    did = store.record_message("telegram", "1", "Salom")
    assert store.get_dialog(did)["followups_sent"] == 0
