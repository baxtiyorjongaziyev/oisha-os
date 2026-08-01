"""System dashboard routes."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from src.api.rbac import Permission, require_permissions

from src.api.routes.state import api_state
from src.settings import settings
from src.time_utils import get_local_now

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)


def _get_legacy_runtime_inventory() -> List[Dict[str, Any]]:
    if api_state.legacy_runtime_inventory_cache is None:
        from src.services.core.agent_runtime import collect_legacy_runtime_inventory
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        api_state.legacy_runtime_inventory_cache = collect_legacy_runtime_inventory(repo_root)
    return list(api_state.legacy_runtime_inventory_cache)


async def build_health_snapshot(
    include_inventory: bool = False, include_traces: bool = False
) -> Dict[str, Any]:
    from src.services.core.agent_runtime import get_runtime_context, get_storage_health

    runtime = get_runtime_context()
    db_path = runtime.get("state_db_path") or getattr(api_state.db_instance, "db_path", None)
    recent_job_runs: List[Dict[str, Any]] = []
    recent_agent_actions: List[Dict[str, Any]] = []
    storage_counts: Dict[str, int] = {}
    storage_cache_used = False

    if api_state.db_instance:
        try:
            async def load_storage_snapshot() -> Dict[str, Any]:
                return {
                    "recent_job_runs": await api_state.db_instance.get_recent_job_runs(limit=10),
                    "storage_counts": await api_state.db_instance.get_storage_counts(),
                    "updated_at": get_local_now().isoformat(),
                }

            api_state._health_db_snapshot_cache = await asyncio.wait_for(
                load_storage_snapshot(),
                timeout=api_state._HEALTH_DB_TIMEOUT_SECONDS,
            )
            recent_job_runs = list(api_state._health_db_snapshot_cache["recent_job_runs"])
            storage_counts = dict(api_state._health_db_snapshot_cache["storage_counts"])
        except asyncio.TimeoutError:
            storage_cache_used = True
        except Exception as exc:
            storage_cache_used = True
            logger.warning("[API] Could not fetch storage health: %s", exc)

        if storage_cache_used:
            recent_job_runs = list(api_state._health_db_snapshot_cache.get("recent_job_runs", []))
            storage_counts = dict(api_state._health_db_snapshot_cache.get("storage_counts", {}))

        if include_traces:
            try:
                recent_agent_actions = await asyncio.wait_for(
                    api_state.db_instance.get_recent_agent_actions(limit=25),
                    timeout=api_state._HEALTH_DB_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                logger.debug("[dashboard] get agent actions failed: %s", exc)

    storage_health = get_storage_health(
        db_path,
        recent_job_runs=recent_job_runs,
        backend=runtime.get("state_backend", "sqlite"),
        storage_counts=storage_counts,
    )
    storage_health["cached"] = storage_cache_used
    storage_health["cache_updated_at"] = api_state._health_db_snapshot_cache.get("updated_at")

    snapshot = {
        "timestamp": get_local_now().isoformat(),
        "status": api_state.cached_status.copy(),
        "runtime": runtime,
        "storage": storage_health,
        "telegram_userbot_access": dict(api_state._userbot_group_access_snapshot),
    }
    if include_inventory:
        snapshot["legacy_runtime_inventory"] = _get_legacy_runtime_inventory()
    if include_traces:
        snapshot["agent_actions"] = recent_agent_actions
    return snapshot


@router.get("/status", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_status():
    from src.services.core.agent_runtime import get_runtime_context
    data = api_state.cached_status.copy()
    data["crm_health"] = f"{api_state.cached_crm_audit.get('health_score', 98)}%"
    runtime = get_runtime_context()
    data["runtime_source"] = runtime.get("runtime_source")
    data["service_name"] = runtime.get("service_name")
    data["state_backend"] = runtime.get("state_backend")
    data["userbot_authorized"] = runtime.get("userbot_authorized")
    return data


@router.get("/runtime", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_runtime():
    from src.services.core.agent_runtime import get_runtime_context
    return {
        "timestamp": get_local_now().isoformat(),
        "runtime": get_runtime_context(),
        "legacy_runtime_inventory": _get_legacy_runtime_inventory(),
    }


@router.get("/health", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_health():
    snapshot = await build_health_snapshot()
    snapshot["crm_audit"] = api_state.cached_crm_audit
    return snapshot


@router.get("/traces", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_traces():
    snapshot = await build_health_snapshot(include_traces=True)
    return {
        "timestamp": snapshot["timestamp"],
        "runtime": snapshot["runtime"],
        "job_runs": snapshot["storage"].get("recent_job_runs", []),
        "agent_actions": snapshot.get("agent_actions", []),
    }


@router.get("/inventory", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_inventory():
    snapshot = await build_health_snapshot(include_inventory=True)
    return {
        "timestamp": snapshot["timestamp"],
        "runtime": snapshot["runtime"],
        "legacy_runtime_inventory": snapshot.get("legacy_runtime_inventory", []),
    }


@router.get("/activity", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_activity():
    return {
        "timestamp": get_local_now().isoformat(),
        "activities": api_state.system_activities[:50],
    }


@router.get("/stats", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_stats():
    counts = {}
    if api_state.db_instance:
        try:
            counts = await api_state.db_instance.get_storage_counts()
        except Exception as exc:
            logger.debug("[dashboard] get storage counts failed: %s", exc)
    return {
        "timestamp": get_local_now().isoformat(),
        "storage": counts,
        "uptime_seconds": (
            datetime.now(timezone.utc) - api_state._boot_at
        ).total_seconds()
        if api_state._boot_at
        else 0,
    }


@router.get("/info", dependencies=[require_permissions(Permission.SYSTEM_READ)])
async def get_system_info():
    from src.services.core.agent_runtime import get_runtime_context
    return {
        "timestamp": get_local_now().isoformat(),
        "runtime": get_runtime_context(),
    }


@router.post("/audit", dependencies=[require_permissions(Permission.AUDIT_READ_ALL)])
async def run_system_audit():
    """Trigger a manual CRM audit."""
    if api_state.crm_audit_running:
        return {"status": "already_running"}
    api_state.crm_audit_running = True
    try:
        from src.services.debug.crm_audit import AmoCRMAudit
        audit = AmoCRMAudit()
        result = await audit.run_full_audit()
        api_state.cached_crm_audit = result
        return result
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return {"status": "error", "message": str(exc)}
    finally:
        api_state.crm_audit_running = False
