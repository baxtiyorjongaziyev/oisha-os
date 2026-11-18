"""Oisha Connect: store, QR oqimi, uzish va API himoyalari (sintetik maʼlumot)."""
from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Principal, Role
from src.services.core.tg_connect import qr_flow, session_ops, store

TG = 111222333


class FakeDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    async def execute(self, query, params=None):
        cur = self.conn.execute(query, params or [])
        return [dict(r) for r in cur.fetchall()]

    async def commit(self):
        self.conn.commit()


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setenv(store.KEY_ENV, Fernet.generate_key().decode())
    d = FakeDB()
    asyncio.run(store.init_tables(d))
    return d


def run(coro):
    return asyncio.run(coro)


def test_session_encrypted_and_bound_to_owner(db):
    run(store.save_connected(db, TG, 5, "mgr", "SESSION-XYZ"))
    acc = run(store.account(db, TG))
    assert acc["session_enc"].startswith("enc:") and "SESSION-XYZ" not in acc["session_enc"]
    assert store.decrypt_session(TG, acc["session_enc"]) == "SESSION-XYZ"
    with pytest.raises(Exception):
        store.decrypt_session(TG + 1, acc["session_enc"])


def test_chats_closed_by_default_and_selection_survives_refresh(db):
    run(store.save_connected(db, TG, 5, None, "S"))
    run(store.replace_chats(db, TG, [{"id": 1, "title": "Mijoz A", "kind": "private"},
                                     {"id": 2, "title": "Oila", "kind": "group"}]))
    assert not any(c["allowed"] for c in run(store.chats(db, TG)))
    assert run(store.set_allowed(db, TG, [1, 999])) == 1  # begona ID eʼtiborsiz
    run(store.replace_chats(db, TG, [{"id": 1, "title": "Mijoz A", "kind": "private"},
                                     {"id": 3, "title": "Yangi", "kind": "group"}]))
    allowed = {c["id"] for c in run(store.chats(db, TG)) if c["allowed"]}
    assert allowed == {1}


def test_mcp_token_hashed_and_cleared_on_revoke(db):
    run(store.save_connected(db, TG, 5, None, "S"))
    token = run(store.issue_mcp_token(db, TG))
    assert run(store.account_by_mcp_token(db, token))["telegram_id"] == TG
    run(store.mark_revoked(db, TG))
    assert run(store.account_by_mcp_token(db, token)) is None
    assert run(store.account(db, TG))["session_enc"] is None


class FakeQR:
    url = "tg://login?token=abc"

    def __init__(self, outcome):
        self.outcome = outcome

    async def wait(self, timeout=None):
        if isinstance(self.outcome, BaseException):
            raise self.outcome

    async def recreate(self):
        pass


class SessionPasswordNeededError(Exception):
    pass


class FakeClient:
    def __init__(self, me_id, outcome=None):
        self.me_id, self.outcome = me_id, outcome
        self.logged_out = False
        self.session = SimpleNamespace(save=lambda: "NEW-SESSION")

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def qr_login(self):
        return FakeQR(self.outcome)

    async def get_me(self):
        return SimpleNamespace(id=self.me_id, username="mgr")

    async def sign_in(self, password=None):
        if password != "right":
            raise ValueError("bad")

    async def log_out(self):
        self.logged_out = True
        return True


async def _drive(client):
    saved = {}

    async def on_done(tg, result):
        saved.update(result)

    att = await qr_flow.start(TG, on_done, factory=lambda: client)
    await att.task
    return att, saved


def test_qr_success_saves_session():
    att, saved = run(_drive(FakeClient(TG)))
    assert att.state == "done" and saved["session"] == "NEW-SESSION"
    assert "qr_url" not in qr_flow.public_view(att)


def test_qr_wrong_account_is_logged_out_and_not_saved():
    client = FakeClient(999)
    att, saved = run(_drive(client))
    assert att.state == "wrong_account" and client.logged_out and saved == {}


def test_qr_2fa_password_not_stored():
    async def scenario():
        client = FakeClient(TG, SessionPasswordNeededError())
        saved = {}

        async def on_done(tg, result):
            saved.update(result)

        att = await qr_flow.start(TG, on_done, factory=lambda: client)
        await att.task
        assert att.state == "password_required"
        assert await qr_flow.submit_password(TG, "wrong", on_done) == "bad_password"
        assert await qr_flow.submit_password(TG, "right", on_done) == "done"
        return att, saved

    att, saved = run(scenario())
    assert saved["session"] == "NEW-SESSION"
    assert "right" not in repr(att.__dict__)


