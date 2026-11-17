"""DevOps & SRE Agent (Contabo VPS Diagnostics, Systemd/Docker Health & Self-Healing Engine).

Provides live, read-only infrastructure inspection and safe self-healing actions for:
- System resources (uptime, CPU loadavg, RAM/Swap, root filesystem usage)
- Core systemd units (oisha-os, oisha-watchdog, hermes-gateway, shirinlaxza-bot, nginx, actions.runner)
- HTTP health/readiness probes (/healthz/ and /readyz on 127.0.0.1:8080)
- Docker containers (twenty, postgres, redis, nocodb, n8n, uptime-kuma, hr-bot)
- Recent journalctl error/warning triage
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Any

from src.time_utils import get_local_now

MONITORED_SYSTEMD_SERVICES: tuple[str, ...] = (
    "oisha-os.service",
    "oisha-watchdog.service",
    "hermes-gateway.service",
    "shirinlaxza-bot.service",
    "nginx.service",
    "actions.runner.baxtiyorjongaziyev-oisha-os.contabo-vps.service",
)

RESTARTABLE_SERVICES: frozenset[str] = frozenset({
    "oisha-os.service",
    "oisha-watchdog.service",
    "hermes-gateway.service",
    "shirinlaxza-bot.service",
})


def _run_cmd(args: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        res = subprocess.run(  # nosec B603
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return res.returncode, (res.stdout or "").strip()
    except Exception as exc:
        return 1, f"error: {type(exc).__name__}"


def _read_host_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "loadavg_1_5_15": None,
        "uptime_seconds": None,
        "memory_mb": None,
        "disk_root": None,
    }
    try:
        if os.path.exists("/proc/loadavg"):
            with open("/proc/loadavg", "r", encoding="utf-8") as f:
                parts = f.read().split()
                if len(parts) >= 3:
                    metrics["loadavg_1_5_15"] = [float(parts[0]), float(parts[1]), float(parts[2])]
        if os.path.exists("/proc/uptime"):
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                metrics["uptime_seconds"] = round(float(f.read().split()[0]), 1)
        if os.path.exists("/proc/meminfo"):
            mem: dict[str, int] = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        num = v.strip().split()[0]
                        if num.isdigit():
                            mem[k.strip()] = int(num)
            total_kb = mem.get("MemTotal", 0)
            avail_kb = mem.get("MemAvailable", 0)
            if total_kb > 0:
                used_kb = max(0, total_kb - avail_kb)
                metrics["memory_mb"] = {
                    "total_mb": round(total_kb / 1024),
                    "used_mb": round(used_kb / 1024),
                    "available_mb": round(avail_kb / 1024),
                    "used_pct": round(used_kb / total_kb * 100, 1),
                }
    except Exception:
        pass

    try:
        usage = shutil.disk_usage("/")
        metrics["disk_root"] = {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "used_pct": round(usage.used / usage.total * 100, 1) if usage.total else 0.0,
        }
    except Exception:
        pass
    return metrics


def _probe_http_json(url: str, timeout: int = 5) -> dict[str, Any]:
    if not url.startswith("http://127.0.0.1:8080/"):
        raise ValueError("only_local_oisha_health_endpoints_allowed")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            body = resp.read().decode("utf-8", errors="replace")
            return {"http_status": resp.status, "ok": resp.status == 200, "data": json.loads(body)}
    except Exception as exc:
        return {"http_status": 0, "ok": False, "error": type(exc).__name__}


def _inspect_systemd_services(services: tuple[str, ...] = MONITORED_SYSTEMD_SERVICES) -> list[dict[str, Any]]:
    if not shutil.which("systemctl"):
        return []
    rows = []
    for svc in services:
        code, state = _run_cmd(["systemctl", "is-active", svc], timeout=5)
        rows.append({
            "service": svc,
            "state": state or "unknown",
            "healthy": code == 0 and state == "active",
        })
    return rows


def _inspect_docker_containers() -> list[dict[str, Any]]:
    if not shutil.which("docker"):
        return []
    code, out = _run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"], timeout=6)
    if code != 0 or not out:
        return []
    containers = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        name, status = line.split("\t", 1)
        healthy = status.lower().startswith("up") and "unhealthy" not in status.lower()
        containers.append({"name": name.strip(), "status": status.strip(), "healthy": healthy})
    return containers


def _recent_service_errors(service: str = "oisha-os.service", lines: int = 120) -> list[str]:
    if not shutil.which("journalctl"):
        return []
    bounded = min(max(int(lines), 20), 300)
    code, out = _run_cmd(["journalctl", "-u", service, "-n", str(bounded), "--no-pager"], timeout=6)
    if code != 0 or not out:
        return []
    matched = []
    for line in out.splitlines():
        if "AMOCRM TOKEN STORE" in line or "Service account credentials not found" in line:
            continue
        if any(tok in line for tok in ("ERROR", "CRITICAL", "Traceback", '"level": "error"')):
            matched.append(line[-240:])
    return matched[-15:]


def inspect_server_status(
    *,
    include_logs: bool = True,
    healthz_url: str = "http://127.0.0.1:8080/healthz/",
    readyz_url: str = "http://127.0.0.1:8080/readyz",
) -> dict[str, Any]:
    """Perform a full DevOps health & infrastructure audit on the host."""
    now = get_local_now()
    host = _read_host_metrics()
    systemd = _inspect_systemd_services()
    docker = _inspect_docker_containers()
    healthz = _probe_http_json(healthz_url)
    readyz = _probe_http_json(readyz_url)
    recent_errors = _recent_service_errors() if include_logs else []

    alerts: list[str] = []
    mem = host.get("memory_mb") or {}
    if mem.get("used_pct", 0) >= 88.0:
        alerts.append(f"high_memory_usage:{mem['used_pct']}%")
    disk = host.get("disk_root") or {}
    if disk.get("used_pct", 0) >= 85.0:
        alerts.append(f"high_disk_usage:{disk['used_pct']}%")
    for s in systemd:
        if not s["healthy"]:
            alerts.append(f"systemd_down:{s['service']}({s['state']})")
    for c in docker:
        if not c["healthy"]:
            alerts.append(f"docker_unhealthy:{c['name']}({c['status']})")
    if not healthz.get("ok"):
        alerts.append("oisha_healthz_failed")
    if not readyz.get("ok"):
        alerts.append("oisha_readyz_failed")

    overall = "HEALTHY" if not alerts else ("DEGRADED" if healthz.get("ok") else "CRITICAL")
    return {
        "success": True,
        "source": "devops_agent_live",
        "as_of_tashkent": now.isoformat(),
        "overall_status": overall,
        "alerts": alerts,
        "host": host,
        "oisha_endpoints": {"healthz": healthz, "readyz": readyz},
        "systemd_services": systemd,
        "docker_containers": docker,
        "recent_errors": recent_errors,
    }


def heal_server_services(*, auto_restart_failed: bool = False) -> dict[str, Any]:
    """Check monitored systemd services and optionally restart failed allowlisted services."""
    status = inspect_server_status(include_logs=False)
    restarted: list[str] = []
    failed_restarts: list[str] = []

    if auto_restart_failed and shutil.which("systemctl"):
        for s in status.get("systemd_services", []):
            svc = s["service"]
            if not s["healthy"] and svc in RESTARTABLE_SERVICES:
                code, _ = _run_cmd(["sudo", "systemctl", "restart", svc], timeout=25)
                if code == 0:
                    restarted.append(svc)
                else:
                    failed_restarts.append(svc)

    post = inspect_server_status(include_logs=False) if restarted else status
    return {
        "success": not failed_restarts,
        "overall_status": post["overall_status"],
        "restarted_services": restarted,
        "failed_restarts": failed_restarts,
        "remaining_alerts": post["alerts"],
    }
