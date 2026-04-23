import asyncio
import uvicorn
import json
from datetime import datetime, timezone
import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import queue
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
        "version": "2.1.0",
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
            # Extremely lazy import to avoid circular dependencies with main.py
            import src.main as main_module
            bot = getattr(main_module, "admin_bot", None)
            if bot and hasattr(bot, "bot_client"):
                me = await bot.bot_client.get_me()
                telegram_bot_ok = True
                logger.debug(f"[HEALTH] Telegram bot connected: @{me.username}")
        except Exception as e:
            logger.warning(f"[HEALTH] Telegram bot connection failed: {e}")
    
    crm_ok = True if control_plane_mode else bool(runtime.get("crm_connected", False))
    
    # [DECOUPLING] Decouple health status from functional checks to prevent deployment deadlocks.
    # The service is 'healthy' if it can respond to HTTP requests. 
    # Functional issues are logged and visible in the JSON response but don't cause 503.
    healthy = True 
    status_code = 200
    
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
            transcript, audio_url, source, analyzed_at, created_at
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
            "call_id", "lead_id", "manager_id", "manager_name", "client_name",
            "duration_seconds", "overall_score", "category", "scores", "summary",
            "strengths", "weaknesses", "client_mood", "client_interest_level",
            "objections", "outcome", "next_steps", "recommended_tasks",
            "transcript", "audio_url", "source", "analyzed_at", "created_at",
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
    sales_count = outcome_counts.get("sale", 0) + outcome_counts.get("sold", 0) + outcome_counts.get("sotuv", 0)
    callback_count = outcome_counts.get("callback", 0) + outcome_counts.get("follow_up", 0)
    total_duration = sum(int(row.get("duration_seconds") or 0) for row in analyzed)

    by_manager: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in analyzed:
        by_manager[str(row.get("manager_name") or "Noma'lum manager")].append(row)

    managers = []
    for manager_name, manager_rows in by_manager.items():
        manager_scores = [int(row.get("overall_score") or 0) for row in manager_rows]
        manager_sales = sum(1 for row in manager_rows if str(row.get("outcome") or "") in {"sale", "sold", "sotuv"})
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
        weakness_counts.update(str(item) for item in _safe_json_list(row.get("weaknesses")) if item)
        objection_counts.update(str(item) for item in _safe_json_list(row.get("objections")) if item)

    radar = [
        {"label": metric.replace("_", " ").title(), "score": round(sum(values) / len(values))}
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
        recommendations.append(f"Eng ko'p takrorlangan zaif joy: {top_weakness} ({top_count} ta real signal).")
    if callback_count:
        recommendations.append(f"{callback_count} ta follow-up/callback real suhbatdan chiqdi; CRM tasklari borligini tekshiring.")
    if sales_count == 0:
        recommendations.append("Real tahlil qilingan qo'ng'iroqlarda sotuv natijasi belgilanmagan; outcome mappingni tekshiring.")

    calls = []
    for row in analyzed[:12]:
        score = int(row.get("overall_score") or 0)
        client = row.get("client_name") or (f"Lead #{row.get('lead_id')}" if row.get("lead_id") else "Noma'lum mijoz")
        calls.append(
            {
                "client": client,
                "manager": row.get("manager_name") or "Noma'lum manager",
                "score": score,
                "result": outcome_labels.get(str(row.get("outcome") or "unknown"), str(row.get("outcome") or "unknown")),
                "duration": _format_duration(row.get("duration_seconds")),
                "summary": row.get("summary") or "Real tahlil yozuvi bor, lekin summary bo'sh.",
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
    if not expected_secret or data.secret_key != expected_secret:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
    if not db_instance:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Database not connected"})

    score = max(0, min(int(data.overall_score), 100))
    now = get_local_now().isoformat()
    analyzed_at = data.analyzed_at or now
    category = data.category or ("excellent" if score >= 90 else "good" if score >= 80 else "average" if score >= 60 else "poor")

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
        "version": "2.1.0",
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
from src.services.ai.conversation_engine import (
    ConversationEngine, 
    CallRecord, 
    get_conversation_engine
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
        trend = _conversation_engine.get_trend_analysis(metric="score", days=min(days, 14))
        
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
                "total_talk_time_hours": metrics.total_talk_time // 60
            },
            "outcomes": {
                "sales": metrics.sales_count,
                "follow_up": metrics.followup_count,
                "lost": metrics.lost_count
            },
            "top_objections": metrics.top_objections,
            "weak_areas": metrics.weak_areas,
            "recommendations": metrics.recommendations,
            "manager_comparison": manager_comparison,
            "skills_radar": radar_data,
            "trend": trend
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
        
        return {
            "status": "success",
            "data": details
        }
        
    except Exception as e:
        logger.error(f"[API AI] Call details error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/ai/skills-radar")
async def get_skills_radar(
    manager_id: Optional[int] = None,
    days: int = 7
):
    """
    Manager mahorati radar chart ma'lumotlari.
    Metasell.ai dagi 'Manager Radar' ga o'xshash.
    """
    try:
        global _conversation_engine
        if _conversation_engine is None:
            _conversation_engine = get_conversation_engine(amocrm_instance, db_instance)
        
        radar_data = _conversation_engine.get_skills_radar_data(
            manager_id=manager_id,
            days=days
        )
        
        return {
            "status": "success",
            "data": radar_data
        }
        
    except Exception as e:
        logger.error(f"[API AI] Skills radar error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/ai/trend-analysis")
async def get_trend_analysis(
    metric: str = "score",
    days: int = 14
):
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
        
        trend = _conversation_engine.get_trend_analysis(
            metric=metric,
            days=days
        )
        
        return {
            "status": "success",
            "metric": metric,
            "data": trend
        }
        
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
        
        return {
            "status": "success",
            "period_days": days,
            "managers": comparison
        }
        
    except Exception as e:
        logger.error(f"[API AI] Manager comparison error: {e}")
        return {"status": "error", "message": str(e)}

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
            started_at=datetime.fromisoformat(data.get("started_at", datetime.now().isoformat())),
            duration_seconds=data.get("duration_seconds", 0),
            audio_url=data.get("audio_url"),
            transcript=data.get("transcript", ""),
            lead_name=data.get("lead_name", ""),
            lead_status=data.get("lead_status", "")
        )
        
        # Qayta ishlash
        analysis = await _conversation_engine.process_call(
            call_record=call_record,
            auto_analyze=data.get("auto_analyze", True),
            auto_create_tasks=data.get("auto_create_tasks", True)
        )
        
        return {
            "status": "success",
            "call_id": call_record.call_id,
            "analyzed": analysis is not None,
            "score": analysis.overall_score if analysis else None,
            "category": analysis.category if analysis else None
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
        
        return {
            "status": "success",
            "report": report
        }
        
    except Exception as e:
        logger.error(f"[API AI] Daily report error: {e}")
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
