"""Oisha-OS Enterprise API Server.

Shared utilities, global state, and FastAPI app creation.
Route handlers live in src/api/routes/.
"""
from __future__ import annotations

import asyncio
import hmac
import inspect
import json
import logging
import os
import time
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException, Query, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.services.core.agent_runtime import (
    collect_legacy_runtime_inventory,
    get_runtime_context,
    get_storage_health,
    set_runtime_context,
)
from src.settings import settings
from src.time_utils import get_local_now

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("OishaAPI")

# ---------------------------------------------------------------------------
# Global Bridges (set by boot.py before server starts)
# ---------------------------------------------------------------------------
command_queue: asyncio.Queue = asyncio.Queue()
outgoing_messages: asyncio.Queue = asyncio.Queue()
user_client: Any = None
db_instance: Any = None
msg_controller: Any = None
action_parser: Any = None
business_connections: Dict[str, Any] = {}
audit_agent: Any = None
amocrm_instance: Any = None

_userbot_group_access_snapshot: Dict[str, Any] = {
    "status": "pending",
    "checked_at": None,
    "groups": {},
    "topics": {},
}
_telegram_ai_ingress_status: Dict[str, Any] = {
    "mode": "unconfigured",
    "active": False,
}

# Health check cache
cached_status: Dict[str, Any] = {
    "status": "initializing",
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
_HEALTH_DB_TIMEOUT_SECONDS: float = 5.0
_health_db_snapshot_cache: Dict[str, Any] = {
    "recent_job_runs": [],
    "storage_counts": {},
    "updated_at": None,
}

# Heartbeat
_last_heartbeat_at: Optional[datetime] = None
_boot_at: datetime = datetime.now(timezone.utc)
_heartbeat_stale_seconds: int = 120

# CRM audit cache
cached_crm_audit: Dict[str, Any] = {
    "health_score": 98,
    "summary": "Audit kutilmoqda...",
    "timestamp": get_local_now().isoformat(),
}
system_activities: List[Dict[str, Any]] = [
    {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": "🚀 System Boot",
        "details": "Oisha-OS Strategic Intelligence is online and listening.",
        "type": "success",
    }
]
legacy_runtime_inventory_cache: Optional[List[Dict[str, Any]]] = None

# AmoCRM backfill
_call_backfill_task: Optional[asyncio.Task] = None
_call_backfill_last_status: Dict[str, Any] = {}

# AI analytics
_quality_analyzer: Any = None
_call_analytics: Any = None
_ai_task_manager: Any = None
_conversation_engine: Any = None

# CRM audit running flag
crm_audit_running: bool = False


# ---------------------------------------------------------------------------
# Shared Helper Functions
# ---------------------------------------------------------------------------

async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value).lstrip("\ufeff").strip()


def _secret_setting_text(value: Any) -> str:
    return _setting_text(value)


def set_telegram_ai_ingress_status(*, mode: str, active: bool) -> None:
    _telegram_ai_ingress_status.update({
        "mode": mode,
        "active": active,
        "updated_at": get_local_now().isoformat(),
    })


