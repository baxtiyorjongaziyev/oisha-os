"""Tizim holati tekshiruvi: muammosiz jim, xatoda HTML ogohlantirish, xom Markdown yoʻq."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.responses import JSONResponse

from src.schedulers.background_monitor import BackgroundMonitor
from src.schedulers.bg_monitor.helpers import check_system_status_alert


def _make_monitor() -> BackgroundMonitor:
    mon = BackgroundMonitor(
        msg_controller=SimpleNamespace(db=SimpleNamespace()),
        client=SimpleNamespace(send_message=AsyncMock()),
        settings=SimpleNamespace(OWNER_ID=150074828),
    )
    mon._notify_admin = AsyncMock()
    return mon


@pytest.mark.asyncio
async def test_healthy_probe_is_silent_by_default():
    async def ok_probe():
        return JSONResponse(
            content={
                "status": "ready",
                "checks": {"database": "ok", "amocrm": "connected", "userbot": "authorized"},
                "blocking": [],
                "degraded": [],
            },
            status_code=200,
        )

    assert await check_system_status_alert(include_ok=False, probe_fn=ok_probe) is None


@pytest.mark.asyncio
async def test_soft_degraded_only_is_silent_by_default():
    async def degraded_probe():
        return {
            "status": "degraded",
            "checks": {"database": "ok", "amocrm": "connected", "userbot": "unauthorized"},
            "blocking": [],
            "degraded": ["instagram_not_configured", "userbot_unauthorized"],
        }

    assert await check_system_status_alert(include_ok=False, probe_fn=degraded_probe) is None


@pytest.mark.asyncio
async def test_blocking_problem_returns_clean_html_alert():
    async def bad_probe():
        return JSONResponse(
            content={
                "status": "not_ready",
                "checks": {"database": "timeout", "amocrm": "connected", "userbot": "authorized"},
                "blocking": ["database_timeout"],
            },
            status_code=503,
        )

    alert = await check_system_status_alert(include_ok=False, probe_fn=bad_probe)
    assert alert is not None
    assert "<b>Oisha OS: Tizimda muammo aniqlandi</b>" in alert
    assert "database_timeout" in alert
    assert "DB: timeout" in alert
    assert "**" not in alert


@pytest.mark.asyncio
async def test_healthy_probe_with_include_ok_uses_html_and_real_checks():
    async def ok_probe():
        return {
            "status": "ready",
            "checks": {"database": "ok", "amocrm": "connected", "userbot": "authorized"},
            "blocking": [],
        }

    msg = await check_system_status_alert(include_ok=True, probe_fn=ok_probe)
    assert msg is not None
    assert msg.startswith("👸 <b>Oisha OS: Tizim nazoratda</b>")
    assert "DB: ok | AmoCRM: connected | Userbot: authorized" in msg
    assert "**" not in msg


@pytest.mark.asyncio
async def test_probe_exception_returns_html_error_alert():
    async def boom():
        raise RuntimeError("probe crashed")

    msg = await check_system_status_alert(include_ok=False, probe_fn=boom)
    assert msg is not None
    assert "<b>Oisha OS: Tizim tekshiruvi xatosi</b>" in msg
    assert "<code>RuntimeError</code>" in msg
    assert "**" not in msg


@pytest.mark.asyncio
async def test_bg_monitor_status_notify_silent_when_ok_and_html_on_problem(monkeypatch):
    monkeypatch.delenv("STATUS_NOTIFY_OK", raising=False)

    async def ok_probe():
        return {"status": "ready", "checks": {"database": "ok", "amocrm": "connected", "userbot": "authorized"}, "blocking": []}

    monkeypatch.setattr("src.api.routes.health.production_readiness_probe", ok_probe)
    mon = _make_monitor()
    await mon._job_status_notify(datetime(2026, 11, 22, 21, 0))
    mon._notify_admin.assert_not_awaited()

    async def bad_probe():
        return {"status": "not_ready", "checks": {"database": "unavailable", "amocrm": "connected", "userbot": "authorized"}, "blocking": ["database_unavailable"]}

    monkeypatch.setattr("src.api.routes.health.production_readiness_probe", bad_probe)
    mon2 = _make_monitor()
    await mon2._job_status_notify(datetime(2026, 11, 22, 21, 0))
    mon2._notify_admin.assert_awaited_once()
    sent_text, kwargs = mon2._notify_admin.call_args[0][0], mon2._notify_admin.call_args[1]
    assert kwargs["parse_mode"] == "HTML"
    assert "database_unavailable" in sent_text
    assert "**" not in sent_text


@pytest.mark.asyncio
async def test_bg_monitor_status_notify_honors_status_notify_ok_env(monkeypatch):
    monkeypatch.setenv("STATUS_NOTIFY_OK", "1")

    async def ok_probe():
        return {"status": "ready", "checks": {"database": "ok", "amocrm": "connected", "userbot": "authorized"}, "blocking": []}

    monkeypatch.setattr("src.api.routes.health.production_readiness_probe", ok_probe)
    mon = _make_monitor()
    await mon._job_status_notify(datetime(2026, 11, 22, 21, 0))
    mon._notify_admin.assert_awaited_once()
    sent_text, kwargs = mon._notify_admin.call_args[0][0], mon._notify_admin.call_args[1]
    assert kwargs["parse_mode"] == "HTML"
    assert "<b>Oisha OS: Tizim nazoratda</b>" in sent_text
    assert "**" not in sent_text


@pytest.mark.asyncio
async def test_periodic_reports_status_check_silent_when_ok_and_html_on_problem(monkeypatch):
    from src.schedulers.main_loop import periodic_reports

    monkeypatch.delenv("STATUS_NOTIFY_OK", raising=False)
    bot_rt = SimpleNamespace(send_message=AsyncMock())
    monkeypatch.setattr(periodic_reports.m, "bot_runtime", bot_rt, raising=False)
    monkeypatch.setattr(periodic_reports.m, "client", None, raising=False)
    monkeypatch.setattr(periodic_reports.settings, "OWNER_ID", 150074828, raising=False)

    async def ok_probe():
        return {"status": "ready", "checks": {"database": "ok", "amocrm": "connected", "userbot": "authorized"}, "blocking": []}

    monkeypatch.setattr("src.api.routes.health.production_readiness_probe", ok_probe)
    task = SimpleNamespace()
    await periodic_reports._check_overdue_and_status(datetime(2026, 11, 22, 21, 0), task)
    bot_rt.send_message.assert_not_awaited()

    async def bad_probe():
        return {"status": "not_ready", "checks": {"database": "timeout", "amocrm": "connected", "userbot": "authorized"}, "blocking": ["database_timeout"]}

    monkeypatch.setattr("src.api.routes.health.production_readiness_probe", bad_probe)
    task2 = SimpleNamespace()
    await periodic_reports._check_overdue_and_status(datetime(2026, 11, 22, 21, 0), task2)
    bot_rt.send_message.assert_awaited_once()
    args, kwargs = bot_rt.send_message.call_args
    assert args[0] == 150074828
    assert kwargs["parse_mode"] == "HTML"
    assert "database_timeout" in args[1]
    assert "**" not in args[1]
