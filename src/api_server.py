import asyncio
import hmac
import uvicorn
import json
import inspect
from datetime import datetime, timezone
import logging
import os
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.services.core.agent_runtime import (
    collect_legacy_runtime_inventory,
    get_runtime_context,
    get_storage_health,
    set_runtime_context,
)
from src.services.core.amocrm_sync import AmoCRMSync
from src.services.core.amocrm_lead_enrichment import AmoCRMLeadEnricher
from src.services.core.call_analyzer import CallAnalyzer
from src.services.core.oisha_product_suite import build_oisha_sales_os_suite
from src.services.core.telegram_ai_features import (
    TelegramBotAPI10Client,
    build_live_feature_status,
    build_offline_feature_status,
    build_text_article_result,
    extract_guest_message_context,
)
from src.agents.autonomous_sales_agent import AutonomousSalesAgent
from src.settings import settings
from src.time_utils import get_local_now
from src.api import dashboard

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OishaAPI")

# Global Bridges
command_queue = asyncio.Queue()
outgoing_messages = asyncio.Queue()
user_client = None
db_instance = None
msg_controller = None
action_parser = None
business_connections = {}  # Store active Telegram Business connections
_userbot_group_access_snapshot: Dict[str, Any] = {
    "status": "pending",
    "checked_at": None,
    "groups": {},
    "topics": {},
}

# Health check cache
cached_status = {"status": "initializing", "timestamp": datetime.now(timezone.utc).isoformat()}
_HEALTH_DB_TIMEOUT_SECONDS = 5.0
_health_db_snapshot_cache: Dict[str, Any] = {
    "recent_job_runs": [],
    "storage_counts": {},
    "updated_at": None,
}


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


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
        entry = {
            "configured": bool(topic_id),
            "topic_id": topic_id,
            "group": group_label,
        }
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

    required_groups = [
        entry for entry in groups.values() if entry.get("configured")
    ]
    required_topics = [
        entry for entry in topics.values() if entry.get("configured")
    ]
    _userbot_group_access_snapshot = {
        "status": (
            "ok"
            if all(entry.get("readable") for entry in required_groups + required_topics)
            else "degraded"
        ),
        "checked_at": checked_at,
        "groups": groups,
        "topics": topics,
    }
    return dict(_userbot_group_access_snapshot)


app = FastAPI(title="Oisha-OS Enterprise API")

# Include Dashboard Router
app.include_router(dashboard.router)


def _setting_text(value: Any) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        value = getter()
    return str(value).lstrip("\ufeff").strip()


def _secret_setting_text(value: Any) -> str:
    return _setting_text(value)


# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Enable CORS for AmoCRM and trusted domains
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


@app.get("/")
async def root_status():
    """Health check for Google Cloud Run."""
    runtime = get_runtime_context()
    response = {
        "status": "online",
        "service": "Oisha-OS Enterprise",
        "version": "2.1.0",
        "timestamp": get_local_now().isoformat(),
        "runtime_source": runtime.get("runtime_source"),
        "service_name": runtime.get("service_name"),
        "runtime_id": runtime.get("runtime_id"),
        "userbot_authorized": runtime.get("userbot_authorized"),
    }
    response.update(cached_status)
    return response


@app.get("/api/oisha/product-suite")
async def oisha_product_suite():
    """Unified DeepSales + Metasell + Reportagram capability contract."""
    return build_oisha_sales_os_suite()


@app.get("/api/telegram/status")
async def telegram_status():
    """Diagnostic info for Telegram Bot API 10.0 integration."""
    try:
        token = os.environ.get("BOT_TOKEN") or settings.BOT_TOKEN.get_secret_value()
        client = TelegramBotAPI10Client(token)
        
        me = await client.get_me()
        webhook_info = await client.get_webhook_info()
        
        return {
            "status": "online",
            "bot": build_live_feature_status(me),
            "webhook": webhook_info,
            "api_10_ready": True
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
@app.get("/healthz")
@app.get("/healthz/")
async def liveness_probe():
    """Cloud Run liveness probe.

    Returns 200 when:
      - Event loop heartbeat is fresh (< _heartbeat_stale_seconds old), AND
      - Userbot client is connected (if present), AND
      - DB responds to a trivial query (if present).

    Returns 503 otherwise — Cloud Run livenessProbe will restart the container.

    Grace period: for the first 20s after boot we return 200 to avoid
    false-positive restarts while the loop finishes wiring up.
    """
    now = datetime.now(timezone.utc)
    boot_age = (now - _boot_at).total_seconds()
    checks: Dict[str, Any] = {
        "boot_age_sec": round(boot_age, 1),
        "heartbeat_age_sec": None,
        "userbot_connected": None,
        "db_ok": None,
    }
    problems: List[str] = []

    # Heartbeat freshness
    if _last_heartbeat_at is not None:
        hb_age = (now - _last_heartbeat_at).total_seconds()
        checks["heartbeat_age_sec"] = round(hb_age, 1)
        if hb_age > _heartbeat_stale_seconds:
            problems.append(f"heartbeat_stale({int(hb_age)}s)")
    elif boot_age > 120:
        # Loop should have ticked by now; if not, something is wrong.
        problems.append("no_heartbeat_ever")

    runtime = get_runtime_context()
    scheduler_mode = runtime.get("scheduler_mode")
    runtime_source = runtime.get("runtime_source", "unknown")
    control_plane_mode = scheduler_mode == "control-plane" or runtime_source == "vm_service"

    async def _probe_database() -> str:
        conn = await db_instance.get_connection()
        probe = conn.execute("SELECT 1")
        if hasattr(probe, "__await__"):
            probe = await probe
        fetchone = getattr(probe, "fetchone", None)
        if callable(fetchone):
            row = fetchone()
            if hasattr(row, "__await__"):
                await row
        return getattr(db_instance, "get_backend_name", lambda: "unknown")()

    dependency_timeout = float(os.getenv("HEALTH_DEPENDENCY_TIMEOUT_SECS", "3.0"))
    live_db_probe_default = "0" if runtime_source == "vm_service" else "1"
    live_db_probe = os.getenv(
        "HEALTH_LIVE_DB_PROBE", live_db_probe_default
    ).strip().lower() in {"1", "true", "yes", "on"}
    db_ok = True
    if db_instance is not None:
        if live_db_probe:
            try:
                backend_name = await asyncio.wait_for(
                    _probe_database(), timeout=dependency_timeout
                )
                checks["db_ok"] = True
                checks["db_backend"] = backend_name
                turso_required = bool(
                    settings.RUNNING_IN_CLOUD
                    and _setting_text(settings.TURSO_DATABASE_URL)
                    and _setting_text(settings.TURSO_AUTH_TOKEN)
                )
                if turso_required and backend_name != "turso":
                    db_ok = False
                    checks["db_ok"] = False
                    problems.append("turso_fallback")
            except asyncio.TimeoutError:
                logger.warning("[HEALTH] Database probe timed out")
                db_ok = False
                checks["db_ok"] = False
                checks["db_backend"] = getattr(
                    db_instance, "get_backend_name", lambda: "unknown"
                )()
                problems.append("db_timeout")
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                logger.warning(f"[HEALTH] Database connection failed: {e}")
                db_ok = False
                checks["db_ok"] = False
                checks["db_backend"] = getattr(
                    db_instance, "get_backend_name", lambda: "unknown"
                )()
                problems.append("db_failed")
        else:
            backend_name = getattr(db_instance, "get_backend_name", lambda: "unknown")()
            checks["db_ok"] = backend_name != "unknown"
            checks["db_backend"] = backend_name
            checks["db_probe"] = "skipped_runtime_cached"
            db_ok = checks["db_ok"]
    else:
        checks["db_ok"] = True

    # Check runtime flag, but fallback to live check if we have a client reference
    userbot_authorized = runtime.get("userbot_authorized", False)
    if not userbot_authorized and user_client:
        try:
            # Quick check if connected and authorized
            userbot_authorized = await asyncio.wait_for(
                user_client.is_user_authorized(), timeout=2.0
            )
        except Exception:
            userbot_authorized = False

    # Cloud Run status check
    telegram_bot_ok = True
    if control_plane_mode:
        # In control-plane mode, the bot itself is idle, just a proxy
        checks["telegram_bot"] = "delegated"
    else:
        # In persistent mode (Eagle Mode), the bot MUST be authorized
        telegram_bot_ok = userbot_authorized
        checks["telegram_bot"] = userbot_authorized

    # Check CRM connectivity. CRM OAuth can be degraded without making the
    # Cloud Run control plane unsafe to serve health/API traffic.
    crm_connected = False
    if (
        not control_plane_mode
        and msg_controller
        and hasattr(msg_controller, "crm")
        and msg_controller.crm
    ):
        try:
            # Check if AmoCRM is actually responding
            crm_connected = await asyncio.wait_for(
                msg_controller.crm.amocrm.check_connection(),
                timeout=dependency_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("[HEALTH] CRM probe timed out")
            crm_connected = False
        except Exception:
            crm_connected = False
    elif control_plane_mode:
        checks["crm_probe"] = "skipped_not_required"

    if control_plane_mode:
        crm_ok = True
    else:
        crm_ok = crm_connected or bool(runtime.get("crm_connected", False))

    # /healthz is the production rollout gate. Keep it honest so a broken
    # revision never receives traffic just because the HTTP server started.
    healthy = not problems and db_ok and telegram_bot_ok and crm_ok
    status_code = 200 if healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "unhealthy",
            "checks": {
                "database": db_ok,
                "database_backend": checks.get("db_backend"),
                "userbot": userbot_authorized,
                "telegram_bot": telegram_bot_ok,
                "crm": crm_connected,
                "crm_required": not control_plane_mode,
                "scheduler_mode": scheduler_mode,
                "problems": problems,
            },
            "timestamp": get_local_now().isoformat(),
        },
    )


