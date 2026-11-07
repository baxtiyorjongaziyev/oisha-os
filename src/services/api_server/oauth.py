import asyncio
import base64
import hashlib
import hmac
import html
import logging
import os
import time
from typing import Dict, Optional
from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from src.context import app_ctx
from src.database import get_db
from src.services.core.airtable_client import AirtableClient
from src.settings import settings

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

from src.services.api_server.telegram_extension import (
    router as telegram_extension_router,
    telegram_extension_history,
    telegram_extension_send,
)
router.include_router(telegram_extension_router)

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

_ALLOWED_LOGIN_REDIRECTS: frozenset[str] = frozenset({
    "/",
    "/capi",
    "/api/marketing/capi/console",
})


_ATTENDANCE_PAGES = frozenset({"/api/attendance/app", "/api/attendance/app/admin"})


def _safe_redirect_target(target: Optional[str]) -> str:
    """Return a strictly whitelisted relative redirection path with zero untrusted taint."""
    if not target or not isinstance(target, str):
        return "/"
    cleaned = target.strip()
    if cleaned == "/capi":
        return "/capi"
    if cleaned == "/api/marketing/capi/console":
        return "/api/marketing/capi/console"
    if cleaned in _ATTENDANCE_PAGES:
        return cleaned
    return "/"


def _safe_login_next(target: Optional[str]) -> str:
    """Return a strictly whitelisted next parameter or empty string."""
    if not target or not isinstance(target, str):
        return ""
    cleaned = target.strip()
    if cleaned == "/capi":
        return "/capi"
    if cleaned == "/api/marketing/capi/console":
        return "/api/marketing/capi/console"
    if cleaned in _ATTENDANCE_PAGES:
        return cleaned
    return ""


@router.get("/api/auth/telegram/login")
async def telegram_login(next: Optional[str] = None):
    """Return an HTML page with seamless Telegram Deep-Link and OTP login."""
    from src.services.api_server.telegram_seamless_auth import render_telegram_login_response

    return render_telegram_login_response(next=next)


@router.get("/api/auth/telegram/poll")
async def telegram_poll(state: str, next: Optional[str] = None):
    """Poll deep-link authorization state and issue JWT session cookie on approval."""
    from src.services.api_server.telegram_seamless_auth import handle_telegram_poll

    return handle_telegram_poll(state=state, next=next)


@router.post("/api/auth/telegram/otp")
async def telegram_otp(otp: str = Form(...), next: Optional[str] = Form(None)):
    """Authenticate via 6-digit Telegram OTP code."""
    from src.services.api_server.telegram_seamless_auth import handle_telegram_otp

    return handle_telegram_otp(otp=otp, next=next)


@router.post("/api/auth/token/login")
async def token_login(token: str = Form(...), next: Optional[str] = Form(None)):
    """Direct token/key authentication (fallback for IP access or direct targetolog login)."""
    import json
    from src.api import auth_service
    from src.api.security import _auth_setting, _clean, _session_secret

    raw_token = _clean(token)
    api_secret = _auth_setting("OISHA_API_SECRET")
    jwt_secret = _session_secret()
    role, subject = None, None

    if api_secret and hmac.compare_digest(raw_token, api_secret):
        role, subject = "owner", "owner-token"
    else:
        try:
            svc_tokens = json.loads(_auth_setting("SERVICE_TOKENS_JSON") or "{}")
        except Exception:
            svc_tokens = {}
        if isinstance(svc_tokens, dict) and raw_token in svc_tokens:
            role = "targetolog"
            subject = svc_tokens[raw_token].get("subject", "targetolog")

    if not role or not jwt_secret:
        raise HTTPException(status_code=401, detail="Noto'g'ri kalit yoki token kiritildi")

    session_jwt = auth_service.issue_session_jwt(
        user_id=1,
        username=subject,
        first_name=subject,
        role=role,
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    target = _safe_redirect_target(next)
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(
        key="oisha_token",
        value=session_jwt,
        max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/api/auth/email/login")
async def email_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: Optional[str] = Form(None),
):
    """Email + parol bilan kirish. Faqat owner yaratgan hisoblar; roʼyxatdan oʼtish yoʼq."""
    from src.api import auth_service
    from src.api import web_auth_store
    from src.api.security import _session_secret

    clean_email = (email or "").strip().lower()[:254]
    ip = (request.client.host if request.client else "") or "unknown"
    if web_auth_store.login_throttled(clean_email, ip):
        raise HTTPException(status_code=429, detail="Juda koʼp urinish. 15 daqiqadan keyin qayta urinib koʼring")

    user = web_auth_store.authenticate_email(clean_email, password or "")
    jwt_secret = _session_secret()
    if not user or not jwt_secret:
        web_auth_store.record_login_failure(clean_email, ip)
        raise HTTPException(status_code=401, detail="Email yoki parol notoʼgʼri")

    web_auth_store.clear_login_failures(clean_email)
    session_jwt = auth_service.issue_session_jwt(
        user_id=int(user["id"]),
        username=user["email"],
        first_name=user.get("name") or user["email"],
        role=str(user.get("role") or "targetolog"),
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    response = RedirectResponse(url=_safe_redirect_target(next), status_code=303)
    response.set_cookie(
        key="oisha_token",
        value=session_jwt,
        max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/api/auth/telegram/callback")
async def telegram_callback(
    id: int,
    first_name: str,
    hash: str,
    last_name: str = None,
    username: str = None,
    photo_url: str = None,
    auth_date: int = None,
    next: str = None,
):
    """Handle Telegram OAuth callback."""
    from src.api import auth_service

    # 1. Verify hash
    bot_token = settings.BOT_TOKEN.get_secret_value()
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
    if str(id) == str(settings.OWNER_ID):
        role = "owner"

    # Dedicated JWT secret (strictly separate from Telegram bot_token)
    raw_secret = os.environ.get("JWT_SECRET") or getattr(settings, "JWT_SECRET", "")
    jwt_secret = str(
        getattr(raw_secret, "get_secret_value", lambda: raw_secret)()
        if hasattr(raw_secret, "get_secret_value")
        else raw_secret or ""
    ).strip()
    if not jwt_secret or len(jwt_secret.encode("utf-8")) < 32:
        logger.error("[OAUTH] JWT_SECRET is not configured or shorter than 32 bytes")
        raise HTTPException(
            status_code=503,
            detail="Session signing secret (JWT_SECRET) is not configured or too short (min 32 bytes)",
        )

    token = auth_service.issue_session_jwt(
        user_id=id,
        username=username,
        first_name=first_name,
        role=role,
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )

    # Create response that stores the cookie and redirects to Dashboard or next URL
    target = _safe_redirect_target(next)
    response = RedirectResponse(url=target)
    response.set_cookie(
        key="oisha_token",
        value=token,
        max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response