async def refresh_userbot_group_access_snapshot(client=None) -> Dict[str, Any]:
    """Read group/topic access through the already-connected production userbot."""
    global _userbot_group_access_snapshot
    active_client = client or user_client
    checked_at = get_local_now().isoformat()
    if active_client is None:
        _userbot_group_access_snapshot = {
            "status": "unavailable",
            "checked_at": checked_at,
            "groups": {},
            "topics": {},
        }
        return dict(_userbot_group_access_snapshot)

    groups: Dict[str, Dict[str, Any]] = {}
    resolved_entities: Dict[str, Any] = {}
    unresolved_groups: List[str] = []
    group_specs = {
        "crm_group": settings.CRM_GROUP_ID,
        "team_group": settings.TEAM_GROUP_ID,
        "projects_group": settings.PROJECTS_GROUP_ID,
    }
    tasks_group_label = "crm_group"
    if settings.TASKS_GROUP_ID:
        group_specs["tasks_group"] = settings.TASKS_GROUP_ID
        tasks_group_label = "tasks_group"
    for label, chat_id in group_specs.items():
        entry: Dict[str, Any] = {"configured": bool(chat_id), "chat_id": chat_id}
        if chat_id:
            try:
                entity = await asyncio.wait_for(
                    active_client.get_entity(chat_id), timeout=8.0
                )
                resolved_entities[label] = entity
                entry["readable"] = True
                entry["source"] = "entity_cache"
            except Exception as exc:
                entry["readable"] = False
                entry["error"] = type(exc).__name__
                unresolved_groups.append(label)
        groups[label] = entry

    dialogs_loaded = False
    if unresolved_groups:
        try:
            dialogs = await asyncio.wait_for(
                active_client.get_dialogs(limit=500), timeout=20.0
            )
            dialogs_loaded = True
            dialog_entities = {
                int(dialog.id): dialog.entity
                for dialog in dialogs
                if getattr(dialog, "id", None) is not None
            }
            for label in unresolved_groups:
                entity = dialog_entities.get(int(groups[label]["chat_id"]))
                if entity is None:
                    continue
                resolved_entities[label] = entity
                groups[label].update({"readable": True, "source": "dialogs"})
                groups[label].pop("error", None)
        except Exception as exc:
            for label in unresolved_groups:
                groups[label]["dialogs_error"] = type(exc).__name__

    for label in unresolved_groups:
        if not groups[label].get("readable") and dialogs_loaded:
            groups[label]["reason"] = "not_in_userbot_dialogs"

    for label, entity in resolved_entities.items():
        forum = getattr(entity, "forum", None)
        if isinstance(forum, bool):
            groups[label]["forum"] = forum

    topics: Dict[str, Dict[str, Any]] = {}
    topic_specs = {
        "crm": ("crm_group", settings.TOPIC_CRM_ID or settings.CRM_TOPIC_ID),
        "reports": ("crm_group", settings.TOPIC_REPORTS_ID),
        "tasks": (tasks_group_label, settings.TOPIC_TASKS_ID),
        "general": ("team_group", settings.TOPIC_GENERAL_ID),
        "kirim": ("team_group", settings.TOPIC_KIRIM_ID),
    }
    for label, (group_label, topic_id) in topic_specs.items():
        group_entry = groups[group_label]
        entry = {"configured": bool(topic_id), "topic_id": topic_id, "group": group_label}
        if topic_id and group_entry.get("readable"):
            try:
                messages = await asyncio.wait_for(
                    active_client.get_messages(
                        resolved_entities.get(group_label, group_entry["chat_id"]),
                        limit=1,
                        reply_to=topic_id,
                    ),
                    timeout=8.0,
                )
                entry["readable"] = True
                entry["sample_messages"] = len(messages or [])
            except Exception as exc:
                entry["readable"] = False
                entry["error"] = type(exc).__name__
                entry["reason"] = (
                    "invalid_or_deleted_topic"
                    if type(exc).__name__ == "BadRequestError"
                    else "topic_unreadable"
                )
        elif topic_id and not group_entry.get("readable"):
            entry["reason"] = "group_unreadable"
        topics[label] = entry

    required_groups = [e for e in groups.values() if e.get("configured")]
    required_topics = [e for e in topics.values() if e.get("configured")]
    _userbot_group_access_snapshot = {
        "status": (
            "ok"
            if all(e.get("readable") for e in required_groups + required_topics)
            else "degraded"
        ),
        "checked_at": checked_at,
        "groups": groups,
        "topics": topics,
    }
    return dict(_userbot_group_access_snapshot)


def mark_heartbeat() -> None:
    global _last_heartbeat_at
    _last_heartbeat_at = datetime.now(timezone.utc)


def add_activity(action: str, details: str = "", type: str = "info"):
    activity = {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": action,
        "details": details,
        "type": type,
    }
    system_activities.insert(0, activity)
    if len(system_activities) > 100:
        system_activities.pop()
    logger.info("[DASHBOARD] %s: %s", action, details)


