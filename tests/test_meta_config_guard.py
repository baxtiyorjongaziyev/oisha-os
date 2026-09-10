import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from src.services.core.instagram import config_guard as guard


def complete():
    return {group[0]: "synthetic-secret-sentinel" for group in guard.REQUIRED_GROUPS}


@pytest.fixture(autouse=True)
def reset_guard(monkeypatch):
    monkeypatch.setattr(guard, "_alerted", False)


@pytest.mark.parametrize("value", [None, "", " \t", SecretStr(" ")])
def test_missing_blank_secrets_are_names_only(value, caplog):
    config = complete()
    config["META_PAGE_ACCESS_TOKEN"] = value
    with caplog.at_level(logging.ERROR):
        result = guard.check_meta_config(SimpleNamespace(**config), {})
    assert result == {"configured": False, "missing_keys": ["META_PAGE_ACCESS_TOKEN"]}
    assert "synthetic-secret-sentinel" not in caplog.text + json.dumps(result)
    assert "restart the service" in caplog.text


def test_aliases_and_secretstr():
    config = complete()
    config["META_INSTAGRAM_ACCOUNT_ID"] = config.pop("META_INSTAGRAM_USER_ID")
    config["INSTAGRAM_VERIFY_TOKEN"] = config.pop("META_VERIFY_TOKEN")
    config["META_PAGE_ACCESS_TOKEN"] = SecretStr(config["META_PAGE_ACCESS_TOKEN"])
    assert guard.check_meta_config(SimpleNamespace(**config), {})["configured"]


def test_outage_dedup_recovery_and_new_loss(caplog):
    with caplog.at_level(logging.ERROR):
        for _ in range(4):
            guard.check_meta_config(SimpleNamespace(), {})
        assert len(caplog.records) == 1
        guard.check_meta_config(SimpleNamespace(), {"META_APP_SECRET": "sentinel"})
        assert len(caplog.records) == 1
        assert guard.check_meta_config(SimpleNamespace(), complete())["configured"]
        guard.check_meta_config(SimpleNamespace(), {})
    assert len(caplog.records) == 2


def test_runtime_fallback_and_no_mutation():
    config = complete()
    env = {"META_PAGE_ACCESS_TOKEN": " "}
    assert guard.check_meta_config(SimpleNamespace(**config), env)["configured"]
    assert env == {"META_PAGE_ACCESS_TOKEN": " "}


@pytest.mark.asyncio
async def test_liveness_never_fails_on_meta_or_deps(monkeypatch):
    """Liveness = "process tirikmi". Meta config, DB, userbot — readiness ishi.

    Ilgari ``/healthz`` Meta config yo'qligini "degraded" deb ko'rsatib,
    boot paytida 503 qaytarardi — Oracle watchdog uni "o'lik" deb restart
    qilib, SIGKILL loop keltirib chiqarardi. Endi liveness doim 200/"alive".
    Meta degradation ``/readyz``da qoladi (test_readiness_soft_degradation).
    """
    from src.api.routes import health
    from src.api.routes.state import api_state

    orig = guard.check_meta_config
    monkeypatch.setattr(guard, "check_meta_config", lambda: orig(SimpleNamespace(), {}))
    # db_instance hali init bo'lmagan — eng yomon boot holati.
    monkeypatch.setattr(api_state, "db_instance", None)

    response = await health.liveness_probe()
    body = json.loads(response.body)

    assert response.status_code == 200
    assert body["status"] == "alive"
    assert body["checks"]["db_instance"] == "pending"
    assert "problems" not in body
    assert "synthetic-secret-sentinel" not in json.dumps(body)


@pytest.mark.asyncio
async def test_readiness_soft_degradation(monkeypatch):
    from src.api.routes import health, amocrm_integration
    from src.api.routes.state import api_state
    from src.services.core import agent_runtime

    original = guard.check_meta_config
    monkeypatch.setattr(guard, "check_meta_config", lambda: original(SimpleNamespace(), {}))
    monkeypatch.setattr(api_state, "db_instance", SimpleNamespace(
        get_connection=AsyncMock(return_value=SimpleNamespace(execute=lambda _: None)),
    ))
    monkeypatch.setattr(amocrm_integration, "_get_amocrm_instance", lambda: SimpleNamespace(
        check_connection=AsyncMock(return_value=True),
    ))
    monkeypatch.setattr(agent_runtime, "get_runtime_context", lambda: {
        "runtime_source": "vm_service", "userbot_authorized": True,
    })
    response = await health.production_readiness_probe()
    body = json.loads(response.body)
    assert response.status_code == 200
    assert body["ready"] is True
    assert body["status"] == "degraded"
    assert body["degraded"] == ["instagram_not_configured"]
    assert body["blocking"] == []


@pytest.mark.asyncio
async def test_startup_checks_before_yield(monkeypatch):
    from src.services.api_server import core

    calls = []
    monkeypatch.setattr(guard, "check_meta_config", lambda: calls.append("checked"))
    async with core.lifespan(core.app):
        assert calls == ["checked"]


@pytest.mark.asyncio
async def test_scheduler_checks_before_first_sleep(monkeypatch):
    from src.schedulers import instagram_comment_backfill_scheduler as scheduler

    calls = []
    monkeypatch.setattr(scheduler, "check_meta_config", lambda: calls.append("checked"))
    monkeypatch.setattr(scheduler, "_enabled", lambda: True)
    monkeypatch.setattr(scheduler.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await scheduler.instagram_comment_backfill_loop()
    assert calls == ["checked"]
