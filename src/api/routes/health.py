"""Health & liveness probe routes."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/healthz")
@router.get("/healthz/")
async def liveness_probe():
    """Cloud Run liveness probe."""
    from src.services.core.agent_runtime import get_runtime_context
    from src.settings import settings

    now = datetime.now(timezone.utc)
    boot_age = (now - api_state._boot_at).total_seconds()
    checks: Dict[str, Any] = {
        "boot_age_sec": round(boot_age, 1),
        "heartbeat_age_sec": None,
        "userbot_connected": None,
        "db_ok": None,
    }
    problems: List[str] = []

    if api_state._last_heartbeat_at is not None:
        hb_age = (now - api_state._last_heartbeat_at).total_seconds()
        checks["heartbeat_age_sec"] = round(hb_age, 1)
        if hb_age > api_state._heartbeat_stale_seconds:
            problems.append(f"heartbeat_stale({int(hb_age)}s)")
    elif boot_age > 120:
        problems.append("no_heartbeat_ever")

    runtime = get_runtime_context()
    scheduler_mode = runtime.get("scheduler_mode")
    runtime_source = runtime.get("runtime_source", "unknown")
    control_plane_mode = scheduler_mode == "control-plane" or runtime_source == "vm_service"

    async def _probe_database() -> str:
        conn = await api_state.db_instance.get_connection()
        probe = conn.execute("SELECT 1")
        if hasattr(probe, "__await__"):
            probe = await probe
        fetchone = getattr(probe, "fetchone", None)
        if callable(fetchone):
            row = fetchone()
            if hasattr(row, "__await__"):
                await row
        return getattr(api_state.db_instance, "get_backend_name", lambda: "unknown")()

    dependency_timeout = float(os.getenv("HEALTH_DEPENDENCY_TIMEOUT_SECS", "3.0"))
    live_db_probe_default = "0" if runtime_source == "vm_service" else "1"
    live_db_probe = os.getenv(
        "HEALTH_LIVE_DB_PROBE", live_db_probe_default
    ).strip().lower() in {"1", "true", "yes", "on"}
    db_ok = True
    if api_state.db_instance is not None:
        if live_db_probe:
            try:
                backend_name = await asyncio.wait_for(
                    _probe_database(), timeout=dependency_timeout
                )
                checks["db_ok"] = True
                checks["db_backend"] = backend_name
            except asyncio.TimeoutError:
                db_ok = False
                checks["db_ok"] = False
                checks["db_backend"] = getattr(
                    api_state.db_instance, "get_backend_name", lambda: "unknown"
                )()
                problems.append("db_timeout")
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                db_ok = False
                checks["db_ok"] = False
                checks["db_backend"] = getattr(
                    api_state.db_instance, "get_backend_name", lambda: "unknown"
                )()
                problems.append("db_failed")
        else:
            backend_name = getattr(api_state.db_instance, "get_backend_name", lambda: "unknown")()
            checks["db_ok"] = backend_name != "unknown"
            checks["db_backend"] = backend_name
            checks["db_probe"] = "skipped_runtime_cached"
            db_ok = checks["db_ok"]
    else:
        checks["db_ok"] = True

    userbot_authorized = runtime.get("userbot_authorized", False)
    if not userbot_authorized and api_state.user_client:
        try:
            userbot_authorized = await asyncio.wait_for(
                api_state.user_client.is_user_authorized(), timeout=2.0
            )
        except Exception:
            userbot_authorized = False

    telegram_bot_ok = True
    if control_plane_mode:
        checks["telegram_bot"] = "delegated"
    else:
        telegram_bot_ok = userbot_authorized
        checks["telegram_bot"] = userbot_authorized

    crm_connected = False
    if (
        not control_plane_mode
        and api_state.msg_controller
        and hasattr(api_state.msg_controller, "crm")
        and api_state.msg_controller.crm
    ):
        try:
            crm_connected = await asyncio.wait_for(
                api_state.msg_controller.crm.amocrm.check_connection(),
                timeout=dependency_timeout,
            )
        except asyncio.TimeoutError:
            crm_connected = False
        except Exception:
            crm_connected = False

    checks["userbot_connected"] = userbot_authorized
    checks["telegram_bot"] = telegram_bot_ok
    checks["crm_connected"] = crm_connected

    overall = "healthy"
    if problems:
        overall = "degraded" if db_ok and telegram_bot_ok else "unhealthy"

    status_code = 200 if overall != "unhealthy" else 503
    result = {
        "status": overall,
        "boot_age_sec": round(boot_age, 1),
        "checks": checks,
        "problems": problems,
        "timestamp": now.isoformat(),
    }
    return JSONResponse(content=result, status_code=status_code)


@router.get("/readyz")
@router.get("/readyz/")
async def production_readiness_probe():
    """Cloud Run readiness probe."""
    from src.services.core.agent_runtime import get_runtime_context
    from src.time_utils import get_local_now

    now = get_local_now()
    checks: Dict[str, Any] = {}
    problems: List[str] = []

    if api_state.db_instance is not None:
        try:
            conn = await asyncio.wait_for(
                api_state.db_instance.get_connection(), timeout=3.0
            )
            result = conn.execute("SELECT 1")
            if hasattr(result, "__await__"):
                result = await result
            checks["database"] = "ok"
        except asyncio.TimeoutError:
            checks["database"] = "timeout"
            problems.append("database_timeout")
        except Exception as exc:
            checks["database"] = f"failed: {type(exc).__name__}"
            problems.append("database_unavailable")
    else:
        checks["database"] = "no_instance"

    userbot_ok = False
    if api_state.user_client is not None:
        try:
            userbot_ok = await asyncio.wait_for(
                api_state.user_client.is_user_authorized(), timeout=2.0
            )
        except Exception:
            userbot_ok = False
    checks["userbot"] = "authorized" if userbot_ok else "unauthorized"
    
    if not userbot_ok and scheduler_mode != "control-plane" and runtime_source != "vm_service":
        problems.append("userbot_unauthorized")

    amocrm_ok = False
    try:
        from src.api.routes.amocrm_integration import _get_amocrm_instance
        amocrm = _get_amocrm_instance()
        if amocrm and hasattr(amocrm, "check_connection"):
            amocrm_ok = await asyncio.wait_for(amocrm.check_connection(), timeout=3.0)
            if not amocrm_ok and getattr(amocrm, "last_error", None):
                problems.append(f"amocrm_error: {amocrm.last_error}")
    except Exception as exc:
        logger.debug("[HEALTH] AmoCRM check: %s", exc)
    checks["amocrm"] = "connected" if amocrm_ok else "unavailable"
    checks["runtime"] = runtime_source

    ready = len(problems) == 0
    result = {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "checks": checks,
        "problems": problems,
        "timestamp": now.isoformat(),
    }
    return JSONResponse(content=result, status_code=200 if ready else 503)