def update_api_status(status: str, message: str):
    global cached_status
    cached_status = {
        "status": status,
        "message": message,
        "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_legacy_runtime_inventory() -> List[Dict[str, Any]]:
    global legacy_runtime_inventory_cache
    if legacy_runtime_inventory_cache is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        legacy_runtime_inventory_cache = collect_legacy_runtime_inventory(repo_root)
    return list(legacy_runtime_inventory_cache)


def _timestamp_to_iso(raw: Any) -> Optional[str]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _parse_state_json(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _get_cron_secret_value() -> str:
    cron_secret = _secret_setting_text(getattr(settings, "AMOCRM_CRON_SECRET", None))
    if cron_secret:
        return cron_secret
    return (os.environ.get("OISHA_API_SECRET") or "").strip()


def _is_authorized_cron_request(request: Request) -> bool:
    secret = _get_cron_secret_value()
    if not secret:
        return False
    auth_header = request.headers.get("Authorization", "")
    return hmac.compare_digest(auth_header, f"Bearer {secret}")


def _get_call_backfill_limit(limit: Optional[int] = None) -> int:
    raw_limit = (
        limit
        or getattr(settings, "AMOCRM_CALL_BACKFILL_LIMIT", None)
        or getattr(settings, "AMOCRM_CALL_ANALYSIS_LIMIT", 20)
        or 20
    )
    try:
        parsed = int(raw_limit)
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, 250))


def _get_call_backfill_interval_seconds() -> int:
    raw_minutes = getattr(settings, "AMOCRM_CALL_BACKFILL_INTERVAL_MINUTES", 60) or 60
    try:
        minutes = int(raw_minutes)
    except (TypeError, ValueError):
        minutes = 60
    return max(1, minutes) * 60


async def _get_db_instance():
    global db_instance
    if db_instance:
        return db_instance
    from src.database import Database
    db_instance = Database()
    await db_instance.init_instance()
    return db_instance


def _get_amocrm_instance():
    global amocrm_instance
    if amocrm_instance:
        return amocrm_instance
    from src.services.core.amocrm_sync import AmoCRMSync
    amocrm_instance = AmoCRMSync(
        subdomain=_setting_text(settings.AMOCRM_SUBDOMAIN),
        client_id=_setting_text(settings.AMOCRM_CLIENT_ID),
        client_secret=_secret_setting_text(settings.AMOCRM_CLIENT_SECRET),
        redirect_url=_setting_text(settings.AMOCRM_REDIRECT_URL),
    )
    return amocrm_instance


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(title="Oisha-OS Enterprise API")

# Include existing routers
from src.api import dashboard
from src.api.live_monitor import router as live_monitor_router
app.include_router(dashboard.router)
app.include_router(live_monitor_router)

# Include new route modules
from src.api.routes.health import router as health_router
from src.api.routes.telegram_routes import router as telegram_router
from src.api.routes.system_dashboard import router as system_router
from src.api.routes.sales_quality import router as sales_quality_router
from src.api.routes.chat_widget import router as chat_router
from src.api.routes.amocrm_integration import router as amocrm_router
from src.api.routes.openclaw_gateway import router as openclaw_router
from src.api.routes.ai_analytics import router as ai_router
from src.api.routes.erp_routes import router as erp_router
from src.api.routes.instagram_routes import router as instagram_router
from src.api.routes.product_suite import router as product_router
from src.api.routes.crm_dashboard import router as crm_dashboard_router

app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(system_router)
app.include_router(sales_quality_router)
app.include_router(chat_router)
app.include_router(amocrm_router)
app.include_router(openclaw_router)
app.include_router(ai_router)
app.include_router(erp_router)
app.include_router(instagram_router)
app.include_router(product_router)
app.include_router(crm_dashboard_router)

# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# CORS
_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
] or [
    "https://oisha.uz",
    "https://www.oisha.uz",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    allow_credentials=True,
)


# ---------------------------------------------------------------------------
# Telegram AI Webhook (kept here due to complexity of process_telegram_ai_update)
# ---------------------------------------------------------------------------

