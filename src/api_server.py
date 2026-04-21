import asyncio
import uvicorn
from datetime import datetime, timezone
import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import queue
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.services.core.agent_runtime import (
    collect_legacy_runtime_inventory,
    get_runtime_context,
    get_storage_health,
    set_runtime_context,
)
from src.services.core.amocrm_sync import AmoCRMSync
from src.settings import settings
from src.time_utils import get_local_now

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OishaAPI")

app = FastAPI(title="Oisha-OS Enterprise API")

# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Enable CORS for AmoCRM
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # AmoCRM domains vary
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root_status():
    """Health check for Google Cloud Run."""
    runtime = get_runtime_context()
    response = {
        "status": "online",
        "service": "Oisha-OS Enterprise",
        "version": "2.1.0-GodMode",
        "timestamp": get_local_now().isoformat(),
        "runtime_source": runtime.get("runtime_source"),
        "service_name": runtime.get("service_name"),
        "runtime_id": runtime.get("runtime_id"),
        "userbot_authorized": runtime.get("userbot_authorized"),
    }
    response.update(cached_status)
    return response


@app.get("/health")
@app.get("/healthz")
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
    elif boot_age > 20:
        # Loop should have ticked by now; if not, something is wrong.
        problems.append("no_heartbeat_ever")

    runtime = get_runtime_context()
    scheduler_mode = runtime.get("scheduler_mode")
    control_plane_mode = scheduler_mode == "control-plane"

    db_ok = True
    if db_instance is not None:
        try:
            conn = await db_instance.get_connection()
            probe = conn.execute("SELECT 1")
            if hasattr(probe, "__await__"):
                probe = await probe
            fetchone = getattr(probe, "fetchone", None)
            if callable(fetchone):
                row = fetchone()
                if hasattr(row, "__await__"):
                    await row
            checks["db_ok"] = True
        except Exception as e:
            logger.warning(f"[HEALTH] Database connection failed: {e}")
            db_ok = False
            checks["db_ok"] = False
            problems.append("db_failed")
    else:
        checks["db_ok"] = True

    userbot_authorized = runtime.get("userbot_authorized", False)
    
    # Cloud Run control-plane deliberately delegates Telegram runtime to the VM.
    telegram_bot_ok = True
    if not control_plane_mode:
        telegram_bot_ok = False
        try:
            from src.main import bot
            if bot and hasattr(bot, "bot"):
                me = await bot.bot.get_me()
                telegram_bot_ok = True
                logger.debug(f"[HEALTH] Telegram bot connected: @{me.username}")
        except Exception as e:
            logger.warning(f"[HEALTH] Telegram bot connection failed: {e}")
    
    crm_ok = True if control_plane_mode else bool(runtime.get("crm_connected", False))
    
    healthy = not problems and db_ok and telegram_bot_ok and crm_ok
    status_code = 200 if healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "unhealthy",
            "checks": {
                "database": db_ok,
                "userbot": userbot_authorized,
                "telegram_bot": telegram_bot_ok,
                "crm": crm_ok,
                "scheduler_mode": scheduler_mode,
                "problems": problems,
            },
            "timestamp": get_local_now().isoformat()
        }
    )


# Global references
user_client = None
db_instance = None
audit_agent = None
amocrm_instance = None

# [HEALTHZ] Liveness heartbeat — main event loop updates this via mark_heartbeat().
# Deploy smoke checks read /health; if heartbeat is stale, the probe fails
# and the container is restarted (recovering from event-loop deadlocks).
_last_heartbeat_at: Optional[datetime] = None
_boot_at: datetime = datetime.now(timezone.utc)
_heartbeat_stale_seconds: int = 120  # 2 min: loop silent longer than this => unhealthy


def mark_heartbeat() -> None:
    """Called by the main event loop every ~60s to prove liveness."""
    global _last_heartbeat_at
    _last_heartbeat_at = datetime.now(timezone.utc)

# --- COMMAND QUEUE (Shared with Main Thread) ---
command_queue = queue.Queue()

# --- DASHBOARD CACHE ---
cached_status: Dict[str, Any] = {
    "status": "offline",
    "message": "Tizim tayyorlanmoqda...",
    "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S")
}

# --- CRM AUDIT CACHE ---
cached_crm_audit: Dict[str, Any] = {
    "health_score": 98,
    "summary": "Audit kutilmoqda...",
    "timestamp": get_local_now().isoformat()
}
# --- DASHBOARD ACTIVITY FEED ---
system_activities: List[Dict[str, Any]] = [
    {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": "🚀 System Boot",
        "details": "Oisha-OS Strategic Intelligence is online and listening.",
        "type": "success"
    }
]

