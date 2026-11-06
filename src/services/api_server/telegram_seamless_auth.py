"""Seamless Telegram Authentication for Oisha-OS (Deep Link + OTP fallback)."""
from __future__ import annotations

import html
import logging
import os
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from src.api import auth_service
from src.api.web_auth_store import (
    create_tg_login_state,
    poll_tg_login_state,
)
from src.settings import settings

logger = logging.getLogger(__name__)


def _get_jwt_secret() -> str:
    """Return active JWT secret or raise 503 if unconfigured."""
    raw_secret = os.environ.get("JWT_SECRET") or getattr(settings, "JWT_SECRET", "")
    jwt_secret = str(
        getattr(raw_secret, "get_secret_value", lambda: raw_secret)()
        if hasattr(raw_secret, "get_secret_value")
        else raw_secret or ""
    ).strip()
    if not jwt_secret or len(jwt_secret.encode("utf-8")) < 32:
        logger.error("[WEB-AUTH] JWT_SECRET is not configured or shorter than 32 bytes")
        raise HTTPException(
            status_code=503,
            detail="Session signing secret (JWT_SECRET) is not configured or too short (min 32 bytes)",
        )
    return jwt_secret


def _set_auth_cookie(response: RedirectResponse | JSONResponse, token: str) -> None:
    """Attach secure session cookie to response."""
    response.set_cookie(
        key="oisha_token",
        value=token,
        max_age=auth_service.SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


def handle_telegram_poll(state: str, next: Optional[str] = None) -> JSONResponse:
    """Check pending login state and return session cookie when approved."""
    from src.services.api_server.oauth import _safe_redirect_target

    clean_state = str(state or "").strip()
    if not clean_state:
        return JSONResponse({"status": "invalid"}, status_code=400)

    data = poll_tg_login_state(clean_state)
    if not data or data.get("status") == "expired":
        return JSONResponse({"status": "expired"})
    if data.get("status") != "approved":
        return JSONResponse({"status": "pending"})

    jwt_secret = _get_jwt_secret()
    token = auth_service.issue_session_jwt(
        user_id=int(data.get("user_id") or 1),
        username=data.get("username") or "telegram_user",
        first_name=data.get("first_name") or "User",
        role=data.get("role") or "client",
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    target = _safe_redirect_target(data.get("next_url") or next)
    resp = JSONResponse({"status": "approved", "redirect_url": target})
    _set_auth_cookie(resp, token)
    return resp


def handle_telegram_otp(otp: str, next: Optional[str] = None) -> RedirectResponse:
    """Authenticate using a 6-digit Telegram OTP code."""
    from src.services.api_server.oauth import _safe_redirect_target

    clean_code = str(otp or "").strip().replace(" ", "").replace("-", "")
    if not clean_code or not clean_code.isdigit():
        raise HTTPException(status_code=400, detail="Kod 6 ta raqamdan iborat boʻlishi kerak")

    data = poll_tg_login_state(f"otp_{clean_code}")
    if not data or data.get("status") != "approved":
        raise HTTPException(status_code=401, detail="Kod notoʻgʻri yoki muddati oʻtgan")

    jwt_secret = _get_jwt_secret()
    token = auth_service.issue_session_jwt(
        user_id=int(data.get("user_id") or 1),
        username=data.get("username") or "telegram_user",
        first_name=data.get("first_name") or "User",
        role=data.get("role") or "client",
        secret=jwt_secret,
        ttl_seconds=auth_service.SESSION_TTL_SECONDS,
    )
    target = _safe_redirect_target(data.get("next_url") or next)
    resp = RedirectResponse(url=target, status_code=303)
    _set_auth_cookie(resp, token)
    return resp


def render_telegram_login_response(next: Optional[str] = None) -> HTMLResponse:
    """Render unified login page with Deep-Link, OTP code, and master token fallbacks."""
    from src.services.api_server.oauth import _safe_login_next

    bot_username = getattr(settings, "BOT_USERNAME", "jonairobot")
    safe_bot = html.escape(str(bot_username).replace("@", ""), quote=True)
    safe_next = _safe_login_next(next)
    raw_auth_url = (
        f"/api/auth/telegram/callback?next={safe_next}"
        if safe_next
        else "/api/auth/telegram/callback"
    )
    auth_url = html.escape(raw_auth_url, quote=True)
    escaped_next = html.escape(safe_next, quote=True)

    state = create_tg_login_state(next_url=safe_next or "/", ttl=600)
    deep_link = f"https://t.me/{safe_bot}?start=login_{state}"

    html_content = f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <title>Oisha-OS Enterprise — Tizimga kirish</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 16px;
            box-sizing: border-box;
        }}
        .card {{
            background: #1e293b;
            padding: 32px 28px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            max-width: 420px;
            width: 100%;
            border: 1px solid #334155;
            box-sizing: border-box;
            text-align: center;
        }}
        .logo {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, #2563eb, #38bdf8);
            border-radius: 12px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            margin-bottom: 12px;
        }}
        h2 {{ color: #ffffff; margin: 0 0 6px; font-size: 22px; font-weight: 700; }}
        p.sub {{ color: #94a3b8; font-size: 13px; margin: 0 0 24px; line-height: 1.4; }}
        .btn-tg {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            background: #0284c7;
            color: #ffffff;
            text-decoration: none;
            padding: 13px 16px;
            border-radius: 10px;
            font-weight: 600;
            font-size: 14px;
            box-sizing: border-box;
            transition: background 0.15s, transform 0.1s;
        }}
        .btn-tg:hover {{ background: #0369a1; transform: translateY(-1px); }}
        .btn-tg svg {{ width: 20px; height: 20px; fill: currentColor; }}
        .status-box {{
            margin-top: 14px;
            font-size: 12px;
            color: #38bdf8;
            min-height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }}
        .spinner {{
            width: 12px;
            height: 12px;
            border: 2px solid #38bdf8;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .divider {{
            display: flex;
            align-items: center;
            text-align: center;
            color: #64748b;
            font-size: 11px;
            margin: 20px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .divider::before, .divider::after {{
            content: '';
            flex: 1;
            border-bottom: 1px solid #334155;
        }}
        .divider:not(:empty)::before {{ margin-right: 10px; }}
        .divider:not(:empty)::after {{ margin-left: 10px; }}
        .inp {{
            width: 100%;
            padding: 10px 12px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #ffffff;
            font-size: 13px;
            box-sizing: border-box;
            outline: none;
        }}
        .inp:focus {{ border-color: #38bdf8; }}
        .btn-secondary {{
            width: 100%;
            background: #334155;
            color: #f8fafc;
            border: none;
            padding: 10px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            margin-top: 8px;
            transition: background 0.15s;
        }}
        .btn-secondary:hover {{ background: #475569; }}
        .details-box {{
            text-align: left;
            margin-top: 16px;
            font-size: 12px;
        }}
        details summary {{
            color: #94a3b8;
            cursor: pointer;
            user-select: none;
            padding: 4px 0;
        }}
        details summary:hover {{ color: #cbd5e1; }}
        /* Preserved for test compatibility */
        .legacy-widget {{ display: none; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">⚡</div>
        <h2>Oisha-OS Enterprise</h2>
        <p class="sub">Tizimga kirish uchun Telegram botingiz orqali tasdiqlang</p>

        <a href="{deep_link}" target="_blank" class="btn-tg" id="btnTg">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.75-.55 2.92-1.27 4.86-2.11 5.83-2.52 2.77-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>
            <span>Telegram orqali kirish (1 ta bosish)</span>
        </a>

        <div class="status-box" id="pollStatus">
            <div class="spinner"></div>
            <span>Tasdiqlash kutilmoqda...</span>
        </div>

        <div class="divider">Yoki 6 xonali kod orqali</div>
        <form method="POST" action="/api/auth/telegram/otp" style="text-align: left;">
            <input type="hidden" name="next" value="{escaped_next}">
            <p style="font-size: 11px; color: #94a3b8; margin: 0 0 6px;">
                Botga <b>/login</b> deb yozib olingan kod:
            </p>
            <div style="display: flex; gap: 8px;">
                <input type="text" name="otp" placeholder="6 xonali kod (masalan: 742819)" maxlength="10" required class="inp" style="letter-spacing: 2px; font-weight: 600; text-align: center;">
                <button type="submit" class="btn-secondary" style="width: auto; margin-top: 0; padding: 0 16px;">Kirish</button>
            </div>
        </form>

        <div class="divider">Yoki email va parol bilan</div>
        <form method="POST" action="/api/auth/email/login" style="text-align: left;">
            <input type="hidden" name="next" value="{escaped_next}">
            <input type="email" name="email" placeholder="Email" required autocomplete="username" class="inp" style="margin-bottom: 8px;">
            <input type="password" name="password" placeholder="Parol" required autocomplete="current-password" class="inp">
            <button type="submit" class="btn-secondary">Parol bilan kirish</button>
        </form>

        <div class="details-box">
            <details>
                <summary>Admin / Master Token orqali kirish</summary>
                <form method="POST" action="/api/auth/token/login" style="margin-top: 10px;">
                    <input type="hidden" name="next" value="{escaped_next}">
                    <input type="password" name="token" placeholder="OISHA_API_SECRET yoki Service Token" required class="inp">
                    <button type="submit" class="btn-secondary">Token bilan kirish</button>
                </form>
            </details>
        </div>

        <div class="legacy-widget">
            <script async src="https://telegram.org/js/telegram-widget.js?22" data-telegram-login="{safe_bot}" data-size="large" data-auth-url="{auth_url}" data-request-access="write"></script>
        </div>
    </div>

    <script>
        const stateToken = "{state}";
        let timer = null;
        function checkState() {{
            fetch('/api/auth/telegram/poll?state=' + encodeURIComponent(stateToken))
                .then(r => r.json())
                .then(data => {{
                    if (data.status === 'approved') {{
                        clearInterval(timer);
                        document.getElementById('pollStatus').innerHTML = '✅ <b>Tasdiqlandi!</b> Yoʻnaltirilmoqda...';
                        window.location.href = data.redirect_url || '/';
                    }} else if (data.status === 'expired') {{
                        clearInterval(timer);
                        document.getElementById('pollStatus').innerHTML = '⚠️ Havola muddati oʻtdi. Sahifani yangilang.';
                    }}
                }})
                .catch(() => {{}});
        }}
        timer = setInterval(checkState, 1500);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)