@app.get("/api/telegram/ai-features")
async def telegram_ai_features(live: bool = False):
    """Bot API 10.0 feature readiness for Oisha.

    Offline mode shows code readiness. live=true also calls Telegram getMe to
    reveal which BotFather-side features are actually enabled for the bot.
    """
    token = _secret_setting_text(settings.BOT_TOKEN)
    payload = build_offline_feature_status()
    payload["configured"] = {
        "bot_token": bool(token),
        "webhook_secret": bool(_secret_setting_text(settings.TELEGRAM_WEBHOOK_SECRET)),
        "guest_mode_env": settings.TELEGRAM_AI_GUEST_MODE_ENABLED,
        "streaming_env": settings.TELEGRAM_AI_STREAMING_ENABLED,
        "bot_to_bot_env": settings.TELEGRAM_BOT_TO_BOT_ENABLED,
        "managed_bots_env": settings.TELEGRAM_MANAGED_BOTS_ENABLED,
        "mini_app_url": bool(settings.TELEGRAM_MINI_APP_URL),
    }

    if not live:
        payload["live"] = None
        return payload

    if not token:
        payload["live"] = {"ok": False, "reason": "BOT_TOKEN missing"}
        return JSONResponse(status_code=503, content=payload)

    client = TelegramBotAPI10Client(token)
    try:
        me = await client.get_me()
        webhook_info = await client.get_webhook_info()
        payload["live"] = {
            "ok": True,
            "capabilities": build_live_feature_status(me),
            "webhook": {
                "url_set": bool(webhook_info.get("url")),
                "pending_update_count": webhook_info.get("pending_update_count"),
                "allowed_updates": webhook_info.get("allowed_updates"),
                "last_error_message": webhook_info.get("last_error_message"),
            },
        }
        return payload
    except Exception as exc:
        logger.warning("[TELEGRAM AI] live feature probe failed: %s", exc)
        payload["live"] = {"ok": False, "reason": str(exc)}
        return JSONResponse(status_code=503, content=payload)


@app.post("/webhook/telegram-ai")
async def telegram_ai_webhook(request: Request):
    """Webhook endpoint for Bot API 10.0 AI features.

    Supports guest_message immediately. Other update kinds are acknowledged
    and surfaced in logs so enabling new BotFather features does not crash the
    production webhook while we progressively attach business flows.
    """
    expected_secret = _secret_setting_text(settings.TELEGRAM_WEBHOOK_SECRET)
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret:
        raise HTTPException(
            status_code=503,
            detail="TELEGRAM_WEBHOOK_SECRET is required before enabling this webhook",
        )
    if not hmac.compare_digest(expected_secret, received_secret):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    update = await request.json()
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="Invalid Telegram update payload")

    update_type = classify_update(update)

    # Route non-guest updates through the unified processor
    if update_type not in ("guest_message", "unknown"):
        if update_type in ("business_message", "business_connection", "managed_bot", "message"):
            try:
                await process_telegram_update(update, update_type)
                logger.info("[TELEGRAM AI] processed update type=%s", update_type)
                return {"ok": True, "handled": True, "update_type": update_type}
            except Exception as exc:
                logger.error("[TELEGRAM AI] failed update type=%s: %s", update_type, exc)
                return {"ok": True, "handled": False, "update_type": update_type, "error": str(exc)}
        logger.info("[TELEGRAM AI] accepted update type=%s (no handler)", update_type)
        return {"ok": True, "handled": False, "update_type": update_type}

    if update_type == "unknown":
        return {"ok": True, "handled": False, "update_type": "unknown"}

    guest_ctx = extract_guest_message_context(update)
    if not guest_ctx:
        return {
            "ok": True,
            "handled": False,
            "update_type": "guest_message",
            "reason": "missing_guest_query_id",
        }

    if not settings.TELEGRAM_AI_GUEST_MODE_ENABLED:
        return {
            "ok": True,
            "handled": False,
            "update_type": "guest_message",
            "reason": "guest_mode_disabled_by_env",
        }

    token = _secret_setting_text(settings.BOT_TOKEN)
    if not token or msg_controller is None:
        return {
            "ok": True,
            "handled": False,
            "update_type": "guest_message",
            "reason": "bot_token_or_controller_not_ready",
        }

    caller_user = guest_ctx.caller_user or {}
    caller_id = int(caller_user.get("id") or 0)
    caller_name = str(caller_user.get("first_name") or "Telegram foydalanuvchi")
    response_text = await msg_controller.get_response(
        user_id=caller_id,
        user_name=caller_name,
        message=guest_ctx.text,
        context={
            "source": "telegram_guest_mode",
            "update_id": guest_ctx.update_id,
            "guest_query_id": guest_ctx.guest_query_id,
            "caller_user": guest_ctx.caller_user,
            "caller_chat": guest_ctx.caller_chat,
        },
    )

    if not response_text:
        response_text = "Oisha savolni qabul qildi, lekin hozir aniq javob shakllanmadi."

    result = build_text_article_result(
        response_text,
        title="Oisha javobi",
        description="Jon Branding AI agent javobi",
    )
    client = TelegramBotAPI10Client(token)
    sent = await client.answer_guest_query(guest_ctx.guest_query_id, result)
    return {
        "ok": True,
        "handled": True,
        "update_type": "guest_message",
        "sent_guest_message": sent,
    }


# Global references
user_client = None
db_instance = None
audit_agent = None
amocrm_instance = None
_call_backfill_task: Optional[asyncio.Task] = None
_call_backfill_last_status: Dict[str, Any] = {}

_CALL_BACKFILL_LAST_STARTED_KEY = "amocrm_call_backfill:last_started_ts"
_CALL_BACKFILL_LAST_FINISHED_KEY = "amocrm_call_backfill:last_finished_ts"
_CALL_BACKFILL_LAST_RESULT_KEY = "amocrm_call_backfill:last_result"
_CALL_BACKFILL_LAST_ERROR_KEY = "amocrm_call_backfill:last_error"


def _get_amocrm_instance() -> AmoCRMSync:
    """Create the shared AmoCRM client with the full OAuth config."""
    global amocrm_instance
    if amocrm_instance:
        return amocrm_instance

    amocrm_instance = AmoCRMSync(
        subdomain=_setting_text(settings.AMOCRM_SUBDOMAIN),
        client_id=_setting_text(settings.AMOCRM_CLIENT_ID),
        client_secret=_secret_setting_text(settings.AMOCRM_CLIENT_SECRET),
        redirect_url=_setting_text(settings.AMOCRM_REDIRECT_URL),
    )
    return amocrm_instance


async def _get_db_instance():
    """Return runtime DB, creating it when the API is started standalone."""
    global db_instance
    if db_instance:
        return db_instance

    from src.database import Database

    db_instance = Database()
    await db_instance.init_instance()
    return db_instance


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


async def _fetch_amocrm_call_analysis_totals(runtime_db: Any) -> Dict[str, Any]:
    if not runtime_db:
        return {
            "total_analyses": 0,
            "amocrm_analyses": 0,
            "tasks_created": 0,
            "latest_analyzed_at": None,
        }

    try:
        conn = await runtime_db.get_connection()
        result = conn.execute(
            """
            SELECT
                COUNT(*) AS total_analyses,
                SUM(CASE WHEN source = 'amocrm' THEN 1 ELSE 0 END) AS amocrm_analyses,
                SUM(CASE WHEN task_id IS NOT NULL AND task_id != '' THEN 1 ELSE 0 END) AS tasks_created,
                MAX(COALESCE(analyzed_at, created_at)) AS latest_analyzed_at
            FROM call_analyses
            """
        )
        result = await _maybe_await(result)
        row = await _maybe_await(result.fetchone())
        data = _row_to_dict(
            row,
            [
                "total_analyses",
                "amocrm_analyses",
                "tasks_created",
                "latest_analyzed_at",
            ],
        )
        return {
            "total_analyses": int(data.get("total_analyses") or 0),
            "amocrm_analyses": int(data.get("amocrm_analyses") or 0),
            "tasks_created": int(data.get("tasks_created") or 0),
            "latest_analyzed_at": data.get("latest_analyzed_at"),
        }
    except Exception as exc:
        logger.warning("[CALL STATUS] Could not fetch call analysis totals: %s", exc)
        return {
            "total_analyses": 0,
            "amocrm_analyses": 0,
            "tasks_created": 0,
            "latest_analyzed_at": None,
            "error": str(exc),
        }


async def _build_amocrm_call_analysis_status(runtime_db: Any) -> Dict[str, Any]:
    last_started_raw = None
    last_finished_raw = None
    last_error = ""
    last_result_raw = ""
    if runtime_db:
        last_started_raw = await _maybe_await(
            runtime_db.get_state(_CALL_BACKFILL_LAST_STARTED_KEY, "")
        )
        last_finished_raw = await _maybe_await(
            runtime_db.get_state(_CALL_BACKFILL_LAST_FINISHED_KEY, "")
        )
        last_result_raw = await _maybe_await(
            runtime_db.get_state(_CALL_BACKFILL_LAST_RESULT_KEY, "")
        )
        last_error = await _maybe_await(
            runtime_db.get_state(_CALL_BACKFILL_LAST_ERROR_KEY, "")
        )

    last_result = _parse_state_json(last_result_raw)
    memory_status = dict(_call_backfill_last_status)

    started_at = (
        _timestamp_to_iso(last_started_raw)
        or last_result.get("started_at")
        or memory_status.get("started_at")
    )
    finished_at = (
        _timestamp_to_iso(last_finished_raw)
        or last_result.get("finished_at")
        or memory_status.get("finished_at")
    )
    if not last_result:
        last_result = dict(memory_status.get("result") or {})
    status_error = last_error or memory_status.get("error", "")

    return {
        "ok": True,
        "running": bool(_call_backfill_task and not _call_backfill_task.done()),
        "config": {
            "enabled": bool(getattr(settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True)),
            "webhook_enabled": bool(getattr(settings, "AMOCRM_CALL_ANALYSIS_ON_WEBHOOK", True)),
            "backfill_on_webhook": bool(getattr(settings, "AMOCRM_CALL_BACKFILL_ON_WEBHOOK", True)),
            "backfill_interval_minutes": int(
                getattr(settings, "AMOCRM_CALL_BACKFILL_INTERVAL_MINUTES", 60) or 60
            ),
            "backfill_limit": _get_call_backfill_limit(),
            "tasks_enabled": bool(getattr(settings, "ENABLE_AMOCRM_CALL_TASKS", True)),
            "task_due_hours": int(getattr(settings, "AMOCRM_CALL_TASK_DUE_HOURS", 24) or 24),
            "model": getattr(settings, "GEMINI_CALL_MODEL", ""),
        },
        "last_run": {
            "started_at": started_at,
            "finished_at": finished_at,
            "result": last_result,
            "error": status_error,
        },
        "totals": await _fetch_amocrm_call_analysis_totals(runtime_db),
    }