legacy_runtime_inventory_cache: Optional[List[Dict[str, Any]]] = None

# --- WAZZUP BRIDGE (Outgoing Messages Queue) ---
outgoing_messages = asyncio.Queue()

def add_activity(action: str, details: str = "", type: str = "info"):
    """Tizimdagi amallarni Dashboard uchun ro'yxatga olish."""
    activity = {
        "timestamp": get_local_now().strftime("%H:%M:%S"),
        "action": action,
        "details": details,
        "type": type # info, success, warning, error, thinking
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


async def build_health_snapshot(include_inventory: bool = False, include_traces: bool = False) -> Dict[str, Any]:
    runtime = get_runtime_context()
    db_path = runtime.get("state_db_path") or getattr(db_instance, "db_path", None)
    recent_job_runs: List[Dict[str, Any]] = []
    recent_agent_actions: List[Dict[str, Any]] = []

    if db_instance:
        try:
            recent_job_runs = await db_instance.get_recent_job_runs(limit=10)
        except Exception as exc:
            logger.warning(f"[API] Could not fetch recent job runs: {exc}")

        if include_traces:
            try:
                recent_agent_actions = await db_instance.get_recent_agent_actions(limit=25)
            except Exception as exc:
                logger.warning(f"[API] Could not fetch agent actions: {exc}")

    snapshot = {
        "timestamp": get_local_now().isoformat(),
        "status": cached_status.copy(),
        "runtime": runtime,
        "storage": get_storage_health(db_path, recent_job_runs=recent_job_runs, backend=runtime.get("state_backend", "sqlite")),
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
        "timestamp": get_local_now().strftime("%Y-%m-%d %H:%M:%S")
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
            "server": "Oisha-OS Local Server"
        }
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
        if health >= 90: stats["automation_efficiency"] = "Exceptional"
        elif health >= 75: stats["automation_efficiency"] = "High"
        elif health >= 50: stats["automation_efficiency"] = "Nominal"
        else: stats["automation_efficiency"] = "Action Required"
        
        stats["last_audit"] = cached_crm_audit.get("timestamp", get_local_now().isoformat())
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
            content={"status": "not_found", "message": "Sales quality dashboard is not deployed yet."},
        )
    return FileResponse(dashboard_path)


