import importlib
from types import SimpleNamespace

watchdog = importlib.import_module("src.services.watchdog")


def test_service_uptime_uses_systemd_main_pid(monkeypatch):
    monkeypatch.setattr(watchdog.os, "name", "posix")
    monkeypatch.setattr(watchdog.subprocess, "check_output", lambda *args, **kwargs: "123\n")
    monkeypatch.setattr(watchdog.os, "stat", lambda path: SimpleNamespace(st_ctime=900.0))
    monkeypatch.setattr(watchdog.time, "time", lambda: 1000.0)

    assert watchdog.service_uptime_seconds() == 100.0


def test_service_uptime_is_unknown_without_running_pid(monkeypatch):
    monkeypatch.setattr(watchdog.os, "name", "posix")
    monkeypatch.setattr(watchdog.subprocess, "check_output", lambda *args, **kwargs: "0\n")

    assert watchdog.service_uptime_seconds() is None
