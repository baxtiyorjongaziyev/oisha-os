"""
Daemon tasks, health checks, cloud artifact restoration, and task spawn utilities.
"""
import asyncio
import base64
import logging
import os
from typing import Any, Dict, Optional

from src.settings import settings
from src.context import app_ctx

logger = logging.getLogger("OishaMain")

TN5_GROUP_ID = (
    settings.CRM_GROUP_ID if settings.CRM_GROUP_ID is not None else -1003820339529
)
TN5_TOPIC_ID = (
    settings.CRM_TOPIC_ID if settings.CRM_TOPIC_ID is not None else 7
)

_SHUTDOWN_DAEMON_TASK_NAMES = {
    "api_heartbeat",
    "background_monitor_task",
    "calendar_autoscan_loop",
    "command_processor",
    "crm_capacity_archiver_loop",
    "evolution_scheduler",
    "guest_bot_enable",
    "health_check_api",
    "oisha_brain_evolution",
    "shutdown_watcher",
    "telegram_group_access_probe_loop",
    "userbot_disconnect_watcher",
}

_SHUTDOWN_DAEMON_CORO_NAMES = {
    "_heartbeat_task",
    "_brain_evolution_loop",
    "_keepalive_loop",
    "_recv_loop",
    "_send_loop",
    "_update_loop",
    "ai_autopilot_loop",
    "background_crm_audit_task",
    "background_loop",
    "background_monitor_task",
    "background_scheduler",
    "calendar_autoscan_loop",
    "command_processor",
    "crm_capacity_archiver_loop",
    "crm_discipline_loop",
    "dm_lead_sync_task",
    "monitor_sessions",
    "run_health_check_api",
    "start_backlog_sync",
    "telegram_group_access_probe_loop",
}

_SHUTDOWN_DAEMON_CORO_SUFFIXES = {
    "AdminBot.start.<locals>.heartbeat",
    "EvolutionScheduler._run_loop",
    "LifespanOn.main",
    "MTProtoSender._keepalive_loop",
    "MTProtoSender._recv_loop",
    "MTProtoSender._send_loop",
    "UpdateMethods._update_loop",
}

def _is_shutdown_daemon_task(task: Any) -> bool:
    """Return whether a pending task is an infrastructure loop, not a handler."""
    task_name = getattr(task, "get_name", lambda: "")() or ""
    if task_name in _SHUTDOWN_DAEMON_TASK_NAMES:
        return True

    coro = getattr(task, "get_coro", lambda: None)()
    coro_name = getattr(coro, "__name__", "") or ""
    if coro_name in _SHUTDOWN_DAEMON_CORO_NAMES:
        return True

    coro_qualname = getattr(coro, "__qualname__", "") or ""
    return any(
        coro_qualname.endswith(suffix) for suffix in _SHUTDOWN_DAEMON_CORO_SUFFIXES
    )


def _shutdown_task_label(task: Any) -> str:
    """Build a secret-free task label for shutdown diagnostics."""
    task_name = getattr(task, "get_name", lambda: "")() or ""
    coro = getattr(task, "get_coro", lambda: None)()
    coro_qualname = getattr(coro, "__qualname__", "") or ""
    coro_name = getattr(coro, "__name__", "") or ""
    return f"{task_name}:{coro_qualname or coro_name or type(coro).__name__}"


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


_EXCLUDED_FOLDER_USER_CACHE: Dict[str, Any] = {"expires_at": 0.0, "user_ids": set()}
_EXCLUDED_FOLDER_CACHE_LOCK = asyncio.Lock()


def spawn_task(coro, name=None):
    """Create an asyncio task with semaphore limiting."""
    sem = app_ctx.task_semaphore
    if sem:
        async def _wrapped():
            async with sem:
                return await coro
        return asyncio.create_task(_wrapped(), name=name)
    return asyncio.create_task(coro, name=name)


def _restore_cloud_artifacts() -> None:
    """Materialize Cloud Run secrets into runtime files when provided."""
    os.makedirs("data", exist_ok=True)

    session_b64 = os.environ.get("USERBOT_SESSION_B64")
    session_path = os.path.join("data", "userbot_session.session")
    if session_b64 and not os.path.exists(session_path):
        try:
            with open(session_path, "wb") as fh:
                fh.write(base64.b64decode(session_b64))
            logger.info("[CLOUD] Restored userbot session from secret.")
        except Exception as exc:
            logger.error(f"[CLOUD] Failed to restore userbot session: {exc}")

    amocrm_token_json = os.environ.get("AMOCRM_TOKEN_JSON")
    amocrm_token_path = os.path.join("data", "amocrm_token.json")
    if amocrm_token_json and not os.path.exists(amocrm_token_path):
        try:
            with open(amocrm_token_path, "w", encoding="utf-8") as fh:
                fh.write(amocrm_token_json)
            logger.info("[CLOUD] Restored AmoCRM token file from secret.")
        except Exception as exc:
            logger.error(f"[CLOUD] Failed to restore AmoCRM token file: {exc}")

    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds_path = os.environ.get("GSHEET_CREDS_FILE", "service_account.json")
    if service_account_json and not os.path.exists(creds_path):
        try:
            with open(creds_path, "w", encoding="utf-8") as fh:
                fh.write(service_account_json)
            logger.info(f"[CLOUD] Restored Google credentials file at {creds_path}.")
        except Exception as exc:
            logger.error(f"[CLOUD] Failed to restore Google credentials file: {exc}")


async def background_monitor_task() -> None:
    """Barcha korporativ monitoring vazifalarini fonda ishga tushirish — wrapper."""
    from src.schedulers.background_monitor import BackgroundMonitor

    monitor = BackgroundMonitor(
        msg_controller=app_ctx.msg_controller,
        client=getattr(app_ctx, "client", None),
        bot_client=app_ctx.bot_runtime or app_ctx.bot_client,
        juma_notifier=app_ctx.juma_notifier,
        settings=settings,
        get_surgical_integration=getattr(app_ctx, "get_surgical_integration", None),
        TN5_GROUP_ID=TN5_GROUP_ID,
        hisobchi_analyst=app_ctx.hisobchi_analyst,
    )
    await monitor.run()


async def run_health_check_api() -> None:
    """Run the FastAPI health check server for Cloud Run compatibility."""
    from src.api.health import run_health_check_api as _impl
    await _impl()


async def stop_health_check_api(
    api_task: Optional[asyncio.Task], timeout_seconds: float = 5.0
) -> None:
    """Ask Uvicorn to finish its lifespan before the event loop is closed."""
    from src.api.health import stop_health_check_api as _impl
    await _impl(api_task, timeout_seconds)


async def _brain_evolution_loop():
    """Runs OishaBrain.evolve() every 6 hours to self-diagnose agent failures."""
    from src.schedulers.brain_evolution import brain_evolution_loop as _impl
    await _impl(oisha_brain=getattr(app_ctx, "oisha_brain", None))