async def process_telegram_ai_update(update: Dict[str, Any]):
    """Central dispatcher for Bot API 10.0 AI updates."""
    from src.services.core.telegram_ai_features import (
        TelegramBotAPI10Client,
        classify_update as classify_bot_api_update,
        extract_guest_message_context,
        build_text_article_result,
    )

    update_type = classify_bot_api_update(update)
    logger.info("[TG-AI] update_type=%s", update_type)

    if update_type == "guest_message":
        guest_ctx = extract_guest_message_context(update)
        if not guest_ctx:
            return {"handled": False, "reason": "no_guest_context"}

        token = os.environ.get("BOT_TOKEN") or settings.BOT_TOKEN.get_secret_value()
        response_text = ""
        try:
            from src.openclaw_bridge import handle_openclaw_message
            response_text = await handle_openclaw_message(
                text=guest_ctx.guest_text,
                sender=guest_ctx.caller_user,
                sender_id=str(guest_ctx.caller_user),
                channel="telegram_business",
            )
        except Exception as exc:
            logger.error("[TG-AI] Agent error: %s", exc)

        if not response_text:
            response_text = "Oisha savolni qabul qildi, lekin hozir aniq javob shakllanmadi."

        result = build_text_article_result(
            response_text,
            title="Oisha javobi",
            description="Jon Branding AI agent javobi",
        )
        client = TelegramBotAPI10Client(token)
        sent = await client.answer_guest_query(guest_ctx.guest_query_id, result)
        return {"ok": True, "handled": True, "update_type": "guest_message", "sent_guest_message": sent}

    return {"handled": False, "reason": f"unhandled_update_type:{update_type}"}


