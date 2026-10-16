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


@router.get("/api/auth/telegram/login")
async def telegram_login(next: Optional[str] = None, magic: Optional[str] = None, sent: Optional[str] = None):
    """Return an HTML page with Telegram Login Widget, 1-click Bot Push Login, and Token Login."""
    import jwt as pyjwt
    from src.api import auth_service
    from src.api.security import _session_secret

    safe_next = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    jwt_secret = _session_secret()

    # 1-Click Magic Link verification
    if magic and jwt_secret:
        try:
            payload = pyjwt.decode(magic, jwt_secret, algorithms=["HS256"])
            if payload.get("purpose") == "magic_login" and payload.get("role") in ("owner", "admin", "targetolog"):
                session_jwt = auth_service.issue_session_jwt(
                    user_id=int(payload.get("uid") or 1),
                    username=str(payload.get("sub") or "owner"),
                    first_name=str(payload.get("name") or "Baxtiyorjon"),
                    role=str(payload.get("role") or "owner"),
                    secret=jwt_secret,
                    ttl_seconds=auth_service.SESSION_TTL_SECONDS,
                )
                resp = RedirectResponse(url=safe_next, status_code=303)
                resp.set_cookie(
                    key="oisha_token",
                    value=session_jwt,
                    max_age=auth_service.SESSION_TTL_SECONDS,
                    httponly=True,
                    samesite="lax",
                    path="/",
                )
                return resp
        except Exception as exc:
            logger.warning("[OAUTH] Magic link invalid or expired: %s", type(exc).__name__)

    bot_username = getattr(settings, "BOT_USERNAME", None) or os.getenv("BOT_USERNAME") or "jonairobot"
    raw_auth_url = f"/api/auth/telegram/callback?next={safe_next}"
    auth_url = html.escape(raw_auth_url, quote=True)
    safe_bot_username = html.escape(str(bot_username).replace("@", "").strip() or "jonairobot", quote=True)
    sent_banner = (
        '<div style="background:#ECFDF5;border:1px solid #10B981;color:#065F46;padding:12px;border-radius:8px;margin-bottom:16px;font-size:13px;font-weight:600;">'
        '✅ Telegram\'ingizga (@jonairobot dan) 1-bosishda kirish havolasi yuborildi! Telegram\'ni ochib havolani bosing.'
        '</div>'
        if sent == "1" else ""
    )
    html_content = f"""
    <html>
        <head>
            <title>Oisha-OS Enterprise Login</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta name="referrer" content="strict-origin-when-cross-origin">
            <style>
                body {{ font-family: 'Inter', -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f3f4f6; color: #1f2937; margin: 0; padding: 16px; }}
                .card {{ background: white; padding: 34px 30px; border-radius: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center; max-width: 420px; width: 100%; box-sizing: border-box; }}
                h2 {{ color: #2563eb; margin: 0 0 10px; font-size: 22px; }}
                p {{ color: #4b5563; margin-bottom: 18px; font-size: 14px; line-height: 1.5; }}
                .tg-push-btn {{ width: 100%; background: #0088cc; color: white; border: none; padding: 12px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 14px; }}
                .tg-push-btn:hover {{ background: #0077b5; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Oisha-OS Enterprise</h2>
                <p>Tizimga kirish uchun Telegram orqali tasdiqlang:</p>
                {sent_banner}
                <form method="POST" action="/api/auth/token/login" style="margin:0 0 12px;">
                    <input type="hidden" name="next" value="{safe_next}">
                    <input type="hidden" name="token" value="__SEND_TELEGRAM_MAGIC__">
                    <button type="submit" class="tg-push-btn">📲 Telegram Botga Kirish Havolasini Yuborish</button>
                </form>
                <div style="min-height: 44px; margin-bottom: 16px; display: flex; justify-content: center;">
                    <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-login="{safe_bot_username}" data-size="large" data-auth-url="{auth_url}" data-request-access="write"></script>
                </div>
                <div style="margin-top: 14px; border-top: 1px solid #e5e7eb; padding-top: 16px;">
                    <p style="font-size: 13px; color: #6b7280; margin-bottom: 10px;">Yoki kirish kaliti (Token) orqali kiring:</p>
                    <form method="POST" action="/api/auth/token/login" style="display: flex; flex-direction: column; gap: 8px;">
                        <input type="hidden" name="next" value="{safe_next}">
                        <input type="password" name="token" placeholder="Kirish kaliti (API Secret yoki Token)" required style="padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; box-sizing: border-box;">
                        <button type="submit" style="background: #2563eb; color: white; border: none; padding: 10px; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 13px;">Tizimga kirish</button>
                    </form>
                </div>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/api/auth/token/login")
async def token_login(request: Request, token: str = Form(...), next: Optional[str] = Form(None)):
    """Direct token/key authentication or 1-click Telegram Bot Magic Link sender."""
    import json
    import jwt as pyjwt
    import requests as std_requests
    from src.api import auth_service
    from src.api.security import _auth_setting, _clean, _session_secret

    raw_token = _clean(token)
    api_secret = _auth_setting("OISHA_API_SECRET")
    jwt_secret = _session_secret()
    target = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"

    if raw_token == "__SEND_TELEGRAM_MAGIC__" and jwt_secret:
        owner_id = int(getattr(settings, "OWNER_ID", 0) or os.getenv("OWNER_ID") or 0)
        bot_token = settings.BOT_TOKEN.get_secret_value() if getattr(settings, "BOT_TOKEN", None) else os.getenv("BOT_TOKEN", "")
        if owner_id and bot_token:
            magic_jwt = pyjwt.encode(
                {"sub": "owner", "uid": owner_id, "name": "Baxtiyorjon", "role": "owner",
                 "purpose": "magic_login", "exp": int(time.time()) + 86400 * 7},
                jwt_secret,
                algorithm="HS256",
            )
            scheme = request.headers.get("x-forwarded-proto") or (
                "https" if "jonbranding.uz" in request.url.netloc else request.url.scheme
            )
            base_url = f"{scheme}://{request.url.netloc}"
            magic_url = f"{base_url}/api/auth/telegram/login?magic={magic_jwt}&next={target}"
            msg_text = (
                "🔐 <b>Oisha CAPI Platform — Tizimga 1-bosishda kirish</b>\n\n"
                "Quyidagi tugmani yoki havolani bosing — parol terishsiz to'g'ridan-to'g'ri CAPI Dashboard ochiladi:\n\n"
                f"👉 <a href=\"{magic_url}\">CAPI Platformaga Kirish (1-bosishda)</a>"
            )
            await asyncio.to_thread(
                std_requests.post,
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": owner_id,
                    "text": msg_text,
                    "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": [[{"text": "🚀 CAPI Dashboardni Ochish", "url": magic_url}]]},
                },
                timeout=10,
            )
            return RedirectResponse(url=f"/api/auth/telegram/login?next={target}&sent=1", status_code=303)

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
    from src.api.security import _session_secret

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
    if not auth_service.is_auth_date_fresh(auth_date):
        raise HTTPException(status_code=403, detail="Auth date is expired")

    db = get_db()
    await db.users.upsert_user(user_id=id, username=username, first_name=first_name, last_name=last_name)
    user = await db.users.get_user(id)
    role = user.get("role", "targetolog") if user else "targetolog"
    whitelist = {str(x) for x in (getattr(settings, "WHITELIST_IDS", None) or [])}
    if str(id) == str(settings.OWNER_ID):
        role = "owner"
    elif str(id) in whitelist:
        role = "admin" if role == "admin" else "targetolog"
    else:
        role = "targetolog"

    jwt_secret = _session_secret()
    if not jwt_secret or len(jwt_secret.encode("utf-8")) < 32:
        logger.error("[OAUTH] Session secret is not configured or shorter than 32 bytes")
        raise HTTPException(status_code=503, detail="Session signing secret is not configured")

    token = auth_service.issue_session_jwt(
        user_id=id,
        username=username,
        first_name=first_name,
        role=role,
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    target = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(
        key="oisha_token",
        value=token,
        max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response
