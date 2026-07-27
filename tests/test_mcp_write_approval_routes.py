import json

import pytest
from fastapi import HTTPException

from src.api.rbac import Principal, Role
from src.api.routes import telegram_mcp


class FakeTelegramClient:
    def __init__(self):
        self.sent = []

    async def send_message(self, target, text):
        self.sent.append((target, text))


def principal(role: Role, subject: str) -> Principal:
    return Principal(subject=subject, role=role, auth_type="session")


@pytest.mark.asyncio
async def test_admin_mcp_write_waits_for_owner_and_executes_once(monkeypatch):
    client = FakeTelegramClient()
    monkeypatch.setattr(telegram_mcp.app_ctx, "client", client)

    response = await telegram_mcp.send_telegram_message(
        telegram_mcp.SendMessageRequest(user_id="123", text="hello"),
        principal(Role.ADMIN, "admin-1"),
    )
    body = json.loads(response.body)

    assert response.status_code == 202
    assert body["status"] == "approval_required"
    assert client.sent == []

    result = await telegram_mcp.execute_write_approval(
        body["ticket_id"],
        principal(Role.OWNER, "owner-1"),
    )
    assert result["status"] == "success"
    assert client.sent == [(123, "hello")]

    with pytest.raises(HTTPException) as exc_info:
        await telegram_mcp.execute_write_approval(
            body["ticket_id"],
            principal(Role.OWNER, "owner-1"),
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_owner_mcp_write_executes_directly(monkeypatch):
    client = FakeTelegramClient()
    monkeypatch.setattr(telegram_mcp.app_ctx, "client", client)

    result = await telegram_mcp.send_telegram_message(
        telegram_mcp.SendMessageRequest(user_id="room", text="direct"),
        principal(Role.OWNER, "owner-1"),
    )

    assert result == {"status": "success", "user_id": "room"}
    assert client.sent == [("room", "direct")]


@pytest.mark.asyncio
async def test_non_owner_cannot_execute_approval(monkeypatch):
    client = FakeTelegramClient()
    monkeypatch.setattr(telegram_mcp.app_ctx, "client", client)

    response = await telegram_mcp.send_telegram_message(
        telegram_mcp.SendMessageRequest(user_id="123", text="hello"),
        principal(Role.ADMIN, "admin-1"),
    )
    ticket_id = json.loads(response.body)["ticket_id"]

    with pytest.raises(HTTPException) as exc_info:
        await telegram_mcp.execute_write_approval(
            ticket_id,
            principal(Role.ADMIN, "admin-1"),
        )
    assert exc_info.value.status_code == 403
    assert client.sent == []
