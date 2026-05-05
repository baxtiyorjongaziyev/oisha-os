from __future__ import annotations

import os
import platform
import socket
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.settings import settings
from src.time_utils import get_local_now

_runtime_context: Dict[str, Any] = {
    "runtime_source": "unknown",
    "canonical_entrypoint": "src/main.py",
    "runtime_id": "unknown",
    "service_name": "Oisha-OS",
    "quiet_hours_enabled": True,
    "state_backend": "sqlite",
    "state_db_path": None,
    "scheduler_mode": "persistent",
    "userbot_authorized": None,
}


def detect_runtime_source() -> str:
    if settings.RUNNING_IN_CLOUD or os.getenv("K_SERVICE"):
        return "cloud_run"
    if os.getenv("INVOCATION_ID") or os.getenv("SYSTEMD_EXEC_PID"):
        return "vm_service"
    return "local"


def build_runtime_context(**overrides: Any) -> Dict[str, Any]:
    raw_runtime_source = overrides.get("runtime_source")
    runtime_source = (
        raw_runtime_source
        if raw_runtime_source and raw_runtime_source != "unknown"
        else detect_runtime_source()
    )
    service_name = (
        overrides.get("service_name") or os.getenv("K_SERVICE") or "oisha-main"
    )
    runtime_id = (
        overrides.get("runtime_id") or os.getenv("K_REVISION") or socket.gethostname()
    )

    context = {
        "runtime_source": runtime_source,
        "canonical_entrypoint": overrides.get("canonical_entrypoint", "src/main.py"),
        "runtime_id": runtime_id,
        "service_name": service_name,
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "quiet_hours_enabled": overrides.get("quiet_hours_enabled", True),
        "state_backend": overrides.get("state_backend", "sqlite"),
        "state_db_path": overrides.get("state_db_path"),
        "scheduler_mode": overrides.get("scheduler_mode", "persistent"),
        "userbot_authorized": overrides.get("userbot_authorized"),
        "detected_at": get_local_now().isoformat(),
    }
    return context


def set_runtime_context(**kwargs: Any) -> Dict[str, Any]:
    _runtime_context.update(build_runtime_context(**{**_runtime_context, **kwargs}))
    return dict(_runtime_context)


def get_runtime_context() -> Dict[str, Any]:
    if _runtime_context.get("runtime_source") in {None, "", "unknown"}:
        return set_runtime_context()
    return dict(_runtime_context)


def get_storage_health(
    db_path: Optional[str],
    recent_job_runs: Optional[List[Dict[str, Any]]] = None,
    backend: str = "sqlite",
) -> Dict[str, Any]:
    if backend != "sqlite":
        return {
            "backend": backend,
            "path": db_path,
            "exists": True,
            "writable": True,
            "size_bytes": 0,
            "scheduler_rows": 0,
            "kv_rows": 0,
            "agent_action_rows": 0,
            "recent_job_runs": recent_job_runs or [],
            "error": None,
        }

    resolved_path = Path(db_path).resolve() if db_path else None
    writable = False
    exists = False
    size_bytes = 0
    scheduler_rows = 0
    kv_rows = 0
    agent_action_rows = 0
    error = None

    if resolved_path:
        exists = resolved_path.exists()
        if exists:
            size_bytes = resolved_path.stat().st_size

        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved_path, "ab"):
                writable = True
        except Exception as exc:
            error = str(exc)

        try:
            if exists:
                conn = sqlite3.connect(str(resolved_path))
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM scheduled_jobs")
                    scheduler_rows = int(cursor.fetchone()[0])
                    cursor.execute("SELECT COUNT(*) FROM kv_settings")
                    kv_rows = int(cursor.fetchone()[0])
                    cursor.execute("SELECT COUNT(*) FROM agent_actions")
                    agent_action_rows = int(cursor.fetchone()[0])
                finally:
                    conn.close()
        except Exception as exc:
            error = str(exc)

    return {
        "backend": backend,
        "path": str(resolved_path) if resolved_path else None,
        "exists": exists,
        "writable": writable,
        "size_bytes": size_bytes,
        "scheduler_rows": scheduler_rows,
        "kv_rows": kv_rows,
        "agent_action_rows": agent_action_rows,
        "recent_job_runs": recent_job_runs or [],
        "error": error,
    }


def collect_legacy_runtime_inventory(root_path: str) -> List[Dict[str, Any]]:
    root = Path(root_path)
    inventory: List[Dict[str, Any]] = []
    include_names = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}
    include_suffixes = {".service"}
    skip_parts = {".git", ".venv", "__pycache__", ".claude", "tmp", "node_modules"}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        if path.name not in include_names and path.suffix not in include_suffixes:
            continue

        runtime_type = "service" if path.suffix == ".service" else "container"
        canonical = path.as_posix() in {
            "deploy/oisha.service",
            "deploy/oisha_sync.service",
            "Dockerfile",
            "deploy/Dockerfile",
            "docker-compose.yml",
            "deploy/docker-compose.yml",
        }

        inventory.append(
            {
                "path": str(path.relative_to(root)),
                "type": runtime_type,
                "canonical_repo_file": canonical,
            }
        )

    inventory.sort(key=lambda item: item["path"])
    return inventory
