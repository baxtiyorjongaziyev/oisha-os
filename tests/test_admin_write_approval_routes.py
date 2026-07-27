import json

import pytest
from fastapi import HTTPException

from src.api import admin
from src.api.rbac import Principal, Role


class FakeAdminBot:
    def __init__(self):
        self.briefings = 0

    async def run_auto_briefing(self):
        self.briefings += 1


def principal(role: Role, subject: str) -> Principal:
    return Principal(subject=subject, role=role, auth_type="session")


@pytest.mark.asyncio
async def test_admin_briefing_waits_for_owner(monkeypatch):
    bot = FakeAdminBot()
    monkeypatch.setattr(admin, "_get_admin_bot", lambda: bot)

    response = await admin.execute_admin_action(
        "send_briefing",
        principal=principal(Role.ADMIN, "admin-1"),
    )
    body = json.loads(response.body)

    assert response.status_code == 202
    assert body["status"] == "approval_required"
    assert bot.briefings == 0

    result = await admin.execute_admin_write_approval(
        body["ticket_id"],
        principal(Role.OWNER, "owner-1"),
    )
    assert result["status"] == "success"
    assert bot.briefings == 1


@pytest.mark.asyncio
async def test_owner_briefing_executes_directly(monkeypatch):
    bot = FakeAdminBot()
    monkeypatch.setattr(admin, "_get_admin_bot", lambda: bot)

    result = await admin.execute_admin_action(
        "send_briefing",
        principal=principal(Role.OWNER, "owner-1"),
    )

    assert result["status"] == "success"
    assert bot.briefings == 1


@pytest.mark.asyncio
async def test_admin_cannot_execute_approval(monkeypatch):
    bot = FakeAdminBot()
    monkeypatch.setattr(admin, "_get_admin_bot", lambda: bot)

    response = await admin.execute_admin_action(
        "send_briefing",
        principal=principal(Role.ADMIN, "admin-1"),
    )
    ticket_id = json.loads(response.body)["ticket_id"]

    with pytest.raises(HTTPException) as exc_info:
        await admin.execute_admin_write_approval(
            ticket_id,
            principal(Role.ADMIN, "admin-1"),
        )
    assert exc_info.value.status_code == 403
    assert bot.briefings == 0
