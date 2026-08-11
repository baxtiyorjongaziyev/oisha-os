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
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.database import get_db
from src.context import app_ctx
from src.services.core.agent_runtime import (
    collect_legacy_runtime_inventory,
    get_runtime_context,
    get_storage_health,
    set_runtime_context,
)
from src.services.core.airtable_client import AirtableClient
from src.api.routes.state import api_state
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
# Global Bridges (removed, now using app_ctx and api_state directly)
# ---------------------------------------------------------------------------
# AmoCRM backfill

# AI analytics
_quality_analyzer: Any = None
_call_analytics: Any = None
_ai_task_manager: Any = None
_conversation_engine: Any = None

# CRM audit running flag
crm_audit_running: bool = False

# State and code verifier cache (in-memory for simple auth flow)
_oauth_sessions: Dict[str, str] = {}


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
    api_state._telegram_ai_ingress_status.update({
        "mode": mode,
        "active": active,
        "updated_at": get_local_now().isoformat(),
    })


async def refresh_userbot_group_access_snapshot(client=None) -> Dict[str, Any]:
    """Read group/topic access through the already-connected production userbot."""
    active_client = client or app_ctx.user_client
    checked_at = get_local_now().isoformat()
    if active_client is None:
        api_state._userbot_group_access_snapshot = {
            "status": "unavailable",
            "checked_at": checked_at,
            "groups": {},
            "topics": {},
        }
        return dict(api_state._userbot_group_access_snapshot)

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
                logger.error("Exception handled in %s", __name__, exc_info=True)
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
            logger.error("Exception handled in %s", __name__, exc_info=True)
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
                logger.error("Exception handled in %s", __name__, exc_info=True)
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
    api_state._userbot_group_access_snapshot = {
        "status": (
            "ok"
            if all(e.get("readable") for e in required_groups + required_topics)
            else "degraded"
        ),
        "checked_at": checked_at,
        "groups": groups,
        "topics": topics,
    }
    return dict(api_state._userbot_group_access_snapshot)


def mark_heartbeat() -> None:
    now = datetime.now(timezone.utc)
    api_state._last_heartbeat_at = now
    api_state._last_heartbeat_at = now




def add_activity(action: str, details: str = "", type: str = "info"):
    activity = {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": action,
        "details": details,
        "type": type,
    }
    api_state.system_activities.insert(0, activity)
    if len(api_state.system_activities) > 100:
        api_state.system_activities.pop()
    logger.info("[DASHBOARD] %s: %s", action, details)


