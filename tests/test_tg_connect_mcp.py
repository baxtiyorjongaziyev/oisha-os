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
    assert {t["name"] for t in tools} == {"list_chats", "read_chat", "search_chat"}
    assert all(t["annotations"]["readOnlyHint"] for t in tools)
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
    assert call(db, "send_message", {"chat_id": 1})[0] is True
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