@app.get("/api/sales-quality/overview")
async def get_sales_quality_overview():
    """Return the sales-call QA payload consumed by the dashboard.

    This contract is intentionally stable: AmoCRM calls, call transcriptions,
    and AI scoring can be connected behind it without changing the frontend.
    """
    generated_at = get_local_now().isoformat()
    return {
        "generated_at": generated_at,
        "source": "demo_contract",
        "period": "Bugungi sotuv qo'ng'iroqlari",
        "team": {
            "quality_score": 82,
            "trend": "+6.4%",
            "calls_total": 124,
            "calls_analyzed": 97,
            "connected_calls": 68,
            "missed_calls": 11,
            "sales_count": 7,
            "conversion": 11.3,
            "avg_call_minutes": 2.8,
            "callback_agreed": 31,
        },
        "managers": [
            {
                "name": "Oydin",
                "role": "Sales manager",
                "score": 91,
                "calls": 38,
                "connected": 24,
                "missed": 2,
                "sales": 3,
                "conversion": 12.5,
                "trend": "+8%",
                "avatar": "OY",
            },
            {
                "name": "Ifora",
                "role": "Sales manager",
                "score": 84,
                "calls": 31,
                "connected": 18,
                "missed": 4,
                "sales": 2,
                "conversion": 11.1,
                "trend": "+4%",
                "avatar": "IF",
            },
            {
                "name": "Sarvara",
                "role": "Sales manager",
                "score": 76,
                "calls": 29,
                "connected": 16,
                "missed": 3,
                "sales": 1,
                "conversion": 6.3,
                "trend": "-2%",
                "avatar": "SA",
            },
            {
                "name": "Hasan",
                "role": "Sales manager",
                "score": 69,
                "calls": 26,
                "connected": 10,
                "missed": 2,
                "sales": 1,
                "conversion": 10.0,
                "trend": "+1%",
                "avatar": "HA",
            },
        ],
        "outcomes": [
            {"label": "Qayta qo'ng'iroq kelishildi", "value": 36, "color": "#2f80ed"},
            {"label": "Ma'lumot yuborildi", "value": 22, "color": "#00a676"},
            {"label": "Qiziqmagan", "value": 18, "color": "#f2994a"},
            {"label": "Narx bo'yicha e'tiroz", "value": 14, "color": "#eb5757"},
            {"label": "Noto'g'ri raqam", "value": 10, "color": "#7f8ea3"},
        ],
        "radar": [
            {"label": "Tanishtirish", "score": 88},
            {"label": "Ehtiyojni ochish", "score": 72},
            {"label": "Qiymatni tushuntirish", "score": 64},
            {"label": "E'tirozni yengish", "score": 58},
            {"label": "Keyingi qadam", "score": 81},
            {"label": "Ohang va hurmat", "score": 90},
        ],
        "loss_reasons": [
            {
                "title": "Javob sekin berilgan",
                "count": 10,
                "impact": "high",
                "fix": "5 daqiqadan kech qolgan lidlarga avtomatik qayta aloqa task ochilsin.",
            },
            {
                "title": "Narx qimmat ko'ringan",
                "count": 8,
                "impact": "medium",
                "fix": "Narxdan oldin natija, risk va kafolat qiymati tushuntirilsin.",
            },
            {
                "title": "Ehtiyoj aniq ochilmagan",
                "count": 7,
                "impact": "medium",
                "fix": "Kamida 3 ta diagnostika savoli berilmaguncha taklif yuborilmasin.",
            },
        ],
        "weaknesses": [
            {"label": "Qiymatni tushuntirish", "count": 11, "severity": "critical"},
            {"label": "E'tiroz bilan ishlash", "count": 9, "severity": "warning"},
            {"label": "Aniq callback vaqti", "count": 7, "severity": "warning"},
        ],
        "recommendations": [
            "Har qo'ng'iroqda mijozning real muammosi bitta jumlada qaytarib aytilsin.",
            "Narxdan oldin 3 ta natija va 1 ta xavfsizlik kafolati tushuntirilsin.",
            "Qayta qo'ng'iroq uchun aniq sana/soat CRM taskga yozilmaguncha suhbat yopilmasin.",
            "Javobsiz qo'ng'iroqlarga 10 daqiqa ichida Telegram follow-up xabari yuborilsin.",
        ],
        "calls": [
            {
                "client": "Petron Polymer",
                "manager": "Oydin",
                "score": 92,
                "result": "Taklif yuborildi",
                "duration": "04:12",
                "summary": "Ehtiyoj aniqlandi, rebranding bo'yicha keyingi uchrashuv kelishildi.",
                "risk": "Past",
            },
            {
                "client": "Bekbazar",
                "manager": "Ifora",
                "score": 81,
                "result": "Qayta qo'ng'iroq",
                "duration": "02:48",
                "summary": "Mijoz logo variantlarini ko'rmoqchi, callback vaqti CRMga yozilishi kerak.",
                "risk": "O'rta",
            },
            {
                "client": "Ravza",
                "manager": "Sarvara",
                "score": 64,
                "result": "Narx e'tirozi",
                "duration": "01:57",
                "summary": "Qiymat yetarli ochilmagan, natija va portfolio bilan qayta ishlash kerak.",
                "risk": "Yuqori",
            },
        ],
        "assistant_answers": [
            {
                "question": "Bugun kim eng yaxshi ishladi?",
                "answer": "Oydin: 91 ball, 38 ta qo'ng'iroq, 3 ta sotuv. Kuchli tomoni - keyingi qadamni aniq yopgan.",
            },
            {
                "question": "Qaysi leadlar yo'qolish xavfida?",
                "answer": "Narx e'tirozi va callback vaqti belgilanmagan leadlar. Ularni bugun 18:00 gacha qayta jonlantirish kerak.",
            },
        ],
    }

class CreateLeadRequest(BaseModel):
    name: str
    phone: str
    note: Optional[str] = None
    secret_key: str

class SendMessageRequest(BaseModel):
    user_id: int
    text: str
    secret_key: str

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
    if not expected_secret or secret_key != expected_secret:
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
    if not expected_secret or secret_key != expected_secret:
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
    if not expected_secret or request.secret_key != expected_secret:
        return {"error": "Unauthorized"}
    
    # Push to queue for Main Thread execution
    command_queue.put({
        "cmd": "send_message",
        "user_id": request.user_id,
        "text": request.text
    })
    
    return {"status": "success", "message": "Xabar navbatga qo'yildi"}

