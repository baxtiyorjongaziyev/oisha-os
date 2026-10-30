"""Attendance must be prepared before ASGI starts serving requests."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from src.api.routes import attendance_routes as routes
from src.services.api_server import core


@pytest.fixture
def startup(monkeypatch):
    from src.services.core.instagram import config_guard
    monkeypatch.setattr(config_guard, "check_meta_config", lambda: None)
    monkeypatch.setattr(core, "mark_heartbeat", lambda *args: None)
    monkeypatch.setattr(core, "add_activity", lambda *args: None)
    monkeypatch.setattr(routes, "_schema_ready", False)
    monkeypatch.setattr(routes, "_schema_lock", asyncio.Lock())
    db = AsyncMock()
    monkeypatch.setattr(routes, "_db", lambda: db)
    bootstrap = AsyncMock()
    monkeypatch.setattr(routes.bootstrap, "run", bootstrap)
    return db, bootstrap


def test_schema_and_bootstrap_finish_before_serving(startup):
    db, bootstrap = startup

    async def scenario():
        async with core.lifespan(core.app):
            assert db.execute.await_count > 0
            bootstrap.assert_awaited_once_with(db)
            ddl_count = db.execute.await_count
            assert await routes._ready_db() is db
            assert db.execute.await_count == ddl_count

    asyncio.run(scenario())


def test_schema_failure_prevents_serving(startup):
    db, bootstrap = startup
    db.execute.side_effect = RuntimeError("synthetic schema failure")

    async def scenario():
        with pytest.raises(RuntimeError, match="synthetic schema failure"):
            async with core.lifespan(core.app):
                pytest.fail("ASGI must not serve before schema exists")
        bootstrap.assert_not_awaited()
        assert routes._schema_ready is False

    asyncio.run(scenario())
