import asyncio
import base64
import hashlib
import logging
import os
import time
from typing import Dict, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from src.context import app_ctx
from src.database import get_db
from src.services.core.airtable_client import AirtableClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["oauth"])


class _OAuthSessionStore:
    def __init__(self) -> None:
        self._data: Dict[str, tuple[str, float]] = {}

    async def set(self, key: str, value: str, ttl: int = 600) -> None:
        self._data[key] = (value, time.time() + ttl)

    async def get(self, key: str) -> Optional[str]:
        item = self._data.get(key)
        if not item:
            return None
        val, expires = item
        if time.time() > expires:
            self._data.pop(key, None)
            return None
        return val

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


_oauth_sessions = _OAuthSessionStore()

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


@router.post("/api/telegram/extension/send")
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

@router.get("/api/auth/airtable/login")
async def airtable_login():
    """Redirect to Airtable for OAuth authorization."""
    # Generate PKCE code verifier and challenge
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    state = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')
    
    # Store verifier temporarily to use in callback
    await _oauth_sessions.set(state, code_verifier, ttl=600)
    
    client = AirtableClient()
    url = client.get_authorization_url(state, code_challenge)
    return RedirectResponse(url)


@router.get("/api/auth/airtable/callback")
async def airtable_callback(code: str = None, state: str = None, error: str = None, error_description: str = None):
    """Handle Airtable OAuth callback."""
    if error:
        raise HTTPException(status_code=400, detail=f"Airtable Auth Error: {error} - {error_description}")
        
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
        
    code_verifier = await _oauth_sessions.get(state)
    if code_verifier:
        await _oauth_sessions.delete(state)
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


@router.get("/api/auth/airtable/status")
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

@router.get("/api/auth/telegram/login")
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


@router.get("/api/auth/telegram/callback")
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
