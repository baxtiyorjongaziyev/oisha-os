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
        
    html_content = (
        "<html><head><title>Airtable Muvaffaqiyatli Ulandi</title>"
        "<style>body{font-family:'Inter',sans-serif;text-align:center;padding-top:50px;background:#f3f4f6;color:#1f2937;}"
        ".card{background:white;padding:40px;border-radius:12px;box-shadow:0 4px 6px rgba(0,0,0,0.1);display:inline-block;}h1{color:#10b981;}</style></head>"
        "<body><div class='card'><h1>✅ Muvaffaqiyatli!</h1><p>Oisha-OS Airtable bilan to'g'ridan-to'g'ri bog'landi.</p>"
        "<p>Ushbu oynani yopishingiz mumkin.</p></div></body></html>"
    )
    return HTMLResponse(content=html_content)


@router.get("/api/auth/airtable/status")
async def airtable_status():
    """Check if Airtable is connected."""
    db = get_db()
    tokens = await db.oauth.get_tokens("airtable")
    if tokens:
        return {"status": "connected", "expires_at": tokens.get("expires_at")}
    return {"status": "disconnected"}


_ALLOWED_LOGIN_REDIRECTS: frozenset[str] = frozenset({
    "/",
    "/capi",
    "/api/marketing/capi/console",
})


@router.get("/login")
@router.get("/api/auth/telegram/login")
async def telegram_login(
    request: Request,
    next: Optional[str] = None,
    magic: Optional[str] = None,
    sent: Optional[str] = None,
    err: Optional[str] = None,
):
    """Return multi-method login page: Universal Telegram Account, Google, Email/Password, and API Token."""
    import jwt as pyjwt
    from src.api import auth_service, web_auth_store
    from src.api.security import _session_secret

    safe_next = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    jwt_secret = _session_secret()

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
                    key="oisha_token", value=session_jwt, max_age=auth_service.SESSION_TTL_SECONDS,
                    httponly=True, samesite="lax", path="/",
                )
                return resp
        except Exception as exc:
            logger.warning("[OAUTH] Magic link invalid or expired: %s", type(exc).__name__)

    bot_username = getattr(settings, "BOT_USERNAME", None) or os.getenv("BOT_USERNAME") or "jonairobot"
    auth_url = html.escape(f"/api/auth/telegram/callback?next={safe_next}", quote=True)
    safe_bot_username = html.escape(str(bot_username).replace("@", "").strip() or "jonairobot", quote=True)
    html_content = web_auth_store.render_universal_login_html(
        safe_next=safe_next, safe_bot_username=safe_bot_username, auth_url=auth_url, sent=sent, err_msg=err,
        google_login_uri=str(request.url_for("google_signin_callback")),
    )
    return HTMLResponse(content=html_content)


