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

# Dependencies that leave Oisha *degraded* rather than *unready*. A dead
# Telegram userbot session or an expired AmoCRM token disables those features,
# but the service keeps serving on the bot-token path — failing readiness on
# them means one stale credential blocks every later deploy too.
# Set READYZ_STRICT_DEPS=1 to restore the old gate, which blocked on the
# userbot; AmoCRM has never blocked readiness and stays soft in both modes.
SOFT_DEPENDENCY_PROBLEMS = frozenset({"userbot_unauthorized", "amocrm_unavailable"})
STRICT_SOFT_DEPENDENCY_PROBLEMS = frozenset({"amocrm_unavailable"})


def _strict_dependencies() -> bool:
    return os.getenv("READYZ_STRICT_DEPS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@router.get("/health")
@router.get("/healthz")
@router.get("/healthz/")
async def liveness_probe():
    """Cloud Run liveness probe."""
    from src.services.core.agent_runtime import get_runtime_context

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
        db_ok = False
        checks["db_ok"] = False
        checks["db_backend"] = "uninitialized"
        problems.append("database_not_initialized")

    userbot_authorized = runtime.get("userbot_authorized", False)
    if not control_plane_mode and not userbot_authorized and api_state.user_client:
        try:
            userbot_authorized = await asyncio.wait_for(
                api_state.user_client.is_user_authorized(), timeout=2.0
            )
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
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
            logger.error("Exception handled in %s", __name__, exc_info=True)
            crm_connected = False

    if control_plane_mode:
        checks["userbot_connected"] = "delegated"
        checks["telegram_bot"] = "delegated"
        checks["crm_connected"] = "delegated"
    else:
        checks["userbot_connected"] = userbot_authorized
        checks["telegram_bot"] = telegram_bot_ok
        checks["crm_connected"] = crm_connected
        if not userbot_authorized:
            problems.append("userbot_disconnected")
        if not crm_connected:
            problems.append("crm_disconnected")

    overall = "healthy"
    if problems:
        overall = "degraded" if db_ok else "unhealthy"

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
    runtime = get_runtime_context()
    scheduler_mode = runtime.get("scheduler_mode", "persistent")
    runtime_source = runtime.get("runtime_source", "unknown")
    control_plane_mode = scheduler_mode == "control-plane"
    vm_service_mode = runtime_source == "vm_service"

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
            logger.error("Exception handled in %s", __name__, exc_info=True)
            checks["database"] = f"failed: {type(exc).__name__}"
            problems.append("database_unavailable")
    else:
        checks["database"] = "no_instance"
        problems.append("database_not_initialized")

    userbot_ok = False
    if control_plane_mode:
        checks["userbot"] = "delegated"
    elif vm_service_mode:
        # The Oracle VM owns the Telethon connection if configured. If userbot
        # session is expired, it runs gracefully in bot-token mode.
        userbot_ok = runtime.get("userbot_authorized") is True
        checks["userbot"] = "authorized" if userbot_ok else "unauthorized"
    elif api_state.user_client is not None:
        try:
            userbot_ok = await asyncio.wait_for(
                api_state.user_client.is_user_authorized(), timeout=2.0
            )
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            userbot_ok = False
        checks["userbot"] = "authorized" if userbot_ok else "unauthorized"
    else:
        checks["userbot"] = "unauthorized"

    if not userbot_ok and not control_plane_mode:
        problems.append("userbot_unauthorized")

    amocrm_ok = False
    amocrm = None
    try:
        from src.api.routes.amocrm_integration import _get_amocrm_instance
        amocrm = _get_amocrm_instance()
        if amocrm and hasattr(amocrm, "check_connection"):
            amocrm_ok = await asyncio.wait_for(amocrm.check_connection(), timeout=3.0)
    except Exception as exc:
        logger.debug("[HEALTH] AmoCRM check: %s", exc)
    checks["amocrm"] = "connected" if amocrm_ok else "unavailable"
    if not amocrm_ok:
        # Surface *why* — "unavailable" alone hides the difference between a
        # transient network blip and a dead refresh token that needs a human
        # to re-authorize. This reaches the owner via the deploy notification's
        # degraded-checks summary.
        detail = getattr(amocrm, "last_error", None) if amocrm else None
        if detail:
            checks["amocrm_detail"] = detail
        if not control_plane_mode:
            problems.append("amocrm_unavailable")
    checks["runtime"] = runtime_source

    soft = (
        STRICT_SOFT_DEPENDENCY_PROBLEMS
        if _strict_dependencies()
        else SOFT_DEPENDENCY_PROBLEMS
    )
    blocking = [p for p in problems if p not in soft]
    degraded = [p for p in problems if p in soft]

    serving = len(blocking) == 0
    if not serving:
        status = "not_ready"
    elif degraded:
        status = "degraded"
    else:
        status = "ready"

    result = {
        "ready": serving,
        "status": status,
        "checks": checks,
        "problems": problems,
        "blocking": blocking,
        "degraded": degraded,
        "timestamp": now.isoformat(),
    }
    return JSONResponse(content=result, status_code=200 if serving else 503)
