from __future__ import annotations

import json

import pytest

import scripts.oisha_mcp_server as mcp_server


class _Instagram:
    def get_profile(self):
        return {
            "ok": True,
            "id": "ig_123",
            "username": "baxtiyorjongaziyev",
        }

    def list_media(self, limit=10):
        assert 1 <= limit <= 25
        return {
            "ok": True,
            "data": [
                {
                    "id": "older",
                    "username": "baxtiyorjongaziyev",
                    "timestamp": "2026-07-01T09:00:00+0000",
                },
                {
                    "id": "latest",
                    "username": "baxtiyorjongaziyev",
                    "timestamp": "2026-07-20T09:00:00+0000",
                    "permalink": "https://instagram.com/p/latest",
                },
            ],
        }


@pytest.fixture
def stub_instagram(monkeypatch):
    """Instagram klientini kesh orqali almashtiramiz.

    Servislar `_services` keshida kech yaratiladi, shuning uchun tayyor
    obyektni to'g'ridan-to'g'ri keshga qo'yish tarmoqqa chiqishni oldini oladi.
    """
    monkeypatch.setitem(mcp_server._services, "instagram", _Instagram())
    return mcp_server._services["instagram"]


@pytest.mark.asyncio
async def test_mcp_lists_read_only_instagram_tools():
    tools = await mcp_server.mcp.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "get_instagram_profile",
        "list_instagram_recent_media",
        "get_instagram_latest_post",
    } <= names


@pytest.mark.asyncio
async def test_mcp_exposes_telegram_and_crm_tools_from_one_server():
    """Telegram va CRM toollari bitta serverda bo'lishi kerak.

    Ilgari ular alohida MCP serverlarda edi (`telegram` va `oisha-amocrm`);
    birlashtirishdan keyin yagona `oisha` serveri ikkalasini ham beradi.
    """
    names = {tool.name for tool in await mcp_server.mcp.list_tools()}

    assert {"get_recent_dialogs", "get_chat_history", "send_telegram_message"} <= names
    assert {"check_amo_auth", "get_sales_report", "get_airtable_projects"} <= names


@pytest.mark.asyncio
async def test_mcp_profile_and_latest_post(stub_instagram):
    profile = json.loads(await mcp_server.get_instagram_profile())
    latest = json.loads(await mcp_server.get_instagram_latest_post())

    assert profile["username"] == "baxtiyorjongaziyev"
    assert latest["latest_post"]["id"] == "latest"
    assert latest["latest_post"]["timestamp"] == "2026-07-20T09:00:00+0000"
    assert latest["checked_count"] == 2


def test_api_request_sets_bearer_auth_from_internal_secret(monkeypatch):
    """Internal MCP request route guard va RBAC'dan birga o'tadi.

    Secret ikki headerda yuboriladi: Bearer RBAC uchun, internal header esa
    endpointning alohida route guard'i uchun.
    """
    monkeypatch.delenv("OISHA_API_USER", raising=False)
    monkeypatch.delenv("OISHA_API_PASS", raising=False)
    monkeypatch.setenv("OISHA_API_SECRET", "internal-secret")

    request = mcp_server._api_request("http://127.0.0.1:8080/api/internal/mcp/dialogs")

    assert request.headers["Authorization"] == "Bearer internal-secret"
    assert request.headers.get("X-oisha-internal-secret") == "internal-secret"


def test_api_request_prefers_bearer_auth_when_secret_exists(monkeypatch):
    monkeypatch.setenv("OISHA_API_USER", "oisha")
    monkeypatch.setenv("OISHA_API_PASS", "from-env")
    monkeypatch.setenv("OISHA_API_SECRET", "internal-secret")

    request = mcp_server._api_request("http://127.0.0.1:8080/api/internal/mcp/dialogs")

    assert request.headers["Authorization"] == "Bearer internal-secret"


def test_api_request_uses_basic_only_when_internal_secret_is_missing(monkeypatch):
    monkeypatch.setenv("OISHA_API_USER", "oisha")
    monkeypatch.setenv("OISHA_API_PASS", "from-env")
    monkeypatch.delenv("OISHA_API_SECRET", raising=False)

    request = mcp_server._api_request("http://127.0.0.1:8080/healthz")

    assert request.headers["Authorization"].startswith("Basic ")
    assert "X-oisha-internal-secret" not in request.headers
