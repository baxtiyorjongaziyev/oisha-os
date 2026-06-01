import asyncio
from types import SimpleNamespace

import pytest

from src import main
from src.main import _is_shutdown_daemon_task


class FakeTask:
    def __init__(self, *, task_name: str = "", coro_name: str = "", qualname: str = ""):
        self._task_name = task_name
        self._coro = SimpleNamespace(__name__=coro_name, __qualname__=qualname)

    def get_name(self) -> str:
        return self._task_name

    def get_coro(self):
        return self._coro


def test_shutdown_daemon_detection_uses_explicit_task_name():
    assert _is_shutdown_daemon_task(FakeTask(task_name="health_check_api"))


def test_shutdown_daemon_detection_uses_background_coroutine_name():
    assert _is_shutdown_daemon_task(FakeTask(coro_name="ai_autopilot_loop"))


def test_shutdown_daemon_detection_recognizes_capacity_archiver():
    assert _is_shutdown_daemon_task(FakeTask(coro_name="crm_capacity_archiver_loop"))


def test_shutdown_daemon_detection_uses_telethon_qualname():
    assert _is_shutdown_daemon_task(
        FakeTask(coro_name="wrapper", qualname="MTProtoSender._recv_loop")
    )


def test_shutdown_daemon_detection_uses_service_loop_qualname():
    assert _is_shutdown_daemon_task(
        FakeTask(coro_name="heartbeat", qualname="AdminBot.start.<locals>.heartbeat")
    )


def test_shutdown_daemon_detection_keeps_short_lived_handler_drainable():
    assert not _is_shutdown_daemon_task(
        FakeTask(coro_name="process_amocrm_event", qualname="process_amocrm_event")
    )


@pytest.mark.asyncio
async def test_stop_health_check_api_requests_clean_uvicorn_exit(monkeypatch):
    server = SimpleNamespace(should_exit=False)
    monkeypatch.setattr(main, "_health_api_server", server)

    async def fake_server():
        while not server.should_exit:
            await asyncio.sleep(0)

    task = asyncio.create_task(fake_server())
    await main.stop_health_check_api(task, timeout_seconds=0.1)

    assert server.should_exit is True
    assert task.done()
    assert main._health_api_server is None
