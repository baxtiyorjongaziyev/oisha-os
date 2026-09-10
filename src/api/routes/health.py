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


@router.get("/readyz")
@router.get("/readyz/")
async def production_readiness_probe():
    """Cloud Run readiness probe."""
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