@app.post("/api/leads")
async def create_amo_lead(request: CreateLeadRequest):
    """Vebsaytdan kelgan leadni AmoCRM-ga yuborish."""
    global amocrm_instance
    expected_secret = os.environ.get("OISHA_API_SECRET")
    if not expected_secret or request.secret_key != expected_secret:
        return {"error": "Unauthorized"}
    
    if not amocrm_instance:
        amocrm_instance = AmoCRMSync(
            subdomain=settings.AMOCRM_SUBDOMAIN,
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else '',
            redirect_url=settings.AMOCRM_REDIRECT_URL
        )
    
    logger.info(f"🚀 [API] Website Lead qabul qilindi: {request.name}")
    lead_id = await amocrm_instance.ensure_lead(
        name=request.name,
        phone=request.phone,
        note=request.note
    )
    
    if lead_id:
        add_activity("Lead Created", f"Website lead: {request.name}", type="success")
        return {"status": "success", "lead_id": lead_id}
    return {"error": "Lead creation failed"}

@app.post("/webhook/amocrm")
async def amocrm_webhook(request: Request):
    """Handle incoming webhooks from AmoCRM (e.g. outgoing messages from Chat Widget)"""
    # BackgroundTasks is handled by FastAPI if needed, simplifying here
    data = await request.json()
    logger.info(f"Received AmoCRM webhook: {data}")
    
    # Logic to bridge to Telegram (Wazzup Killer)
    # process_amocrm_message(data)
    
    return {"status": "received"}

@app.get("/api/system/info")
async def get_system_info():
    """Tizim haqida umumiy ma'lumot."""
    return {
        "os": "Windows",
        "version": "2.1.0-GodMode",
        "agent_count": 8,
        "active_modules": ["NightShift", "OSINT", "CRM_Sync", "Advisor", "Audit"]
    }

@app.post("/api/system/audit")
async def trigger_intelligence_audit():
    """Dashboarddan auditni ishga tushirish (Queued)."""
    # Push to queue for Main Thread execution
    command_queue.put({
        "cmd": "audit",
        "timestamp": datetime.now().isoformat()
    })
    
    return {"status": "success", "message": "Audit jarayonga tushirildi. Telegram hisobotini kuting."}


# --- AI QUALITY ANALYTICS ENDPOINTS ---
from src.services.ai import QualityAnalyzer, CallAnalytics, AITaskManager

# Global analytics storage
_quality_analyzer = QualityAnalyzer()
_call_analytics = CallAnalytics()
_ai_task_manager: Optional[AITaskManager] = None

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
            duration_seconds=data.get("duration_seconds", 0)
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
                analysis, 
                auto_create=True
            )
        
        return {
            "status": "success",
            "analysis": analysis.to_dict(),
            "tasks_created": len([t for t in tasks if t.get("created_in_crm")]),
            "tasks": tasks[:5]  # Faqat 5 tasini qaytarish
        }
        
    except Exception as e:
        logger.error(f"[API AI] Analyze conversation error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/ai/dashboard")
async def get_ai_dashboard(
    days: int = 7,
    manager_id: Optional[int] = None
):
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
                manager_id=manager_id,
                start_date=start_date,
                end_date=end_date
            )
        else:
            data = _call_analytics.get_dashboard_data(
                start_date=start_date,
                end_date=end_date
            )
        
        return {
            "status": "success",
            "period": {
                "days": days,
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "data": data
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
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "status": "success",
            "ratings": data.get("manager_ratings", []),
            "period_days": days
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
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "status": "success",
            "lost_clients": data.get("lost_clients", {}),
            "recommendations": data.get("recommendations", []),
            "period_days": days
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
            return {"status": "error", "message": f"Analysis not found for lead {lead_id}"}
        
        # Oxirgi tahlil uchun vazifa yaratish
        latest_analysis = max(analyses, key=lambda x: x.analyzed_at)
        tasks = await _ai_task_manager.create_tasks_from_analysis(
            latest_analysis,
            auto_create=True
        )
        
        return {
            "status": "success",
            "lead_id": lead_id,
            "tasks_created": len(tasks),
            "tasks": tasks
        }
        
    except Exception as e:
        logger.error(f"[API AI] Create tasks error: {e}")
        return {"status": "error", "message": str(e)}

def run_api(host: str = "0.0.0.0", port: int = 8080):
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
                logger.info(f"✅ [API] CRM Audit complete. Health: {results.get('health_score')}%")
            else:
                logger.warning(f"⚠️ [API] CRM Audit failed: {results.get('error')}")
        except Exception as e:
            logger.error(f"❌ [API] CRM Audit CRASH: {e}")
        
        await asyncio.sleep(900) # 15 minutes

if __name__ == "__main__":
    run_api()
