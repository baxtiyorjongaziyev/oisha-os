"""/connect bot buyrugʻi: holat, uzish tasdigʻi, faqat oʻz akkaunti (sintetik maʼlumot)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.services.core.dispatcher import handlers_connect as hc
from src.services.core.tg_connect import session_ops, store
from tests.test_tg_connect import TG, FakeDB  # noqa: F401 - db fixture qayta ishlatiladi
from tests.test_tg_connect import db  # noqa: F401


class Msg:
    def __init__(self, text, uid=TG, chat="private"):
        self.text, self.chat = text, SimpleNamespace(type=chat)
        self.from_user = SimpleNamespace(id=uid, username="mgr")
        self.sent = []

    async def answer(self, text, **kw):
        self.sent.append((text, kw))

    async def edit_text(self, text, **kw):
        self.sent.append((text, kw))


@pytest.fixture
def employee(db, monkeypatch):  # noqa: F811
    db.conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, telegram_id INTEGER, is_active INTEGER)")
    db.conn.execute("INSERT INTO employees VALUES (5, ?, 1)", [TG])
    monkeypatch.setattr(hc, "_markup", lambda b: b)
    return db


def run(c):
    return asyncio.run(c)


def test_group_chat_ignored(employee):
    m = Msg("/connect", chat="group")
    run(hc.handle_connect(m, db=employee))
    assert m.sent == []


def test_non_employee_refused(db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(hc, "_markup", lambda b: b)
    m = Msg("/connect", uid=42)
    run(hc.handle_connect(m, db=db))
    assert m.sent[0][0] == hc.NOT_EMPLOYEE


def test_not_connected_shows_guarantees_and_page_button(employee):
    m = Msg("/connect")
    run(hc.handle_connect(m, db=employee))
    text, kw = m.sent[0]
    assert "Kafolatlar" in text
    assert kw["reply_markup"]["inline_keyboard"][0][0]["url"] == hc.connect_url()


def test_connected_status_counts_allowed_chats(employee):
    run(store.save_connected(employee, TG, 5, "mgr", "S"))
    run(store.replace_chats(employee, TG, [{"id": 1, "title": "A", "kind": "private"},
                                           {"id": 2, "title": "B", "kind": "group"}]))
    run(store.set_allowed(employee, TG, [2]))
    m = Msg("/connect")
    run(hc.handle_connect(m, db=employee))
    assert "ulangan" in m.sent[0][0] and "<b>1</b>" in m.sent[0][0]


def test_off_asks_confirmation_then_revokes(employee, monkeypatch):
    run(store.save_connected(employee, TG, 5, "mgr", "S"))
    m = Msg("/connect off")
    run(hc.handle_connect(m, db=employee))
    assert m.sent[0][1]["reply_markup"] == hc.revoke_buttons()
    assert run(store.account(employee, TG))["status"] == "connected"  # hali uzilmagan

    calls = []

    async def fake_revoke(db, tg, actor, ip=None, factory=None):
        calls.append((tg, actor))
        return True

    monkeypatch.setattr(session_ops, "revoke", fake_revoke)
    msg = Msg("")
    cb = SimpleNamespace(data=hc.CB_REVOKE, from_user=SimpleNamespace(id=TG), message=msg,
                         answer=lambda *a, **k: asyncio.sleep(0))
    run(hc.handle_revoke_callback(cb, db=employee))
    assert calls == [(TG, f"bot:{TG}")] and "uzildi" in msg.sent[0][0]


def test_cancel_keeps_connection(employee):
    run(store.save_connected(employee, TG, 5, "mgr", "S"))
    msg = Msg("")
    cb = SimpleNamespace(data=hc.CB_CANCEL, from_user=SimpleNamespace(id=TG), message=msg,
                         answer=lambda *a, **k: asyncio.sleep(0))
    run(hc.handle_revoke_callback(cb, db=employee))
    assert run(store.account(employee, TG))["status"] == "connected"
