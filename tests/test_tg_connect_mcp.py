"""Oisha Connect MCP: faqat ruxsat berilgan chatlar, faqat oʻqish, kalit tekshiruvi (sintetik maʼlumot)."""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.core.tg_connect import mcp_server, store
from tests.test_tg_connect import TG, db  # noqa: F401 - db fixture


def run(c):
    return asyncio.run(c)


def _setup(db):  # noqa: F811
    run(store.save_connected(db, TG, 5, "mgr", "SESSION"))
    run(store.replace_chats(db, TG, [{"id": 1, "title": "Mijoz A", "kind": "private"},
                                     {"id": 2, "title": "Oila", "kind": "group"}]))
    run(store.set_allowed(db, TG, [1]))


async def fake_reader(session, chat_id, limit=30, query=None):
    assert session == "SESSION"
    return [{"id": 9, "date": None, "from": "Ali", "text": f"salom {chat_id} {query or ''}"}]


def call(db, name, args=None):  # noqa: F811
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}
    res = run(mcp_server.handle(db, TG, msg, reader=fake_reader))["result"]
    return res["isError"], json.loads(res["content"][0]["text"])


def test_initialize_and_tools_are_read_only(db):  # noqa: F811
    init = run(mcp_server.handle(db, TG, {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}}))
    assert init["result"]["capabilities"] == {"tools": {"listChanged": False}}
    tools = run(mcp_server.handle(db, TG, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"list_chats", "read_chat", "search_chat", "send_message", "edit_message", "delete_messages",
            "forward_messages", "send_file", "get_action_status"} == names
    ro = {t["name"] for t in tools if t["annotations"]["readOnlyHint"]}
    assert ro == {"list_chats", "read_chat", "search_chat", "get_action_status"}
    assert run(mcp_server.handle(db, TG, {"jsonrpc": "2.0", "method": "notifications/initialized"})) is None


def test_only_allowed_chats_are_listed_and_readable(db):  # noqa: F811
    _setup(db)
    err, chats = call(db, "list_chats")
    assert not err and [c["id"] for c in chats] == [1]
    err, data = call(db, "read_chat", {"chat_id": 1})
    assert not err and data["messages"][0]["from"] == "Ali"
    err, data = call(db, "read_chat", {"chat_id": 2})
    assert err and "not allowed" in data["error"]
    err, data = call(db, "search_chat", {"chat_id": 1, "query": "narx"})
    assert not err and "narx" in data["messages"][0]["text"]
    actions = [e["action"] for e in run(store.audit_log(db, TG))]
    assert {"mcp_list_chats", "mcp_read_chat", "mcp_search_chat"} <= set(actions)


def test_unknown_tool_and_method(db):  # noqa: F811
    _setup(db)
    assert call(db, "send_message", {"chat_id": 1})[0] is True  # text yoʻq
    assert call(db, "launch_rockets", {})[0] is True
    res = run(mcp_server.handle(db, TG, {"jsonrpc": "2.0", "id": 3, "method": "resources/list"}))
    assert res["error"]["code"] == -32601


def test_http_endpoint_token_header_and_path(monkeypatch, db):  # noqa: F811
    from src.api.routes import tg_connect_mcp, tg_connect_routes

    _setup(db)
    token = run(store.issue_mcp_token(db, TG))

    async def ready():
        return db

    monkeypatch.setattr(tg_connect_mcp, "_ready_db", ready)
    monkeypatch.setattr(tg_connect_routes, "_ready_db", ready)
    app = FastAPI()
    app.include_router(tg_connect_mcp.router)
    c = TestClient(app)
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert c.post("/api/connect/mcp", json=body).status_code == 401
    assert c.post("/api/connect/mcp/oc_wrong", json=body).status_code == 401
    assert c.post("/api/connect/mcp", json=body, headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert c.post(f"/api/connect/mcp/{token}", json=body).json()["result"]["tools"]
    # yangi kalit eskisini bekor qiladi
    run(store.issue_mcp_token(db, TG))
    assert c.post(f"/api/connect/mcp/{token}", json=body).status_code == 401


class Spy:
    def __init__(self):
        self.executed, self.notified = [], []

    async def executor(self, session, kind, payload):
        self.executed.append((session, kind, payload))
        return {"message_id": 77}

    async def notify(self, tg, action_id, text):
        self.notified.append((tg, action_id, text))
        return True


def wcall(db, spy, name, args):  # noqa: F811
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
    res = run(mcp_server.handle(db, TG, msg, reader=fake_reader, notify=spy.notify,
                                executor=spy.executor))["result"]
    return res["isError"], json.loads(res["content"][0]["text"])


def test_write_needs_approval_then_owner_executes(db):  # noqa: F811
    from src.services.core.tg_connect import actions

    _setup(db)
    spy = Spy()
    err, data = wcall(db, spy, "send_message", {"chat_id": 1, "text": "Narx 5 mln"})
    assert not err and data["state"] == "pending_approval" and spy.executed == []
    assert "Narx 5 mln" in spy.notified[0][2]
    aid = data["action_id"]
    assert run(actions.decide(db, TG + 1, aid, True, executor=spy.executor))["state"] == "not_pending"
    assert spy.executed == []  # begona odam tasdiqlay olmaydi
    assert run(actions.decide(db, TG, aid, True, executor=spy.executor))["state"] == "done"
    assert spy.executed[0][1:] == ("send_message", {"chat_id": 1, "text": "Narx 5 mln"})
    assert run(actions.decide(db, TG, aid, True, executor=spy.executor))["state"] == "not_pending"
    assert wcall(db, spy, "get_action_status", {"action_id": aid})[1]["state"] == "done"


def test_reject_never_executes(db):  # noqa: F811
    from src.services.core.tg_connect import actions

    _setup(db)
    spy = Spy()
    aid = wcall(db, spy, "delete_messages", {"chat_id": 1, "message_ids": [5]})[1]["action_id"]
    assert run(actions.decide(db, TG, aid, False, executor=spy.executor))["state"] == "rejected"
    assert spy.executed == []


def test_autonomous_chat_executes_immediately(db):  # noqa: F811
    _setup(db)
    run(store.set_autonomous(db, TG, [1]))
    spy = Spy()
    err, data = wcall(db, spy, "send_message", {"chat_id": 1, "text": "ok"})
    assert not err and data["state"] == "done" and spy.notified == []


def test_forward_needs_both_chats_autonomous(db):  # noqa: F811
    _setup(db)
    run(store.set_allowed(db, TG, [1, 2]))
    run(store.set_autonomous(db, TG, [1]))
    spy = Spy()
    data = wcall(db, spy, "forward_messages", {"from_chat_id": 1, "to_chat_id": 2, "message_ids": [3]})[1]
    assert data["state"] == "pending_approval"


def test_write_to_closed_chat_refused_and_all_chats_toggle(db):  # noqa: F811
    _setup(db)
    spy = Spy()
    err, data = wcall(db, spy, "send_message", {"chat_id": 2, "text": "x"})
    assert err and "not allowed" in data["error"]
    run(store.set_all_chats(db, TG, True))
    assert sorted(c["id"] for c in call(db, "list_chats")[1]) == [1, 2]
    assert not call(db, "read_chat", {"chat_id": 999})[0]  # roʻyxatda yoʻq chat ham
    assert wcall(db, spy, "send_message", {"chat_id": 2, "text": "x"})[1]["state"] == "pending_approval"


def test_send_file_requires_https(db):  # noqa: F811
    _setup(db)
    spy = Spy()
    err, data = wcall(db, spy, "send_file", {"chat_id": 1, "file_url": "http://x/a.pdf"})
    assert err and "https" in data["error"]