def update_api_status(status: str, message: str):
    api_state.cached_status = {
        "status": status,
        "message": message,
        "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_legacy_runtime_inventory() -> List[Dict[str, Any]]:
    if api_state.legacy_runtime_inventory_cache is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        api_state.legacy_runtime_inventory_cache = collect_legacy_runtime_inventory(repo_root)
    return list(api_state.legacy_runtime_inventory_cache)


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
    return (getattr(settings, "OISHA_API_SECRET", "") or "").strip()


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
    if app_ctx.db_instance:
        return app_ctx.db_instance
    from src.database import Database
    app_ctx.db_instance = Database()
    await app_ctx.db_instance.init_instance()
    return app_ctx.db_instance


def _get_amocrm_instance():
    if app_ctx.amocrm_instance:
        return app_ctx.amocrm_instance
    from src.services.core.crm.amocrm_sync import AmoCRMSync
    app_ctx.amocrm_instance = AmoCRMSync(
        subdomain=_setting_text(settings.AMOCRM_SUBDOMAIN),
        client_id=_setting_text(settings.AMOCRM_CLIENT_ID),
        client_secret=_secret_setting_text(settings.AMOCRM_CLIENT_SECRET),
        redirect_url=_setting_text(settings.AMOCRM_REDIRECT_URL),
    )
    return app_ctx.amocrm_instance


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(title="Oisha-OS Enterprise API")

# OAuth2 Middleware for MCP Endpoints
@app.middleware("http")
async def verify_oauth_for_mcp(request: Request, call_next):
    if request.url.path.startswith("/telegram-mcp"):
        # Allow OPTIONS request for CORS
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Basic secret check
        auth_header = request.headers.get("Authorization")
        expected_token = getattr(settings, "OISHA_API_SECRET", "")
        
        # In Gemini Web / ChatGPT Custom Actions, they send "Bearer <token>"
        is_authorized = False
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token and token == expected_token:
                is_authorized = True
                
        # Fallback to direct path secret (our previous approach)
        if not is_authorized and f"/telegram-mcp-{expected_token}" in request.url.path:
            is_authorized = True
            
        if not is_authorized:
            return JSONResponse({"detail": "Unauthorized. Bearer token missing or invalid."}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
            
    return await call_next(request)

# Include existing routers
from src.api import admin, dashboard
from src.api.live_monitor import router as live_monitor_router

app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(live_monitor_router)

# Hisobchi MCP router
try:
    from src.services.core.hisobchi_mcp import mcp_router
    if mcp_router is not None:
        app.include_router(mcp_router)
        _mcp_logger = logging.getLogger(__name__)
        _mcp_logger.info("[MCP] Hisobchi MCP router mounted at /mcp")
except Exception as exc:
    logger.warning("[MCP] Hisobchi MCP router not mounted: %s", exc)

# Telegram SSE MCP Server
try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
    from oisha_mcp_server import mcp as telegram_mcp_instance
    app.mount("/telegram-mcp", telegram_mcp_instance.sse_app(mount_path="/telegram-mcp"))
    logger.info("[MCP] Telegram SSE MCP server mounted at /telegram-mcp")
except Exception as exc:
    logger.warning("[MCP] Failed to mount Telegram SSE MCP: %s", exc)


# Include new route modules
from src.api.routes.health import router as health_router, liveness_probe
from src.api.routes.telegram_routes import router as telegram_router
from src.api.routes.telegram_mcp import router as telegram_mcp_router
from src.api.routes.system_dashboard import router as system_router
from src.api.routes.sales_quality import router as sales_quality_router
from src.api.routes.chat_widget import router as chat_router
from src.api.routes.amocrm_integration import router as amocrm_router
from src.api.routes.openclaw_gateway import router as openclaw_router
from src.api.routes.ai_analytics import router as ai_router
from src.api.routes.erp_routes import router as erp_router
from src.api.routes.instagram_routes import router as instagram_router
from src.api.routes.product_suite import router as product_router
from src.api.routes.business_commands import router as business_commands_router
from src.api.routes.crm_dashboard import router as crm_dashboard_router
from src.api.routes.finance_dashboard import router as finance_dashboard_router
from src.api.routes.marketing_dashboard import router as marketing_router
from src.api.routes.callmaster_routes import router as callmaster_router

app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(telegram_mcp_router)
app.include_router(system_router)
app.include_router(sales_quality_router)
app.include_router(chat_router)
app.include_router(amocrm_router)
app.include_router(openclaw_router)
app.include_router(ai_router)
app.include_router(erp_router)
app.include_router(instagram_router)
app.include_router(product_router)
app.include_router(business_commands_router)
app.include_router(crm_dashboard_router)
app.include_router(finance_dashboard_router)
app.include_router(marketing_router)
app.include_router(callmaster_router)
app.add_api_route("/health", liveness_probe, methods=["GET"], include_in_schema=False)
app.add_api_route("/healthz", liveness_probe, methods=["GET"], include_in_schema=False)
app.add_api_route("/healthz/", liveness_probe, methods=["GET"], include_in_schema=False)

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
    "https://oisha.jonbranding.uz",
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
    from src.services.core.telegram.telegram_ai_features import (
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


# =====================================================================
# AmoCRM Chat Integration (Wazzup Alternative)
# =====================================================================

@app.post("/webhook/amocrm_chat")
async def amocrm_chat_webhook(request: Request):
    """Receive outgoing messages from AmoCRM Chat and send them to Telegram."""
    try:
        body = await request.json()
        logger.info(f"[AMOCRM CHAT WEBHOOK] Received: {body}")
        
        # We need to extract the target Telegram ID and message text
        # AmoCRM sends payload depending on the action (e.g. new message)
        # Assuming format: {"message": {"text": "...", "receiver": {"id": "..."}}} 
        # or conversation client_id
        
        # Typically AmoCRM sends a webhook payload array or dict.
        msg_data = body.get("message", {})
        text = msg_data.get("text")
        client_id = msg_data.get("conversation", {}).get("client_id")
        
        if text and client_id:
            telegram_id = int(client_id)
            if app_ctx.outgoing_messages is None:
                app_ctx.outgoing_messages = asyncio.Queue()
            await app_ctx.outgoing_messages.put({
                "chat_id": telegram_id,
                "text": text
            })
            logger.info(f"[AMOCRM CHAT] Queued message to {telegram_id}")
            return {"status": "ok"}
        return {"status": "ignored"}
    except Exception as e:
        logger.error(f"[AMOCRM CHAT WEBHOOK ERROR] {e}")
        return {"status": "error", "detail": "Webhook processing failed"}


@app.post("/webhook/amocrm_notes")
async def amocrm_notes_webhook(request: Request):
    """Receive note[add] webhooks from AmoCRM to send Telegram messages natively."""
    try:
        form = await request.form()
        notes = {}
        for key, value in form.multi_items():
            if key.startswith("notes[add]["):
                parts = key.replace("notes[add][", "").split("][")
                if len(parts) >= 2:
                    idx = parts[0]
                    field = parts[-1].rstrip("]")
                    if idx not in notes:
                        notes[idx] = {}
                    notes[idx][field] = value
                    
        for idx, note_data in notes.items():
            text = note_data.get("text", "")
            lead_id_str = note_data.get("element_id")
            
            # Agar menejer "TG: salom" deb yozsa
            if text.lower().startswith("tg:") and lead_id_str:
                clean_text = text[3:].strip()
                lead_id = int(lead_id_str)
                
                from src.services.core.crm.amocrm_sync import AmoCRMSync
                amocrm = AmoCRMSync()
                phone = amocrm.get_lead_phone(lead_id)
                
                if phone:
                    if app_ctx.outgoing_messages is None:
                        app_ctx.outgoing_messages = asyncio.Queue()
                    await app_ctx.outgoing_messages.put({
                        "chat_id": phone,
                        "text": clean_text
                    })
                    logger.info(f"[NATIVE AMOCRM CHAT] Sent to {phone}: {clean_text}")
                    
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[AMOCRM NOTES WEBHOOK ERROR] {e}")
        return {"status": "error"}

# =====================================================================
# Telegram Chrome Extension Integratsiyasi
# =====================================================================

@app.get("/api/telegram/extension/history")
async def telegram_extension_history(phone: str):
    """Fetch chat history (via AmoCRM notes) for a given phone number."""
    try:
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        amocrm = AmoCRMSync()
        
        # 1. Mijozni topish
        lead = amocrm.find_active_lead_by_phone(phone)
        if not lead:
            # Agar bitim topilmasa, kontakt bo'yicha qidirib ko'ramiz
            contact = amocrm.get_contact_by_phone(phone)
            if not contact:
                return {"success": False, "error": "Mijoz topilmadi"}
            leads = amocrm.get_active_leads_for_contact(contact["id"])
            if leads:
                lead = leads[0]
            else:
                return {"success": False, "error": "Mijozning faol bitimi yo'q"}
                
        lead_id = lead["id"]
        
        # 2. Mijoz izohlarini (Notes) olish
        notes = await amocrm.get_lead_notes(lead_id)
        
        messages = []
        for note in notes:
            text = note.get("params", {}).get("text", "")
            if not text:
                continue
                
            # Biz yuborgan yoki bot yozgan xabarlarni ajratamiz
            is_outbound = "Menejer:" in text or "TG:" in text or "Oisha:" in text or note.get("created_by") != 0
            
            # Matnni tozalash (masalan "TG: " ni olib tashlash)
            clean_text = text.replace("TG: ", "").replace("Menejer: ", "")
            
            messages.append({
                "text": clean_text,
                "outbound": is_outbound,
                "created_at": note.get("created_at")
            })
            
        # Vaqt bo'yicha saralash
        messages.sort(key=lambda x: x["created_at"])
        
        # Telegram Chat ID ni topish (custom field lardan)
        chat_id = phone # Fallback
        
        return {
            "success": True, 
            "messages": messages,
            "chatId": chat_id,
            "leadId": lead_id
        }
    except Exception as e:
        logger.error(f"[TELEGRAM EXT HISTORY] {e}")
        return {"success": False, "error": "Telegram history request failed"}


@app.post("/api/telegram/extension/send")
async def telegram_extension_send(request: Request):
    """Send a message to a client via Telegram and log it in AmoCRM."""
    try:
        data = await request.json()
        chat_id = data.get("chat_id")
        text = data.get("text")
        
        if not chat_id or not text:
            return {"success": False, "error": "chat_id and text required"}
            
        # 1. Telegram orqali yuborish (app_ctx.outgoing_messages queue)
        if app_ctx.outgoing_messages is None:
            app_ctx.outgoing_messages = asyncio.Queue()
            
        await app_ctx.outgoing_messages.put({
            "chat_id": chat_id, # Agar phone bo'lsa, qanday ishlaydi? telegram_bot_client raqam bo'yicha yubora oladimi?
            "text": text
        })
        
        # 2. AmoCRM ga Note qilib yozib qo'yish (kelajakdagi tarix uchun)
        from src.services.core.crm.amocrm_sync import AmoCRMSync
        amocrm = AmoCRMSync()
        lead = amocrm.find_active_lead_by_phone(chat_id)
        if lead:
            # Menejer yuborganligini bildirish uchun
            amocrm.add_lead_note(lead["id"], f"TG: {text}")
            
        return {"success": True}
    except Exception as e:
        logger.error(f"[TELEGRAM EXT SEND] {e}")
        return {"success": False, "error": "Telegram message send failed"}

# =====================================================================
# Airtable OAuth 2.0 Integratsiyasi
# =====================================================================

@app.get("/api/auth/airtable/login")
async def airtable_login():
    """Redirect to Airtable for OAuth authorization."""
    # Generate PKCE code verifier and challenge
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    state = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')
    
    # Store verifier temporarily to use in callback
    _oauth_sessions[state] = code_verifier
    
    client = AirtableClient()
    url = client.get_authorization_url(state, code_challenge)
    return RedirectResponse(url)


@app.get("/api/auth/airtable/callback")
async def airtable_callback(code: str = None, state: str = None, error: str = None, error_description: str = None):
    """Handle Airtable OAuth callback."""
    if error:
        raise HTTPException(status_code=400, detail=f"Airtable Auth Error: {error} - {error_description}")
        
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
        
    code_verifier = _oauth_sessions.pop(state, None)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
        
    client = AirtableClient()
    try:
        await client.exchange_code_for_token(code, code_verifier)
    except Exception as e:
        logger.error(f"Failed to exchange Airtable token: {e}")
        raise HTTPException(status_code=500, detail="Failed to exchange token")
        
    html_content = """
    <html>
        <head>
            <title>Airtable Muvaffaqiyatli Ulandi</title>
            <style>
                body { font-family: 'Inter', sans-serif; text-align: center; padding-top: 50px; background: #f3f4f6; color: #1f2937; }
                .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: inline-block; }
                h1 { color: #10b981; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>âœ… Muvaffaqiyatli!</h1>
                <p>Oisha-OS Airtable bilan to'g'ridan-to'g'ri bog'landi.</p>
                <p>Ushbu oynani yopishingiz mumkin.</p>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/auth/airtable/status")
async def airtable_status():
    """Check if Airtable is connected."""
    db = get_db()
    tokens = await db.oauth.get_tokens("airtable")
    if tokens:
        return {"status": "connected", "expires_at": tokens.get("expires_at")}
    return {"status": "disconnected"}


# =====================================================================
# Telegram OAuth Integratsiyasi (ERP Login)
# =====================================================================

@app.get("/api/auth/telegram/login")
async def telegram_login():
    """Return an HTML page with the Telegram Login Widget."""
    import config
    bot_username = getattr(config, "BOT_USERNAME", "jonairobot")
    # For local testing, auth_url could be the local IP, but for prod it's the domain
    html_content = f"""
    <html>
        <head>
            <title>Oisha-OS Enterprise Login</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f3f4f6; color: #1f2937; margin: 0; }}
                .card {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; max-width: 400px; width: 100%; }}
                h2 {{ color: #2563eb; margin-bottom: 20px; }}
                p {{ color: #4b5563; margin-bottom: 30px; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Oisha-OS Enterprise</h2>
                <p>Tizimga kirish uchun Telegram orqali tasdiqlang. Hech qanday parol kerak emas.</p>
                <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-login="{bot_username.replace('@', '')}" data-size="large" data-auth-url="/api/auth/telegram/callback" data-request-access="write"></script>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/auth/telegram/callback")
async def telegram_callback(
    id: int,
    first_name: str,
    hash: str,
    last_name: str = None,
    username: str = None,
    photo_url: str = None,
    auth_date: int = None,
):
    """Handle Telegram OAuth callback."""
    import config
    from src.api import auth_service

    # 1. Verify hash
    bot_token = config.BOT_TOKEN
    fields = {
        "id": str(id) if id is not None else None,
        "first_name": first_name,
        "auth_date": str(auth_date) if auth_date is not None else None,
        "last_name": last_name,
        "username": username,
        "photo_url": photo_url,
    }
    if not auth_service.verify_telegram_hash(fields, bot_token, hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram Auth Hash")

    # Check expiry (prevent replay attacks - 24 hours max)
    if not auth_service.is_auth_date_fresh(auth_date):
        raise HTTPException(status_code=403, detail="Auth date is expired")

    # 2. Get or Create user in DB, sync role
    db = get_db()
    # Ensure they exist in our users table
    await db.users.upsert_user(
        user_id=id,
        username=username,
        first_name=first_name,
        last_name=last_name
    )
    user = await db.users.get_user(id)
    role = user.get("role", "client") if user else "client"

    # Generate JWT (fallback to bot token if no separate secret)
    jwt_secret = getattr(config, "JWT_SECRET", bot_token)
    token = auth_service.issue_session_jwt(
        user_id=id, username=username, first_name=first_name,
        role=role, secret=jwt_secret,
    )

    # Create response that stores the cookie and redirects to Dashboard
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="oisha_token",
        value=token,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
    )
    return response



@app.get("/client")
async def client_dashboard(request: Request):
    """Serve the Client Dashboard (MVP)."""
    # Simple check for JWT token in cookies
    token = request.cookies.get("oisha_token")
    if not token:
        return RedirectResponse(url="/api/auth/telegram/login")

    import config
    from src.api import auth_service
    jwt_secret = getattr(config, "JWT_SECRET", config.BOT_TOKEN)
    payload = auth_service.decode_session_jwt(token, jwt_secret)
    if payload is None:
        # Invalid or expired token
        return RedirectResponse(url="/api/auth/telegram/login")
    user_id = payload.get("sub")
    first_name = payload.get("first_name", "Foydalanuvchi")
    role = payload.get("role", "client")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Oisha-OS | {first_name}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #2563eb;
                --primary-hover: #1d4ed8;
                --bg: #f3f4f6;
                --card-bg: #ffffff;
                --text: #1f2937;
                --text-light: #6b7280;
                --success: #10b981;
                --warning: #f59e0b;
                --danger: #ef4444;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }}
            body {{ background-color: var(--bg); color: var(--text); }}
            
            /* Navbar */
            header {{ background: var(--card-bg); padding: 1rem 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; }}
            .logo {{ font-weight: 700; font-size: 1.25rem; color: var(--primary); display: flex; align-items: center; gap: 0.5rem; }}
            .user-profile {{ display: flex; align-items: center; gap: 1rem; }}
            .avatar {{ width: 36px; height: 36px; background: var(--primary); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; }}
            
            /* Main Content */
            main {{ padding: 2rem; max-width: 1200px; margin: 0 auto; }}
            .welcome {{ margin-bottom: 2rem; }}
            .welcome h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
            .welcome p {{ color: var(--text-light); }}
            
            /* Kanban Board */
            .kanban-board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; align-items: start; }}
            .column {{ background: var(--card-bg); border-radius: 0.75rem; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-height: 400px; }}
            .column-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; padding-bottom: 0.75rem; border-bottom: 2px solid var(--bg); font-weight: 600; }}
            .count-badge {{ background: var(--bg); padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.875rem; color: var(--text-light); }}
            
            /* Task Cards */
            .task-card {{ background: var(--bg); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; border: 1px solid #e5e7eb; transition: transform 0.2s, box-shadow 0.2s; cursor: pointer; }}
            .task-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .task-title {{ font-weight: 600; margin-bottom: 0.5rem; font-size: 0.95rem; }}
            .task-meta {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-light); margin-top: 1rem; }}
            .priority-tag {{ padding: 0.15rem 0.5rem; border-radius: 0.25rem; font-weight: 500; }}
            .priority-high {{ background: #fee2e2; color: var(--danger); }}
            .priority-medium {{ background: #fef3c7; color: var(--warning); }}
            .priority-low {{ background: #d1fae5; color: var(--success); }}
            
            /* Empty State */
            .empty-state {{ text-align: center; padding: 2rem; color: var(--text-light); font-size: 0.9rem; }}
            
            /* FAB */
            .fab {{ position: fixed; bottom: 2rem; right: 2rem; width: 56px; height: 56px; background: var(--primary); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; box-shadow: 0 4px 12px rgba(37,99,235,0.4); cursor: pointer; transition: transform 0.2s; border: none; }}
            .fab:hover {{ transform: scale(1.05); background: var(--primary-hover); }}
            
            @media (max-width: 768px) {{
                .kanban-board {{ grid-template-columns: 1fr; }}
                main {{ padding: 1rem; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                Oisha-OS
            </div>
            <div class="user-profile">
                <span style="font-weight: 500; font-size: 0.9rem;">{first_name}</span>
                <div class="avatar">{first_name[0].upper()}</div>
            </div>
        </header>

        <main>
            <div class="welcome">
                <h1>Xush kelibsiz, {first_name}!</h1>
                <p>Loyihalaringiz va vazifalaringiz shu yerda boshqariladi.</p>
            </div>

            <div class="kanban-board">
                <!-- Bajarilmoqda -->
                <div class="column">
                    <div class="column-header">
                        <span style="color: var(--primary);">Jarayonda (In Progress)</span>
                        <span class="count-badge" id="count-progress">0</span>
                    </div>
                    <div id="col-progress" class="task-list">
                        <div class="empty-state">Vazifalar yo'q</div>
                    </div>
                </div>

                <!-- Kutilmoqda -->
                <div class="column">
                    <div class="column-header">
                        <span style="color: var(--warning);">Mijoz Tasdig'ida</span>
                        <span class="count-badge" id="count-review">0</span>
                    </div>
                    <div id="col-review" class="task-list">
                        <div class="empty-state">Vazifalar yo'q</div>
                    </div>
                </div>

                <!-- Bajarildi -->
                <div class="column">
                    <div class="column-header">
                        <span style="color: var(--success);">Tugatilgan</span>
                        <span class="count-badge" id="count-done">0</span>
                    </div>
                    <div id="col-done" class="task-list">
                        <div class="empty-state">Vazifalar yo'q</div>
                    </div>
                </div>
            </div>
        </main>
        
        <script>
            // MVP script for future API connection
            document.addEventListener('DOMContentLoaded', () => {{
                console.log("Dashboard loaded for role: {role}");
                // Future: fetch('/api/tasks') and render
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


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
                api_state.cached_crm_audit = results
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
    connection = api_state.business_connections.get(connection_id) or {}
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
    if api_state._call_backfill_task and not api_state._call_backfill_task.done():
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
    api_state._call_backfill_task = asyncio.create_task(
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
    mem = api_state._call_backfill_last_status or {}
    if not mem:
        mem = getattr(_api_state, "api_state._call_backfill_last_status", {}) or {}
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

    running = bool(api_state._call_backfill_task and not api_state._call_backfill_task.done())
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


# Backward-compat re-exports: these symbols are pulled back into the
# api_server namespace for legacy callers that do `from src.api_server import X`.
# They are INTENTIONALLY at module end â€” the router modules import from here, so
# importing them earlier would create circular imports. Do not move to the top.
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
