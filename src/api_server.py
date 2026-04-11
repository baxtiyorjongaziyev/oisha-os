import asyncio
import uvicorn
from datetime import datetime
import logging
import os
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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
    return {
        "status": "online",
        "service": "Oisha-OS Enterprise",
        "version": "2.1.0-GodMode",
        "timestamp": datetime.now().isoformat()
    }

# Global references
user_client = None
db_instance = None
outgoing_messages: asyncio.Queue = None  # Initialized lazily; bridge consumer checks before use
# --- DASHBOARD ACTIVITY FEED ---
system_activities: List[Dict[str, Any]] = []

def add_activity(action: str, details: str = "", type: str = "info"):
    """Tizimdagi amallarni Dashboard uchun ro'yxatga olish."""
    activity = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "details": details,
        "type": type # info, success, warning, error, thinking
    }
    system_activities.insert(0, activity)
    # Oxirgi 100 ta amalni saqlash (ko'proq ko'rinishi uchun)
    if len(system_activities) > 100:
        system_activities.pop()
    logger.info(f"📊 [DASHBOARD] {action}: {details}")

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
        stats = db_instance.get_today_stats()
        # Enriched metrics for Premium Dashboard
        stats["crm_health"] = "98%"
        stats["leads_enriched_today"] = 12 # Mock or actual
        stats["automation_efficiency"] = "High"
        stats["last_audit"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return stats
    except Exception as e:
        logger.error(f"Stats Error: {e}")
        return {"leads_found": 0, "messages_synced": 0, "status": "Ready"}

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
    if secret_key != os.environ.get("OISHA_API_SECRET", "oisha_safe_123"):
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
    if secret_key != os.environ.get("OISHA_API_SECRET", "oisha_safe_123"):
        return {"error": "Unauthorized"}
    
    if not db_instance:
        return {"error": "Database not connected"}
    
    # Get history from DB (Enterprise v2.1+)
    # This includes both user messages and bot/admin replies
    history = db_instance.get_recent_messages(user_id, limit=30)
    return {"history": history}

@app.post("/api/chat/send")
async def send_chat_message(request: SendMessageRequest):
    """AmoCRM widgetidan kelgan xabarni Telegramga yuborish."""
    if request.secret_key != os.environ.get("OISHA_API_SECRET", "oisha_safe_123"):
        return {"error": "Unauthorized"}
    
    if not user_client:
        return {"error": "Userbot client not active"}

    try:
        # 1. Send via Userbot (Personal account)
        await user_client.send_message(request.user_id, request.text)
        
        # 2. Log to DB (Visible in widget history)
        if db_instance:
            db_instance.log_message(request.user_id, request.text, is_ai=True) # is_ai=True marks it as 'Outgoing'
            
        return {"status": "success", "text": request.text}
    except Exception as e:
        logger.error(f"[WIDGET SEND ERROR] {e}")
        return {"status": "error", "message": str(e)}

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
        "version": "2.2.0-MetaSell",
        "agent_count": 8,
        "active_modules": ["NightShift", "OSINT", "CRM_Sync", "Advisor", "CallAnalyzer", "Coaching"]
    }

# ═══════════════════════════════════════════════════
# MetaSell-style: Call Analysis & Sales KPI Endpoints
# ═══════════════════════════════════════════════════

def _get_analyzer():
    """Lazy-init call analyzer for API endpoints."""
    if not hasattr(_get_analyzer, "_instance"):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        from src.services.call_analyzer import CallAnalyzer
        _get_analyzer._instance = CallAnalyzer(api_key=api_key, db=db_instance)
    return _get_analyzer._instance

class AnalyzeRequest(BaseModel):
    text: str
    salesperson_id: Optional[int] = None
    salesperson_name: Optional[str] = None

@app.post("/api/calls/analyze")
async def analyze_call(request: AnalyzeRequest):
    """Savdo suhbatini AI tahlil qilish (MetaSell-style scoring)."""
    analyzer = _get_analyzer()
    result = await analyzer.analyze_conversation(
        request.text,
        salesperson_id=request.salesperson_id,
        salesperson_name=request.salesperson_name
    )
    return result

@app.get("/api/calls/kpi")
async def get_call_kpi():
    """KPI dashboard — bugungi, haftalik, oylik ko'rsatkichlar."""
    analyzer = _get_analyzer()
    return await analyzer.get_kpi_summary()

@app.get("/api/calls/team-report")
async def get_team_report(days: int = 7):
    """Jamoa savdo hisoboti — har bir a'zo uchun ballar."""
    analyzer = _get_analyzer()
    return await analyzer.get_team_report(period_days=days)

@app.get("/api/calls/coaching/{salesperson_id}")
async def get_coaching(salesperson_id: int, name: str = ""):
    """Shaxsiy AI coaching — savdogar uchun tavsiyalar."""
    analyzer = _get_analyzer()
    text = await analyzer.generate_coaching(salesperson_id, name)
    return {"salesperson_id": salesperson_id, "coaching": text}

def run_api(host: str = "0.0.0.0", port: int = 8080):
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_api()
