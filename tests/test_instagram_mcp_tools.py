from __future__ import annotations

import json

import pytest

import scripts.mcp_server as mcp_server


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


@pytest.mark.asyncio
async def test_mcp_lists_read_only_instagram_tools():
    tools = await mcp_server.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "get_instagram_profile",
        "list_instagram_recent_media",
        "get_instagram_latest_post",
    } <= names


@pytest.mark.asyncio
async def test_mcp_profile_and_latest_post(monkeypatch):
    monkeypatch.setattr(mcp_server, "instagram", _Instagram())

    profile_content = await mcp_server.call_tool("get_instagram_profile", {})
    latest_content = await mcp_server.call_tool("get_instagram_latest_post", {})
    profile = json.loads(profile_content[0].text)
    latest = json.loads(latest_content[0].text)

    assert profile["username"] == "baxtiyorjongaziyev"
    assert latest["latest_post"]["id"] == "latest"
    assert latest["latest_post"]["timestamp"] == "2026-07-20T09:00:00+0000"
    assert latest["checked_count"] == 2

