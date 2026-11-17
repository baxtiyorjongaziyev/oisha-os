"""Production deploy must never invoke disruptive OpenClaw doctor by default."""
from types import SimpleNamespace

from scripts import sync_agents_runtime as agents


def _run_sync(tmp_path, monkeypatch, *, enable_doctor=False):
    monkeypatch.setattr(agents.os, "name", "posix")
    home = tmp_path / "home" / "ubuntu"
    (home / ".openclaw").mkdir(parents=True)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(agents.subprocess, "run", fake_run)
    monkeypatch.setattr(agents, "sync_openclaw_workspace", lambda *a, **k: True)
    if enable_doctor:
        monkeypatch.setenv("OISHA_RUN_OPENCLAW_DOCTOR_FIX", "1")
    else:
        monkeypatch.delenv("OISHA_RUN_OPENCLAW_DOCTOR_FIX", raising=False)
    agents.sync_all_openclaw_installations([home])
    return calls


def test_regular_deploy_sync_skips_doctor(tmp_path, monkeypatch):
    calls = _run_sync(tmp_path, monkeypatch)
    assert len(calls) == 1
    assert all("doctor --fix" not in str(command) for command, _ in calls)
    assert "openclaw config set" in str(calls[0][0])
    assert calls[0][1]["timeout"] == 30


def test_manual_doctor_requires_explicit_opt_in(tmp_path, monkeypatch):
    calls = _run_sync(tmp_path, monkeypatch, enable_doctor=True)
    assert len(calls) == 2
    assert "openclaw doctor --fix" in str(calls[0][0])
    assert calls[0][1]["timeout"] == 60
    assert calls[1][1]["timeout"] == 30
