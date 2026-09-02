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
    monkeypatch.setattr("src.api.routes.amocrm_integration._get_amocrm_instance", lambda: None)
    # A dead userbot session (e.g. AUTH_KEY_DUPLICATED) is a soft dependency by
    # default: Oisha keeps serving on the bot-token path, so /readyz reports it
    # as "degraded" (still 200) rather than failing the whole deploy gate.
    # Pin a non-exempt-from-detection runtime explicitly — CI runners set
    # SYSTEMD_EXEC_PID, which would otherwise make detect_runtime_source()
    # resolve to "vm_service" on its own.
    from src.services.core.agent_runtime import set_runtime_context

    set_runtime_context(runtime_source="cloud_run")

    response = await api_server.production_readiness_probe()

    assert response.status_code == 200
    body = response.body.decode()
    assert '"status":"degraded"' in body
    assert "userbot_unauthorized" in body
    # AmoCRM is unmocked here too, so it degrades alongside the userbot.
    assert '"degraded":["userbot_unauthorized","amocrm_unavailable"]' in body
    assert '"blocking":[]' in body


@pytest.mark.asyncio
async def test_readiness_strict_mode_still_blocks_on_userbot(monkeypatch):
    """READYZ_STRICT_DEPS=1 restores the old all-or-nothing gate."""
    monkeypatch.setenv("READYZ_STRICT_DEPS", "1")
    monkeypatch.setattr(api_state, "db_instance", _Database())
    monkeypatch.setattr(api_state, "user_client", None)
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

    from src.services.core.agent_runtime import set_runtime_context

    set_runtime_context(runtime_source="cloud_run", userbot_authorized=False)

    response = await api_server.production_readiness_probe()

    assert response.status_code == 200
    assert b'"status":"ready"' in response.body


@pytest.mark.asyncio
async def test_readiness_rejects_missing_database_even_on_vm(monkeypatch):
    monkeypatch.setattr(api_state, "db_instance", None)
    monkeypatch.setattr(api_state, "user_client", None)
    mock_amocrm = SimpleNamespace(
        check_connection=AsyncMock(return_value=True),
        last_error=None,
    )
    monkeypatch.setattr(
        "src.api.routes.amocrm_integration._get_amocrm_instance",
        lambda: mock_amocrm,
    )
    from src.services.core.agent_runtime import set_runtime_context

    set_runtime_context(runtime_source="vm_service")
    response = await api_server.production_readiness_probe()

    assert response.status_code == 503
    assert b"database_not_initialized" in response.body


@pytest.mark.asyncio
async def test_readiness_uses_cached_userbot_state_on_vm_service(monkeypatch):
    monkeypatch.setattr(api_state, "db_instance", _Database())
    user_client = SimpleNamespace(is_user_authorized=AsyncMock(return_value=True))
    monkeypatch.setattr(api_state, "user_client", user_client)

    mock_amocrm = SimpleNamespace(check_connection=AsyncMock(return_value=True), last_error=None)
    monkeypatch.setattr(
        "src.api.routes.amocrm_integration._get_amocrm_instance",
        lambda: mock_amocrm,
    )

    from src.services.core.agent_runtime import set_runtime_context

    set_runtime_context(runtime_source="vm_service", userbot_authorized=True)

    response = await api_server.production_readiness_probe()

    assert response.status_code == 200
    assert b'"userbot":"authorized"' in response.body
    user_client.is_user_authorized.assert_not_called()


@pytest.mark.asyncio
async def test_readiness_rejects_cached_unauthorized_userbot_on_vm_service(monkeypatch):
    monkeypatch.setattr(api_state, "db_instance", _Database())
    user_client = SimpleNamespace(is_user_authorized=AsyncMock(return_value=True))
    monkeypatch.setattr(api_state, "user_client", user_client)

    mock_amocrm = SimpleNamespace(
        check_connection=AsyncMock(return_value=True), last_error=None
    )
    monkeypatch.setattr(
        "src.api.routes.amocrm_integration._get_amocrm_instance",
        lambda: mock_amocrm,
    )

    from src.services.core.agent_runtime import set_runtime_context

    set_runtime_context(runtime_source="vm_service", userbot_authorized=False)

    response = await api_server.production_readiness_probe()

    # A cached-unauthorized userbot on the Oracle VM is exactly the
    # AUTH_KEY_DUPLICATED scenario: Oisha keeps serving in bot-token mode, so
    # this must degrade rather than fail the whole oracle-deploy health gate.
    assert response.status_code == 200
    assert b'"status":"degraded"' in response.body
    assert b'"userbot":"unauthorized"' in response.body
    assert b'"userbot_unauthorized"' in response.body
    user_client.is_user_authorized.assert_not_called()
