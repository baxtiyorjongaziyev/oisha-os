from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import api_server


class _Cursor:
    async def fetchone(self):
        return (1,)


class _Database:
    async def get_connection(self):
        return SimpleNamespace(execute=lambda _query: _Cursor())

    def get_backend_name(self):
        return "turso"


@pytest.mark.asyncio
async def test_readiness_requires_userbot_and_amocrm(monkeypatch):
    monkeypatch.setattr(api_server, "db_instance", _Database())
    monkeypatch.setattr(api_server, "user_client", None)
    monkeypatch.setattr(
        api_server,
        "_get_amocrm_instance",
        lambda: SimpleNamespace(check_connection=AsyncMock(return_value=True), last_error=None),
    )

    response = await api_server.production_readiness_probe()

    assert response.status_code == 503
    assert b"userbot_unauthorized" in response.body


@pytest.mark.asyncio
async def test_readiness_passes_critical_dependencies(monkeypatch):
    monkeypatch.setattr(api_server, "db_instance", _Database())
    monkeypatch.setattr(
        api_server,
        "user_client",
        SimpleNamespace(is_user_authorized=AsyncMock(return_value=True)),
    )
    monkeypatch.setattr(
        api_server,
        "_get_amocrm_instance",
        lambda: SimpleNamespace(check_connection=AsyncMock(return_value=True), last_error=None),
    )

    response = await api_server.production_readiness_probe()

    assert response.status_code == 200
    assert b'"status":"ready"' in response.body
