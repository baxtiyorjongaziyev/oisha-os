"""Readiness gate: soft dependencies degrade, they do not block the rollout."""

import json

import pytest

from src.api.routes import health
from src.api.routes.state import api_state


class _FakeCursor:
    def fetchone(self):
        return (1,)


class _FakeConnection:
    def execute(self, *_args, **_kwargs):
        return _FakeCursor()


class _FakeDatabase:
    async def get_connection(self):
        return _FakeConnection()

    def get_backend_name(self):
        return "sqlite"


def _body(response):
    return json.loads(response.body.decode())


@pytest.fixture
def vm_runtime(monkeypatch):
    """Oracle VM service mode with a working DB and no AmoCRM instance."""
    monkeypatch.setattr(api_state, "db_instance", _FakeDatabase())
    monkeypatch.setattr(api_state, "user_client", None)
    monkeypatch.setattr("src.api.routes.amocrm_integration._get_amocrm_instance", lambda: None)
    monkeypatch.delenv("READYZ_STRICT_DEPS", raising=False)

    def _runtime(authorized):
        monkeypatch.setattr(
            "src.services.core.agent_runtime.get_runtime_context",
            lambda: {
                "scheduler_mode": "persistent",
                "runtime_source": "vm_service",
                "userbot_authorized": authorized,
            },
        )

    return _runtime


@pytest.mark.asyncio
async def test_dead_userbot_session_serves_200_as_degraded(vm_runtime, monkeypatch):
    """AUTH_KEY_DUPLICATED must not fail the deploy gate by default."""
    vm_runtime(False)

    response = await health.production_readiness_probe()
    body = _body(response)

    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["ready"] is True
    assert body["blocking"] == []
    assert "userbot_unauthorized" in body["degraded"]
    assert body["checks"]["userbot"] == "unauthorized"


@pytest.mark.asyncio
async def test_amocrm_outage_is_degraded_not_blocking(vm_runtime):
    vm_runtime(True)

    response = await health.production_readiness_probe()
    body = _body(response)

    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert "amocrm_unavailable" in body["degraded"]
    assert body["blocking"] == []


@pytest.mark.asyncio
async def test_amocrm_outage_surfaces_last_error_detail(vm_runtime, monkeypatch):
    """The reason (e.g. a dead refresh token) must reach the deploy notification —
    "unavailable" alone hides whether this is a transient blip or something that
    needs a human to re-authorize."""
    vm_runtime(True)

    class _FakeAmoCRM:
        last_error = "oauth_reauthorization_required_http_401"

        async def check_connection(self):
            return False

    monkeypatch.setattr(
        "src.api.routes.amocrm_integration._get_amocrm_instance",
        lambda: _FakeAmoCRM(),
    )

    response = await health.production_readiness_probe()
    body = _body(response)

    assert body["checks"]["amocrm_detail"] == "oauth_reauthorization_required_http_401"


@pytest.mark.asyncio
async def test_strict_mode_restores_blocking_userbot(vm_runtime, monkeypatch):
    vm_runtime(False)
    monkeypatch.setenv("READYZ_STRICT_DEPS", "1")

    response = await health.production_readiness_probe()
    body = _body(response)

    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert body["ready"] is False
    assert "userbot_unauthorized" in body["blocking"]
    # AmoCRM has never blocked readiness — it stays soft even in strict mode.
    assert body["degraded"] == ["amocrm_unavailable"]


@pytest.mark.asyncio
async def test_database_failure_always_blocks(vm_runtime, monkeypatch):
    """The DB is the one hard dependency; degrading it would hide a real outage."""
    vm_runtime(True)

    class _BrokenDatabase:
        async def get_connection(self):
            raise RuntimeError("turso unreachable")

    monkeypatch.setattr(api_state, "db_instance", _BrokenDatabase())

    response = await health.production_readiness_probe()
    body = _body(response)

    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert "database_unavailable" in body["blocking"]
