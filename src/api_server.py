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

def run_api(host: str = "0.0.0.0", port: int = 8080):
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_api()
