import asyncio
import uvicorn
from datetime import datetime
import logging
import os
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import queue
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
audit_agent = None

# --- COMMAND QUEUE (Shared with Main Thread) ---
command_queue = queue.Queue()

# --- DASHBOARD CACHE ---
cached_status: Dict[str, Any] = {
    "status": "offline",
    "message": "Tizim tayyorlanmoqda...",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# --- CRM AUDIT CACHE ---
cached_crm_audit: Dict[str, Any] = {
    "health_score": 98,
    "summary": "Audit kutilmoqda...",
    "timestamp": datetime.now().isoformat()
}
# --- DASHBOARD ACTIVITY FEED ---
system_activities: List[Dict[str, Any]] = [
    {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "action": "🚀 System Boot",
        "details": "Oisha-OS Strategic Intelligence is online and listening.",
        "type": "success"
    }
]

# --- WAZZUP BRIDGE (Outgoing Messages Queue) ---
outgoing_messages = asyncio.Queue()

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

@app.get("/api/system/status")
async def get_system_status():
    global cached_status, cached_crm_audit
    # Update health score from audit cache
    data = cached_status.copy()
    data["crm_health"] = f"{cached_crm_audit.get('health_score', 98)}%"
    return data

def update_api_status(status: str, message: str):
    """Updates the thread-safe status cache for the dashboard."""
    global cached_status
    cached_status = {
        "status": status,
        "message": message,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        
        stats["last_audit"] = cached_crm_audit.get("timestamp", datetime.now().isoformat())
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
    history = await db_instance.get_recent_messages(user_id, limit=30)
    return {"history": history}

@app.post("/api/chat/send")
async def send_chat_message(request: SendMessageRequest):
    """AmoCRM widgetidan kelgan xabarni Telegramga yuborish (Queued)."""
    if request.secret_key != os.environ.get("OISHA_API_SECRET", "oisha_safe_123"):
        return {"error": "Unauthorized"}
    
    # Push to queue for Main Thread execution
    command_queue.put({
        "cmd": "send_message",
        "user_id": request.user_id,
        "text": request.text
    })
    
    return {"status": "success", "message": "Xabar navbatga qo'yildi"}

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

def run_api(host: str = "0.0.0.0", port: int = 8080):
    uvicorn.run(app, host=host, port=port)

async def background_crm_audit_task():
    """Background task to refresh CRM audit data every 15 minutes."""
    from src.services.crm_audit import AmoCRMAudit
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
