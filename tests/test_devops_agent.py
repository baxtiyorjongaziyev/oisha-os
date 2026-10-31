from __future__ import annotations

import pytest

from src.services.core import devops_agent
from src.services.core.devops_agent import (
    _probe_http_json,
    heal_server_services,
    inspect_server_status,
)


def test_probe_http_json_rejects_external_urls():
    with pytest.raises(ValueError, match="only_local_oisha_health_endpoints_allowed"):
        _probe_http_json("https://example.com/healthz")


def test_inspect_server_status_healthy(monkeypatch):
    monkeypatch.setattr(
        devops_agent,
        "_read_host_metrics",
        lambda: {
            "loadavg_1_5_15": [0.4, 0.3, 0.2],
            "uptime_seconds": 100000.0,
            "memory_mb": {"total_mb": 8000, "used_mb": 3500, "available_mb": 4500, "used_pct": 43.8},
            "disk_root": {"total_gb": 145.0, "used_gb": 41.0, "free_gb": 104.0, "used_pct": 28.3},
        },
    )
    monkeypatch.setattr(
        devops_agent,
        "_inspect_systemd_services",
        lambda: [{"service": "oisha-os.service", "state": "active", "healthy": True}],
    )
    monkeypatch.setattr(
        devops_agent,
        "_inspect_docker_containers",
        lambda: [{"name": "twenty-server-1", "status": "Up 11 days (healthy)", "healthy": True}],
    )
    monkeypatch.setattr(
        devops_agent,
        "_probe_http_json",
        lambda url, timeout=5: {"http_status": 200, "ok": True, "data": {"status": "alive"}},
    )
    monkeypatch.setattr(devops_agent, "_recent_service_errors", lambda: [])

    res = inspect_server_status()
    assert res["success"] is True
    assert res["overall_status"] == "HEALTHY"
    assert res["alerts"] == []


def test_inspect_server_status_detects_degraded_and_heal_restarts(monkeypatch):
    state = {"restarted": False}

    monkeypatch.setattr(
        devops_agent,
        "_read_host_metrics",
        lambda: {
            "loadavg_1_5_15": [1.0, 1.0, 1.0],
            "uptime_seconds": 500.0,
            "memory_mb": {"total_mb": 8000, "used_mb": 4000, "available_mb": 4000, "used_pct": 50.0},
            "disk_root": {"total_gb": 145.0, "used_gb": 41.0, "free_gb": 104.0, "used_pct": 28.3},
        },
    )
    monkeypatch.setattr(
        devops_agent,
        "_inspect_systemd_services",
        lambda: [
            {
                "service": "hermes-gateway.service",
                "state": "active" if state["restarted"] else "failed",
                "healthy": state["restarted"],
            }
        ],
    )
    monkeypatch.setattr(devops_agent, "_inspect_docker_containers", lambda: [])
    monkeypatch.setattr(
        devops_agent,
        "_probe_http_json",
        lambda url, timeout=5: {"http_status": 200, "ok": True, "data": {"status": "alive"}},
    )
    monkeypatch.setattr(devops_agent.shutil, "which", lambda cmd: "/usr/bin/systemctl")

    def fake_run_cmd(args, timeout=8):
        if args[:3] == ["sudo", "systemctl", "restart"]:
            state["restarted"] = True
            return 0, ""
        return 0, "active"

    monkeypatch.setattr(devops_agent, "_run_cmd", fake_run_cmd)

    heal = heal_server_services(auto_restart_failed=True)
    assert heal["success"] is True
    assert heal["restarted_services"] == ["hermes-gateway.service"]
    assert heal["overall_status"] == "HEALTHY"
