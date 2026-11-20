"""Contract and authorization checks for Oisha business MCP (no live integrations)."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rbac import Principal, Role
from src.api.routes import agency_mcp


def _app_with_principal(monkeypatch, principal):
    from src.api import security

    monkeypatch.setattr(security, "authorize_connection", lambda _connection: principal)
    app = FastAPI()
    app.include_router(agency_mcp.router)
    return TestClient(app)


def _rpc(method, params=None, rid=1):
    message = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        message["params"] = params
    return message


def _content(response):
    result = response.json()["result"]
    return json.loads(result["content"][0]["text"]), result["isError"]


def test_anonymous_request_is_denied(monkeypatch):
    client = _app_with_principal(monkeypatch, None)
    response = client.post("/api/agency-mcp", json=_rpc("tools/list"))
    assert response.status_code == 401


def test_seller_without_mcp_permission_is_denied(monkeypatch):
    user = Principal(subject="sales1", role=Role.SELLER, auth_type="session")
    client = _app_with_principal(monkeypatch, user)
    response = client.post("/api/agency-mcp", json=_rpc("tools/list"))
    assert response.status_code == 403


def test_service_token_only_lists_its_scoped_sources(monkeypatch):
    user = Principal(
        subject="readonly-ai",
        role=Role.SERVICE,
        auth_type="bearer",
        scopes=frozenset({"mcp:read", "marketing:read"}),
    )
    client = _app_with_principal(monkeypatch, user)
    response = client.post(
        "/api/agency-mcp",
        json=_rpc("tools/call", {"name": "list_business_sources", "arguments": {}}),
    )
    assert response.status_code == 200
    payload, error = _content(response)
    assert error is False
    assert [item["id"] for item in payload["sources"]] == ["marketing"]


def test_service_token_cannot_read_finance_without_scope(monkeypatch):
    user = Principal(
        subject="readonly-ai",
        role=Role.SERVICE,
        auth_type="bearer",
        scopes=frozenset({"mcp:read", "marketing:read"}),
    )
    client = _app_with_principal(monkeypatch, user)
    response = client.post(
        "/api/agency-mcp",
        json=_rpc("tools/call", {
            "name": "read_business_source",
            "arguments": {"source": "finance"},
        }),
    )
    payload, error = _content(response)
    assert error is True
    assert payload == {"error": "permission_denied"}


def test_owner_gets_readonly_tools_and_business_data(monkeypatch):
    user = Principal(subject="owner", role=Role.OWNER, auth_type="session")
    client = _app_with_principal(monkeypatch, user)

    names = [
        tool["name"]
        for tool in client.post("/api/agency-mcp", json=_rpc("tools/list"))
        .json()["result"]["tools"]
    ]
    assert names == ["list_business_sources", "read_business_source"]

    async def fake_read(source, args, principal):
        assert source == "sales_report"
        assert args["period"] == "monthly"
        assert principal.subject == "owner"
        return {"available": True, "metrics": {"leads": 25, "sales": 3}}

    monkeypatch.setattr(agency_mcp, "_read", fake_read)
    response = client.post(
        "/api/agency-mcp",
        json=_rpc("tools/call", {
            "name": "read_business_source",
            "arguments": {"source": "sales_report", "period": "monthly"},
        }),
    )
    payload, error = _content(response)
    assert not error
    assert payload["origin"] == "amocrm"
    assert payload["data"]["metrics"]["sales"] == 3


def test_unsupported_parameters_cannot_trigger_raw_fetch(monkeypatch):
    user = Principal(subject="owner", role=Role.OWNER, auth_type="session")
    client = _app_with_principal(monkeypatch, user)
    response = client.post(
        "/api/agency-mcp",
        json=_rpc("tools/call", {
            "name": "read_business_source",
            "arguments": {"source": "finance", "url": "http://127.0.0.1"},
        }),
    )
    assert response.json()["error"]["code"] == -32602


def test_internal_source_errors_do_not_leak_details(monkeypatch):
    user = Principal(subject="owner", role=Role.OWNER, auth_type="session")
    client = _app_with_principal(monkeypatch, user)

    async def broken(*args, **kwargs):
        raise RuntimeError("private database details")

    monkeypatch.setattr(agency_mcp, "_read", broken)
    response = client.post(
        "/api/agency-mcp",
        json=_rpc("tools/call", {
            "name": "read_business_source",
            "arguments": {"source": "finance"},
        }),
    )
    payload, error = _content(response)
    assert error is True
    assert payload == {"error": "source_unavailable", "source": "finance"}
    assert "private" not in response.text


def test_stateless_handshake_and_get_not_supported(monkeypatch):
    user = Principal(subject="owner", role=Role.OWNER, auth_type="session")
    client = _app_with_principal(monkeypatch, user)
    response = client.post("/api/agency-mcp", json=_rpc("initialize"))
    assert response.json()["result"]["protocolVersion"] == "2025-06-18"
    assert client.get("/api/agency-mcp").status_code == 405
