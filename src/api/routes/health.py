"""Health & liveness probe routes."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.routes.state import api_state
from src.services.core.instagram.config_guard import add_meta_health

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Dependencies that leave Oisha *degraded* rather than *unready*. A dead
# Telegram userbot session or an expired AmoCRM token disables those features,
# but the service keeps serving on the bot-token path — failing readiness on
# them means one stale credential blocks every later deploy too.
# Set READYZ_STRICT_DEPS=1 to restore the old gate, which blocked on the
# userbot; AmoCRM has never blocked readiness and stays soft in both modes.
SOFT_DEPENDENCY_PROBLEMS = frozenset({
    "userbot_unauthorized", "amocrm_unavailable", "instagram_not_configured",
})
STRICT_SOFT_DEPENDENCY_PROBLEMS = frozenset({
    "amocrm_unavailable", "instagram_not_configured",
})


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
    """Liveness probe — "process tirikmi va event loop javob beryaptimi".

    DIQQAT: bu **faqat** liveness. DB, userbot, AmoCRM, Meta config, heartbeat —
    hammasi *readiness* (``/readyz``) ishi. Ilgari bu probe ularning barchasini
    tekshirib, boot paytida (``db_instance`` hali init bo'lmaganda) yoki bitta
    eskirgan credential borligida **503** qaytarardi. Oracle VM'dagi watchdog
    503'ni "o'lik" deb sanab ``systemctl restart`` qilardi — natijada har ~8
    daqiqada SIGKILL restart loop.

    Endi: agar bu coroutine bajarilyapti bo'lsa, process tirik va event loop
    bloklanmagan — **doim 200**. Og'ir bog'liqlik tekshiruvi ``/readyz``da
    qoladi (u to'g'ri soft/blocking ajratadi).
    """
    now = datetime.now(timezone.utc)
    boot_age = (now - api_state._boot_at).total_seconds()

    checks: Dict[str, Any] = {
        "boot_age_sec": round(boot_age, 1),
        "event_loop": "responsive",
        "db_instance": "present" if api_state.db_instance is not None else "pending",
    }
    if api_state._last_heartbeat_at is not None:
        checks["heartbeat_age_sec"] = round(
            (now - api_state._last_heartbeat_at).total_seconds(), 1
        )
    else:
        checks["heartbeat_age_sec"] = None

    return JSONResponse(
        content={
            "status": "alive",
            "boot_age_sec": round(boot_age, 1),
            "checks": checks,
            "timestamp": now.isoformat(),
        },
        status_code=200,
    )


async def _probe_database() -> tuple[str, Optional[str]]:
    """Run readiness database check with a 3s bound."""
    if api_state.db_instance is None:
        return "no_instance", "database_not_initialized"
    try:
        conn = await asyncio.wait_for(
            api_state.db_instance.get_connection(), timeout=3.0
        )
        result = conn.execute("SELECT 1")
        if hasattr(result, "__await__"):
            await asyncio.wait_for(result, timeout=3.0)
        return "ok", None
    except asyncio.TimeoutError:
        return "timeout", "database_timeout"
    except Exception as exc:
        logger.error("Exception handled in %s", __name__, exc_info=True)
        return f"failed: {type(exc).__name__}", "database_unavailable"


async def _probe_userbot(
    *, control_plane_mode: bool, vm_service_mode: bool, runtime: Dict[str, Any]
) -> tuple[str, Optional[str]]:
    """Check Telethon userbot authorization without blocking bot-token readiness."""
    if control_plane_mode:
        return "delegated", None
    if vm_service_mode:
        userbot_ok = runtime.get("userbot_authorized") is True
    elif api_state.user_client is not None:
        try:
            userbot_ok = await asyncio.wait_for(
                api_state.user_client.is_user_authorized(), timeout=2.0
            )
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            userbot_ok = False
    else:
        userbot_ok = False
    return ("authorized" if userbot_ok else "unauthorized"), (
        None if userbot_ok else "userbot_unauthorized"
    )


async def _probe_amocrm(*, control_plane_mode: bool) -> tuple[str, Optional[str], Optional[str]]:
    """Check AmoCRM readiness concurrently within a tight 4s ceiling."""
    amocrm_ok = False
    amocrm = None
    detail: Optional[str] = None
    try:
        from src.api.routes.amocrm_integration import _get_amocrm_instance

        amocrm = _get_amocrm_instance()
        if amocrm and hasattr(amocrm, "check_connection"):
            amocrm_ok = await asyncio.wait_for(amocrm.check_connection(), timeout=4.0)
    except asyncio.TimeoutError:
        detail = "probe_timeout"
    except Exception as exc:
        logger.debug("[HEALTH] AmoCRM check: %s", exc)
    if amocrm_ok:
        return "connected", None, None
    detail = detail or (getattr(amocrm, "last_error", None) if amocrm else None)
    return "unavailable", detail, (None if control_plane_mode else "amocrm_unavailable")


@router.get("/readyz")
@router.get("/readyz/")
async def production_readiness_probe():
    """Cloud Run readiness probe (probes DB, userbot and AmoCRM concurrently)."""
    from src.services.core.agent_runtime import get_runtime_context
    from src.time_utils import get_local_now

    now = get_local_now()
    checks: Dict[str, Any] = {}
    problems: List[str] = []
    add_meta_health(checks, problems)
    runtime = get_runtime_context()
    scheduler_mode = runtime.get("scheduler_mode", "persistent")
    runtime_source = runtime.get("runtime_source", "unknown")
    control_plane_mode = scheduler_mode == "control-plane"
    vm_service_mode = runtime_source == "vm_service"

    (db_status, db_problem), (ub_status, ub_problem), (crm_status, crm_detail, crm_problem) = (
        await asyncio.gather(
            _probe_database(),
            _probe_userbot(
                control_plane_mode=control_plane_mode,
                vm_service_mode=vm_service_mode,
                runtime=runtime,
            ),
            _probe_amocrm(control_plane_mode=control_plane_mode),
        )
    )
    checks["database"] = db_status
    checks["userbot"] = ub_status
    checks["amocrm"] = crm_status
    if crm_detail:
        checks["amocrm_detail"] = crm_detail
    for problem in (db_problem, ub_problem, crm_problem):
        if problem:
            problems.append(problem)
    checks["runtime"] = runtime_source

    return _build_readiness_response(checks, problems, now)


def _build_readiness_response(
    checks: Dict[str, Any], problems: List[str], now: datetime
) -> JSONResponse:
    """Partition readiness problems into blocking vs degraded and serialize HTTP status."""
    soft = (
        STRICT_SOFT_DEPENDENCY_PROBLEMS
        if _strict_dependencies()
        else SOFT_DEPENDENCY_PROBLEMS
    )
    blocking = [p for p in problems if p not in soft]
    degraded = [p for p in problems if p in soft]
    serving = len(blocking) == 0
    status = "not_ready" if not serving else ("degraded" if degraded else "ready")
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
