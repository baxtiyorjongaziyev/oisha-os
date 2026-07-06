from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import api_server
from src.api.routes.state import api_state


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
    monkeypatch.setattr(api_state, "db_instance", _Database())
    monkeypatch.setattr(api_state, "user_client", None)
    # userbot_unauthorized is exempt when runtime_source=="vm_service" (Oracle
    # VM re-auth is treated as non-fatal there). This test is about the
    # generic unauthorized-userbot path, not runtime detection, so pin a
    # non-exempt runtime explicitly — CI runners set SYSTEMD_EXEC_PID, which
    # would otherwise make detect_runtime_source() resolve to "vm_service"
    # and silently suppress the very problem this test asserts on.
    from src.services.core.agent_runtime import set_runtime_context

    set_runtime_context(runtime_source="cloud_run")

    response = await api_server.production_readiness_probe()

    assert response.status_code == 503
    assert b"userbot_unauthorized" in response.body


@pytest.mark.asyncio
async def test_readiness_passes_critical_dependencies(monkeypatch):
    monkeypatch.setattr(api_state, "db_instance", _Database())
    monkeypatch.setattr(
        api_state,
        "user_client",
        SimpleNamespace(is_user_authorized=AsyncMock(return_value=True)),
    )

    mock_amocrm = SimpleNamespace(check_connection=AsyncMock(return_value=True), last_error=None)
    monkeypatch.setattr(
        "src.api.routes.amocrm_integration._get_amocrm_instance",
        lambda: mock_amocrm,
    )

    response = await api_server.production_readiness_probe()

    assert response.status_code == 200
    assert b'"status":"ready"' in response.body