async def _run_amocrm_call_backfill(
    runtime_db: Any,
    *,
    reason: str,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    global _call_backfill_last_status

    run_limit = _get_call_backfill_limit(limit)
    started_at = datetime.now(timezone.utc)
    stats: Dict[str, Any] = {
        "leads_scanned": 0,
        "calls_processed": 0,
        "limit": run_limit,
        "reason": reason,
    }
    _call_backfill_last_status = {
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "result": {},
        "error": "",
    }

    try:
        logger.info(
            "[CALL BACKFILL] Starting scan: reason=%s limit=%s",
            reason,
            run_limit,
        )
        analyzer = CallAnalyzer(
            amocrm=_get_amocrm_instance(),
            db=runtime_db,
        )
        result = await analyzer.analyze_recent_calls(limit=run_limit)
        stats.update(result or {})
        stats["ok"] = True
        stats["started_at"] = started_at.isoformat()
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        _call_backfill_last_status = {
            "started_at": stats["started_at"],
            "finished_at": stats["finished_at"],
            "result": dict(stats),
            "error": "",
        }
        if runtime_db:
            await _maybe_await(
                runtime_db.set_state(
                    _CALL_BACKFILL_LAST_FINISHED_KEY,
                    str(datetime.now(timezone.utc).timestamp()),
                )
            )
            await _maybe_await(
                runtime_db.set_state(
                    _CALL_BACKFILL_LAST_RESULT_KEY,
                    json.dumps(stats, ensure_ascii=False),
                )
            )
        add_activity(
            "AmoCRM call backfill",
            f"scanned={stats.get('leads_scanned', 0)} processed={stats.get('calls_processed', 0)}",
            type="success",
        )
        logger.info("[CALL BACKFILL] Finished: %s", stats)
        return stats
    except Exception as exc:
        stats["ok"] = False
        stats["error"] = str(exc)
        _call_backfill_last_status = {
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": dict(stats),
            "error": str(exc),
        }
        logger.error("[CALL BACKFILL] Failed: %s", exc, exc_info=True)
        if runtime_db:
            await _maybe_await(runtime_db.set_state(_CALL_BACKFILL_LAST_ERROR_KEY, str(exc)))
        add_activity("AmoCRM call backfill", str(exc)[:120], type="error")
        return stats


async def _schedule_amocrm_call_backfill(
    runtime_db: Any,
    *,
    reason: str,
    limit: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    global _call_backfill_task

    if not getattr(settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True):
        return {"queued": False, "reason": "call_analysis_disabled"}

    if not force and not getattr(settings, "AMOCRM_CALL_BACKFILL_ON_WEBHOOK", True):
        return {"queued": False, "reason": "backfill_disabled"}

    if _call_backfill_task and not _call_backfill_task.done():
        return {"queued": False, "reason": "already_running"}

    now_ts = datetime.now(timezone.utc).timestamp()
    if not force and runtime_db:
        try:
            last_started_raw = await _maybe_await(
                runtime_db.get_state(_CALL_BACKFILL_LAST_STARTED_KEY, "0")
            )
            last_started = float(last_started_raw or 0)
        except (TypeError, ValueError):
            last_started = 0.0
        except Exception as exc:
            logger.warning("[CALL BACKFILL] Could not read throttle state: %s", exc)
            last_started = 0.0

        interval_seconds = _get_call_backfill_interval_seconds()
        if now_ts - last_started < interval_seconds:
            return {
                "queued": False,
                "reason": "throttled",
                "retry_after_seconds": int(interval_seconds - (now_ts - last_started)),
            }

    if runtime_db:
        try:
            await _maybe_await(
                runtime_db.set_state(_CALL_BACKFILL_LAST_STARTED_KEY, str(now_ts))
            )
        except Exception as exc:
            logger.warning("[CALL BACKFILL] Could not write throttle state: %s", exc)

    run_limit = _get_call_backfill_limit(limit)
    _call_backfill_task = asyncio.create_task(
        _run_amocrm_call_backfill(runtime_db, reason=reason, limit=run_limit)
    )
    return {"queued": True, "reason": reason, "limit": run_limit}


# [HEALTHZ] Liveness heartbeat — main event loop updates this via mark_heartbeat().
# Deploy smoke checks read /healthz/; if heartbeat is stale, the probe fails
# and the container is restarted (recovering from event-loop deadlocks).
_last_heartbeat_at: Optional[datetime] = None
_boot_at: datetime = datetime.now(timezone.utc)
_heartbeat_stale_seconds: int = 120  # 2 min: loop silent longer than this => unhealthy


def mark_heartbeat() -> None:
    """Called by the main event loop every ~60s to prove liveness."""
    global _last_heartbeat_at
    _last_heartbeat_at = datetime.now(timezone.utc)



# --- DASHBOARD CACHE ---
cached_status: Dict[str, Any] = {
    "status": "offline",
    "message": "Tizim tayyorlanmoqda...",
    "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S"),
}

# --- CRM AUDIT CACHE ---
cached_crm_audit: Dict[str, Any] = {
    "health_score": 98,
    "summary": "Audit kutilmoqda...",
    "timestamp": get_local_now().isoformat(),
}
# --- DASHBOARD ACTIVITY FEED ---
system_activities: List[Dict[str, Any]] = [
    {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": "🚀 System Boot",
        "details": "Oisha-OS Strategic Intelligence is online and listening.",
        "type": "success",
    }
]

legacy_runtime_inventory_cache: Optional[List[Dict[str, Any]]] = None



def add_activity(action: str, details: str = "", type: str = "info"):
    """Tizimdagi amallarni Dashboard uchun ro'yxatga olish."""
    activity = {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": action,
        "details": details,
        "type": type,  # info, success, warning, error, thinking
    }
    system_activities.insert(0, activity)
    # Oxirgi 100 ta amalni saqlash (ko'proq ko'rinishi uchun)
    if len(system_activities) > 100:
        system_activities.pop()
    logger.info(f"📊 [DASHBOARD] {action}: {details}")


def get_legacy_runtime_inventory() -> List[Dict[str, Any]]:
    global legacy_runtime_inventory_cache
    if legacy_runtime_inventory_cache is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        legacy_runtime_inventory_cache = collect_legacy_runtime_inventory(repo_root)
    return list(legacy_runtime_inventory_cache)


async def build_health_snapshot(
    include_inventory: bool = False, include_traces: bool = False
) -> Dict[str, Any]:
    global _health_db_snapshot_cache
    runtime = get_runtime_context()
    db_path = runtime.get("state_db_path") or getattr(db_instance, "db_path", None)
    recent_job_runs: List[Dict[str, Any]] = []
    recent_agent_actions: List[Dict[str, Any]] = []
    storage_counts: Dict[str, int] = {}
    storage_cache_used = False

    if db_instance:
        try:
            async def load_storage_snapshot() -> Dict[str, Any]:
                return {
                    "recent_job_runs": await db_instance.get_recent_job_runs(limit=10),
                    "storage_counts": await db_instance.get_storage_counts(),
                    "updated_at": get_local_now().isoformat(),
                }

            _health_db_snapshot_cache = await asyncio.wait_for(
                load_storage_snapshot(),
                timeout=_HEALTH_DB_TIMEOUT_SECONDS,
            )
            recent_job_runs = list(_health_db_snapshot_cache["recent_job_runs"])
            storage_counts = dict(_health_db_snapshot_cache["storage_counts"])
        except asyncio.TimeoutError:
            storage_cache_used = True
            logger.warning("[API] Storage health query timed out; using cached snapshot.")
        except Exception as exc:
            storage_cache_used = True
            logger.warning(f"[API] Could not fetch storage health: {exc}")

        if storage_cache_used:
            recent_job_runs = list(
                _health_db_snapshot_cache.get("recent_job_runs", [])
            )
            storage_counts = dict(
                _health_db_snapshot_cache.get("storage_counts", {})
            )

        if include_traces:
            try:
                recent_agent_actions = await asyncio.wait_for(
                    db_instance.get_recent_agent_actions(limit=25),
                    timeout=_HEALTH_DB_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning("[API] Agent action query timed out.")
            except Exception as exc:
                logger.warning(f"[API] Could not fetch agent actions: {exc}")

    storage_health = get_storage_health(
        db_path,
        recent_job_runs=recent_job_runs,
        backend=runtime.get("state_backend", "sqlite"),
        storage_counts=storage_counts,
    )
    storage_health["cached"] = storage_cache_used
    storage_health["cache_updated_at"] = _health_db_snapshot_cache.get("updated_at")

    snapshot = {
        "timestamp": get_local_now().isoformat(),
        "status": cached_status.copy(),
        "runtime": runtime,
        "storage": storage_health,
        "telegram_userbot_access": dict(_userbot_group_access_snapshot),
    }
    if include_inventory:
        snapshot["legacy_runtime_inventory"] = get_legacy_runtime_inventory()
    if include_traces:
        snapshot["agent_actions"] = recent_agent_actions
    return snapshot


@app.get("/api/system/status")
async def get_system_status():
    global cached_status, cached_crm_audit
    # Update health score from audit cache
    data = cached_status.copy()
    data["crm_health"] = f"{cached_crm_audit.get('health_score', 98)}%"
    runtime = get_runtime_context()
    data["runtime_source"] = runtime.get("runtime_source")
    data["service_name"] = runtime.get("service_name")
    data["state_backend"] = runtime.get("state_backend")
    data["userbot_authorized"] = runtime.get("userbot_authorized")
    return data


def update_api_status(status: str, message: str):
    """Updates the thread-safe status cache for the dashboard."""
    global cached_status
    cached_status = {
        "status": status,
        "message": message,
        "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/system/runtime")
async def get_system_runtime():
    return {
        "timestamp": get_local_now().isoformat(),
        "runtime": get_runtime_context(),
        "legacy_runtime_inventory": get_legacy_runtime_inventory(),
    }


@app.get("/api/system/health")
async def get_system_health():
    snapshot = await build_health_snapshot()
    snapshot["crm_audit"] = cached_crm_audit
    return snapshot


@app.get("/api/system/traces")
async def get_system_traces():
    snapshot = await build_health_snapshot(include_traces=True)
    return {
        "timestamp": snapshot["timestamp"],
        "runtime": snapshot["runtime"],
        "job_runs": snapshot["storage"].get("recent_job_runs", []),
        "agent_actions": snapshot.get("agent_actions", []),
    }


@app.get("/api/system/inventory")
async def get_system_inventory():
    snapshot = await build_health_snapshot(include_inventory=True)
    return {
        "timestamp": snapshot["timestamp"],
        "runtime": snapshot["runtime"],
        "legacy_runtime_inventory": snapshot.get("legacy_runtime_inventory", []),
    }


@app.get("/api/system/activity")
async def get_activity():
    return {
        "activities": system_activities,
        "stats": {
            "uptime": "online",
            "mode": "Autonomous v2.1",
            "server": "Oisha-OS Local Server",
        },
    }


@app.get("/api/system/stats")
async def get_stats():
    """Dashboard uchun biznes ko'rsatkichlarni hisoblash."""
    if not db_instance:
        return {"error": "DB not found"}

    try:
        stats = await db_instance.get_today_stats()
        # Enriched metrics for Premium Dashboard from REAL CACHE
        global cached_crm_audit
        health = cached_crm_audit.get("health_score", 0)

        stats["crm_health"] = f"{health}%"
        stats["leads_enriched_today"] = stats.get("leads_found", 0)

        # Qualitative performance labels
        if health >= 90:
            stats["automation_efficiency"] = "Exceptional"
        elif health >= 75:
            stats["automation_efficiency"] = "High"
        elif health >= 50:
            stats["automation_efficiency"] = "Nominal"
        else:
            stats["automation_efficiency"] = "Action Required"

        stats["last_audit"] = cached_crm_audit.get(
            "timestamp", get_local_now().isoformat()
        )
        return stats
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        return {"leads_found": 0, "messages_synced": 0, "status": "Ready"}


@app.get("/dashboard/sales-quality")
async def sales_quality_dashboard():
    """Metasell-style sales quality dashboard page."""
    dashboard_path = os.path.join(static_dir, "sales-quality.html")
    if not os.path.exists(dashboard_path):
        return JSONResponse(
            status_code=404,
            content={
                "status": "not_found",
                "message": "Sales quality dashboard is not deployed yet.",
            },
        )
    return FileResponse(dashboard_path)


def _safe_json_list(value: Any) -> List[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _row_to_dict(row: Any, columns: List[str]) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    keys = getattr(row, "keys", None)
    if callable(keys):
        return {key: row[key] for key in keys()}
    return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}


async def _fetch_call_analysis_rows(limit: int = 500) -> List[Dict[str, Any]]:
    if not db_instance:
        return []

    conn = await db_instance.get_connection()
    result = conn.execute(
        """
        SELECT
            call_id, lead_id, manager_id, manager_name, client_name,
            duration_seconds, overall_score, category, scores, summary,
            strengths, weaknesses, client_mood, client_interest_level,
            objections, outcome, next_steps, recommended_tasks,
            transcript, audio_url, caller_phone, task_id, task_created_at,
            source, analyzed_at, created_at
        FROM call_analyses
        ORDER BY COALESCE(analyzed_at, created_at) DESC
        LIMIT ?
        """,
        (limit,),
    )
    if hasattr(result, "__await__"):
        result = await result

    fetchall = getattr(result, "fetchall", None)
    rows = fetchall() if callable(fetchall) else []
    if hasattr(rows, "__await__"):
        rows = await rows

    description = getattr(result, "description", None) or []
    columns = [str(item[0]) for item in description]
    if not columns:
        columns = [
            "call_id",
            "lead_id",
            "manager_id",
            "manager_name",
            "client_name",
            "duration_seconds",
            "overall_score",
            "category",
            "scores",
            "summary",
            "strengths",
            "weaknesses",
            "client_mood",
            "client_interest_level",
            "objections",
            "outcome",
            "next_steps",
            "recommended_tasks",
            "transcript",
            "audio_url",
            "caller_phone",
            "task_id",
            "task_created_at",
            "source",
            "analyzed_at",
            "created_at",
        ]
    return [_row_to_dict(row, columns) for row in rows]


def _score_to_risk(score: Optional[int]) -> str:
    if score is None:
        return "Noma'lum"
    if score < 60:
        return "Yuqori"
    if score < 75:
        return "O'rta"
    return "Past"


def _format_duration(seconds: Any) -> str:
    try:
        seconds = max(int(seconds or 0), 0)
    except (TypeError, ValueError):
        seconds = 0
    minutes, rest = divmod(seconds, 60)
    return f"{minutes:02d}:{rest:02d}"


def _avatar(name: str) -> str:
    clean = "".join(part[:1] for part in (name or "NA").split()[:2]).upper()
    return clean or "NA"


def _build_empty_sales_quality(generated_at: str, reason: str) -> Dict[str, Any]:
    return {
        "generated_at": generated_at,
        "source": "real_call_analytics",
        "real_data": False,
        "status": "waiting_for_real_call_analysis",
        "message": reason,
        "period": "Real qo'ng'iroq tahlili",
        "team": {
            "quality_score": None,
            "trend": "--",
            "calls_total": 0,
            "calls_analyzed": 0,
            "connected_calls": 0,
            "missed_calls": 0,
            "sales_count": 0,
            "conversion": 0,
            "avg_call_minutes": 0,
            "callback_agreed": 0,
        },
        "managers": [],
        "outcomes": [],
        "radar": [],
        "loss_reasons": [],
        "weaknesses": [],
        "recommendations": [
            "Real dashboard uchun qo'ng'iroq transcript/audio tahlili `call_analyses` jadvaliga yozilishi kerak.",
            "AmoCRM/telefoniya yoki MetaSell eksporti ulangandan keyin bu sahifa faqat o'sha real yozuvlarni ko'rsatadi.",
        ],
        "calls": [],
        "assistant_answers": [
            {
                "question": "Bu dashboard realmi?",
                "answer": "Hozircha real qo'ng'iroq tahlili yozuvi topilmadi. Shu sababli Oisha fake ball va menejer reytingi chiqarmayapti.",
            }
        ],
    }


def _build_sales_quality_payload(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    generated_at = get_local_now().isoformat()
    analyzed = [row for row in rows if row.get("overall_score") is not None]
    if not analyzed:
        return _build_empty_sales_quality(
            generated_at,
            "Real qo'ng'iroq tahlili topilmadi. Fake raqamlar o'chirildi.",
        )

    scores = [int(row.get("overall_score") or 0) for row in analyzed]
    outcome_counts = Counter(str(row.get("outcome") or "unknown") for row in analyzed)
    sales_count = (
        outcome_counts.get("sale", 0)
        + outcome_counts.get("sold", 0)
        + outcome_counts.get("sotuv", 0)
    )
    callback_count = outcome_counts.get("callback", 0) + outcome_counts.get(
        "follow_up", 0
    )
    total_duration = sum(int(row.get("duration_seconds") or 0) for row in analyzed)

    by_manager: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in analyzed:
        by_manager[str(row.get("manager_name") or "Noma'lum manager")].append(row)

    managers = []
    for manager_name, manager_rows in by_manager.items():
        manager_scores = [int(row.get("overall_score") or 0) for row in manager_rows]
        manager_sales = sum(
            1
            for row in manager_rows
            if str(row.get("outcome") or "") in {"sale", "sold", "sotuv"}
        )
        managers.append(
            {
                "name": manager_name,
                "role": "Sales manager",
                "score": round(sum(manager_scores) / len(manager_scores)),
                "calls": len(manager_rows),
                "connected": len(manager_rows),
                "missed": 0,
                "sales": manager_sales,
                "conversion": round(manager_sales / max(len(manager_rows), 1) * 100, 1),
                "trend": "real",
                "avatar": _avatar(manager_name),
            }
        )
    managers.sort(key=lambda item: item["score"], reverse=True)

    outcome_labels = {
        "sale": "Sotuv bo'ldi",
        "sold": "Sotuv bo'ldi",
        "sotuv": "Sotuv bo'ldi",
        "follow_up": "Follow-up kerak",
        "callback": "Qayta qo'ng'iroq kelishildi",
        "lost": "Yo'qotildi",
        "unknown": "Natija belgilanmagan",
    }
    outcome_colors = ["#2f80ed", "#00a676", "#f2994a", "#eb5757", "#7f8ea3"]
    outcomes = [
        {
            "label": outcome_labels.get(outcome, outcome),
            "value": count,
            "color": outcome_colors[index % len(outcome_colors)],
        }
        for index, (outcome, count) in enumerate(outcome_counts.most_common())
    ]

    metric_scores: Dict[str, List[int]] = defaultdict(list)
    weakness_counts: Counter[str] = Counter()
    objection_counts: Counter[str] = Counter()
    for row in analyzed:
        for score in _safe_json_list(row.get("scores")):
            metric = score.get("metric") if isinstance(score, dict) else None
            value = score.get("score") if isinstance(score, dict) else None
            if metric and value is not None:
                metric_scores[str(metric)].append(int(value))
        weakness_counts.update(
            str(item) for item in _safe_json_list(row.get("weaknesses")) if item
        )
        objection_counts.update(
            str(item) for item in _safe_json_list(row.get("objections")) if item
        )

    radar = [
        {
            "label": metric.replace("_", " ").title(),
            "score": round(sum(values) / len(values)),
        }
        for metric, values in metric_scores.items()
    ]

    weaknesses = [
        {
            "label": label,
            "count": count,
            "severity": "critical" if count >= 3 else "warning",
        }
        for label, count in weakness_counts.most_common(8)
    ]
    loss_reasons = [
        {
            "title": label,
            "count": count,
            "impact": "high" if count >= 3 else "medium",
            "fix": f"{label} bo'yicha real suhbatlardan kelgan signal. Managerga aniq corrective task ochish kerak.",
        }
        for label, count in (weakness_counts + objection_counts).most_common(6)
    ]

    recommendations = []
    if weakness_counts:
        top_weakness, top_count = weakness_counts.most_common(1)[0]
        recommendations.append(
            f"Eng ko'p takrorlangan zaif joy: {top_weakness} ({top_count} ta real signal)."
        )
    if callback_count:
        recommendations.append(
            f"{callback_count} ta follow-up/callback real suhbatdan chiqdi; CRM tasklari borligini tekshiring."
        )
    if sales_count == 0:
        recommendations.append(
            "Real tahlil qilingan qo'ng'iroqlarda sotuv natijasi belgilanmagan; outcome mappingni tekshiring."
        )

    calls = []
    for row in analyzed[:12]:
        score = int(row.get("overall_score") or 0)
        client = row.get("client_name") or (
            f"Lead #{row.get('lead_id')}" if row.get("lead_id") else "Noma'lum mijoz"
        )
        calls.append(
            {
                "client": client,
                "manager": row.get("manager_name") or "Noma'lum manager",
                "score": score,
                "result": outcome_labels.get(
                    str(row.get("outcome") or "unknown"),
                    str(row.get("outcome") or "unknown"),
                ),
                "duration": _format_duration(row.get("duration_seconds")),
                "summary": row.get("summary")
                or "Real tahlil yozuvi bor, lekin summary bo'sh.",
                "risk": _score_to_risk(score),
            }
        )

    average_score = round(sum(scores) / len(scores), 1)
    return {
        "generated_at": generated_at,
        "source": "real_call_analytics",
        "real_data": True,
        "status": "ok",
        "period": "Real qo'ng'iroq tahlillari",
        "team": {
            "quality_score": average_score,
            "trend": "real",
            "calls_total": len(rows),
            "calls_analyzed": len(analyzed),
            "connected_calls": len(analyzed),
            "missed_calls": 0,
            "sales_count": sales_count,
            "conversion": round(sales_count / max(len(analyzed), 1) * 100, 1),
            "avg_call_minutes": round(total_duration / max(len(analyzed), 1) / 60, 1),
            "callback_agreed": callback_count,
        },
        "managers": managers,
        "outcomes": outcomes,
        "radar": radar,
        "loss_reasons": loss_reasons,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "calls": calls,
        "assistant_answers": [
            {
                "question": "Bu dashboard realmi?",
                "answer": f"Ha. Bu sahifa `call_analyses` jadvalidagi {len(analyzed)} ta real tahlil yozuvidan hisoblandi.",
            }
        ],
    }


@app.get("/api/sales-quality/overview")
async def get_sales_quality_overview():
    """Return only real sales-call QA data. Never synthesize demo metrics."""
    try:
        rows = await _fetch_call_analysis_rows()
    except Exception as exc:
        logger.error(f"[SALES QUALITY] Real data read failed: {exc}")
        return _build_empty_sales_quality(
            get_local_now().isoformat(),
            f"Real call analytics o'qishda xato: {type(exc).__name__}",
        )
    return _build_sales_quality_payload(rows)


class SalesQualityAnalysisRequest(BaseModel):
    secret_key: str
    call_id: str
    lead_id: Optional[int] = None
    manager_id: Optional[int] = None
    manager_name: str = ""
    client_name: Optional[str] = None
    duration_seconds: int = 0
    overall_score: int
    category: Optional[str] = None
    scores: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    client_mood: str = "neutral"
    client_interest_level: int = 0
    objections_raised: List[str] = Field(default_factory=list)
    outcome: str = "unknown"
    next_steps: List[str] = Field(default_factory=list)
    recommended_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    transcript: str = ""
    audio_url: Optional[str] = None
    source: str = "external"
    analyzed_at: Optional[str] = None


@app.post("/api/sales-quality/ingest-analysis")
async def ingest_sales_quality_analysis(data: SalesQualityAnalysisRequest):
    """Store a real external call analysis result for the dashboard."""
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(data.secret_key, expected_secret):
        return JSONResponse(
            status_code=401, content={"status": "error", "message": "Unauthorized"}
        )
    if not db_instance:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Database not connected"},
        )

    score = max(0, min(int(data.overall_score), 100))
    now = get_local_now().isoformat()
    analyzed_at = data.analyzed_at or now
    category = data.category or (
        "excellent"
        if score >= 90
        else "good" if score >= 80 else "average" if score >= 60 else "poor"
    )

    conn = await db_instance.get_connection()
    result = conn.execute(
        """
        INSERT OR REPLACE INTO call_analyses (
            call_id, lead_id, manager_id, manager_name, client_name,
            duration_seconds, overall_score, category, scores, summary,
            strengths, weaknesses, client_mood, client_interest_level,
            objections, outcome, next_steps, recommended_tasks,
            transcript, audio_url, source, analyzed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.call_id,
            data.lead_id,
            data.manager_id,
            data.manager_name,
            data.client_name,
            max(int(data.duration_seconds or 0), 0),
            score,
            category,
            json.dumps(data.scores, ensure_ascii=False),
            data.summary,
            json.dumps(data.strengths, ensure_ascii=False),
            json.dumps(data.weaknesses, ensure_ascii=False),
            data.client_mood,
            max(0, min(int(data.client_interest_level or 0), 100)),
            json.dumps(data.objections_raised, ensure_ascii=False),
            data.outcome,
            json.dumps(data.next_steps, ensure_ascii=False),
            json.dumps(data.recommended_tasks, ensure_ascii=False),
            data.transcript,
            data.audio_url,
            data.source,
            analyzed_at,
            now,
        ),
    )
    if hasattr(result, "__await__"):
        await result
    commit = getattr(conn, "commit", None)
    if callable(commit):
        committed = commit()
        if hasattr(committed, "__await__"):
            await committed

    return {"status": "ok", "call_id": data.call_id, "source": "real_call_analytics"}


class CreateLeadRequest(BaseModel):
    name: str
    phone: str
    note: Optional[str] = None
    secret_key: str


class SendMessageRequest(BaseModel):
    user_id: Any
    text: str
    secret_key: str
    model: Optional[str] = settings.GEMINI_CALL_MODEL


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Oisha-OS API Server Starting...")
    yield
    # Shutdown logic
    logger.info("Oisha-OS API Server Stopping...")


@app.get("/api/chat/lookup/{phone}")
async def lookup_user_by_phone(phone: str, secret_key: str):
    """AmoCRM mijoz telefoni orqali Telegram ID sini topish."""
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(secret_key, expected_secret):
        return {"error": "Unauthorized"}

    if not db_instance:
        return {"error": "Database not connected"}

    user_id = await db_instance.get_user_id_by_phone(phone)
    if user_id:
        return {"user_id": user_id, "status": "found"}
    return {"status": "not_found"}


@app.get("/api/chat/history/{user_id}")
async def get_chat_history(user_id: int, secret_key: str):
    """Mijoz bilan shaxsiy suhbat tarixini widget uchun qaytarish."""
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(secret_key, expected_secret):
        return {"error": "Unauthorized"}

    if not db_instance:
        return {"error": "Database not connected"}

    # Get history from DB (Enterprise v2.1+)
    # This includes both user messages and bot/admin replies
    history = await db_instance.get_recent_messages(user_id, limit=30)
    return {"history": history}


@app.post("/api/chat/send")
async def send_chat_message(request: SendMessageRequest):
    """AmoCRM widgetidan kelgan xabarni Telegramga yuborish (Queued)."""
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(
        request.secret_key, expected_secret
    ):
        return {"error": "Unauthorized"}

    # Push to queue for Main Thread execution
    command_queue.put_nowait(
        {
            "cmd": "send_message",
            "user_id": request.user_id,
            "text": request.text,
            "model": request.model,
        }
    )

    return {"status": "success", "message": "Xabar navbatga qo'yildi"}


@app.post("/api/leads")
async def create_amo_lead(request: CreateLeadRequest):
    """Vebsaytdan kelgan leadni AmoCRM-ga yuborish."""
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or not hmac.compare_digest(
        request.secret_key, expected_secret
    ):
        return {"error": "Unauthorized"}

    amocrm = _get_amocrm_instance()

    logger.info(f"🚀 [API] Website Lead qabul qilindi: {request.name}")
    lead_id = await amocrm.ensure_lead(
        name=request.name, phone=request.phone, note=request.note
    )

    if lead_id:
        add_activity("Lead Created", f"Website lead: {request.name}", type="success")
        return {"status": "success", "lead_id": lead_id}
    return {"error": "Lead creation failed"}


@app.post("/api/amocrm-refresh")
async def refresh_amocrm_token(request: Request):
    """Cron yoki manual refresh uchun endpoint."""
    auth_header = request.headers.get("Authorization")

    cron_secret = (
        settings.AMOCRM_CRON_SECRET.get_secret_value()
        if settings.AMOCRM_CRON_SECRET
        else None
    )

    if not cron_secret:
        return {"ok": False, "error": "CRON_SECRET not configured"}

    if not auth_header or auth_header != f"Bearer {cron_secret}":
        return {"ok": False, "error": "Unauthorized"}

    amocrm = _get_amocrm_instance()
    success = amocrm.refresh_token()
    if success:
        expires_at = amocrm.token_data.get("expires_at", "unknown")
        return {"ok": True, "expires_at": expires_at}
    else:
        return {"ok": False, "error": amocrm.last_error or "Refresh failed"}


@app.post("/api/amocrm-call-analysis/run")
async def run_amocrm_call_analysis_job(
    request: Request,
    limit: Optional[int] = Query(None, ge=1, le=250),
    wait: bool = Query(False),
    force: bool = Query(False),
):
    """Authenticated trigger for AmoCRM call recording backfill."""
    if not _is_authorized_cron_request(request):
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "Unauthorized"},
        )

    runtime_db = db_instance or await _get_db_instance()
    if wait:
        if _call_backfill_task and not _call_backfill_task.done():
            return JSONResponse(
                status_code=409,
                content={"ok": False, "error": "call_backfill_already_running"},
            )
        stats = await _run_amocrm_call_backfill(
            runtime_db,
            reason="manual_api_wait",
            limit=limit,
        )
        return {"ok": bool(stats.get("ok")), "mode": "wait", "stats": stats}

    queued = await _schedule_amocrm_call_backfill(
        runtime_db,
        reason="manual_api",
        limit=limit,
        force=force,
    )
    return {"ok": bool(queued.get("queued")), **queued}


@app.get("/api/amocrm-call-analysis/status")
async def get_amocrm_call_analysis_status(request: Request):
    """Authenticated status for the AmoCRM call analysis/backfill pipeline."""
    if not _is_authorized_cron_request(request):
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "Unauthorized"},
        )

    runtime_db = db_instance or await _get_db_instance()
    return await _build_amocrm_call_analysis_status(runtime_db)


@app.post("/webhook/amocrm")
async def amocrm_webhook(request: Request):
    """Handle incoming webhooks from AmoCRM."""
    try:
        # AmoCRM webhooks are often form-encoded
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form_data = await request.form()
            data = dict(form_data)

        logger.info(f"📩 [Webhook] AmoCRM event received: {list(data.keys())}")
        
        # Process in background
        asyncio.create_task(process_amocrm_event(data))
        
        return {"status": "ok", "message": "Event queued"}
    except Exception as e:
        logger.error(f"❌ [Webhook] Error: {e}")
        return {"status": "error", "message": str(e)}


async def process_amocrm_event(data: Dict[str, Any]):
    """
    AmoCRM eventini tahlil qilish va avtonom agentni ishga tushirish.
    """
    global amocrm_instance, db_instance
    
    try:
        # 1. Lead ID ni aniqlash (AmoCRM standard webhook format)
        lead_id = None
        # leads[add][0][id] yoki leads[update][0][id] formatida keladi
        for key in data.keys():
            if "leads[" in key and "][id]" in key:
                lead_id = data[key]
                break
        
        if not lead_id:
            return

        # 2. AmoCRM va Agentni tayyorlash
        amocrm_instance = _get_amocrm_instance()
        runtime_db = db_instance or await _get_db_instance()

        agent = AutonomousSalesAgent(db=runtime_db)
        
        # 3. Lead va Kontekst ma'lumotlarini olish
        lead_data = await amocrm_instance.get_lead(int(lead_id))
        if not lead_data:
            return
            
        phone = amocrm_instance.get_lead_phone(int(lead_id))

        if getattr(settings, "ENABLE_AMOCRM_LEAD_ENRICHMENT", True):
            try:
                enricher = AmoCRMLeadEnricher(
                    amocrm=amocrm_instance,
                    db=runtime_db,
                    user_client=user_client,
                )
                enrichment_result = await enricher.enrich_lead(
                    lead_id=int(lead_id),
                    lead_data=lead_data,
                    phone=phone,
                )
                logger.info(
                    "[Webhook] AmoCRM enrichment result: %s",
                    enrichment_result.to_dict(),
                )
            except Exception as enrich_exc:
                logger.error(
                    "[Webhook] AmoCRM enrichment failed for lead %s: %s",
                    lead_id,
                    enrich_exc,
                    exc_info=True,
                )

        if getattr(settings, "ENABLE_AMOCRM_CALL_ANALYSIS", True) and getattr(
            settings, "AMOCRM_CALL_ANALYSIS_ON_WEBHOOK", True
        ):
            try:
                call_analyzer = CallAnalyzer(
                    amocrm=amocrm_instance,
                    db=runtime_db,
                )
                calls_processed = await call_analyzer.process_call_recordings_for_lead(
                    lead_id=int(lead_id),
                    caller_phone=phone or "",
                    responsible_user_id=lead_data.get("responsible_user_id"),
                )
                logger.info(
                    "[Webhook] AmoCRM call analysis result: lead_id=%s processed=%s",
                    lead_id,
                    calls_processed,
                )
            except Exception as call_exc:
                logger.error(
                    "[Webhook] AmoCRM call analysis failed for lead %s: %s",
                    lead_id,
                    call_exc,
                    exc_info=True,
                )

        backfill_status = await _schedule_amocrm_call_backfill(
            runtime_db,
            reason=f"amocrm_webhook:{lead_id}",
        )
        if backfill_status.get("queued"):
            logger.info("[Webhook] AmoCRM call backfill queued: %s", backfill_status)
        
        # 4. Agentni ishga tushirish
        # Webhookdan kelgan trigger uchun maxsus xabar yuboramiz
        trigger_msg = "CRM status yangilandi yoki yangi lead keldi. Muzokarani tahlil qiling."
        
        result = await agent.handle_incoming(
            user_id=str(phone or lead_id),
            message=trigger_msg,
            crm_data={
                "lead_id": int(lead_id),
                "status_id": lead_data.get("status_id"),
                "pipeline_id": lead_data.get("pipeline_id"),
                "phone": phone,
                "name": lead_data.get("name")
            },
            autonomy_level="full"
        )
        
        # 5. Qarorni ijro etish
        if result.get("decision") == "send" and result.get("response"):
            response_text = result["response"]
            
            # AmoCRM ga note sifatida qo'shish (Audit trail uchun)
            await _maybe_await(amocrm_instance.add_lead_note(
                int(lead_id), 
                f"🤖 [Oisha Autonomous]: {response_text}"
            ))
            
            # Agar Telegram client bo'lsa va phone bo'lsa, to'g'ridan-to'g'ri yuborish mumkin
            # (Bu qism loyiha talabiga ko'ra integratsiya qilinadi)
            logger.info(f"✅ [Agent] Autonomous response sent for lead {lead_id}")
            
        elif result.get("decision") == "escalate":
            logger.warning(f"⚠️ [Agent] Escalation triggered for lead {lead_id}: {result.get('reason')}")
            await _maybe_await(amocrm_instance.add_lead_note(
                int(lead_id),
                f"🚨 [Oisha Escalation]: {result.get('reason')}. Human intervention needed."
            ))

    except Exception as e:
        logger.error(f"❌ [Webhook Process] Error: {e}", exc_info=True)


# ─── OPENCLAW GATEWAY BRIDGE ──────────────────────────────────────────────────


class OpenClawMessage(BaseModel):
    """Incoming message from OpenClaw gateway."""

    session: str = "main"
    channel: str = "unknown"
    sender: str = ""
    sender_id: Optional[str] = None
    text: str = ""
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OpenClawResponse(BaseModel):
    reply: str
    actions: List[Dict[str, Any]] = Field(default_factory=list)


@app.post("/webhook/openclaw")
async def openclaw_webhook(request: Request):
    """
    OpenClaw Gateway → Oisha-OS köprüsü.

    OpenClaw barcha kanallardan (WhatsApp, Slack, Discord, Telegram, ...)
    xabarlarni shu endpointga yuboradi. Oisha agenti javob qaytaradi,
    OpenClaw esa javobni tegishli kanalga jo'natadi.

    Xavfsizlik: OPENCLAW_SECRET env o'zgaruvchisi orqali HMAC tekshiruvi.
    """
    # HMAC signature tekshiruvi
    expected_secret = os.environ.get("OPENCLAW_SECRET")
    if expected_secret:
        signature = request.headers.get("x-openclaw-signature", "")
        body = await request.body()
        expected_sig = hmac.new(expected_secret.encode(), body, "sha256").hexdigest()
        if not hmac.compare_digest(f"sha256={expected_sig}", signature):
            return JSONResponse(status_code=401, content={"error": "Invalid signature"})
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    else:
        try:
            data = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    text = data.get("text") or data.get("message") or ""
    sender = data.get("sender") or data.get("from") or "unknown"
    sender_id = data.get("sender_id") or data.get("user_id") or sender
    channel = data.get("channel") or "openclaw"
    session = data.get("session") or "main"

    if not text.strip():
        return {"reply": "", "status": "empty"}

    logger.info(f"[OPENCLAW] {channel}/{sender}: {text[:80]}")
    add_activity(f"OpenClaw [{channel}]", f"{sender}: {text[:60]}", type="info")

    # Agent orqali javob olish
    try:
        from src.openclaw_bridge import handle_openclaw_message

        reply = await handle_openclaw_message(
            text=text,
            sender=sender,
            sender_id=str(sender_id),
            channel=channel,
            session=session,
            db=db_instance,
            metadata=data.get("metadata", {}),
        )
    except Exception as e:
        logger.error(f"[OPENCLAW] Agent xatosi: {e}")
        reply = "Kechirasiz, hozir texnik muammo bor. Biroz kutib qayta yozing."

    add_activity(f"OpenClaw reply [{channel}]", f"→ {reply[:60]}", type="success")
    return {"reply": reply, "status": "ok", "channel": channel, "session": session}


@app.get("/webhook/openclaw/health")
async def openclaw_health():
    """OpenClaw gateway uchun ping endpoint."""
    return {
        "status": "ok",
        "service": "oisha-os",
        "version": "2.1.0",
        "capabilities": [
            "sales",
            "support",
            "crm",
            "calendar",
            "lead_management",
            "negotiation",
            "research",
        ],
        "channels_accepted": ["whatsapp", "telegram", "slack", "discord", "any"],
    }

# ─── TELEGRAM BOT API 10.0 WEBHOOK ──────────────────────────────────────────

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Telegram Bot API 10.0 Webhook.
    Handles Guest Mode, Business Messages, and other new AI features.
    """
    try:
        data = await request.json()
        update_type = classify_update(data)
        
        logger.info(f"🤖 [Telegram Webhook] Received update type: {update_type}")
        
        # We process this in background to avoid Telegram timeout
        asyncio.create_task(process_telegram_update(data, update_type))
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ [Telegram Webhook] Error: {e}")
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})

def classify_update(data: Dict[str, Any]) -> str:
    """Classifies the Telegram update type based on payload keys."""
    if "guest_message" in data:
        return "guest_message"
    if "business_message" in data:
        return "business_message"
    if "business_connection" in data:
        return "business_connection"
    if "managed_bot" in data:
        return "managed_bot"
    if "message" in data:
        return "message"
    return "unknown"

_bot2bot_tracker: Dict[str, list] = {}
BOT2BOT_MAX_ROUNDS = 5
BOT2BOT_COOLDOWN_SEC = 60


def _bot2bot_allowed(from_id: int, chat_id: int) -> bool:
    """Rate-limit bot-to-bot exchanges to prevent infinite loops."""
    import time

    key = f"{from_id}:{chat_id}"
    now = time.time()
    history = _bot2bot_tracker.get(key, [])
    history = [ts for ts in history if now - ts < BOT2BOT_COOLDOWN_SEC]
    if len(history) >= BOT2BOT_MAX_ROUNDS:
        return False
    history.append(now)
    _bot2bot_tracker[key] = history
    return True


async def process_telegram_update(update: Dict[str, Any], update_type: str):
    """Processes the telegram update using appropriate handlers."""
    from src.handlers.messages import (
        handle_guest_query,
        handle_business_message,
        handle_business_connection,
        handle_managed_bot,
        handle_direct_message,
    )
    from telegram import Update, Bot

    try:
        bot_token = os.environ.get("BOT_TOKEN") or settings.BOT_TOKEN.get_secret_value()
        bot = Bot(token=bot_token)
        ptb_update = Update.de_json(update, bot)

        # Bot-to-bot loop safeguard
        msg = update.get("message") or update.get("business_message") or {}
        from_user = msg.get("from", {})
        if from_user.get("is_bot"):
            chat_id = msg.get("chat", {}).get("id", 0)
            if not _bot2bot_allowed(from_user.get("id", 0), chat_id):
                logger.warning(
                    "[BOT2BOT] Loop safeguard triggered for bot %s in chat %s",
                    from_user.get("id"),
                    chat_id,
                )
                return

        if update_type == "guest_query":
            await handle_guest_query(ptb_update, None, db_instance, msg_controller, bot_token)

        elif update_type == "business_message":
            await handle_business_message(ptb_update, None, db_instance, action_parser, msg_controller)

        elif update_type == "business_connection":
            await handle_business_connection(ptb_update, None, business_connections)

        elif update_type == "managed_bot":
            await handle_managed_bot(ptb_update, None)

        elif update_type == "message":
            await handle_direct_message(ptb_update, None, db_instance, action_parser, msg_controller)

    except Exception as e:
        logger.error(f"❌ [Telegram Process] Error: {e}", exc_info=True)
@app.get("/api/system/info")
async def get_system_info():
    """Tizim haqida umumiy ma'lumot."""
    return {
        "os": "Windows",
        "version": "2.1.0",
        "agent_count": 8,
        "active_modules": ["NightShift", "OSINT", "CRM_Sync", "Advisor", "Audit"],
        "status": "active"
    }


@app.post("/api/system/audit")
async def trigger_intelligence_audit():
    """Dashboarddan auditni ishga tushirish (Queued)."""
    # Push to queue for Main Thread execution
    command_queue.put_nowait({"cmd": "audit", "timestamp": datetime.now().isoformat()})

    return {
        "status": "success",
        "message": "Audit jarayonga tushirildi. Telegram hisobotini kuting.",
    }


# --- AI QUALITY ANALYTICS ENDPOINTS ---
from src.services.ai import QualityAnalyzer, CallAnalytics, AITaskManager
from src.services.ai.conversation_engine import (
    ConversationEngine,
    CallRecord,
    get_conversation_engine,
)

# Global analytics storage
_quality_analyzer = QualityAnalyzer()
_call_analytics = CallAnalytics()
_ai_task_manager: Optional[AITaskManager] = None
_conversation_engine: Optional[ConversationEngine] = None


@app.post("/api/ai/analyze-conversation")
async def analyze_conversation(request: Request):
    """
    Suhbatni AI tahlil qilish va sifat ballari berish.

    Request body:
    {
        "conversation_text": "Suhbat matni...",
        "conversation_id": "conv_123",
        "lead_id": 12345,
        "manager_id": 678,
        "manager_name": "John Doe",
        "duration_seconds": 300,
        "auto_create_tasks": false  // AmoCRM da vazifa yaratish
    }
    """
    try:
        data = await request.json()

        # Suhbatni tahlil qilish
        analysis = _quality_analyzer.analyze_conversation(
            conversation_text=data.get("conversation_text", ""),
            conversation_id=data.get("conversation_id", ""),
            lead_id=data.get("lead_id"),
            manager_id=data.get("manager_id"),
            manager_name=data.get("manager_name", ""),
            duration_seconds=data.get("duration_seconds", 0),
        )

        # Analitika saqlash
        _call_analytics.add_analysis(analysis)

        # Agar auto_create_tasks=True bo'lsa, AmoCRM da vazifa yaratish
        tasks = []
        if data.get("auto_create_tasks", False) and amocrm_instance:
            global _ai_task_manager
            if _ai_task_manager is None:
                _ai_task_manager = AITaskManager(amocrm_instance)

            tasks = await _ai_task_manager.create_tasks_from_analysis(
                analysis, auto_create=True
            )

        return {
            "status": "success",
            "analysis": analysis.to_dict(),
            "tasks_created": len([t for t in tasks if t.get("created_in_crm")]),
            "tasks": tasks[:5],  # Faqat 5 tasini qaytarish
        }

    except Exception as e:
        logger.error(f"[API AI] Analyze conversation error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/dashboard")
async def get_ai_dashboard(days: int = 7, manager_id: Optional[int] = None):
    """
    AI analitika dashboard ma'lumotlari.

    Query params:
    - days: N kunlik statistika (default: 7)
    - manager_id: Faqat bitta manager (optional)
    """
    try:
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        if manager_id:
            data = _call_analytics.get_manager_dashboard(
                manager_id=manager_id, start_date=start_date, end_date=end_date
            )
        else:
            data = _call_analytics.get_dashboard_data(
                start_date=start_date, end_date=end_date
            )

        return {
            "status": "success",
            "period": {
                "days": days,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "data": data,
        }

    except Exception as e:
        logger.error(f"[API AI] Dashboard error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/manager-ratings")
async def get_manager_ratings(days: int = 7):
    """Manager reytinglari."""
    try:
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        data = _call_analytics.get_dashboard_data(
            start_date=start_date, end_date=end_date
        )

        return {
            "status": "success",
            "ratings": data.get("manager_ratings", []),
            "period_days": days,
        }

    except Exception as e:
        logger.error(f"[API AI] Manager ratings error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/lost-clients-analysis")
async def get_lost_clients_analysis(days: int = 30):
    """Yo'qotilgan mijozlar tahlili."""
    try:
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        data = _call_analytics.get_dashboard_data(
            start_date=start_date, end_date=end_date
        )

        return {
            "status": "success",
            "lost_clients": data.get("lost_clients", {}),
            "recommendations": data.get("recommendations", []),
            "period_days": days,
        }

    except Exception as e:
        logger.error(f"[API AI] Lost clients analysis error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/ai/create-tasks-from-analysis")
async def create_tasks_from_analysis(request: Request):
    """
    Tahlil asosida AmoCRM da vazifa yaratish.

    Request body:
    {
        "lead_id": 12345,
        "analysis_id": "conv_123"
    }
    """
    try:
        if not amocrm_instance:
            return {"status": "error", "message": "AmoCRM not configured"}

        data = await request.json()
        lead_id = data.get("lead_id")

        # Task manager init
        global _ai_task_manager
        if _ai_task_manager is None:
            _ai_task_manager = AITaskManager(amocrm_instance)

        # Lead uchun tahlil topish
        analyses = [a for a in _call_analytics.analyses if a.lead_id == lead_id]

        if not analyses:
            return {
                "status": "error",
                "message": f"Analysis not found for lead {lead_id}",
            }

        # Oxirgi tahlil uchun vazifa yaratish
        latest_analysis = max(analyses, key=lambda x: x.analyzed_at)
        tasks = await _ai_task_manager.create_tasks_from_analysis(
            latest_analysis, auto_create=True
        )

        return {
            "status": "success",
            "lead_id": lead_id,
            "tasks_created": len(tasks),
            "tasks": tasks,
        }

    except Exception as e:
        logger.error(f"[API AI] Create tasks error: {e}")
        return {"status": "error", "message": str(e)}


# --- METASELL.AI STYLE ENDPOINTS ---


@app.get("/api/ai/metasell-dashboard")
async def get_metasell_dashboard(days: int = 7):
    """
    Metasell.ai o'xshash dashboard ma'lumotlari.

    Returns:
        - Umumiy statistika
        - Manager reytinglari
        - Natija taqsimoti
        - E'tirozlar tahlili
        - Tavsiyalar
    """
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        # Dashboard metrikalari
        metrics = _conversation_engine.get_dashboard_metrics(days=days)

        # Manager taqqoslash
        manager_comparison = _conversation_engine.get_manager_comparison(days=days)

        # Radar data (jamoa bo'yicha)
        radar_data = _conversation_engine.get_skills_radar_data(days=days)

        # Trend (so'nggi 14 kun)
        trend = _conversation_engine.get_trend_analysis(
            metric="score", days=min(days, 14)
        )

        return {
            "status": "success",
            "period_days": days,
            "summary": {
                "total_calls": metrics.total_calls_week,
                "total_calls_today": metrics.total_calls_today,
                "avg_score": metrics.avg_score_week,
                "avg_score_today": metrics.avg_score_today,
                "conversion_rate": metrics.conversion_rate,
                "sales_count": metrics.sales_count,
                "active_managers": metrics.active_managers,
                "total_talk_time_hours": metrics.total_talk_time // 60,
            },
            "outcomes": {
                "sales": metrics.sales_count,
                "follow_up": metrics.followup_count,
                "lost": metrics.lost_count,
            },
            "top_objections": metrics.top_objections,
            "weak_areas": metrics.weak_areas,
            "recommendations": metrics.recommendations,
            "manager_comparison": manager_comparison,
            "skills_radar": radar_data,
            "trend": trend,
        }

    except Exception as e:
        logger.error(f"[API AI] Metasell dashboard error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/call-details/{call_id}")
async def get_call_details(call_id: str):
    """Qo'ng'iroq tafsilotlari (metasell.ai o'xshash)."""
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        details = _conversation_engine.get_call_details(call_id)

        if not details:
            return {"status": "error", "message": "Call not found"}

        return {"status": "success", "data": details}

    except Exception as e:
        logger.error(f"[API AI] Call details error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/skills-radar")
async def get_skills_radar(manager_id: Optional[int] = None, days: int = 7):
    """
    Manager mahorati radar chart ma'lumotlari.
    Metasell.ai dagi 'Manager Radar' ga o'xshash.
    """
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        radar_data = _conversation_engine.get_skills_radar_data(
            manager_id=manager_id, days=days
        )

        return {"status": "success", "data": radar_data}

    except Exception as e:
        logger.error(f"[API AI] Skills radar error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/trend-analysis")
async def get_trend_analysis(metric: str = "score", days: int = 14):
    """
    Dinamik tahlil (trend).

    Query params:
    - metric: 'score', 'conversion', 'duration'
    - days: Kunlar soni
    """
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        trend = _conversation_engine.get_trend_analysis(metric=metric, days=days)

        return {"status": "success", "metric": metric, "data": trend}

    except Exception as e:
        logger.error(f"[API AI] Trend analysis error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/manager-comparison")
async def get_manager_comparison(days: int = 7):
    """Managerlar taqqoslash (reyting)."""
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        comparison = _conversation_engine.get_manager_comparison(days=days)

        return {"status": "success", "period_days": days, "managers": comparison}

    except Exception as e:
        logger.error(f"[API AI] Manager comparison error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/lead-classifier")
async def get_lead_classification():
    """
    AI Lead Classifier — sdelkalarni audio/notes tahlili orqali klassifikatsiya.
    Real mijoz / shaxsiy / spam aniqlaydi.
    """
    try:
        amocrm = _get_amocrm_instance()

        gemini_key = _secret_setting_text(settings.GEMINI_API_KEY)
        if not gemini_key:
            return {"status": "error", "message": "GEMINI_API_KEY not configured"}

        from src.services.core.lead_classifier import LeadClassifier
        classifier = LeadClassifier(amocrm, gemini_key)
        results = await classifier.classify_all_active_leads()

        return {
            "status": "success",
            "summary": classifier.get_summary(),
            "results": [
                {
                    "lead_id": r.lead_id,
                    "lead_name": r.lead_name,
                    "category": r.category.value,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "evidence": r.evidence,
                    "notes_analyzed": r.notes_analyzed,
                    "audio_transcribed": r.audio_transcribed,
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error(f"[API AI] Lead classifier error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/ai/lead-classifier/tag")
async def tag_unnecessary_leads():
    """Keraksiz sdelkalarni tag qilish (PERSONAL_NOT_CLIENT, SPAM_DETECTED)."""
    try:
        amocrm = _get_amocrm_instance()

        gemini_key = _secret_setting_text(settings.GEMINI_API_KEY)
        if not gemini_key:
            return {"status": "error", "message": "GEMINI_API_KEY not configured"}

        from src.services.core.lead_classifier import LeadClassifier
        classifier = LeadClassifier(amocrm, gemini_key)
        results = await classifier.classify_all_active_leads()
        tagged = await classifier.tag_unnecessary_leads(results)

        return {
            "status": "success",
            "tagged_count": tagged,
            "summary": classifier.get_summary(),
        }
    except Exception as e:
        logger.error(f"[API AI] Lead tagger error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/deal-hygiene")
async def get_deal_hygiene(
    limit: int = 100,
    apply_changes: bool = Query(False, alias="apply"),
    create_tasks: bool = True,
):
    """
    AmoCRM hygiene audit:
    - MetaSell/call-analysis xulosalari asosida keraksiz sdelkalarni ajratadi.
    - Telegram akkaunt + telefon mosligi orqali duplikat sdelka ehtimollarini topadi.
    - apply_changes=True bo'lmasa AmoCRMga hech narsa yozmaydi.
    """
    try:
        from src.services.core.deal_hygiene import AmoCRMDealHygieneAgent

        amocrm = _get_amocrm_instance()
        db = await _get_db_instance()
        agent = AmoCRMDealHygieneAgent(amocrm=amocrm, db=db)
        report = await agent.audit(limit=limit)

        applied = None
        if apply_changes:
            applied = await agent.apply_report(report, create_tasks=create_tasks)

        return {
            "status": "success",
            "applied": applied,
            **report,
        }
    except Exception as e:
        logger.error(f"[API AI] Deal hygiene error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.post("/api/ai/deal-hygiene/apply")
async def apply_deal_hygiene(limit: int = 100, create_tasks: bool = True):
    """Safe apply: tag, note and optional review task only. No delete/merge."""
    return await get_deal_hygiene(
        limit=limit,
        apply_changes=True,
        create_tasks=create_tasks,
    )


@app.post("/api/ai/process-call")
async def process_call(request: Request):
    """
    Yangi qo'ng'iroqni qayta ishlash.
    AmoCRM webhook orqali chaqiriladi.
    """
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        data = await request.json()

        # CallRecord yaratish
        call_record = CallRecord(
            call_id=data.get("call_id", ""),
            lead_id=data.get("lead_id", 0),
            manager_id=data.get("manager_id", 0),
            manager_name=data.get("manager_name", ""),
            started_at=datetime.fromisoformat(
                data.get("started_at", datetime.now().isoformat())
            ),
            duration_seconds=data.get("duration_seconds", 0),
            audio_url=data.get("audio_url"),
            transcript=data.get("transcript", ""),
            lead_name=data.get("lead_name", ""),
            lead_status=data.get("lead_status", ""),
        )

        # Qayta ishlash
        analysis = await _conversation_engine.process_call(
            call_record=call_record,
            auto_analyze=data.get("auto_analyze", True),
            auto_create_tasks=data.get("auto_create_tasks", True),
        )

        return {
            "status": "success",
            "call_id": call_record.call_id,
            "analyzed": analysis is not None,
            "score": analysis.overall_score if analysis else None,
            "category": analysis.category if analysis else None,
        }

    except Exception as e:
        logger.error(f"[API AI] Process call error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/ai/daily-report")
async def get_daily_report():
    """Kunlik hisobot (Telegramga yuborish uchun)."""
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)

        report = _conversation_engine.generate_daily_report()

        return {"status": "success", "report": report}

    except Exception as e:
        logger.error(f"[API AI] Daily report error: {e}")
        return {"status": "error", "message": str(e)}


# ─── OPENAI-COMPATIBLE ENDPOINT (OpenClaw model backend) ─────────────────────


@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible model list — OpenClaw uses this to discover oisha-os."""
    return {
        "object": "list",
        "data": [
            {
                "id": "oisha-agent",
                "object": "model",
                "created": 1700000000,
                "owned_by": "oisha-os",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint.

    OpenClaw bu endpointga barcha kanal xabarlarini yuboradi,
    Oisha agenti qayta ishlaydi va OpenAI formatida javob qaytaradi.
    """
    data = await request.json()

    messages = data.get("messages", [])
    session_id = data.get("user", "openclaw-main")
    stream = data.get("stream", False)

    # Oxirgi user xabarini olish
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            user_text = content if isinstance(content, str) else str(content)
            break

    if not user_text:
        user_text = "salom"

    logger.info(f"[OpenAI-compat] session={session_id} msg={user_text[:60]}")

    try:
        from src.openclaw_bridge import handle_openclaw_message

        reply = await handle_openclaw_message(
            text=user_text,
            sender=session_id,
            sender_id=session_id,
            channel="openclaw",
            session=session_id,
            db=db_instance,
            metadata={"source": "openai-compat"},
        )
    except Exception as exc:
        logger.error(f"[OpenAI-compat] Agent xatosi: {exc}")
        reply = "Kechirasiz, texnik muammo yuz berdi."

    import time

    completion_id = f"chatcmpl-oisha-{int(time.time())}"

    if stream:
        # Stream formatida javob
        from fastapi.responses import StreamingResponse

        async def event_stream():
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "oisha-agent",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": reply},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            done = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "oisha-agent",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "oisha-agent",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(user_text.split()),
            "completion_tokens": len(reply.split()),
            "total_tokens": len(user_text.split()) + len(reply.split()),
        },
    }


def run_api(host: str = "0.0.0.0", port: int = 8080):  # nosec
    uvicorn.run(app, host=host, port=port)


async def background_crm_audit_task():
    """Background task to refresh CRM audit data every 15 minutes."""
    from src.services.debug.crm_audit import AmoCRMAudit

    global cached_crm_audit
    audit = AmoCRMAudit()
    while True:
        try:
            logger.info("🕵️ [API] Starting background CRM audit...")
            results = await audit.run_full_audit()
            if results and "error" not in results:
                cached_crm_audit = results
                logger.info(
                    f"✅ [API] CRM Audit complete. Health: {results.get('health_score')}%"
                )
            else:
                logger.warning(f"⚠️ [API] CRM Audit failed: {results.get('error')}")
        except Exception as e:
            logger.error(f"❌ [API] CRM Audit CRASH: {e}")

        await asyncio.sleep(900)  # 15 minutes


if __name__ == "__main__":
    run_api()