@router.get("/api/auth/telegram/poll")
async def telegram_login_poll(state: str):
    """Poll whether the user has pressed Start in @jonairobot for web login."""
    from fastapi.responses import JSONResponse
    from src.api import auth_service, web_auth_store
    from src.api.security import _session_secret

    info = web_auth_store.poll_tg_login_state(state)
    if not info or info.get("status") != "approved":
        return JSONResponse({"status": (info or {}).get("status", "invalid")})
    jwt_secret = _session_secret()
    if not jwt_secret:
        return JSONResponse({"status": "error"}, status_code=503)
    session_jwt = auth_service.issue_session_jwt(
        user_id=int(info.get("user_id") or 1),
        username=str(info.get("username") or "telegram_user"),
        first_name=str(info.get("first_name") or "Foydalanuvchi"),
        role=str(info.get("role") or "targetolog"),
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    target = info.get("next_url") if info.get("next_url") in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    resp = JSONResponse({"status": "approved", "redirect": target})
    resp.set_cookie(
        key="oisha_token", value=session_jwt, max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True, samesite="lax", path="/",
    )
    return resp


def _set_session_redirect(user_id: int, username: str, first_name: str, role: str, jwt_secret: str, target: str) -> RedirectResponse:
    from src.api import auth_service
    session_jwt = auth_service.issue_session_jwt(
        user_id=int(user_id), username=str(username), first_name=str(first_name),
        role=str(role or "targetolog"), secret=jwt_secret, ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    resp = RedirectResponse(url=target, status_code=303)
    resp.set_cookie(key="oisha_token", value=session_jwt, max_age=auth_service.SESSION_TTL_SECONDS, httponly=True, samesite="lax", path="/")
    return resp


@router.post("/api/auth/telegram/otp")
async def telegram_otp_login(code: str = Form(...), next: Optional[str] = Form(None)):
    """Verify 6-digit OTP code issued by @jonairobot and set session cookie."""
    from src.api import web_auth_store
    from src.api.security import _session_secret

    safe_next = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    info = web_auth_store.poll_tg_login_state(f"otp_{str(code or '').strip()}")
    jwt_secret = _session_secret()
    if not info or info.get("status") != "approved" or not jwt_secret:
        return RedirectResponse(url=f"/login?next={safe_next}&err=6-xonali+kod+xato+yoki+muddati+tugagan", status_code=303)
    return _set_session_redirect(
        int(info.get("user_id") or 1), str(info.get("username") or "telegram_user"),
        str(info.get("first_name") or "Foydalanuvchi"), str(info.get("role") or "targetolog"), jwt_secret, safe_next,
    )


@router.post("/api/auth/email/login")
async def email_password_login(
    email: str = Form(...), password: str = Form(...), name: Optional[str] = Form(None),
    mode: str = Form("login"), next: Optional[str] = Form(None),
):
    """Login or register using Email + Password."""
    from src.api import web_auth_store
    from src.api.security import _session_secret

    safe_next = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    user = web_auth_store.register_or_login_email(email, password, name=name, is_register=(mode == "register"))
    jwt_secret = _session_secret()
    if not user or not jwt_secret:
        msg = "Ushbu email band yoki ma'lumot xato" if mode == "register" else "Email yoki parol noto'g'ri (yoki avval Ro'yxatdan o'ting)"
        return RedirectResponse(url=f"/login?next={safe_next}&err={msg}", status_code=303)
    return _set_session_redirect(int(user["id"]), str(user["email"]), str(user["name"]), str(user.get("role") or "targetolog"), jwt_secret, safe_next)


@router.post("/api/auth/google/callback")
async def google_signin_callback(
    request: Request, credential: str = Form(...), next: Optional[str] = None,
    g_csrf_token: str = Form(""),
):
    """Handle Google Identity Services Sign-In callback."""
    from src.api import web_auth_store
    from src.api.security import _session_secret

    safe_next = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    cookie_csrf = request.cookies.get("g_csrf_token", "")
    if not cookie_csrf or not g_csrf_token or not hmac.compare_digest(
        cookie_csrf.encode(), g_csrf_token.encode(),
    ):
        raise HTTPException(400, "Invalid Google CSRF token")
    jwt_secret = _session_secret()
    if not jwt_secret:
        raise HTTPException(503, "Session signing secret is not configured")
    user = await asyncio.to_thread(web_auth_store.verify_google_credential, credential)
    if not user:
        return RedirectResponse(url=f"/login?next={safe_next}&err=Google+avtorizatsiya+xatosi", status_code=303)
    return _set_session_redirect(int(user["id"]), str(user["email"]), str(user["name"]), str(user.get("role") or "targetolog"), jwt_secret, safe_next)


@router.api_route("/api/auth/logout", methods=["GET", "POST"])
async def web_logout():
    """Clear browser session cookie and redirect to login page."""
    resp = RedirectResponse(url="/login?next=/api/marketing/capi/console", status_code=303)
    resp.delete_cookie(key="oisha_token", path="/")
    return resp


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
        user_id=1, username=subject, first_name=subject, role=role,
        secret=jwt_secret, ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(key="oisha_token", value=session_jwt, max_age=auth_service.SESSION_TTL_SECONDS, httponly=True, samesite="lax", path="/")
    return response


@router.get("/api/auth/telegram/callback")
async def telegram_callback(
    id: int, first_name: str, hash: str, last_name: str = None,
    username: str = None, photo_url: str = None, auth_date: int = None, next: str = None,
):
    """Handle Telegram OAuth callback."""
    from src.api import auth_service
    from src.api.security import _session_secret

    bot_token = settings.BOT_TOKEN.get_secret_value()
    fields = {"id": str(id) if id is not None else None, "first_name": first_name, "auth_date": str(auth_date) if auth_date is not None else None, "last_name": last_name, "username": username, "photo_url": photo_url}
    if not auth_service.verify_telegram_hash(fields, bot_token, hash) or not auth_service.is_auth_date_fresh(auth_date):
        raise HTTPException(status_code=403, detail="Invalid Telegram Auth Hash or expired")

    db = get_db()
    await db.users.upsert_user(user_id=id, username=username, first_name=first_name, last_name=last_name)
    user = await db.users.get_user(id)
    role = user.get("role", "targetolog") if user else "targetolog"
    whitelist = {str(x) for x in (getattr(settings, "WHITELIST_IDS", None) or [])}
    role = "owner" if str(id) == str(settings.OWNER_ID) else ("admin" if str(id) in whitelist and role == "admin" else "targetolog")

    jwt_secret = _session_secret()
    if not jwt_secret or len(jwt_secret.encode("utf-8")) < 32:
        logger.error("[OAUTH] Session secret is not configured or shorter than 32 bytes")
        raise HTTPException(status_code=503, detail="Session signing secret is not configured")

    token = auth_service.issue_session_jwt(
        user_id=id, username=username, first_name=first_name, role=role,
        secret=jwt_secret, ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    target = next if next in _ALLOWED_LOGIN_REDIRECTS else "/api/marketing/capi/console"
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(key="oisha_token", value=token, max_age=auth_service.SESSION_TTL_SECONDS, httponly=True, samesite="lax", path="/")
    return response