@app.post("/webhook/telegram-ai")
async def telegram_ai_webhook(request: Request):
    """HTTPS ingress for Bot API 10.0 AI updates."""
    expected_secret = _secret_setting_text(settings.TELEGRAM_WEBHOOK_SECRET)
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret:
        raise HTTPException(status_code=503, detail="TELEGRAM_WEBHOOK_SECRET is required")
    if not hmac.compare_digest(expected_secret, received_secret):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    update = await request.json()
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram update payload")
    return await process_telegram_ai_update(update)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Legacy webhook alias."""
    return await telegram_ai_webhook(request)


# ---------------------------------------------------------------------------
# Lifespan + Background Tasks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Oisha-OS API Server Starting...")
    yield
    logger.info("Oisha-OS API Server Stopping...")


async def background_crm_audit_task():
    while True:
        try:
            try:
                from src.services.debug.crm_audit import AmoCRMAudit
                audit = AmoCRMAudit()
            except ImportError:
                await asyncio.sleep(900)
                continue
            results = await audit.run_full_audit()
            if results and "error" not in results:
                global cached_crm_audit
                cached_crm_audit = results
                logger.info("[API] CRM Audit complete. Health: %s%%", results.get("health_score"))
        except Exception as e:
            logger.error("[API] CRM Audit CRASH: %s", e)
        await asyncio.sleep(900)


# ---------------------------------------------------------------------------
# Bot-to-bot safeguards (used by process_telegram_update)
# ---------------------------------------------------------------------------

_bot2bot_tracker: Dict[str, list] = {}
BOT2BOT_MAX_ROUNDS = int(os.getenv("TELEGRAM_BOT_TO_BOT_MAX_ROUNDS", "1"))
BOT2BOT_COOLDOWN_SEC = int(os.getenv("TELEGRAM_BOT_TO_BOT_COOLDOWN_SECONDS", "300"))


def _bot2bot_allowed(from_id: int, chat_id: int) -> bool:
    key = f"{from_id}:{chat_id}"
    now = time.time()
    history = _bot2bot_tracker.get(key, [])
    history = [ts for ts in history if now - ts < BOT2BOT_COOLDOWN_SEC]
    if len(history) >= BOT2BOT_MAX_ROUNDS:
        return False
    history.append(now)
    _bot2bot_tracker[key] = history
    return True


def _bot2bot_skip_reason(from_user: Dict[str, Any], chat_id: int) -> str:
    if not from_user.get("is_bot"):
        return ""
    if not settings.TELEGRAM_BOT_TO_BOT_ENABLED:
        return "disabled"
    if not _bot2bot_allowed(from_user.get("id", 0), chat_id):
        return "rate_limit"
    return ""


def _business_message_skip_reason(message: Dict[str, Any]) -> str:
    if not isinstance(message, dict):
        return ""
    if message.get("sender_business_bot"):
        return "sender_business_bot"
    try:
        sender_id = int((message.get("from") or {}).get("id") or 0)
    except (TypeError, ValueError):
        sender_id = 0
    if not sender_id:
        return ""
    owner_ids = {int(getattr(settings, "OWNER_ID", 0) or 0)}
    connection_id = str(message.get("business_connection_id") or "")
    connection = business_connections.get(connection_id) or {}
    try:
        owner_ids.add(int(connection.get("user_id") or 0))
    except (TypeError, ValueError):
        pass
    if sender_id in owner_ids:
        return "business_owner"
    message_date = message.get("date")
    if not message_date:
        return ""
    try:
        message_age = datetime.now(timezone.utc).timestamp() - int(message_date)
        max_backlog_age = int(os.getenv("TELEGRAM_BUSINESS_MAX_BACKLOG_SECONDS", "300"))
    except (TypeError, ValueError):
        return ""
    return "stale_backlog" if message_age > max_backlog_age else ""


# ---------------------------------------------------------------------------
# Backward-compatible wrappers (tests and external code import from here)
# ---------------------------------------------------------------------------

async def _schedule_amocrm_call_backfill(
    db, *, reason: str = "unknown", limit: int = None, force: bool = False
):
    global _call_backfill_task
    if _call_backfill_task and not _call_backfill_task.done():
        if not force:
            return {"queued": False, "reason": "already_running"}

    if not force and db:
        try:
            last_started_raw = await db.get_state(_CALL_BACKFILL_LAST_STARTED_KEY)
            if last_started_raw:
                elapsed = time.time() - float(last_started_raw)
                interval = _get_call_backfill_interval_seconds()
                if elapsed < interval:
                    return {
                        "queued": False,
                        "reason": "throttled",
                        "retry_after_seconds": int(interval - elapsed),
                    }
        except Exception as exc:
            logger.debug("[backfill] throttle check failed: %s", exc)

    limit = _get_call_backfill_limit(limit)
    if db:
        try:
            await db.set_state(_CALL_BACKFILL_LAST_STARTED_KEY, str(time.time()))
        except Exception as exc:
            logger.debug("[backfill] failed to set start state: %s", exc)
    _call_backfill_task = asyncio.create_task(
        _run_amocrm_call_backfill(db, reason=reason, limit=limit)
    )
    return {"queued": True, "reason": reason, "limit": limit}


async def _build_amocrm_call_analysis_status(db) -> dict:
    last_started_raw = None
    last_finished_raw = None
    last_result_raw = ""
    last_error = ""

    if db:
        try:
            last_started_raw = await db.get_state(_CALL_BACKFILL_LAST_STARTED_KEY)
        except Exception as exc:
            logger.debug("[backfill] get state started failed: %s", exc)
        try:
            last_finished_raw = await db.get_state(_CALL_BACKFILL_LAST_FINISHED_KEY)
        except Exception as exc:
            logger.debug("[backfill] get state finished failed: %s", exc)
        try:
            last_result_raw = await db.get_state(_CALL_BACKFILL_LAST_RESULT_KEY) or ""
        except Exception as exc:
            logger.debug("[backfill] get state result failed: %s", exc)
        try:
            last_error = await db.get_state(_CALL_BACKFILL_LAST_ERROR_KEY) or ""
        except Exception as exc:
            logger.debug("[backfill] get state error failed: %s", exc)

    # Memory fallback
    from src.api.routes.state import api_state as _api_state
    mem = _call_backfill_last_status or {}
    if not mem:
        mem = getattr(_api_state, "_call_backfill_last_status", {}) or {}
    if not last_started_raw and mem.get("started_at"):
        last_started_raw = mem["started_at"]
    if not last_finished_raw and mem.get("finished_at"):
        last_finished_raw = mem["finished_at"]
    if not last_result_raw and mem.get("result"):
        last_result_raw = mem["result"]
    if not last_error and mem.get("error"):
        last_error = mem["error"]

    last_result = _parse_state_json(last_result_raw) if last_result_raw else {}

    # Totals
    totals = {}
    if db:
        try:
            conn = await db.get_connection()
            r = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN source='amocrm' THEN 1 ELSE 0 END) as amocrm, "
                "SUM(CASE WHEN recommended_tasks IS NOT NULL AND recommended_tasks != '[]' THEN 1 ELSE 0 END) as tasks "
                "FROM call_analyses"
            )
            if hasattr(r, "__await__"):
                r = await r
            row = r.fetchone() if hasattr(r, "fetchone") else None
            if row and hasattr(row, "__await__"):
                row = await row
            if row:
                if isinstance(row, dict):
                    totals = {
                        "total_analyses": row.get("total_analyses") or row.get("total", 0),
                        "amocrm_analyses": row.get("amocrm_analyses") or row.get("amocrm", 0),
                        "tasks_created": row.get("tasks_created") or row.get("tasks", 0),
                    }
                else:
                    totals = {
                        "total_analyses": row[0] if len(row) > 0 else 0,
                        "amocrm_analyses": row[1] if len(row) > 1 else 0,
                        "tasks_created": row[2] if len(row) > 2 else 0,
                    }
        except Exception as exc:
            logger.debug("[backfill] totals query failed: %s", exc)

    running = bool(_call_backfill_task and not _call_backfill_task.done())
    last_run = {}
    if last_started_raw or last_finished_raw:
        last_run["started_at"] = last_started_raw if isinstance(last_started_raw, str) and "T" in str(last_started_raw) else _timestamp_to_iso(last_started_raw)
        last_run["finished_at"] = last_finished_raw if isinstance(last_finished_raw, str) and "T" in str(last_finished_raw) else _timestamp_to_iso(last_finished_raw)
        if last_result:
            last_run["result"] = last_result
        if last_error:
            last_run["error"] = last_error

    return {
        "ok": not bool(last_error),
        "running": running,
        "last_run": last_run,
        "totals": totals,
    }


from src.api.routes.chat_widget import (  # noqa: F401
    lookup_user_by_phone,
    get_chat_history,
    send_chat_message,
    SendMessageRequest,
    CreateLeadRequest,
)
from src.api.routes.product_suite import oisha_product_suite  # noqa: F401
from src.api.routes.sales_quality import (  # noqa: F401
    get_sales_quality_overview,
    _build_sales_quality_payload,
    _build_empty_sales_quality,
    _safe_json_list,
    _row_to_dict,
    _score_to_risk,
    _format_duration,
    _avatar,
)
from src.api.routes.system_dashboard import build_health_snapshot  # noqa: F401
from src.api.routes.health import (  # noqa: F401
    liveness_probe,
    production_readiness_probe,
)
from src.api.routes.telegram_routes import telegram_group_access  # noqa: F401
from src.api.routes.openclaw_gateway import (  # noqa: F401
    openclaw_webhook,
    openclaw_health,
    v1_models,
    v1_chat_completions,
)
from src.api.routes.amocrm_integration import (  # noqa: F401
    _run_amocrm_call_backfill,
    _process_amocrm_event as process_amocrm_event,
    _CALL_BACKFILL_LAST_STARTED_KEY,
    _CALL_BACKFILL_LAST_FINISHED_KEY,
    _CALL_BACKFILL_LAST_RESULT_KEY,
    _CALL_BACKFILL_LAST_ERROR_KEY,
)
from src.agents.autonomous_sales_agent import AutonomousSalesAgent  # noqa: F401

# ---------------------------------------------------------------------------
# Entry Points
# ---------------------------------------------------------------------------

def run_api(host: str = "0.0.0.0", port: int = 8080):  # nosec
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_api()
