import json
from unittest.mock import AsyncMock

import pytest

from src import api_server


def _healthy_dependency(name: str) -> dict:
    return {
        "ok": True,
        "name": name,
        "reason": "verified",
        "checked_at": "2026-06-13T10:00:00+05:00",
    }


@pytest.mark.asyncio
async def test_erp_readiness_reports_every_required_dependency(monkeypatch):
    dependencies = {
        name: _healthy_dependency(name)
        for name in api_server.ERP_REQUIRED_DEPENDENCIES
    }
    monkeypatch.setattr(
        api_server,
        "_collect_erp_dependencies",
        AsyncMock(return_value=dependencies),
    )

    result = await api_server.build_erp_readiness()

    assert result["ready"] is True
    assert result["autonomy_level"] == "A2"
    assert result["blockers"] == []
    assert set(result["dependencies"]) == set(api_server.ERP_REQUIRED_DEPENDENCIES)


@pytest.mark.asyncio
async def test_erp_readiness_blocks_autonomy_when_real_source_is_unavailable(
    monkeypatch,
):
    dependencies = {
        name: _healthy_dependency(name)
        for name in api_server.ERP_REQUIRED_DEPENDENCIES
    }
    dependencies["amocrm"] = {
        "ok": False,
        "name": "amocrm",
        "reason": "oauth_expired",
        "checked_at": "2026-06-13T10:00:00+05:00",
    }
    dependencies["calendar"] = {
        "ok": False,
        "name": "calendar",
        "reason": "credentials_missing",
        "checked_at": "2026-06-13T10:00:00+05:00",
    }
    monkeypatch.setattr(
        api_server,
        "_collect_erp_dependencies",
        AsyncMock(return_value=dependencies),
    )

    result = await api_server.build_erp_readiness()

    assert result["ready"] is False
    assert result["autonomy_level"] == "A0"
    assert result["blockers"] == [
        "amocrm:oauth_expired",
        "calendar:credentials_missing",
    ]


@pytest.mark.asyncio
async def test_erp_readiness_endpoint_returns_503_until_dependencies_are_verified(
    monkeypatch,
):
    monkeypatch.setattr(
        api_server,
        "build_erp_readiness",
        AsyncMock(
            return_value={
                "ready": False,
                "autonomy_level": "A0",
                "dependencies": {},
                "blockers": ["telegram_userbot:unauthorized"],
                "checked_at": "2026-06-13T10:00:00+05:00",
            }
        ),
    )

    response = await api_server.erp_readiness_probe()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload["ready"] is False
    assert payload["blockers"] == ["telegram_userbot:unauthorized"]