def test_revoke_logs_out_remotely_and_wipes(db):
    run(store.save_connected(db, TG, 5, None, "S"))
    client = FakeClient(TG)
    assert run(session_ops.revoke(db, TG, str(TG), factory=lambda s: client)) == {"telegram_logout": True}
    assert client.logged_out
    assert run(store.account(db, TG))["status"] == "revoked"
    assert run(store.audit_log(db, TG))[0]["action"] == "revoked"
    assert run(session_ops.revoke(db, TG, str(TG), factory=lambda s: client)) is None


def _app(monkeypatch, db, principal):
    from src.api import security
    from src.api.routes import tg_connect_routes as routes

    monkeypatch.setattr(security, "authorize_connection", lambda conn: principal)
    monkeypatch.setattr(routes, "_db", lambda: db)
    monkeypatch.setattr(routes, "_schema_ready", True)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_api_requires_employee_and_never_returns_session(monkeypatch, db):
    seller = Principal(subject=str(TG), role=Role.SELLER, auth_type="telegram")
    client = _app(monkeypatch, db, seller)
    assert client.get("/api/connect/status").status_code == 403  # employees jadvali yoʻq

    db.conn.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, telegram_id INTEGER, is_active INTEGER)")
    db.conn.execute("INSERT INTO employees VALUES (5, ?, 1)", [TG])
    run(store.save_connected(db, TG, 5, "mgr", "SECRET-SESSION"))
    res = client.get("/api/connect/status")
    assert res.status_code == 200 and res.json()["connected"] is True
    assert "SECRET" not in res.text and "enc:" not in res.text


def test_api_rejects_non_telegram_principal(monkeypatch, db):
    p = Principal(subject="api-key-1", role=Role.ADMIN, auth_type="api_key")
    assert _app(monkeypatch, db, p).get("/api/connect/status").status_code == 403


def test_revoke_disconnects_client_when_logout_fails(db):
    run(store.save_connected(db, TG, 5, None, "S"))

    class Failing(FakeClient):
        disconnected = False

        async def log_out(self):
            raise ConnectionError("down")

        async def disconnect(self):
            Failing.disconnected = True

    client = Failing(TG)
    assert run(session_ops.revoke(db, TG, str(TG), factory=lambda s: client)) == {"telegram_logout": False}
    assert Failing.disconnected
    assert run(store.audit_log(db, TG))[0]["detail"] == {"telegram_logout": False}


def test_abandoned_2fa_attempt_is_closed_after_ttl(monkeypatch):
    monkeypatch.setattr(qr_flow, "ATTEMPT_TTL_S", 0.05)

    class Tracking(FakeClient):
        async def disconnect(self):
            self.closed = True

    async def scenario():
        client = Tracking(TG, SessionPasswordNeededError())

        async def on_done(tg, result):
            pass

        att = await qr_flow.start(TG, on_done, factory=lambda: client)
        await att.task
        await asyncio.sleep(0.2)
        return att, client

    att, client = run(scenario())
    assert att.state == "expired" and getattr(client, "closed", False)


def test_connect_page_is_served_under_api_prefix():
    from src.api.routes import tg_connect_routes as routes
    from src.services.api_server.oauth import _safe_login_next

    paths = {r.path for r in routes.pages_router.routes}
    assert paths == {"/api/connect/app", "/api/connect/app/connect.js"}
    assert _safe_login_next("/api/connect/app") == "/api/connect/app"


def test_refresh_never_reverts_saved_selection(db):
    run(store.save_connected(db, TG, 5, None, "S"))
    run(store.replace_chats(db, TG, [{"id": 1, "title": "A", "kind": "private"}]))
    run(store.set_allowed(db, TG, [1]))
    run(store.set_allowed(db, TG, []))  # menejer opt-out qildi
    run(store.replace_chats(db, TG, [{"id": 1, "title": "A2", "kind": "private"}]))
    assert run(store.chats(db, TG)) == [{"id": 1, "title": "A2", "kind": "private", "allowed": False}]
